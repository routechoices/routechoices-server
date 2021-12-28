from django.conf import settings
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.iostream import StreamClosedError
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from routechoices.core.models import Event, ChatMessage
from asgiref.sync import sync_to_async
import asyncio
import orjson as json
import hashlib
from routechoices.lib.helpers import safe64encode

EVENT_NEW_MESSAGE = asyncio.Event()

class HealthCheckHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(tornado.escape.json_encode({'status': 'ok'}))


class LiveEventChatHandler(tornado.web.RequestHandler):    
    def post(self, event_id):
        if self.request.headers.get("Authorization") != f'Bearer {settings.CHAT_INTERNAL_SECRET}':
            raise tornado.web.HTTPError(403)
        EVENT_NEW_MESSAGE.set()


class LiveEventChatStream(tornado.web.RequestHandler):
    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')

    async def publish(self, type_, **kwargs):
        try:
            jsonified = str(json.dumps({"type": type_, **kwargs}), 'utf-8')
            self.write(f'data: {jsonified}\n\n'.encode())
            await self.flush()
        except StreamClosedError:
            pass
    
    async def wait_for_messages(self, evt, timeout):
        try:
            await asyncio.wait_for(evt.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        return evt.is_set()

    async def get(self, event_id):
        self.event_id = event_id
        event = await sync_to_async(
            Event.objects.filter(
                aid=event_id,
                start_date__lte=now(),
                end_date__gte=now(),
                allow_live_chat=True,
            ).first,
            thread_sensitive=True
        )()
        if not event:
            self.set_status(404)
        fetch_from = None
        first = True
        while True:
            if first:
                new_event = True
                first = False
            else:
                await self.publish('ping')
                await EVENT_NEW_MESSAGE.wait()
                new_event = True
            if new_event:
                EVENT_NEW_MESSAGE.clear()
                date_args = {}
                if fetch_from:
                    date_args['creation_date__gt'] = fetch_from
                new_messages = await sync_to_async(
                    lambda: list(ChatMessage.objects.filter(event_id=event.id, **date_args).all()),
                    thread_sensitive=True
                )()
                for new_message in new_messages:
                    hash_user = hashlib.sha256()
                    hash_user.update(new_message.nickname.encode('utf-8'))
                    hash_user.update(new_message.ip_address.encode('utf-8'))
                    doc = {
                        'nickname': new_message.nickname,
                        'message': new_message.message,
                        'timestamp': new_message.creation_date.timestamp(),
                        'user_hash': safe64encode(hash_user.digest()),
                    }
                    if fetch_from:
                        fetch_from = max(new_message.creation_date, fetch_from)
                    else:
                        fetch_from = new_message.creation_date
                    await self.publish('message', **doc)


class Command(BaseCommand):
    help = 'Run a chat server for Live events.'

    def handle(self, *args, **options):
        tornado_app = tornado.web.Application([
            (r'/health', HealthCheckHandler),
            (r'/([a-zA-Z0-9_-]{11})', LiveEventChatHandler),
            (r'/sse/([a-zA-Z0-9_-]{11})', LiveEventChatStream),
        ])
        tornado_app.listen(8009)
        try:
            tornado.ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            tornado.ioloop.IOLoop.current().stop()

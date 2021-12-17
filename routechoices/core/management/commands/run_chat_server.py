from django.conf import settings
import tornado.ioloop
import tornado.web
import tornado.websocket
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from routechoices.core.models import Event
from asgiref.sync import sync_to_async


EVENTS_CHATS = {}


class HealthCheckHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(tornado.escape.json_encode({'status': 'ok'}))


class LiveEventChatHandler(tornado.web.RequestHandler):    
    def post(self, event_id):
        if self.request.headers.get("Authorization") != f'Bearer {settings.CHAT_INTERNAL_SECRET}':
            raise tornado.web.HTTPError(403)
        for item in EVENTS_CHATS.get(event_id, []):
            item.write_message(self.request.body)


class LiveEventChatSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    async def open(self, event_id):
        self.room_id = event_id
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
            self.close()
        if not event_id in EVENTS_CHATS:
            EVENTS_CHATS[event_id] = []
        EVENTS_CHATS[event_id].append(self)

    def on_close(self):
        EVENTS_CHATS[self.room_id].remove(self)
        if len(EVENTS_CHATS[self.room_id]) == 0:
            EVENTS_CHATS.pop(self.room_id, None)


class Command(BaseCommand):
    help = 'Run a chat server for Live events.'

    def handle(self, *args, **options):
        tornado_app = tornado.web.Application([
            (r'/heath', HealthCheckHandler),
            (r'/([a-zA-Z0-9_-]{11})', LiveEventChatHandler),
            (r'/ws/([a-zA-Z0-9_-]{11})', LiveEventChatSocket)
        ])
        tornado_app.listen(8009)
        try:
            tornado.ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            tornado.ioloop.IOLoop.current().stop()

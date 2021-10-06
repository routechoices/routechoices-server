import json
import arrow
import tornado.ioloop
import tornado.web
import tornado.websocket
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from routechoices.core.models import Event, ChatMessage
from asgiref.sync import sync_to_async
import hashlib

EVENTS_CHATS = {}


class LiveEventChatHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.set_header("Access-Control-Allow-Headers", "access-control-allow-origin,authorization,content-type") 

    
    async def options(self, event_id):
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
            raise tornado.web.HTTPError(404)
        self.set_status(204)
        self.finish()

    async def get(self, event_id):
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
            raise tornado.web.HTTPError(404)
        msgs = await sync_to_async(
            lambda x: list(ChatMessage.objects.filter(event=x))
        )(event)
        out = []
        for msg in msgs:
            remote_ip = msg.ip_address
            hash_user = hashlib.sha256()
            hash_user.update(msg.nickname.encode('utf-8'))
            hash_user.update(remote_ip.encode('utf-8'))
            out.append({
                "nickname": msg.nickname,
                "message": msg.message,
                "timestamp": msg.creation_date.timestamp(),
                "user_hash": hash_user.hexdigest(),
            })
        self.write(tornado.escape.json_encode(out))

    async def post(self, event_id):
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
            raise tornado.web.HTTPError(404)
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(400)
        if not data.get('nickname') or not data.get('message'):
            raise tornado.web.HTTPError(400)
        remote_ip = self.request.headers.get("X-Real-IP") or \
            self.request.headers.get("X-Forwarded-For") or \
            self.request.remote_ip
        
        hash_user = hashlib.sha256()
        hash_user.update(data['nickname'].encode('utf-8'))
        hash_user.update(remote_ip.encode('utf-8'))
        
        doc = {
            "nickname": data['nickname'],
            "message": data['message'],
            "timestamp": arrow.utcnow().timestamp(),
            "user_hash": hash_user.hexdigest(),
        }
        
        await sync_to_async(
            ChatMessage.objects.create
        )(
            nickname=data['nickname'],
            message=data['message'],
            ip_address=remote_ip,
            event=event
        )
        for item in EVENTS_CHATS.get(event_id, []):
            item.write_message(json.dumps(doc))


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
            (r'/([a-zA-Z0-9_-]{11})', LiveEventChatHandler),
            (r'/ws/([a-zA-Z0-9_-]{11})', LiveEventChatSocket)
        ])
        tornado_app.listen(8009)
        try:
            tornado.ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            tornado.ioloop.IOLoop.current().stop()

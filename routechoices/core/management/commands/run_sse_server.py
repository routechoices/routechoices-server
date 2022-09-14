import asyncio
from importlib import import_module

import async_timeout
import orjson as json
import redis.asyncio as redis
import tornado.ioloop
import tornado.web
import tornado.websocket
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from tornado.iostream import StreamClosedError

from routechoices.core.models import Event


class HealthCheckHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(tornado.escape.json_encode({"status": "ok"}))


class LiveEventDataStream(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.listening = False
        return super().__init__(*args, **kwargs)

    def initialize(self, manager):
        self.queue = asyncio.Queue()
        self.manager = manager
        self.set_header(
            "Access-Control-Allow-Origin", self.request.headers.get("Origin", "*")
        )
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.set_header("content-type", "text/event-stream")
        self.set_header("cache-control", "no-cache")

    async def get_current_user(self):
        engine = import_module(settings.SESSION_ENGINE)
        cookie = self.get_cookie(settings.SESSION_COOKIE_NAME)
        if not cookie:
            return None

        class Dummy:
            pass

        django_request = Dummy()
        django_request.session = engine.SessionStore(cookie)
        user = await sync_to_async(get_user)(django_request)
        return user

    async def publish(self, type_, **kwargs):
        if not self.listening:
            return
        jsonified = str(json.dumps({"type": type_, **kwargs}), "utf-8")
        try:
            self.write(f"data: {jsonified}\n\n".encode())
            await self.flush()
        except StreamClosedError:
            self.listening = False

    async def get(self, event_id):
        self.event_id = event_id

        event = await sync_to_async(
            Event.objects.select_related("club")
            .filter(
                aid=event_id,
                start_date__lte=now(),
                end_date__gte=now(),
            )
            .first,
            thread_sensitive=True,
        )()
        if not event:
            raise tornado.web.HTTPError(404)

        user = await self.get_current_user()
        if not user:
            raise tornado.web.HTTPError(403)
        if not user.is_superuser:
            if not user.is_authenticated:
                raise tornado.web.HTTPError(403)
            is_admin = await sync_to_async(
                event.club.admins.filter(id=user.id).exists, thread_sensitive=True
            )()
            if not is_admin:
                raise tornado.web.HTTPError(403)
        await self.manager.subscribe(self, f"routechoices_event_data:{event_id}")
        self.listening = True
        while self.listening:
            try:
                async with async_timeout.timeout(5):
                    message_raw = await self.queue.get()
                    try:
                        data = json.loads(message_raw.get("data").decode())
                    except Exception:
                        pass
                    await self.publish("locations", **data)
            except asyncio.TimeoutError:
                await self.publish("ping")


class Subscription:
    """Handles subscriptions to Redis PUB/SUB channels."""

    def __init__(self, redis, channel):
        self._redis = redis
        self._pubsub = self._redis.pubsub()
        self.name = channel
        self.listeners = set()
        self.listening = False

    async def subscribe(self):
        print(f"Started listening for {self.name}")
        await self._pubsub.subscribe(self.name)

    def __str__(self):
        return self.name

    def add_listener(self, listener):
        self.listeners.add(listener)

    async def broadcast(self):
        """Listen for new messages on Redis and broadcast to all
        HTTP listeners.
        """
        while len(self.listeners) > 0:
            self.listening = True
            closed = []
            try:
                async with async_timeout.timeout(10):
                    message = await self._pubsub.get_message(
                        ignore_subscribe_messages=True
                    )
            except asyncio.TimeoutError:
                message = None
            finally:
                for listener in self.listeners:
                    if not listener.listening:
                        closed.append(listener)
                    elif message is not None:
                        listener.queue.put_nowait(message)

                if len(closed) > 0:
                    [self.listeners.remove(listener) for listener in closed]

        self.listening = False
        await self._pubsub.unsubscribe()
        print(f"Stopped listening for {self.name}")


class SubscriptionManager:
    """Manages all subscriptions."""

    def __init__(self, loop=None):
        self.redis = None
        self.subscriptions = dict()
        self.loop = loop or asyncio.get_event_loop()

    async def connect(self):
        self.redis = await redis.from_url(settings.REDIS_URL)

    async def subscribe(self, listener, channel: str):
        """Subscribe to a new channel."""
        if channel in self.subscriptions:
            subscription = self.subscriptions[channel]
        else:
            subscription = Subscription(self.redis, channel)
            self.subscriptions[channel] = subscription
        subscription.add_listener(listener)
        if not subscription.listening:
            await subscription.subscribe()
            self.loop.call_soon(lambda: asyncio.Task(subscription.broadcast()))


class Command(BaseCommand):
    help = "Run SSE servers."

    def handle(self, *args, **options):

        loop = asyncio.get_event_loop()

        manager = SubscriptionManager()
        loop.run_until_complete(manager.connect())

        live_data_tornado_app = tornado.web.Application(
            [
                (r"/health", HealthCheckHandler),
                (
                    r"/sse/([a-zA-Z0-9_-]{11})",
                    LiveEventDataStream,
                    dict(manager=manager),
                ),
            ]
        )
        live_data_tornado_app.listen(8010)

        try:
            tornado.ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            tornado.ioloop.IOLoop.current().stop()

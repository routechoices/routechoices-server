import logging
import os

import arrow
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import connection
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer

from routechoices.core.models import Device, TcpDeviceCommand

logger = logging.getLogger("TCP Rotating Log")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    os.path.join(settings.BASE_DIR, "logs", "tcp.log"), maxBytes=10000000, backupCount=5
)
logger.addHandler(handler)


class GenericTCPServer(TCPServer):
    connection_class = None

    async def handle_stream(self, stream, address):
        if not self.connection_class:
            return
        c = self.connection_class(stream, address, logger)
        try:
            await c.start_listening()
        except StreamClosedError:
            pass


@sync_to_async
def get_device_by_imei(imei):
    device = Device.objects.filter(physical_device__imei=imei).first()
    connection.close()
    return device


@sync_to_async
def add_locations(device, locations):
    device.add_locations(locations)
    connection.close()


@sync_to_async
def send_sos(device):
    r = device.send_sos()
    connection.close()
    return r


@sync_to_async
def save_device(device):
    device.add_save()
    connection.close()


@sync_to_async
def get_pending_commands(imei):
    commands = list(
        TcpDeviceCommand.objects.filter(target__imei=imei, sent=False).values_list(
            "command", flat=True
        )
    )
    t = arrow.now().datetime
    connection.close()
    return t, commands


@sync_to_async
def mark_pending_commands_sent(imei, max_date):
    r = TcpDeviceCommand.objects.filter(
        target__imei=imei,
        sent=False,
        creation_date__lte=max_date,
    ).update(sent=True, modification_date=arrow.now().datetime)
    connection.close()
    return r

import asyncio
import logging
import os
import socket

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase
from tornado.iostream import IOStream
from tornado.testing import AsyncTestCase, bind_unused_port, gen_test

from routechoices.core.management.commands.run_tcp_server import (
    GT06Server,
    QueclinkServer,
    TMT250Server,
    XexunServer,
)
from routechoices.core.models import Device, ImeiDevice

logger = logging.getLogger("TCP Rotating Log")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    os.path.join(settings.BASE_DIR, "logs", "tests_tcp.log"),
    maxBytes=10000000,
    backupCount=5,
)
logger.addHandler(handler)
socket.setdefaulttimeout(30)


@sync_to_async
def create_imei_device(imei):
    device = Device.objects.create()
    ImeiDevice.objects.create(imei=imei, device_id=device.id)
    connection.close()
    return device


@sync_to_async
def refresh_device(device):
    device.refresh_from_db()
    connection.close()
    return device


class TCPConnectionsTest(AsyncTestCase, TransactionTestCase):
    @gen_test
    async def test_gt06(self):
        init_data = bytes.fromhex("78781101086020106158874800003200000190010d0a")
        ack_data = bytes.fromhex("787805010001d9dc0d0a")
        gps_data = bytes.fromhex(
            "787826220a03170f3217cc026c6c820c37168200153e01cc002633000e7f010000000860a50d0a"
        )

        server = client = None
        device = await create_imei_device("860201061588748")
        sock, port = bind_unused_port()
        server = GT06Server()
        server.add_socket(sock)
        client = IOStream(socket.socket())
        await client.connect(("localhost", port))
        await client.write(init_data)
        data = await client.read_bytes(255, partial=True)
        self.assertEquals(data, ack_data)
        await client.write(gps_data)
        await asyncio.sleep(1)
        device = await refresh_device(device)
        self.assertEquals(device.location_count, 1)
        if server is not None:
            server.stop()
        if client is not None:
            client.close()

    @gen_test
    async def test_queclink(self):
        hbt_data = b"+ACK:GTHBD,C30203,860201061588748,,20240201161532,FFFF$"
        ack_data = b"+SACK:GTHBD,C30203,FFFF$"
        gps_data = b"+BUFF:GTFRI,8020040200,860201061588748,,12194,10,1,3,0.0,0,20.1,-71.596533,-33.524718,20240201161533,0730,0001,772A,052B253E,02,0,0.0,,,,,0,420000,,,,20230926200340,1549$"

        server = client = None
        device = await create_imei_device("860201061588748")
        sock, port = bind_unused_port()
        server = QueclinkServer()
        server.add_socket(sock)
        client = IOStream(socket.socket())
        await client.connect(("localhost", port))
        await client.write(hbt_data)
        data = await client.read_bytes(255, partial=True)
        self.assertEquals(data, ack_data)
        await client.write(gps_data)
        await asyncio.sleep(1)
        device = await refresh_device(device)
        self.assertEquals(device.location_count, 1)
        if server is not None:
            server.stop()
        if client is not None:
            client.close()

    @gen_test
    async def test_teltonika(self):
        init_data = bytes.fromhex("000f333536333037303432343431303133")
        ack_data = b"\x01"
        gps_data = bytes.fromhex(
            "00000000000000FE080400000113fc208dff000f33353633303730343234343130313304030101150316030001460000015d0000000113fc17610b000f14ffe0209cc580006e00c00500010004030101150316010001460000015e0000000113fc284945000f150f00209cd200009501080400000004030101150016030001460000015d0000000113fc267c5b000f150a50209cccc0009300680400000004030101150016030001460000015b0004"
        )

        server = client = None
        device = await create_imei_device("356307042441013")
        sock, port = bind_unused_port()
        server = TMT250Server()
        server.add_socket(sock)
        client = IOStream(socket.socket())
        await client.connect(("localhost", port))
        await client.write(init_data)
        data = await client.read_bytes(255, partial=True)
        self.assertEquals(data, ack_data)
        await client.write(gps_data)
        await asyncio.sleep(1)
        device = await refresh_device(device)
        self.assertEquals(device.location_count, 4)
        if server is not None:
            server.stop()
        if client is not None:
            client.close()

    @gen_test
    async def test_xexun(self):
        gps_data = b"0711011831,+8613145826126,GPRMC,103148.000,A,2234.0239,N,11403.0765,E,0.00,,011107,,,A*75,F,imei:352022008228783,101\x8D"

        server = client = None
        device = await create_imei_device("352022008228783")
        sock, port = bind_unused_port()
        server = XexunServer()
        server.add_socket(sock)
        client = IOStream(socket.socket())
        await client.connect(("localhost", port))
        await client.write(gps_data)

        await asyncio.sleep(1)
        device = await refresh_device(device)
        self.assertEquals(device.location_count, 1)
        if server is not None:
            server.stop()
        if client is not None:
            client.close()

    @gen_test
    async def test_xexun_alt(self):
        gps_data = b"090805215127,+22663173122,GPRMC,215127.083,A,4717.3044,N,01135.0005,E,0.39,217.95,050809,,,A*6D,F,, imei:352022008228783,05,552.4,F:4.06V,0,141,54982,232,01,1A30,0949"

        server = client = None
        device = await create_imei_device("352022008228783")
        sock, port = bind_unused_port()
        server = XexunServer()
        server.add_socket(sock)
        client = IOStream(socket.socket())
        await client.connect(("localhost", port))
        await client.write(gps_data)

        await asyncio.sleep(1)
        device = await refresh_device(device)
        self.assertEquals(device.location_count, 1)
        if server is not None:
            server.stop()
        if client is not None:
            client.close()

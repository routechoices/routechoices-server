# coding=utf-8
import json
import math
import os.path
from struct import pack, unpack
import time
import arrow
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.core.management.base import BaseCommand
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer

from routechoices.core.models import Device, TcpDeviceCommand
from routechoices.lib.validators import validate_imei
from routechoices.lib.helpers import safe64encode, random_key

import logging

logger = logging.getLogger("TCP Rotating Log")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    os.path.join(settings.BASE_DIR, 'logs', 'tcp.log'),
    maxBytes=10000000,
    backupCount=5
)
logger.addHandler(handler)


def _get_device(imei):
    try:
        return Device.objects.get(physical_device__imei=imei)
    except DatabaseError:
        from django import db
        db.close_connection()
        time.sleep(5)
        return _get_device(imei)
    except Exception:
        return None


def _get_pending_commands(imei):
    try:
        commands = list(
            TcpDeviceCommand.objects.filter(target__imei=imei, sent=False).values_list(
                "command", flat=True
            )
        )
        t = arrow.now().datetime
        return t, commands
    except DatabaseError:
        from django import db
        db.close_connection()
        return None
    except Exception:
        return None


def _mark_pending_commands_sent(imei, max_date):
    try:
        return TcpDeviceCommand.objects.filter(
            target__imei=imei,
            sent=False,
            creation_date__lte=max_date,
        ).update(sent=True, modification_date=arrow.now().datetime)
    except DatabaseError:
        from django import db
        db.close_connection()
        return 0
    except Exception:
        return 0


class TMT250Decoder:
    def __init__(self):
        self.packet = {}
        self.battery_level = None

    def generate_response(self, success=True):
        s = self.packet["num_data"] if success else 0
        return pack(">i", s)

    def decode_alv(self, data):
        self.packet["zeroes"] = unpack(">i", data[:4])[0]
        if self.packet["zeroes"] != 0:
            raise Exception("zeroes should be 0")
        self.packet["length"] = unpack(">i", data[4:8])[0]
        self.packet["codec"] = data[8]
        if self.packet["codec"] != 8:
            raise Exception("codec should be 8")
        self.packet["num_data"] = data[9]
        self.extract_records(data)
        return self.packet

    def extract_records(self, buffer):
        remaining_data = self.packet["num_data"]
        self.packet["records"] = []
        pointer = 10
        while remaining_data > 0:
            timestamp = unpack(">Q", buffer[pointer : pointer + 8])[0] / 1e3
            lon = unpack(">i", buffer[pointer + 9 : pointer + 13])[0] / 1e7
            lat = unpack(">i", buffer[pointer + 13 : pointer + 17])[0] / 1e7

            n1 = buffer[pointer + 26]
            pointer += 27
            for i in range(n1):
                avl_id = buffer[pointer + i * 2]
                if avl_id == 113:
                    self.battery_level = buffer[pointer + 1 + i * 2]
            pointer += n1 * 2

            n2 = buffer[pointer]
            pointer += 1 + 3 * n2

            n4 = buffer[pointer]
            pointer += 1 + 5 * n4

            n8 = buffer[pointer]
            pointer += 1 + 9 * n8
            self.packet["records"].append(
                {
                    "timestamp": timestamp,
                    "latlon": [lat, lon],
                }
            )
            remaining_data -= 1
        return pointer


class TMT250Connection:
    def __init__(self, stream, address):
        print(f"received a new connection from {address} on port 2000")
        self.aid = random_key()
        self.imei = None
        self.address = address
        self.stream = stream
        self.stream.set_close_callback(self._on_close)
        self.decoder = TMT250Decoder()
        self.packet_len = 0
        self.buffer = None
        self.db_device = None

    async def start_listening(self):
        print("start listening from %s", self.address)
        data = bytearray(b"0" * 1024)
        data_len = await self.stream.read_into(data, partial=True)
        if data_len < 3:
            print("too little data", flush=True)
            await self.stream.write(pack("b", 0))
            self.stream.close()
            return
        data = data[:data_len]
        imei_len = (data[0] << 8) + data[1]
        imei = ""
        is_valid_imei = True
        try:
            imei = data[2:].decode("ascii")
            validate_imei(imei)
        except Exception:
            is_valid_imei = False
        if imei_len != len(imei) or not is_valid_imei:
            print(
                f"invalid identification {self.address}, {imei}, {imei_len}", flush=True
            )
            await self.stream.write(pack("b", 0))
            self.stream.close()
            return
        logger.info(f'{time.time()}, TMT250 CONN, {self.aid}, {self.address}: {safe64encode(bytes(data))}')
        self.db_device = await sync_to_async(_get_device, thread_sensitive=True)(imei)
        if not self.db_device:
            print(f"imei not registered {self.address}, {imei}", flush=True)
            await self.stream.write(pack("b", 0))
            self.stream.close()
            return
        self.imei = imei
        await self.stream.write(pack("b", 1))
        print(f"{self.imei} is connected", flush=True)

        while await self._on_write_complete():
            pass

    async def _on_read_line(self, data):
        zeroes = unpack(">i", data[:4])[0]
        if zeroes != 0:
            raise Exception("zeroes should be 0")
        self.packet_length = unpack(">i", data[4:8])[0] + 4
        self.buffer = bytes(data)
        await self._on_full_data(self.buffer)

    async def _on_write_complete(self):
        if not self.stream.reading():
            data = bytearray(b"0" * 2048)
            try:
                data_len = await self.stream.read_into(data, partial=True)
                print(f"{self.imei} is sending {data_len} bytes")
                logger.info(f'{time.time()}, TMT250 DATA, {self.aid}, {self.address}: {safe64encode(bytes(data[:data_len]))}')
                await self._on_read_line(data[:data_len])
            except Exception as e:
                print("exception reading data " + str(e))
                return False
        return True

    def _on_close(self):
        print("client quit", self.address)

    async def _on_full_data(self, data):
        try:
            decoded = self.decoder.decode_alv(self.buffer)
        except Exception:
            print("error decoding packet")
            await self.stream.write(self.decoder.generate_response(False))
        else:
            loc_array = []
            for r in decoded.get("records", []):
                loc_array.append((int(r["timestamp"]), r["latlon"][0], r["latlon"][1]))
            if not self.db_device.user_agent:
                self.db_device.user_agent = "Teltonika"
            if self.decoder.battery_level:
                self.db_device.battery_level = self.decoder.battery_level
            await sync_to_async(self.db_device.add_locations, thread_sensitive=True)(
                loc_array
            )
            self.waiting_for_content = True
            await self.stream.write(self.decoder.generate_response())


class TMT250Server(TCPServer):
    async def handle_stream(self, stream, address):
        c = TMT250Connection(stream, address)
        try:
            await c.start_listening()
        except StreamClosedError:
            pass


class GL200Connection:
    def __init__(self, stream, address):
        print(f"Received a new connection from {address} on port 2002")
        self.aid = random_key()
        self.imei = None
        self.address = address
        self.stream = stream
        self.stream.set_close_callback(self.on_close)
        self.db_device = None

    async def start_listening(self):
        print(f"Start listening from {self.address}")
        imei = None
        try:
            data_bin = await self.stream.read_until(b"$")
            data = data_bin.decode("ascii")
            logger.info(f'{time.time()}, GL300 DATA, {self.aid}, {self.address}, {data}')
            print(f"Received data ({data})", flush=True)
            parts = data.split(",")
            if parts[0][:7] == "+ACK:GT" or parts[0][:8] in ("+RESP:GT", "+BUFF:GT"):
                imei = parts[2]
        except Exception as e:
            print(f"Error parsing initial message: {str(e)}", flush=True)
            self.stream.close()
            return
        if not imei:
            print("No imei", flush=True)
            self.stream.close()
            return
        is_valid_imei = True
        try:
            validate_imei(imei)
        except ValidationError:
            is_valid_imei = False
        if not is_valid_imei:
            print("Invalid imei", flush=True)
            self.stream.close()
            return
        self.db_device = await sync_to_async(_get_device, thread_sensitive=True)(imei)
        if not self.db_device:
            print(f"Imei not registered {self.address}, {imei}", flush=True)
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")

        await self.send_pending_commands()

        await self.process_line(data)

        while await self.read_line():
            pass

    async def send_pending_commands(self):
        if not self.imei:
            return
        access_date, commands = await sync_to_async(_get_pending_commands)(self.imei)
        for command in commands:
            self.stream.write(command.encode())
        commands_count = len(commands)
        if commands_count > 0:
            print(f"{commands_count} commands sent")
            await sync_to_async(_mark_pending_commands_sent, thread_sensitive=True)(
                self.imei, access_date
            )

    async def process_line(self, data):
        try:
            parts = data.split(",")
            if parts[0][:8] in ("+RESP:GT", "+BUFF:GT") and parts[0][8:] in (
                "FRI",
                "GEO",
                "SPD",
                "SOS",
                "RTL",
                "PNL",
                "NMR",
                "DIS",
                "DOG",
                "IGL",
                "LOC",
            ):
                imei = parts[2]
                if imei != self.imei:
                    raise Exception("Cannot change IMEI while connected")
                nb_pts = int(parts[6])
                print(f"Contains {nb_pts} pts")
                if 12 * nb_pts + 10 == len(parts):
                    len_points = 12
                elif 11 * nb_pts + 11 == len(parts):
                    len_points = 11
                else:
                    len_points = math.floor((len(parts) - 10) / nb_pts)
                print(f"Each point has {len_points} data")
                pts = []
                for i in range(nb_pts):
                    try:
                        lon = float(parts[11 + i * len_points])
                        lat = float(parts[12 + i * len_points])
                        tim = arrow.get(
                            parts[13 + i * len_points], "YYYYMMDDHHmmss"
                        ).int_timestamp
                    except Exception as e:
                        print(f"Error parsing position: {str(e)}", flush=True)
                        continue
                    else:
                        pts.append((tim, lat, lon))
                batt = int(parts[-3])
                await self.on_data(pts, batt)
            elif parts[0] == "+ACK:GTHBD":
                self.stream.write(f"+SACK:GTHBD,{parts[1]},{parts[5]}$".encode("ascii"))
        except Exception as e:
            print(f"Error processing line: {str(e)}", flush=True)
            self.stream.close()
            return False
        return True

    async def read_line(self):
        data_bin = await self.stream.read_until(b"$")
        data = data_bin.decode("ascii")
        logger.info(f'{time.time()}, GL300 DATA, {self.aid}, {self.address}, {data}')
        print(f"Received data ({data})")
        await self.send_pending_commands()
        return await self.process_line(data)

    async def on_data(self, pts, batt=None):
        if not self.db_device.user_agent:
            self.db_device.user_agent = "Queclink"
        if batt:
            self.db_device.battery_level = batt
        loc_array = pts
        await sync_to_async(self.db_device.add_locations, thread_sensitive=True)(
            loc_array
        )
        print(f"{len(pts)} Locations wrote to DB", flush=True)

    def on_close(self):
        print("Client quit", flush=True)


class GL200Server(TCPServer):
    async def handle_stream(self, stream, address):
        c = GL200Connection(stream, address)
        try:
            await c.start_listening()
        except StreamClosedError:
            pass


class TrackTapeConnection:
    def __init__(self, stream, address):
        print(f"received a new connection from {address} on port 2004")
        self.imei = None
        self.address = address
        self.stream = stream
        self.stream.set_close_callback(self._on_close)
        self.db_device = None

    async def start_listening(self):
        print(f"Start listening from {self.address}")
        imei = None
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_until(b"\n")
                data_raw = data_bin.decode("ascii").strip()
            print(f"Received data ({data_raw})", flush=True)
            data = json.loads(data_raw)
            imei = data.get("id")
        except Exception as e:
            print(e, flush=True)
            self.stream.close()
            return
        if not imei:
            print("No imei", flush=True)
            self.stream.close()
            return
        is_valid_imei = True
        try:
            validate_imei(imei)
        except ValidationError:
            is_valid_imei = False
        if not is_valid_imei:
            print("Invalid imei", flush=True)
            self.stream.close()
            return
        self.db_device = await sync_to_async(_get_device, thread_sensitive=True)(imei)
        if not self.db_device:
            print(f"Imei not registered {self.address}, {imei}", flush=True)
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")

        self._process_data(data)

        while await self._read_line():
            pass

    async def _process_data(self, data):
        imei = data.get("id")
        if imei != self.imei:
            return False
        locs = data.get("positions", [])
        loc_array = []
        for loc in locs:
            try:
                tim = arrow.get(loc.get("timestamp")).int_timestamp
                lon = float(loc.get("lon"))
                lat = float(loc.get("lat"))
                loc_array.append((tim, lat, lon))
            except Exception:
                continue
        if loc_array:
            await sync_to_async(self.db_device.add_locations, thread_sensitive=True)(
                loc_array
            )
            print(f"{len(loc_array)} locations wrote to DB", flush=True)

    async def _read_line(self):
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_until(b"\n")
                data_raw = data_bin.decode("ascii").strip()
            print(f"Received data ({data_raw})")
            data = json.loads(data_raw)
            self._process_data(data)
        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("client quit", flush=True)


class TrackTapeServer(TCPServer):
    async def handle_stream(self, stream, address):
        c = TrackTapeConnection(stream, address)
        try:
            await c.start_listening()
        except StreamClosedError:
            pass


class Command(BaseCommand):
    help = "Run a TCP server for GPS trackers."

    def handle(self, *args, **options):
        tmt250_server = TMT250Server()
        gl200_server = GL200Server()
        tracktape_server = TrackTapeServer()
        tmt250_server.listen(settings.TMT250_PORT)
        gl200_server.listen(settings.GL200_PORT)
        tracktape_server.listen(settings.TRACKTAPE_PORT)
        try:
            print("Start listening TCP data...", flush=True)
            logger.info(f'{time.time()}, UP')
            IOLoop.current().start()
        except KeyboardInterrupt:
            tmt250_server.stop()
            gl200_server.stop()
            tracktape_server.stop()
            IOLoop.current().stop()
        except Exception:
            pass
        print("Stopped listening TCP data...", flush=True)
        logger.info(f'{time.time()}, DOWN')
        logging.shutdown()

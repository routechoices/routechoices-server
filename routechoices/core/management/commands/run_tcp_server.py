# coding=utf-8
import json
from struct import pack, unpack

import arrow
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer

from routechoices.core.models import Device
from routechoices.lib.validators import validate_imei


def _get_device(imei):
    try:
        return Device.objects.get(physical_device__imei=imei)
    except Exception:
        return None


class TMT250Decoder:
    def __init__(self):
        self.packet = {}

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
            pointer += 27 + n1 * 2

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
        print(f"received a new connection from {address} on port 2002")
        self.imei = None
        self.address = address
        self.stream = stream
        self.stream.set_close_callback(self._on_close)
        self.db_device = None

    async def start_listening(self):
        print(f"start listening from {self.address}")
        imei = None
        try:
            data_bin = await self.stream.read_until(b"$")
            data = data_bin.decode("ascii")
            print(f"received data ({data})", flush=True)
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
                "INF",
            ):
                imei = parts[2]
            elif parts[0] == "+ACK:GTHBD":
                self.stream.write(f"+SACK:GTHBD,{parts[1]},{parts[5]}$".encode("ascii"))
                imei = parts[2]
        except Exception as e:
            print(e, flush=True)
            self.stream.close()
            return
        is_valid_imei = True
        try:
            validate_imei(imei)
        except ValidationError:
            is_valid_imei = False
        if not imei:
            print("no imei")
            self.stream.close()
            return
        elif not is_valid_imei:
            print("invalid imei")
            self.stream.close()
            return
        self.db_device = await sync_to_async(_get_device, thread_sensitive=True)(imei)
        if not self.db_device:
            print(f"imei not registered {self.address}, {imei}")
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")
        if parts[0][8:] != "INF":
            try:
                lon = float(parts[11])
                lat = float(parts[12])
                tim = arrow.get(parts[13], "YYYYMMDDHHmmss").int_timestamp
                await self._on_data(tim, lat, lon)
            except Exception:
                self.stream.close()
                return
        while await self._read_line():
            pass

    async def _read_line(self):
        try:
            data_bin = await self.stream.read_until(b"$")
            data = data_bin.decode("ascii")
            print(f"received data ({data})")
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
            ):
                imei = parts[2]
                if imei != self.imei:
                    raise Exception("Cannot change IMEI while connected")
                lon = float(parts[11])
                lat = float(parts[12])
                tim = arrow.get(parts[13], "YYYYMMDDHHmmss").int_timestamp
                await self._on_data(tim, lat, lon)
            elif parts[0] == "+ACK:GTHBD":
                self.stream.write(f"+SACK:GTHBD,{parts[1]},{parts[5]}$".encode("ascii"))
        except Exception:
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("client quit", self.address)

    async def _on_data(self, timestamp, lat, lon):
        if not self.db_device.user_agent:
            self.db_device.user_agent = "Queclink"
        loc_array = [(timestamp, lat, lon)]
        await sync_to_async(self.db_device.add_locations, thread_sensitive=True)(
            loc_array
        )
        print("data wrote to db")


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
        print(f"start listening from {self.address}")
        imei = None
        try:
            data_bin = await self.stream.read_until(b"\n")
            data_raw = data_bin.decode("ascii")
            print(f"received data ({data_raw})", flush=True)
            data = json.loads(data_raw)
            imei = data.get("id")
        except Exception as e:
            print(e, flush=True)
            self.stream.close()
            return
        is_valid_imei = True
        try:
            validate_imei(imei)
        except ValidationError:
            is_valid_imei = False
        if not imei:
            print("no imei")
            self.stream.close()
            return
        elif not is_valid_imei:
            print("invalid imei")
            self.stream.close()
            return
        self.db_device = await sync_to_async(_get_device, thread_sensitive=True)(imei)
        if not self.db_device:
            print(f"imei not registered {self.address}, {imei}")
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")
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
        if not self.db_device.user_agent:
            self.db_device.user_agent = "TrackTape"
        if loc_array:
            await sync_to_async(self.db_device.add_locations, thread_sensitive=True)(
                loc_array
            )
        while await self._read_line():
            pass

    async def _read_line(self):
        try:
            data_bin = await self.stream.read_until(b"\n")
            data_raw = data_bin.decode("ascii")
            print(f"received data ({data_raw})")
            data = json.loads(data_raw)
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
                await sync_to_async(
                    self.db_device.add_locations, thread_sensitive=True
                )(loc_array)
        except Exception:
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("client quit", self.address)


class TrackTapeServer(TCPServer):
    async def handle_stream(self, stream, address):
        c = TrackTapeConnection(stream, address)
        try:
            await c.start_listening()
        except StreamClosedError:
            pass


class Command(BaseCommand):
    help = "Run a tcp server for GPS trackers."

    def handle(self, *args, **options):
        tmt250_server = TMT250Server()
        gl200_server = GL200Server()
        tracktape_server = TrackTapeServer()
        tmt250_server.listen(settings.TMT250_PORT)
        gl200_server.listen(settings.GL200_PORT)
        tracktape_server.listen(settings.TRACKTAPE_PORT)
        try:
            IOLoop.current().start()
        except KeyboardInterrupt:
            tmt250_server.stop()
            gl200_server.stop()
            tracktape_server.stop()
            IOLoop.current().stop()

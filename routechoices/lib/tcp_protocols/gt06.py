from struct import pack, unpack

import arrow
from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError

from routechoices.lib.crc_itu import crc16
from routechoices.lib.helpers import random_key, safe64encode
from routechoices.lib.tcp_protocols.commons import _get_device
from routechoices.lib.validators import validate_imei


class GT06Connection:
    def __init__(self, stream, address, logger):
        print(f"received a new connection from {address}")
        self.aid = random_key()
        self.imei = None
        self.address = address
        self.stream = stream
        self.stream.set_close_callback(self._on_close)
        self.db_device = None
        self.logger = logger

    async def start_listening(self):
        print(f"Start listening from {self.address}")
        imei = None
        try:
            data_bin = b""
            while not data_bin:
                data_bin = await self.stream.read_until(b"\r\n", 255)
            # First packet is login info packet
            if data_bin[:4] != b"\x78\x78\x11\x01":
                print("Invalid start")
                self.stream.close()
                return
            imei = data_bin[4:12].hex()[1:]
        except Exception as e:
            print(e, flush=True)
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

        serial_number = data_bin[16:18]
        data_to_send = b"\x05\x01" + serial_number
        checksum = pack(">H", crc16(data_to_send))
        self.stream.write(b"\x78\x78" + data_to_send + checksum + b"\r\n")

        while await self._read_line():
            pass

    async def _process_data(self, data_bin):
        self.logger.info(
            f"{arrow.now().datetime}, GT06 DATA, "
            f"{self.aid}, {self.address}: {safe64encode(data_bin)}"
        )
        if not self.db_device.user_agent:
            self.db_device.user_agent = "Gt06"

        date_bin = data_bin[4:10]
        lat_bin = data_bin[11:15]
        lon_bin = data_bin[15:19]
        flags = data_bin[20]

        north = flags & 0x4
        west = flags & 0x8

        year, month, day, hours, minutes, seconds = unpack(">BBBBBB", date_bin)
        year += 2000
        date_str = f"{year}-{month:02}-{day:02}T{hours:02}:{minutes:02}:{seconds:02}Z"
        lat = unpack(">I", lat_bin)[0] / 60 / 30000
        if not north:
            lat *= -1

        lon = unpack(">I", lon_bin)[0] / 60 / 30000
        if west:
            lon *= -1

        is_alarm = data_bin[3] == 0x26

        if flags & 0x16:
            loc_array = [(arrow.get(date_str).timestamp(), lat, lon)]
            await sync_to_async(self.db_device.add_locations, thread_sensitive=True)(
                loc_array
            )
            print("1 locations wrote to DB", flush=True)

        if is_alarm:
            sos_device_aid, sos_lat, sos_lon, sos_sent_to = await sync_to_async(
                self.db_device.send_sos, thread_sensitive=True
            )()
            print(
                f"SOS triggered by device {sos_device_aid}, {sos_lat},"
                f" {sos_lon} email sent to {sos_sent_to}",
                flush=True,
            )

    async def _read_line(self):
        try:
            data_bin = b""
            while not data_bin:
                data_bin = await self.stream.read_until(b"\r\n", 255)
            # GPS AND ALARM DATA
            if data_bin[:2] == b"\x78\x78" and data_bin[3] in (0x22, 0x26):
                await self._process_data(data_bin)
            # HEARTBEAT
            if data_bin[:4] == b"\x78\x78\x0a\x13":
                serial_number = data_bin[9:11]
                data_to_send = b"\x05\x13" + serial_number
                checksum = pack(">H", crc16(data_to_send))
                self.stream.write(b"\x78\x78" + data_to_send + checksum + b"\r\n")

        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("client quit", flush=True)

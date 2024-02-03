from struct import pack, unpack

import arrow
from django.core.exceptions import ValidationError

from routechoices.lib.crc_itu import crc16
from routechoices.lib.helpers import random_key, safe64encode
from routechoices.lib.tcp_protocols.commons import (
    GenericTCPServer,
    add_locations,
    get_device_by_imei,
    save_device,
)
from routechoices.lib.validators import validate_imei


class GT06Connection:
    def __init__(self, stream, address, logger):
        print(f"Received a new connection from {address} on gt06 port")
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
        self.db_device = await get_device_by_imei(imei)
        if not self.db_device:
            print(f"Imei {imei} not registered  ({self.address})", flush=True)
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")

        serial_number = data_bin[16:18]
        data_to_send = b"\x05\x01" + serial_number
        checksum = pack(">H", crc16(data_to_send))
        await self.stream.write(b"\x78\x78" + data_to_send + checksum + b"\r\n")

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

        if flags & 0x16:
            loc_array = [(arrow.get(date_str).timestamp(), lat, lon)]
            await add_locations(self.db_device, loc_array)
            print("1 locations wrote to DB", flush=True)

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
                battery_level = int(min(100, data_bin[5] * 100 / 6))
                data_to_send = b"\x05\x13" + serial_number
                checksum = pack(">H", crc16(data_to_send))
                await self.stream.write(b"\x78\x78" + data_to_send + checksum + b"\r\n")
                self.db_device.battery_level = battery_level
                await save_device(self.db_device)

        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("Client quit", flush=True)


class GT06Server(GenericTCPServer):
    connection_class = GT06Connection

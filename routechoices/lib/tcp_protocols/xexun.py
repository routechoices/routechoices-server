import re

import arrow
from django.core.exceptions import ValidationError

from routechoices.lib.helpers import random_key
from routechoices.lib.tcp_protocols.commons import (
    GenericTCPServer,
    add_locations,
    get_device_by_imei,
)
from routechoices.lib.validators import validate_imei


class XexunConnection:
    def __init__(self, stream, address, logger):
        print(f"Received a new connection from {address} on xexun port")
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
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_bytes(255, partial=True)
                data_raw = data_bin[:-2].decode("ascii").strip()
                data_raw = re.search(r"G[PN]RMC,.+", data_raw).group(0)
            print(f"Received data ({data_raw})", flush=True)
            imei = re.search(r"imei:(\d+),", data_raw).group(1)
        except Exception as e:
            print("Error parsing data: " + str(e), flush=True)
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
        print("Valid Imei", flush=True)
        self.db_device = await get_device_by_imei(imei)
        if not self.db_device:
            print(f"Imei {imei} not registered  ({self.address})", flush=True)
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected", flush=True)

        await self._process_data(data_raw)

        while await self._read_line():
            pass

    async def _process_data(self, data_raw):
        data = data_raw.split(",")
        if not self.db_device.user_agent:
            self.db_device.user_agent = "Xexun ARM"
        imei = re.search(r"imei:(\d+),", data_raw).group(1)
        if imei != self.imei:
            return False
        self.logger.info(
            f"{arrow.now().datetime}, XEXUN DATA, "
            f"{self.aid}, {self.address}: {','.join(data)}"
        )
        try:
            tim = arrow.get(f"{data[9]} {data[1][:6]}", "DDMMYY HHmmss").int_timestamp
            lat_minute = float(data[3])
            lat = lat_minute // 100 + (lat_minute % 100) / 60
            if data[4] == "S":
                lat *= -1
            lon_minute = float(data[5])
            lon = lon_minute // 100 + (lon_minute % 100) / 60
            if data[6] == "W":
                lon *= -1
        except Exception as e:
            print(f"Could not parse GPS data {str(e)}", flush=True)
        else:

            loc_array = [(tim, lat, lon)]
            if data[2] == "A":
                await add_locations(self.db_device, loc_array)
                print(f"{len(loc_array)} locations wrote to DB", flush=True)

    async def _read_line(self):
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_bytes(255, partial=True)
                data_raw = data_bin[:-2].decode("ascii").strip()
                data_raw = re.search(r"G[PN]RMC,.+", data_raw).group(0)
            print(f"Received data ({data_raw})")
            await self._process_data(data_raw)
        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("Client quit", flush=True)


class XexunServer(GenericTCPServer):
    connection_class = XexunConnection

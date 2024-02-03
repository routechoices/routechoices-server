import json

import arrow
from django.core.exceptions import ValidationError

from routechoices.lib.helpers import random_key, safe64encode
from routechoices.lib.tcp_protocols.commons import (
    GenericTCPServer,
    add_locations,
    get_device_by_imei,
)
from routechoices.lib.validators import validate_imei


class TrackTapeConnection:
    def __init__(self, stream, address, logger):
        print(f"received a new connection from {address} on tracktape port")
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
        self.db_device = await get_device_by_imei(imei)
        if not self.db_device:
            print(f"Imei {imei} not registered ({self.address})", flush=True)
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")

        await self._process_data(data)

        while await self._read_line():
            pass

    async def _process_data(self, data):
        if not self.db_device.user_agent:
            self.db_device.user_agent = "TrackTape"
        imei = data.get("id")
        if imei != self.imei:
            return False
        try:
            battery_level = int(data.get("batteryLevel"))
        except Exception:
            pass
        else:
            self.db_device.battery_level = battery_level
        locs = data.get("positions", [])
        loc_array = []
        self.logger.info(
            f"{arrow.now().datetime}, TRCKTP DATA, "
            f"{self.aid}, {self.address}: {safe64encode(json.dumps(data))}"
        )
        for loc in locs:
            try:
                tim = arrow.get(loc.get("timestamp")).int_timestamp
                lon = float(loc.get("lon"))
                lat = float(loc.get("lat"))
                loc_array.append((tim, lat, lon))
            except Exception:
                continue
        if loc_array:
            await add_locations(self.db_device, loc_array)
            print(f"{len(loc_array)} locations wrote to DB", flush=True)

    async def _read_line(self):
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_until(b"\n")
                data_raw = data_bin.decode("ascii").strip()
            print(f"Received data ({data_raw})")
            data = json.loads(data_raw)
            await self._process_data(data)
        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("Client quit", flush=True)


class TrackTapeServer(GenericTCPServer):
    connection_class = TrackTapeConnection

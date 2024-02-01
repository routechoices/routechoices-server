import arrow
from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError

from routechoices.lib.helpers import random_key
from routechoices.lib.tcp_protocols.commons import _get_device
from routechoices.lib.validators import validate_imei


class XexunConnection:
    def __init__(self, stream, address, logger):
        print(f"received a new connection from {address} on xexun port")
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
                data_raw = data_bin.decode("ascii").strip()
            print(f"Received data ({data_raw})", flush=True)
            data = data_raw.split(",")
            imei = data[17].split(":")[1]
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

        await self._process_data(data)

        while await self._read_line():
            pass

    async def _process_data(self, data):
        if not self.db_device.user_agent:
            self.db_device.user_agent = "Xexun ARM"
        imei = data[17].split(":")[1]
        if imei != self.imei:
            return False
        self.logger.info(
            f"{arrow.now().datetime}, XEXUN DATA, "
            f"{self.aid}, {self.address}: {','.join(data)}"
        )
        try:
            tim = arrow.get(f"{data[11]} {data[3][:6]}", "DDMMYY HHmmss").int_timestamp
            lat_minute = float(data[5])
            lat = lat_minute // 100 + (lat_minute % 100) / 60
            if data[6] == "S":
                lat *= -1
            lon_minute = float(data[7])
            lon = lon_minute // 100 + (lon_minute % 100) / 60
            if data[8] == "W":
                lon *= -1
        except Exception:
            print("Could not parse GPS data", flush=True)
        else:
            loc_array = [(tim, lat, lon)]
            if data[4] == "A":
                await sync_to_async(
                    self.db_device.add_locations, thread_sensitive=True
                )(loc_array)
                print(f"{len(loc_array)} locations wrote to DB", flush=True)

    async def _read_line(self):
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_bytes(255, partial=True)
                data_raw = data_bin.decode("ascii").strip()
            print(f"Received data ({data_raw})")
            data = data_raw.split(",")
            await self._process_data(data)
        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("client quit", flush=True)

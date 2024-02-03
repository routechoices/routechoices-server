import arrow
from django.core.exceptions import ValidationError

from routechoices.lib.helpers import random_key, safe64encode
from routechoices.lib.tcp_protocols.commons import (
    GenericTCPServer,
    add_locations,
    get_device_by_imei,
    send_sos,
)
from routechoices.lib.validators import validate_imei


class MicTrackConnection:
    def __init__(self, stream, address, logger):
        print(f"Received a new connection from {address} on mictrack port")
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
            data_bin = await self.stream.read_bytes(2)
            data_raw = data_bin.decode("ascii")
            if data_raw == "MT":
                self.protocol_version = 2
            elif data_raw.startswith("#"):
                self.protocol_version = 1
            else:
                print("Unknown protocol", flush=True)
                self.stream.close()
                return
            if self.protocol_version == 1:
                data_bin = await self.stream.read_until(b"\r\n##", 1000)
                data_raw += data_bin.decode("ascii").strip()
            else:
                data_bin = await self.stream.read_bytes(22)
                data_raw += data_bin.decode("ascii")
            if self.protocol_version == 1:
                data = data_raw.split("#")
                imei = data[1]
            else:
                data = data_raw.split(";")
                imei = data[2]
                if data[3] == "R0":
                    while len(data_raw.split("+")) < 9:
                        data_bin = await self.stream.read_bytes(90, partial=True)
                        data_raw += data_bin.decode("ascii")
                    data = data_raw.split(";")
                else:
                    data_bin = await self.stream.read_bytes(90, partial=True)
                    data_raw += data_bin.decode("ascii")
            print(f"Received data ({data_raw})", flush=True)
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
        if self.protocol_version == 1:
            self.logger.info(
                f"{arrow.now().datetime}, MICTRK DATA, "
                f"{self.aid}, {self.address}: {safe64encode(data_raw)}"
            )
        else:
            self.logger.info(
                f"{arrow.now().datetime}, MICTRK DATA2, "
                f"{self.aid}, {self.address}: {safe64encode(data_raw)}"
            )
        self.db_device = await get_device_by_imei(imei)
        if not self.db_device:
            print(f"Imei {imei} not registered ({self.address})", flush=True)
            self.stream.close()
            return
        self.imei = imei
        print(f"{self.imei} is connected")
        if self.protocol_version == 1:
            await self._process_data(data)
            while await self._read_line():
                pass
        else:
            await self._process_data2(data)
            while await self._read_line2():
                pass

    async def _process_data(self, data):
        imei = data[1]
        sos_triggered = data[4] == "SOS"
        if imei != self.imei:
            return False
        gps_data = data[6].split(",")
        try:
            batt_volt, msg_type = gps_data[0].split("$")
        except Exception:
            print("Invalid format", flush=True)
            return False
        if msg_type != "GPRMC" or gps_data[2] not in ("A", "L"):
            print("Not GPS data or invalid data", flush=True)
            return False
        try:
            tim = arrow.get(
                f"{gps_data[9]} {gps_data[1]}", "DDMMYY HHmmss.S"
            ).int_timestamp
            lat_minute = float(gps_data[3])
            lat = lat_minute // 100 + (lat_minute % 100) / 60
            if gps_data[4] == "S":
                lat *= -1
            lon_minute = float(gps_data[5])
            lon = lon_minute // 100 + (lon_minute % 100) / 60
            if gps_data[6] == "W":
                lon *= -1
        except Exception:
            print("Could not parse GPS data", flush=True)
            return False
        if not self.db_device.user_agent:
            self.db_device.user_agent = "MicTrack V1"
        try:
            # https://help.mictrack.com/articles/how-to-calculate-battery-voltage-into-percentage-for-mictrack-devices/
            # we assume 4.2V battery going empty at 3.3V
            self.db_device.battery_level = max(
                [0, min([100, int((int(batt_volt) - 33) / 9 * 100)])]
            )
        except Exception:
            print("Invalid battery level value", flush=True)
            pass
        await add_locations(self.db_device, [(tim, lat, lon)])
        print("1 location wrote to DB", flush=True)
        if sos_triggered:
            sos_device_aid, sos_lat, sos_lon, sos_sent_to = await send_sos(
                self.db_device
            )
            print(
                (
                    f"SOS triggered by device {sos_device_aid}, "
                    f"{sos_lat}, {sos_lon} email sent to {sos_sent_to}"
                ),
                flush=True,
            )

    async def _process_data2(self, data):
        imei = data[2]
        if imei != self.imei:
            return False
        msg_type = data[3]
        if msg_type != "R0":
            print("Not GPS data", flush=True)
            return False
        gps_data = data[4].split("+")
        sos_triggered = gps_data[6] == "5"
        batt_volt = gps_data[7]
        try:
            tim = arrow.get(gps_data[1], "YYMMDDHHmmss").int_timestamp
            lat = float(gps_data[2])
            lon = float(gps_data[3])
        except Exception:
            print("Could not parse GPS data", flush=True)
            return False
        if not self.db_device.user_agent:
            self.db_device.user_agent = "MicTrack V2"
        try:
            # https://help.mictrack.com/articles/how-to-calculate-battery-voltage-into-percentage-for-mictrack-devices/
            # we assume 4.2V battery going empty at 3.5V
            self.db_device.battery_level = max(
                [0, min([100, int((int(batt_volt) - 3500) / 700 * 100)])]
            )
        except Exception:
            print("Invalid battery level value", flush=True)
            pass
        await add_locations(self.db_device, [(tim, lat, lon)])
        print("1 location wrote to DB", flush=True)
        if sos_triggered:
            sos_device_aid, sos_lat, sos_lon, sos_sent_to = await send_sos(
                self.db_device
            )
            print(
                (
                    f"SOS triggered by device {sos_device_aid}, "
                    f"{sos_lat}, {sos_lon} email sent to {sos_sent_to}"
                ),
                flush=True,
            )

    async def _read_line(self):
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_until(b"\r\n##")
                data_raw = data_bin.decode("ascii").strip()
            if not data_raw.startswith("#"):
                print("Invalid protocol")
                self.stream.close()
                return False
            print(f"Received data ({data_raw})")
            self.logger.info(
                f"{arrow.now().datetime}, MICTRK DATA, "
                f"{self.aid}, {self.address}: {safe64encode(data_raw)}"
            )
            data = data_raw.split("#")
            await self._process_data(data)
        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    async def _read_line2(self):
        try:
            data_raw = ""
            while not data_raw:
                data_bin = await self.stream.read_bytes(24)
                data_raw = data_bin.decode("ascii")
            if not data_raw.startswith("MT;"):
                print("Invalid protocol")
                self.stream.close()
                return False
            data = data_raw.split(";")
            if data[3] == "R0":
                while len(data_raw.split("+")) < 9:
                    data_bin = await self.stream.read_bytes(90, partial=True)
                    data_raw += data_bin.decode("ascii")
                data = data_raw.split(";")
            else:
                data_bin = await self.stream.read_bytes(90, partial=True)
                data_raw += data_bin.decode("ascii")
            print(f"Received data ({data_raw})")
            self.logger.info(
                f"{arrow.now().datetime}, MICTRK DATA2, "
                f"{self.aid}, {self.address}: {safe64encode(data_raw)}"
            )
            await self._process_data2(data)
        except Exception as e:
            print(f"Error parsing data: {str(e)}")
            self.stream.close()
            return False
        return True

    def _on_close(self):
        print("Client quit", flush=True)


class MicTrackServer(GenericTCPServer):
    connection_class = MicTrackConnection

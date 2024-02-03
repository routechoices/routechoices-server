import math

import arrow
from django.core.exceptions import ValidationError

from routechoices.lib.helpers import random_key
from routechoices.lib.tcp_protocols.commons import (
    GenericTCPServer,
    add_locations,
    get_device_by_imei,
    get_pending_commands,
    mark_pending_commands_sent,
    save_device,
    send_sos,
)
from routechoices.lib.validators import validate_imei


class QueclinkConnection:
    def __init__(self, stream, address, logger):
        print(f"Received a new connection from {address} on queclink port")
        self.aid = random_key()
        self.imei = None
        self.address = address
        self.stream = stream
        self.stream.set_close_callback(self.on_close)
        self.db_device = None
        self.logger = logger

    async def start_listening(self):
        print(f"Start listening from {self.address}")
        imei = None
        try:
            data_bin = await self.stream.read_until(b"$")
            data = data_bin.decode("ascii")
            self.logger.info(
                f"{arrow.now().datetime}, GL300 DATA, "
                f"{self.aid}, {self.address}, {data}"
            )
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
        self.db_device = await get_device_by_imei(imei)
        if not self.db_device:
            print(f"Imei {imei} not registered ({self.address})", flush=True)
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
        access_date, commands = await get_pending_commands(self.imei)
        for command in commands:
            await self.stream.write(command.encode())
        commands_count = len(commands)
        if commands_count > 0:
            print(f"{commands_count} commands sent")
            await mark_pending_commands_sent(self.imei, access_date)

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
                batt = None
                try:
                    batt = int(parts[-3])
                except Exception:
                    pass
                await self.on_data(pts, batt)
                if parts[0][8:] == "SOS":
                    sos_device_aid, sos_lat, sos_lon, sos_sent_to = await send_sos(
                        self.db_device
                    )
                    print(
                        f"SOS triggered by device {sos_device_aid}, {sos_lat},"
                        f" {sos_lon} email sent to {sos_sent_to}",
                        flush=True,
                    )
            elif parts[0] == "+ACK:GTHBD":
                await self.stream.write(
                    f"+SACK:GTHBD,{parts[1]},{parts[5]}".encode("ascii")
                )
            elif parts[0][:8] == "+RESP:GT" and parts[0][8:] == "INF":
                imei = parts[2]
                if imei != self.imei:
                    raise Exception("Cannot change IMEI while connected")
                try:
                    print(f"Battery level at {parts[18]}%", flush=True)
                    batt = int(parts[18])
                except Exception as e:
                    print(f"Error parsing battery level: {str(e)}", flush=True)
                self.db_device.battery_level = batt
                await save_device(self.db_device)
        except Exception as e:
            print(f"Error processing line: {str(e)}", flush=True)
            self.stream.close()
            return False
        return True

    async def read_line(self):
        data_bin = await self.stream.read_until(b"$")
        data = data_bin.decode("ascii")
        self.logger.info(
            f"{arrow.now().datetime}, GL300 DATA, {self.aid}, {self.address}, {data}"
        )
        print(f"Received data ({data})")
        await self.send_pending_commands()
        return await self.process_line(data)

    async def on_data(self, pts, batt=None):
        if not self.db_device.user_agent:
            self.db_device.user_agent = "Queclink"
        if batt:
            self.db_device.battery_level = batt
        loc_array = pts
        await add_locations(self.db_device, loc_array)
        print(f"{len(pts)} Locations wrote to DB", flush=True)

    def on_close(self):
        print("Client quit", flush=True)


class QueclinkServer(GenericTCPServer):
    connection_class = QueclinkConnection

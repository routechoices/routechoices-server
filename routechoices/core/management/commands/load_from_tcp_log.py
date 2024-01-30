import math
import os.path

import arrow
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from routechoices.core.models import Device
from routechoices.lib.validators import validate_imei


def process_file(file_path):
    devices = {}
    new_locs = {}
    print(file_path)
    with open(file_path, "r", encoding="utf-8") as fp:
        while line := fp.readline():
            if ", " not in line:
                continue
            ts, type = line.split(", ", 1)
            if type.startswith("GL300 DATA"):
                ts, type, aid, address, port, data = line.split(", ", 5)
                imei = None
                parts = data.split(",")
                if parts[0][:8] not in ("+RESP:GT", "+BUFF:GT"):
                    continue
                imei = parts[2]
                is_valid_imei = True
                try:
                    validate_imei(imei)
                except ValidationError:
                    is_valid_imei = False
                if not is_valid_imei:
                    continue
                device = devices.get(imei)
                if not device:
                    device = Device.objects.filter(physical_device__imei=imei).first()
                    if not device:
                        continue
                    devices[imei] = device
                    new_locs[imei] = []
                if parts[0][8:] in (
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
                    nb_pts = int(parts[6])
                    if 12 * nb_pts + 10 == len(parts):
                        len_points = 12
                    elif 11 * nb_pts + 11 == len(parts):
                        len_points = 11
                    else:
                        len_points = math.floor((len(parts) - 10) / nb_pts)
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
                            new_locs[imei].append((tim, lat, lon))
    for imei in new_locs:
        devices[imei].add_locations(new_locs[imei])
        print(f"{len(new_locs[imei])} added to device {imei}")


class Command(BaseCommand):
    help = "Load data from TCP server logs."

    def handle(self, *args, **options):
        for i in range(5, 0, -1):
            file_path = os.path.join(settings.BASE_DIR, "logs", f"tcp.log.{i}")
            if os.path.exists(file_path):
                process_file(file_path)
        file_path = os.path.join(settings.BASE_DIR, "logs", "tcp.log")
        if os.path.exists(file_path):
            process_file(file_path)

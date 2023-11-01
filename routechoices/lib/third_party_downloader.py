import arrow
import requests
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils.timezone import now
from PIL import Image

from routechoices.core.models import (
    PRIVACY_SECRET,
    Club,
    Competitor,
    Device,
    Event,
    Map,
)
from routechoices.lib.helpers import (
    epoch_to_datetime,
    safe64encodedsha,
    three_point_calibration_to_corners,
)


class EventImportError(Exception):
    pass


class MapsImportError(Exception):
    pass


class CompetitorsImportError(Exception):
    pass


class ThirdPartyTrackingSolution:
    name = None
    slug = None

    def __init__(self):
        self.club = self.get_or_create_club()

    def get_or_create_club(self):
        if not self.name or not self.slug:
            raise ValueError()
        admins = User.objects.filter(is_superuser=True)
        club, created = Club.objects.get_or_create(
            slug=self.slug, defaults={"name": self.name}
        )
        if created:
            club.admins.set(admins)
            club.save()
        return club

    def get_or_create_event(self, uid):
        raise NotImplementedError()

    def get_or_create_event_maps(self, event, uid):
        raise NotImplementedError()

    def get_or_create_event_competitors(self, event, uid):
        raise NotImplementedError()


class GpsSeurantaNet(ThirdPartyTrackingSolution):
    GPSSEURANTA_EVENT_URL = "http://www.tulospalvelu.fi/gps/"
    name = "GPS Seuranta"
    slug = "gpsseuranta"

    def parse_init_file(self, init_raw_data):
        event_data = {"COMPETITOR": []}
        for line in init_raw_data.split("\n"):
            try:
                key, val = line.strip().split(":")
                if key != "COMPETITOR":
                    event_data[key] = val
                else:
                    event_data[key].append(val)
            except ValueError:
                continue
        return event_data

    def decode_data_line(self, data):
        if not data:
            return []
        o_pt = data[0].split("_")
        if o_pt[0] == "*" or o_pt[1] == "*" or o_pt[2] == "*":
            return []
        t = int(o_pt[0]) + 1136073600
        prev_loc = {
            "lat": int(o_pt[2]) * 1.0 / 1e5,
            "lon": int(o_pt[1]) * 2.0 / 1e5,
            "ts": t,
        }
        loc_array = []
        loc_array.append((t, prev_loc["lat"], prev_loc["lon"]))
        for p in data[1:]:
            if len(p) < 3:
                continue
            if "_" in p:
                pt = p.split("_")
                if pt[0] == "*":
                    pt[0] = 0
                if pt[1] == "*":
                    pt[1] = 0
                if pt[2] == "*":
                    pt[2] = 0
                dt = int(pt[0])
                dlon = int(pt[1])
                dlat = int(pt[2])
            else:
                chars = (
                    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    + "abcdefghijklmnopqrstuvwxyz"
                )
                dt = chars.index(p[0]) - 31
                dlon = chars.index(p[1]) - 31
                dlat = chars.index(p[2]) - 31
            t = prev_loc["ts"] + dt
            prev_loc = {
                "lat": ((prev_loc["lat"] * 1e5) + dlat) / 1e5,
                "lon": ((prev_loc["lon"] * 5e4) + dlon) / 5e4,
                "ts": t,
            }
            loc_array.append((t, prev_loc["lat"], prev_loc["lon"]))
        return loc_array

    def get_or_create_event_maps(self, event, uid):
        calibration_string = self.init_data.get("CALIBRATION")
        try:
            map_url = f"{self.GPSSEURANTA_EVENT_URL}{uid}/map"
            map_obj, _ = Map.objects.get_or_create(
                name=event.name,
                club=self.club,
            )
            r = requests.get(map_url)
            if r.status_code != 200:
                map_obj.delete()
                raise MapsImportError("API returned error code")
            map_file = ContentFile(r.content)
            with Image.open(map_file) as img:
                width, height = img.size
            corners = three_point_calibration_to_corners(
                calibration_string, width, height
            )
            coordinates = ",".join([str(x) for x in corners])

            map_obj.image.save("imported_image", map_file, save=False)
            map_obj.corners_coordinates = coordinates
            map_obj.save()
            return [map_obj]
        except MapsImportError:
            return []

    def get_or_create_event_competitors(self, event, uid):
        device_map = {}
        data_url = f"{self.GPSSEURANTA_EVENT_URL}{uid}/data.lst"
        r = requests.get(data_url)
        if r.status_code == 200:
            data_raw = r.text
            for line in data_raw.split("\n"):
                line_data = line.strip().split(".")
                if len(line_data) == 0:
                    continue
                dev_id = line_data[0]
                if "_" in dev_id:
                    dev_id, _ = dev_id.split("_", 1)
                new_locations = self.decode_data_line(line_data[1:])
                if not device_map.get(dev_id):
                    device_map[dev_id], created = Device.objects.get_or_create(
                        aid=safe64encodedsha(f"{dev_id}:{uid}")[:8] + "_SEU",
                        defaults={"is_gpx": True},
                    )
                    if not created:
                        device_map[dev_id].locations_series = []
                device_map[dev_id].add_locations(new_locations, save=False)

        competitors = []
        for c_raw in self.init_data.get("COMPETITOR"):
            c_data = c_raw.strip().split("|")
            competitor, _ = Competitor.objects.get_or_create(
                name=c_data[3],
                short_name=c_data[4],
                event=event,
            )

            start_time = None
            start_time_raw = (
                f"{c_data[1]}"
                f"{c_data[2].zfill(4) if len(c_data[2]) < 5 else c_data[2].zfill(6)}"
            )
            try:
                if len(start_time_raw) == 12:
                    start_time = arrow.get(start_time_raw, "YYYYMMDDHHmm")
                else:
                    start_time = arrow.get(start_time_raw, "YYYYMMDDHHmmss")
            except Exception:
                pass
            else:
                start_time = start_time.shift(
                    minutes=-int(self.init_data.get("TIMEZONE", 0))
                ).datetime
                competitor.start_time = start_time

            competitor_device = device_map.get(c_data[0])
            if competitor_device:
                competitor_device.save()
                competitor.device = competitor_device

            competitors.append(competitor)

        return competitors

    def get_or_create_event(self, uid):
        event_url = f"{self.GPSSEURANTA_EVENT_URL}{uid}/init.txt"
        r = requests.get(event_url)
        if r.status_code != 200:
            raise EventImportError("API returned error code" + event_url)
        self.init_data = self.parse_init_file(r.text)

        event_name = self.init_data.get("RACENAME", uid)
        event, _ = Event.objects.get_or_create(
            club=self.club,
            slug=uid,
            defaults={
                "name": event_name[:255],
                "privacy": PRIVACY_SECRET,
                "start_date": now(),
                "end_date": now(),
            },
        )
        maps = self.get_or_create_event_maps(uid)
        if maps:
            event.map = maps[0]

        start_date = None
        end_date = None

        competitors = self.get_or_create_event_competitors(event, uid)
        for competitor in competitors:
            competitor.save()
            if competitor.device.location_count > 0:
                locations = competitor.device.locations_series
                from_date = locations[0][0]
                to_date = locations[-1][0]
                if not start_date or start_date > from_date:
                    start_date = from_date
                if not end_date or end_date < to_date:
                    end_date = to_date

        event.start_date = epoch_to_datetime(start_date)
        event.end_date = epoch_to_datetime(end_date)
        event.save()
        return event

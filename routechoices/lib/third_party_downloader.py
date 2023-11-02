import json
import tempfile

import arrow
import requests
from bs4 import BeautifulSoup
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
    MapAssignation,
)
from routechoices.lib.helpers import (
    compute_corners_from_kml_latlonbox,
    epoch_to_datetime,
    safe64encodedsha,
    three_point_calibration_to_corners,
)
from routechoices.lib.mtb_decoder import MtbDecoder
from routechoices.lib.tractrac_ws_decoder import TracTracWSReader


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

    def parse_init_data(self, uid):
        raise NotImplementedError()

    def get_or_create_event(self, uid):
        raise NotImplementedError()

    def get_or_create_event_maps(self, event, uid):
        raise NotImplementedError()

    def assign_maps_to_event(self, event, maps):
        if maps:
            event.map = maps[0]
            for xtra_map in maps[1:]:
                MapAssignation.object.get_or_create(
                    name=xtra_map.name,
                    map=xtra_map,
                    event=event,
                )
        return event

    def get_or_create_event_competitors(self, event, uid):
        raise NotImplementedError()

    def assign_competitors_to_event(self, event, competitors):
        start_date = None
        end_date = None
        for competitor in competitors:
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
        return event

    def import_event(self, uid):
        self.parse_init_data(uid)
        event = self.get_or_create_event(uid)
        maps = self.get_or_create_event_maps(event, uid)
        event = self.assign_maps_to_event(event, maps)
        competitors = self.get_or_create_event_competitors(event, uid)
        event = self.assign_competitors_to_event(event, competitors)
        event.save()
        return event


class SportRec(ThirdPartyTrackingSolution):
    slug = "sportrec"
    name = "SportRec"

    def parse_init_data(self, uid):
        r = requests.get(
            f"https://sportrec.eu/ui/nsport_admin/index.php?r=api/competition&id={uid}"
        )
        if r.status_code != 200:
            raise EventImportError("API returned error code")
        self.init_data = r.json()

    def get_or_create_event(self, uid):
        event_name = self.init_data["competition"]["title"]
        event, _ = Event.objects.get_or_create(
            club=self.club,
            slug=uid,
            defaults={
                "name": event_name[:255],
                "privacy": PRIVACY_SECRET,
                "start_date": arrow.get(
                    self.init_data["competition"]["time_start"]
                ).datetime,
                "end_date": arrow.get(
                    self.init_data["competition"]["time_finish"]
                ).datetime,
            },
        )
        return event

    def get_or_create_event_maps(self, event, uid):
        if not self.init_data["hasMap"]:
            return []
        map_url = f"https://sportrec.eu/ui/nsport_admin/index.php?r=api/map&id={uid}"
        map_obj, created = Map.objects.get_or_create(
            name=event.name,
            club=self.club,
        )
        r = requests.get(map_url)
        if r.status_code != 200:
            map_obj.delete()
            raise MapsImportError("API returned error code")
        try:
            map_file = ContentFile(r.content)
            map_data = self.init_data["track"]
            coords = map_data["map_box"]
            n, e, s, w = [
                float(x) for x in coords.replace("(", "").replace(")", "").split(",")
            ]
            corners_latlon = compute_corners_from_kml_latlonbox(
                n, e, s, w, -float(map_data["map_angle"])
            )
            corners_coords = []
            for corner in corners_latlon:
                corners_coords += [corner[0], corner[1]]
            calib_string = ",".join(str(round(x, 5)) for x in corners_coords)
            map_obj.image.save("imported_image", map_file, save=False)
            map_obj.corners_coordinates = calib_string
            map_obj.save()
        except Exception:
            map_obj.delete()
            raise MapsImportError("Error importing map")
        else:
            return [map_obj]

    def get_or_create_event_competitors(self, event, uid):
        data_url = (
            f"https://sportrec.eu/ui/nsport_admin/index.php?r=api/history&id={uid}"
        )
        response = requests.get(data_url, stream=True)
        if response.status_code != 200:
            raise CompetitorsImportError("API returned error code")

        device_map = {}
        with tempfile.TemporaryFile() as lf:
            for block in response.iter_content(1024 * 8):
                if not block:
                    break
                lf.write(block)
            lf.flush()
            lf.seek(0)
            try:
                device_data = json.load(lf)
            except Exception:
                raise CompetitorsImportError("Invalid JSON")
        try:
            for d in device_data["locations"]:
                device_map[d["device_id"]] = [
                    (int(float(x["aq"]) / 1e3), float(x["lat"]), float(x["lon"]))
                    for x in d["locations"]
                ]
        except Exception:
            raise CompetitorsImportError("Unexpected data structure")

        competitors = []
        for c_data in self.init_data["participants"]:
            competitor, _ = Competitor.objects.get_or_create(
                name=c_data["fullname"],
                short_name=c_data["shortname"],
                event=event,
            )
            dev_id = c_data["device_id"]
            dev_data = device_map.get(dev_id)
            dev_obj = None
            if dev_data:
                dev_obj, created = Device.objects.get_or_create(
                    aid="SPR_" + safe64encodedsha("{dev_id}:{uid}"),
                    defaults={
                        "is_gpx": True,
                    },
                )
                if not created:
                    dev_obj.locations_series = []
                dev_obj.add_locations(dev_data)
                dev_obj.save()
                competitor.device = dev_obj
            if start_time := c_data.get("time_start"):
                start_time = arrow.get(start_time).datetime
            competitor.save()
            competitors.append(competitor)
        return competitors


class OTracker(ThirdPartyTrackingSolution):
    slug = "otracker"
    name = "OTracker"

    def parse_init_data(self, uid):
        rp = requests.get(f"https://otracker.lt/events/{uid}")
        if rp.status_code != 200:
            raise EventImportError("API returned error code")
        soup = BeautifulSoup(rp.text, "html.parser")
        name = soup.find("title").string[:-13]

        r = requests.get(f"https://otracker.lt/data/events/{uid}")
        if r.status_code != 200:
            raise EventImportError("API returned error code")
        self.init_data = r.json()
        self.init_data["event"]["name"] = name

    def get_or_create_event(self, uid):
        start_date = arrow.get(
            self.init_data["event"]["replay_time"]["from_ts"]
        ).datetime
        end_date = arrow.get(self.init_data["event"]["replay_time"]["to_ts"]).datetime
        event, _ = Event.objects.get_or_create(
            club=self.club,
            slug=safe64encodedsha(uid)[:50],
            defaults={
                "name": self.init_data["event"]["name"][:255],
                "privacy": PRIVACY_SECRET,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return event

    def get_or_create_event_maps(self, event, uid):
        map_data = self.init_data["event"]["map_image"]
        map_url = map_data["url"]
        if not map_url:
            return []
        r = requests.get(map_url)
        if r.status_code != 200:
            raise MapsImportError("API returned error code")
        map_obj, _ = Map.objects.get_or_create(
            name=event.name,
            club=self.club,
        )
        try:
            map_file = ContentFile(r.content)
            map_opt = map_data["options"]
            corners_coords = []
            for corner in ("tl", "tr", "br", "bl"):
                corners_coords += [
                    map_opt[corner]["lat"],
                    map_opt[corner]["lon"],
                ]
            calib_string = ",".join(str(x) for x in corners_coords)
            map_obj.image.save("imported_image", map_file, save=False)
            map_obj.corners_coordinates = calib_string
            map_obj.save()
        except Exception:
            map_obj.delete()
            raise MapsImportError("Error importing map")
        else:
            return [map_obj]

    def get_or_create_event_competitors(self, event, uid):
        data_url = (
            f"https://otracker.lt/data/locations/history/{uid}?map_type=tileimage"
        )
        response = requests.get(data_url, stream=True)
        if response.status_code != 200:
            raise CompetitorsImportError("API returned error code")
        with tempfile.TemporaryFile() as lf:
            for block in response.iter_content(1024 * 8):
                if not block:
                    break
                lf.write(block)
            lf.flush()
            lf.seek(0)

            try:
                orig_device_map = json.load(lf)
            except Exception:
                raise CompetitorsImportError("Invalid JSON")
        device_map = {}
        event_offset_time = self.init_data["event"]["replay_time"]["from_ts"]
        try:
            for d in orig_device_map:
                device_map[d] = [
                    (x["fix_time"] + event_offset_time, x["lat"], x["lon"])
                    for x in orig_device_map[d]
                ]
        except Exception:
            raise CompetitorsImportError("Unexpected data structure")

        competitors = []
        for c_data in self.init_data["competitors"].values():
            start_time = c_data.get("sync_offset") + event_offset_time
            competitor, _ = Competitor.objects.get_or_create(
                name=c_data["name"],
                short_name=c_data["short_name"],
                event=event,
            )
            competitor.start_time = arrow.get(start_time).datetime
            dev_id = str(c_data["id"])
            dev_data = device_map.get(dev_id)
            dev_obj = None
            if dev_data:
                dev_obj, created = Device.objects.get_or_create(
                    aid="OTR_" + safe64encodedsha(f"{dev_id}:{uid}")[:8],
                    defaults={
                        "is_gpx": True,
                    },
                )
                if not created:
                    dev_obj.locations_series = []
                dev_obj.add_locations(dev_data)
                dev_obj.save()
                competitor.device = dev_obj
            competitor.save()
            competitors.append(competitor)
        return competitors


class GpsSeurantaNet(ThirdPartyTrackingSolution):
    GPSSEURANTA_EVENT_URL = "http://www.tulospalvelu.fi/gps/"
    name = "GPS Seuranta"
    slug = "gpsseuranta"

    def parse_init_data(self, uid):
        event_url = f"{self.GPSSEURANTA_EVENT_URL}{uid}/init.txt"
        r = requests.get(event_url)
        if r.status_code != 200:
            raise EventImportError("API returned error code" + event_url)
        event_data = {"COMPETITOR": []}
        for line in r.text.split("\n"):
            try:
                key, val = line.strip().split(":")
                if key != "COMPETITOR":
                    event_data[key] = val
                else:
                    event_data[key].append(val)
            except ValueError:
                continue
        self.init_data = event_data

    def get_or_create_event(self, uid):
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
        return event

    def get_or_create_event_maps(self, event, uid):
        calibration_string = self.init_data.get("CALIBRATION")
        map_obj, _ = Map.objects.get_or_create(
            name=event.name,
            club=self.club,
        )
        map_url = f"{self.GPSSEURANTA_EVENT_URL}{uid}/map"
        r = requests.get(map_url)
        if r.status_code != 200:
            map_obj.delete()
            raise MapsImportError("API returned error code")
        try:
            map_file = ContentFile(r.content)
            with Image.open(map_file) as img:
                width, height = img.size
            corners = three_point_calibration_to_corners(
                calibration_string, width, height
            )
            coordinates = ",".join([str(round(x, 5)) for x in corners])

            map_obj.image.save("imported_image", map_file, save=False)
            map_obj.corners_coordinates = coordinates
            map_obj.save()
        except Exception:
            map_obj.delete()
            raise MapsImportError("Error importing map")
        else:
            return [map_obj]

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
                    dev_obj, created = Device.objects.get_or_create(
                        aid="SEU_" + safe64encodedsha(f"{dev_id}:{uid}")[:8],
                        defaults={"is_gpx": True},
                    )
                    if not created:
                        dev_obj.locations_series = []
                    device_map[dev_id] = dev_obj
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

            device = device_map.get(c_data[0])
            if device:
                device.save()
                competitor.device = device
            competitor.save()
            competitors.append(competitor)

        return competitors

    @classmethod
    def decode_data_line(cls, data):
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


class Loggator(ThirdPartyTrackingSolution):
    LOGGATOR_EVENT_URL = "https://loggator.com/api/events/"
    name = "Loggator"
    slug = "loggator"

    def parse_init_data(self, uid):
        event_url = f"{self.LOGGATOR_EVENT_URL}{uid}.json"
        r = requests.get(event_url)
        if r.status_code != 200:
            raise EventImportError("API returned error code")
        self.init_data = r.json()

    def get_or_create_event(self, uid):
        event, created = Event.objects.get_or_create(
            club=self.club,
            slug=self.init_data["event"]["slug"],
            defaults={
                "name": self.init_data["event"]["name"][:255],
                "privacy": PRIVACY_SECRET,
                "start_date": arrow.get(self.init_data["event"]["start_date"]).datetime,
                "end_date": arrow.get(self.init_data["event"]["end_date"]).datetime,
            },
        )
        return event

    def get_or_create_event_maps(self, event, uid):
        map_data = self.init_data.get("map")
        if not map_data:
            return []
        map_obj, created = Map.objects.get_or_create(
            name=event.name,
            club=self.club,
        )
        map_url = map_data["url"]
        r = requests.get(map_url)
        if r.status_code != 200:
            map_obj.delete()
            raise MapsImportError("API returned error code")
        try:
            map_file = ContentFile(r.content)
            coordinates = ",".join(
                [
                    str(map_data["coordinates"]["topLeft"]["lat"]),
                    str(map_data["coordinates"]["topLeft"]["lng"]),
                    str(map_data["coordinates"]["topRight"]["lat"]),
                    str(map_data["coordinates"]["topRight"]["lng"]),
                    str(map_data["coordinates"]["bottomRight"]["lat"]),
                    str(map_data["coordinates"]["bottomRight"]["lng"]),
                    str(map_data["coordinates"]["bottomLeft"]["lat"]),
                    str(map_data["coordinates"]["bottomLeft"]["lng"]),
                ]
            )
            map_obj.image.save("imported_image", map_file, save=False)
            map_obj.corners_coordinates = coordinates
            map_obj.save()
        except Exception:
            map_obj.delete()
            raise MapsImportError("Error importing map")
        else:
            return [map_obj]

    def get_or_create_event_competitors(self, event, uid):
        device_map = {}
        locations_by_device_id = {}
        r = requests.get(self.init_data["tracks"])
        if r.status_code == 200:
            tracks_raw = r.json()["data"]
            tracks_pts = tracks_raw.split(";")
            for pt in tracks_pts:
                d = pt.split(",")
                dev_id = f"{int(d[0])}"
                if not device_map.get(dev_id):
                    dev_obj, created = Device.objects.get_or_create(
                        aid="LOG_" + safe64encodedsha(f"{dev_id}:{uid}")[:8],
                        defaults={
                            "is_gpx": True,
                        },
                    )
                    if not created:
                        dev_obj.locations_series = []
                    device_map[dev_id] = dev_obj
                    locations_by_device_id[dev_id] = []
                locations_by_device_id[dev_id].append(
                    (int(d[4]), float(d[1]), float(d[2]))
                )

        competitors = []
        for c_data in self.init_data["competitors"]:
            competitor, _ = Competitor.objects.get_or_create(
                name=c_data["name"],
                short_name=c_data["shortname"],
                event=event,
            )
            competitor.start_time = arrow.get(c_data["start_time"]).datetime
            device_id = f"{c_data['device_id']}"
            device = device_map.get(device_id)
            if device:
                device.add_locations(locations_by_device_id[device_id])
                device.save()
                competitor.device = device
            competitor.save()
            competitors.append(competitor)
        return competitors


class Tractrac(ThirdPartyTrackingSolution):
    name = "TracTrac"
    slug = "tractrac"

    def parse_init_data(self, uid):
        r = requests.get(uid)
        if r.status_code != 200:
            raise EventImportError("API returned error code")
        self.init_data = r.json()

    def get_or_create_event(self, uid):
        event_name = f'{self.init_data["eventName"]} - {self.init_data["raceName"]}'
        slug = safe64encodedsha(self.init_data["raceId"])[:50]
        event, _ = Event.objects.get_or_create(
            club=self.club,
            slug=slug,
            defaults={
                "name": event_name,
                "privacy": PRIVACY_SECRET,
                "start_date": arrow.get(
                    self.init_data["raceTrackingStartTime"]
                ).datetime,
                "end_date": arrow.get(self.init_data["raceTrackingEndTime"]).datetime,
            },
        )
        return event

    def get_or_create_event_maps(self, event, uid):
        maps = []
        for map_data in self.init_data["maps"]:
            map_obj, _ = Map.objects.get_or_create(
                name=map_data.get("name"),
                club=self.club,
            )
            map_url = map_data.get("location")
            if map_url.startswith("//"):
                map_url = f"http:{map_url}"
            r = requests.get(map_url, verify=False)
            if r.status_code != 200:
                map_obj.delete()
                raise MapsImportError("API returned error code")
            try:
                map_file = ContentFile(r.content)
                with Image.open(map_file) as img:
                    width, height = img.size
                calibration_string = "|".join(
                    str(x)
                    for x in [
                        map_data["long1"],
                        map_data["lat1"],
                        map_data["x1"],
                        map_data["y1"],
                        map_data["long2"],
                        map_data["lat2"],
                        map_data["x2"],
                        map_data["y2"],
                        map_data["long3"],
                        map_data["lat3"],
                        map_data["x3"],
                        map_data["y3"],
                    ]
                )
                corners = three_point_calibration_to_corners(
                    calibration_string,
                    width,
                    height,
                )
                coordinates = ",".join([str(round(x, 5)) for x in corners])
                map_obj.image.save("imported_image", map_file, save=False)
                map_obj.corners_coordinates = coordinates
                map_obj.save()
            except Exception:
                map_obj.delete()
                raise MapsImportError("Error importing a map")
            else:
                map_obj.is_main = map_data.get("is_default_loaded")
                maps.append(map_obj)
        sorted_maps = list(sorted(maps, key=lambda obj: (not obj.is_main, obj.name)))
        return sorted_maps

    def get_or_create_event_competitors(self, event, uid):
        device_map = None
        mtb_url = self.init_data["parameters"].get("stored-uri")
        if mtb_url and isinstance(mtb_url, dict):
            mtb_url = mtb_url.get("all")
        if mtb_url and not mtb_url.startswith("tcp:") and ".mtb" in mtb_url:
            data_url = mtb_url
            if not data_url.startswith("http"):
                data_url = f"http:{data_url}"
            response = requests.get(data_url, stream=True)
            if response.status_code == 200:
                with tempfile.TemporaryFile() as lf:
                    for block in response.iter_content(1024 * 8):
                        if not block:
                            break
                        lf.write(block)
                    lf.flush()
                    lf.seek(0)
                    try:
                        device_map = MtbDecoder(lf).decode()
                    except Exception:
                        if not self.init_data["parameters"].get("ws-uri"):
                            raise CompetitorsImportError("Could not decode mtb")
        if self.init_data["parameters"].get("ws-uri") and not device_map:
            try:
                url = f'{self.init_data["parameters"].get("ws-uri")}/{self.init_data["eventType"]}?snapping=false'
                device_map = TracTracWSReader().read_data(url)
            except Exception:
                raise CompetitorsImportError("Could not decode ws data")
        if not device_map:
            raise CompetitorsImportError("Did not figure out how to get data")

        competitors = []
        for c_data in self.init_data["competitors"].values():
            st = c_data.get("startTime")
            if not st:
                st = self.init_data["raceTrackingStartTime"]
            dev_id = c_data["uuid"]
            dev_obj = None
            dev_data = device_map.get(dev_id)
            competitor, _ = Competitor.objects.get_or_create(
                name=c_data["name"],
                short_name=c_data["nameShort"],
                event=event,
            )
            competitor.start_time = arrow.get(st).datetime
            if dev_data:
                dev_obj, created = Device.objects.get_or_create(
                    aid="TRC_" + safe64encodedsha(f"{dev_id}:{uid}")[:8],
                    defaults={
                        "is_gpx": True,
                    },
                )
                if not created:
                    dev_obj.locations_series = []
                dev_obj.add_locations(dev_data)
                dev_obj.save()
                competitor.device = dev_obj
            competitor.save()
            competitors.append(competitor)
        return competitors

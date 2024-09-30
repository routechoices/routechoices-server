import bisect
import json
import math
import re
import tempfile
import urllib.parse
from io import BytesIO
from operator import itemgetter

import arrow
from bs4 import BeautifulSoup
from curl_cffi import requests
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

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
    epoch_to_datetime,
    get_remote_image_sizes,
    initial_of_name,
    project,
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
            if competitor.device and competitor.device.location_count > 0:
                locations = competitor.device.locations_series
                from_date = locations[0][0]
                to_date = locations[-1][0]
                if not start_date or start_date > from_date:
                    start_date = from_date
                if not end_date or end_date < to_date:
                    end_date = to_date
        if start_date and end_date:
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


class Livelox(ThirdPartyTrackingSolution):
    slug = "livelox"
    name = "Livelox"
    HEADERS = {
        "content-type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }

    def parse_init_data(self, uid):
        details = dict(urllib.parse.parse_qsl(uid))

        class_ids = []
        class_id = details.get("classId")
        if class_id:
            class_ids = [int(class_id)]

        relay_legs = []
        relay_leg = details.get("relayLeg")
        if relay_leg:
            relay_legs = [int(relay_leg)]

        post_data = json.dumps(
            {
                "classIds": class_ids,
                "courseIds": [],
                "relayLegs": relay_legs,
                "relayLegGroupIds": [],
            }
        )
        r = requests.post(
            "https://www.livelox.com/Data/ClassInfo",
            data=post_data,
            headers=self.HEADERS,
        )
        if r.status_code != 200:
            raise EventImportError(f"Can not fetch class info data {r.status_code}")
        self.init_data = r.json().get("general", {})

        post_data = json.dumps(
            {
                "classIds": class_ids,
                "courseIds": [],
                "relayLegs": relay_legs,
                "relayLegGroupIds": [],
                "includeMap": True,
                "includeCourses": True,
            }
        )
        r = requests.post(
            "https://www.livelox.com/Data/ClassBlob",
            data=post_data,
            headers=self.HEADERS,
            timeout=60,
        )
        if r.status_code != 200:
            raise EventImportError("Can not fetch class blob data")
        self.init_data["xtra"] = r.json()
        self.init_data["relay_leg"] = int(relay_leg) if relay_leg else ""
        self.init_data["class_id"] = int(class_id)

    def get_or_create_event(self, uid):
        event_name = (
            f"{self.init_data['class']['event']['name']} - "
            f"{self.init_data['class']['name']}"
        )
        relay_leg = self.init_data["relay_leg"]
        if relay_leg:
            name = ""
            for leg in self.init_data["class"]["relayLegs"]:
                if leg.get("leg") == relay_leg:
                    name = leg["name"]
                    break
            else:
                name = f"#{relay_leg}"
            event_name += f" - {name}"

        event_start = arrow.get(
            self.init_data["class"]["event"]["timeInterval"]["start"]
        ).datetime
        event_end = arrow.get(
            self.init_data["class"]["event"]["timeInterval"]["end"]
        ).datetime
        slug = str(self.init_data["class_id"])
        if relay_leg:
            slug += f"-{relay_leg}"
        event, _ = Event.objects.get_or_create(
            club=self.club,
            slug=slug,
            defaults={
                "name": event_name,
                "start_date": event_start,
                "end_date": event_end,
                "privacy": PRIVACY_SECRET,
            },
        )
        return event

    def get_or_create_event_maps(self, event, uid):
        try:
            map_data = self.init_data["xtra"]["map"]
            map_bounds = map_data["boundingQuadrilateral"]["vertices"]
            map_url = map_data["url"]
            map_resolution = map_data["resolution"]
        except Exception:
            raise MapsImportError("Could not extract basic map info")
        courses = []
        # first determine the course for this leg if is relay
        relay_leg = self.init_data["relay_leg"]
        if relay_leg:
            course_ids = []
            groups = self.init_data["class"]["relayLegGroups"]
            for group in groups:
                if relay_leg in group["relayLegs"]:
                    course_ids += [c["id"] for c in group["courses"]]
            for course in self.init_data["xtra"]["courses"]:
                if course["id"] in course_ids:
                    courses.append(course)
        else:
            courses = self.init_data["xtra"]["courses"]

        r = requests.get(map_url)
        if r.status_code != 200:
            raise MapsImportError("Could not download image")

        map_obj, _ = Map.objects.get_or_create(
            name=event.name,
            club=self.club,
        )
        img_blob = ContentFile(r.content)
        map_obj.image.save("imported_image", img_blob)
        im = Image.open(img_blob)
        width, height = im.size
        map_obj.width = width
        map_obj.height = height
        map_obj.save()
        upscale = 4
        with Image.open(img_blob).convert("RGBA") as img:
            map_drawing = Image.new(
                "RGBA",
                (img.size[0] * upscale, img.size[1] * upscale),
                (255, 255, 255, 0),
            )
        coordinates = [f"{b['latitude']},{b['longitude']}" for b in map_bounds[::-1]]
        map_obj.corners_coordinates = ",".join(coordinates)

        draw = ImageDraw.Draw(map_drawing)
        circle_size = int(40 * map_resolution) * upscale
        line_width = int(8 * map_resolution) * upscale
        line_color = (128, 0, 128, 180)

        routes = [c["controls"] for c in courses]
        for route in routes:
            ctrls = [
                map_obj.wsg84_to_map_xy(
                    c["control"]["position"]["latitude"],
                    c["control"]["position"]["longitude"],
                )
                for c in route
            ]
            for i, ctrl in enumerate(ctrls[:-1]):
                if ctrl[0] == ctrls[i + 1][0]:
                    ctrl[0] -= 0.0001
                pt = ctrl
                next_pt = ctrls[i + 1]
                angle = math.atan2(next_pt[1] - pt[1], next_pt[0] - pt[0])
                if i == 0:
                    # draw start triangle
                    draw.line(
                        [
                            int(pt[0] * upscale + circle_size * math.cos(angle)),
                            int(pt[1] * upscale + circle_size * math.sin(angle)),
                            int(
                                pt[0] * upscale
                                + circle_size * math.cos(angle + 2 * math.pi / 3)
                            ),
                            int(
                                pt[1] * upscale
                                + circle_size * math.sin(angle + 2 * math.pi / 3)
                            ),
                            int(
                                pt[0] * upscale
                                + circle_size * math.cos(angle - 2 * math.pi / 3)
                            ),
                            int(
                                pt[1] * upscale
                                + circle_size * math.sin(angle - 2 * math.pi / 3)
                            ),
                            int(pt[0] * upscale + circle_size * math.cos(angle)),
                            int(pt[1] * upscale + circle_size * math.sin(angle)),
                        ],
                        fill=line_color,
                        width=line_width,
                        joint="curve",
                    )
                # draw line between controls
                draw.line(
                    [
                        int(pt[0] * upscale + circle_size * math.cos(angle)),
                        int(pt[1] * upscale + circle_size * math.sin(angle)),
                        int(next_pt[0] * upscale - circle_size * math.cos(angle)),
                        int(next_pt[1] * upscale - circle_size * math.sin(angle)),
                    ],
                    fill=line_color,
                    width=line_width,
                )
                # draw controls
                draw.ellipse(
                    [
                        int(next_pt[0] * upscale - circle_size),
                        int(next_pt[1] * upscale - circle_size),
                        int(next_pt[0] * upscale + circle_size),
                        int(next_pt[1] * upscale + circle_size),
                    ],
                    outline=line_color,
                    width=line_width,
                )
                # draw finish
                if i == (len(ctrls) - 2):
                    inner_circle_size = int(30 * map_resolution) * upscale
                    draw.ellipse(
                        [
                            int(next_pt[0] * upscale - inner_circle_size),
                            int(next_pt[1] * upscale - inner_circle_size),
                            int(next_pt[0] * upscale + inner_circle_size),
                            int(next_pt[1] * upscale + inner_circle_size),
                        ],
                        outline=line_color,
                        width=line_width,
                    )
        out_buffer = BytesIO()
        params = {
            "dpi": (72, 72),
        }
        map_drawing = map_drawing.resize(img.size, resample=Image.Resampling.BICUBIC)
        out = Image.alpha_composite(img, map_drawing)
        out.save(out_buffer, "PNG", **params)
        out_buffer.seek(0)
        f_new = ContentFile(out_buffer.read())
        map_obj.image.save("imported_image", f_new)
        map_obj.width = out.width
        map_obj.height = out.height
        map_obj.save()
        return [map_obj]

    def get_or_create_event_competitors(self, event, uid):
        participant_data = [
            d for d in self.init_data["xtra"]["participants"] if d.get("routeData")
        ]
        time_offset = 22089888e5
        map_projection = self.init_data["xtra"]["map"].get("projection")
        if map_projection:
            matrix = (
                map_projection["matrix"][0]
                + map_projection["matrix"][1]
                + map_projection["matrix"][2]
            )
        competitors = []
        for p in participant_data:
            c_name = f"{p.get('firstName')} {p.get('lastName')}"
            c_sname = initial_of_name(c_name)
            competitor, _ = Competitor.objects.get_or_create(
                name=c_name,
                short_name=c_sname,
                event=event,
            )
            pts = []
            if not p.get("routeData"):
                continue
            p_data64 = p["routeData"]
            d = LiveloxBase64Reader(p_data64)
            pts_raw = d.readWaypoints()
            for pt in pts_raw:
                if map_projection:
                    px, py = project(matrix, pt[1] / 10, pt[2] / 10)
                    latlon = event.map.map_xy_to_wsg84(px, py)
                    pts.append(
                        (int((pt[0] - time_offset) / 1e3), latlon["lat"], latlon["lon"])
                    )
                else:
                    pts.append(
                        (int((pt[0] - time_offset) / 1e3), pt[1] / 1e6, pt[2] / 1e6)
                    )
            dev_obj, created = Device.objects.get_or_create(
                aid="LLX_" + safe64encodedsha(f"{p['id']}:{uid}")[:8], is_gpx=True
            )
            if not created:
                dev_obj.location_series = []
            if pts:
                dev_obj.add_locations(pts)
                dev_obj.save()
                competitor.device = dev_obj
            competitor.save()
            competitors.append(competitor)
        return competitors


class SportRec(ThirdPartyTrackingSolution):
    slug = "sportrec"
    name = "SportRec"

    def parse_init_data(self, uid):
        r = requests.get(f"https://sportrec.eu/gps/{uid}")
        if r.status_code != 200:
            raise EventImportError("API returned error code")
        page = r.text
        if match := re.search(r"'competitioninfo/(?P<id>[^'?]+)", page):
            event_id = match.group("id")
        else:
            raise EventImportError("Cannot determine event id")
        r = requests.get(f"https://sportrec.eu/gps/competitioninfo/{event_id}")
        if r.status_code != 200:
            raise EventImportError("Cannot fetch event data")
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
        map_url = f"https://sportrec.eu/gps/map/{self.init_data['competition']['hashlink']}/{self.init_data['competition']['id']}.png"
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
            corners_latlon = self.init_data["competition"]["bounds"].values()
            corners_coords = []
            for corner in corners_latlon:
                corners_coords += corner
            calib_string = ",".join(str(round(x, 5)) for x in corners_coords)
            map_obj.image.save("imported_image", map_file, save=False)
            im = Image.open(map_file)
            width, height = im.size
            map_obj.width = width
            map_obj.height = height
            map_obj.image.update_dimension_fields(force=True)
            map_obj.corners_coordinates = calib_string
            map_obj.save()
        except Exception:
            map_obj.delete()
            raise MapsImportError("Error importing map")
        else:
            return [map_obj]

    def get_or_create_event_competitors(self, event, uid):
        data_url = f"https://sportrec.eu/gps/competitionhistory2/{self.init_data['competition']['hashlink']}?live=0"
        response = requests.get(data_url, stream=True)
        if response.status_code != 200:
            raise CompetitorsImportError(
                f"API returned error code {response.status_code}"
            )

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
            for dev_id in device_data.keys():
                locations = []
                for time in device_data[dev_id].keys():
                    pos = device_data[dev_id][time]["p"]
                    locations.append(
                        (int(float(time) / 1e3), float(pos[0]), float(pos[1]))
                    )
                device_map[dev_id] = locations
        except Exception:
            raise CompetitorsImportError("Unexpected data structure")
        competitors = []
        for c_data in self.init_data["participants"].values():
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
                    aid="SPR_"
                    + safe64encodedsha(
                        f"{dev_id}:{self.init_data['competition']['hashlink']}"
                    )[:8],
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
                competitor.start_time = arrow.get(start_time).datetime
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
            im = Image.open(map_file)
            width, height = im.size
            map_obj.width = width
            map_obj.height = height
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
        self.uid = uid
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

    def is_live(self):
        return self.init_data["LIVE"] == "1"

    def get_start_time(self):
        min_start_time = arrow.utcnow().shift(
            minutes=int(self.init_data.get("TIMEZONE", 0))
        )
        for c_id, c in self.get_competiors_data():
            if c.start_time:
                min_start_time = min(min_start_time, c.start_time)
        return min_start_time

    def get_end_time(self):
        if self.is_live():
            return arrow.utcnow().shift(hours=1).datetime
        return arrow.utcnow().datetime

    def get_event(self):
        event = Event()
        event.slug = self.uid
        event.club = self.club
        event.name = self.init_data.get("RACENAME", self.uid)[:255]
        event.start_date = self.get_start_time()
        event.end_date = self.get_end_time()
        event.send_interval = int(self.init_data.get("GRABINTERVAL", 10))
        return event

    def get_or_create_event(self, uid):
        tmp_event = self.get_event()
        event, _ = Event.objects.get_or_create(
            club=self.club,
            slug=tmp_event.slug,
            defaults={
                "name": tmp_event.name,
                "privacy": PRIVACY_SECRET,
                "start_date": tmp_event.start_date,
                "end_date": tmp_event.end_date,
            },
        )
        return event

    def get_map_url(self):
        return f"{self.GPSSEURANTA_EVENT_URL}{self.uid}/map"

    def get_map(self, download_map=False):
        map_url = self.get_map_url()
        try:
            length, size = get_remote_image_sizes(map_url)
        except Exception:
            return None

        calibration_string = self.init_data.get("CALIBRATION")
        if not size or not calibration_string:
            return None

        map_obj = Map()
        map_obj.width = size[0]
        map_obj.height = size[1]
        corners = three_point_calibration_to_corners(
            calibration_string, size[0], size[1]
        )
        coordinates = ",".join([str(round(x, 5)) for x in corners])
        map_obj.corners_coordinates = coordinates

        if download_map:
            r = requests.get(map_url)
            if r.status_code == 200:
                map_file = ContentFile(r.content)
                map_obj.image.save("map", map_file, save=False)
        return map_obj

    def get_or_create_event_maps(self, event, uid):
        tmp_map = self.get_map(download_map=True)
        if not tmp_map:
            raise MapsImportError("Error importing map")
        map_obj, _ = Map.objects.get_or_create(
            name=event.name,
            club=self.club,
            defaults={
                "image": tmp_map.image,
                "width": tmp_map.width,
                "height": tmp_map.height,
                "corners_coordinates": tmp_map.corners_coordinates,
            },
        )
        return [map_obj]

    def get_competitor_devices_data(self, uid, event):
        devices_data = {}
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
                if not devices_data.get(dev_id):
                    devices_data[dev_id] = new_locations
                else:
                    devices_data[dev_id] += new_locations

        cropped_devices_data = {}
        from_ts = event.start_date.timestamp()
        for dev_id, locations in devices_data.items():
            locations = sorted(locations, key=itemgetter(0))
            from_idx = bisect.bisect_left(locations, from_ts, key=itemgetter(0))
            locations = locations[from_idx:]

        return cropped_devices_data

    def get_competiors_data(self):
        competitors = {}
        for c_raw in self.init_data.get("COMPETITOR", []):
            c_data = c_raw.strip().split("|")
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
            competitors[c_data[0]] = Competitor(
                name=c_data[3],
                short_name=c_data[4],
                start_time=start_time,
            )

    def get_or_create_event_competitors(self, event, uid):
        devices_data = self.get_competitor_devices_data(uid, event)
        device_map = {}
        for dev_id, locations in devices_data.items():
            dev_obj, created = Device.objects.get_or_create(
                aid="SEU_" + safe64encodedsha(f"{dev_id}:{uid}")[:8],
                defaults={"is_gpx": True},
            )
            if not created:
                dev_obj.locations_series = []
            dev_obj.locations_series = locations
            device_map[dev_id] = dev_obj

        competitors = self.get_competiors_data()
        for cid, tmp_competitor in competitors.items():
            competitor, _ = Competitor.objects.get_or_create(
                name=tmp_competitor.name,
                short_name=tmp_competitor.short_name,
                event=event,
            )
            device = device_map.get(cid)
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
        loc = [
            int(o_pt[0]) + 1136073600,  # ts
            int(o_pt[2]) / 1e5,  # lat
            int(o_pt[1]) / 5e4,  # lon
        ]
        locs = [tuple(loc)]

        def get_char_index(c):
            ascii_index = ord(c)
            if ascii_index < 65:
                return ascii_index - 79
            if ascii_index < 97:
                return ascii_index - 86
            return ascii_index - 92

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
                dt = get_char_index(p[0])
                dlon = get_char_index(p[1])
                dlat = get_char_index(p[2])
            loc[0] += dt
            loc[1] += dlat / 1e5
            loc[2] += dlon / 5e4
            locs.append(tuple(loc))
        return locs


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
            im = Image.open(map_file)
            width, height = im.size
            map_obj.width = width
            map_obj.height = height
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
                map_obj.width = width
                map_obj.height = height
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


class LiveloxBase64Reader:
    base64util = {
        "usableBitsPerByte": 6,
        "headerBits": 8,
        "numberToLetter": (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        ),
        "pow2": [0] * 64,
        "bitLengthMaxValues": [0] * 65,
        "letterToNumber": {},
    }
    for i in range(64):
        base64util["pow2"][i] = 2**i
    for i in range(1, 65):
        base64util["bitLengthMaxValues"][i] = (
            base64util["bitLengthMaxValues"][i - 1] + base64util["pow2"][i - 1]
        )
    for i, letter in enumerate(base64util["numberToLetter"]):
        base64util["letterToNumber"][letter] = i
    base64util["letterToNumber"]["="] = 0

    def __init__(self, data):
        self.length = len(data)
        self.byte_array = [0] * self.length
        self.current_byte_pos = 0
        self.current_bit_pos = 0
        self.bits_read_in_current_byte = 0
        self.next_bit_position = None
        self.next_bits_read_in_current_byte = None
        self.byte = None
        self.value = None
        self.bits_left_to_read = None
        self.i = None
        self.bytes_read = None
        self.header = None

        for i in range(self.length):
            self.byte_array[i] = self.base64util["letterToNumber"][data[i]]

    def read_n_bits(self, n):
        self.value = 0
        self.bits_left_to_read = self.bits_read_in_current_byte + n
        self.bytes_read = 0
        while self.bits_left_to_read > 0:
            self.bits_left_to_read -= 6
            self.bytes_read += 1
        self.next_bit_position = self.current_bit_pos + n
        self.next_bits_read_in_current_byte = self.next_bit_position % 6
        self.i = 0
        while self.i < self.bytes_read:
            self.byte = self.byte_array[self.i + self.current_byte_pos]
            if self.i == 0:
                self.byte &= self.base64util["bitLengthMaxValues"][
                    6 - self.bits_read_in_current_byte
                ]
            if self.i < self.bytes_read - 1:
                self.value += (
                    self.base64util["pow2"][
                        (self.bytes_read - self.i - 1) * 6
                        - (
                            0
                            if self.next_bits_read_in_current_byte == 0
                            else (6 - self.next_bits_read_in_current_byte)
                        )
                    ]
                    * self.byte
                )
            else:
                if self.next_bits_read_in_current_byte > 0:
                    self.byte >>= 6 - self.next_bits_read_in_current_byte
                self.value += self.byte
            self.i += 1
        self.current_bit_pos = self.next_bit_position
        self.bits_read_in_current_byte = self.next_bits_read_in_current_byte
        self.current_byte_pos += (
            self.bytes_read
            if self.bits_read_in_current_byte == 0
            else (self.bytes_read - 1)
        )
        return self.value

    def read_value(self):
        self.header = self.read_n_bits(8)
        return (
            (-1 if (self.header & 2) else 1)
            * (1e3 if (self.header & 1) else 1)
            * self.read_n_bits(self.header >> 2)
        )

    def readWaypoints(self):
        k = self.read_value()
        pts = []
        t = 0
        lat = 0
        lng = 0
        for _ in range(k):
            t += self.read_value()
            lat += self.read_value()
            lng += self.read_value()
            pts.append((t, lat, lng))
        return pts

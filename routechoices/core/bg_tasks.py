import json
import math
import re
import tempfile
from io import BytesIO

import arrow
import requests
from background_task import background
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
)
from routechoices.lib.helpers import (
    compute_corners_from_kml_latlonbox,
    epoch_to_datetime,
    initial_of_name,
    project,
    short_random_key,
)
from routechoices.lib.third_party_downloader import (
    GpsSeurantaNet,
    Loggator,
    OTracker,
    Tractrac,
)


class EventImportError(Exception):
    pass


class MapImportError(Exception):
    pass


@background(schedule=0)
def import_single_event_from_gps_seuranta(event_id):
    event_id = event_id.strip()
    if match := re.match(
        r"https?://((gps|www)\.)?tulospalvelu\.fi/gps/(?P<uid>[^/]+)/?", event_id
    ):
        event_id = match.group("uid")
    solution = GpsSeurantaNet()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_loggator(event_id):
    event_id = event_id.strip()
    if match := re.match(
        r"https?://(events\.)?loggator\.com/(?P<uid>[^/]+)/?", event_id
    ):
        event_id = match.group("uid")
    solution = Loggator()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_tractrac(event_id):
    prefix = "https://live.tractrac.com/viewer/index.html?target="
    if event_id.startswith(prefix):
        event_id = event_id[len(prefix) :]
    solution = Tractrac()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_otracker(event_id):
    prefix = "https://otracker.lt/events/"
    if event_id.startswith(prefix):
        event_id = event_id[len(prefix) :]
    solution = OTracker()
    event = solution.import_event(event_id)
    return event


def get_livelox_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug="livelox", defaults={"name": "Livelox"}
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


def get_sportrec_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug="sportrec", defaults={"name": "SportRec"}
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


def import_map_from_sportrec(club, event_id, map_data, name):
    map_url = f"https://sportrec.eu/ui/nsport_admin/index.php?r=api/map&id={event_id}"
    r = requests.get(map_url)
    map_file = ContentFile(r.content)
    if r.status_code != 200:
        raise MapImportError("API returned error code")
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    coords = map_data["map_box"]
    n, e, s, w = [float(x) for x in coords.replace("(", "").replace(")", "").split(",")]

    nw, ne, se, sw = compute_corners_from_kml_latlonbox(
        n, e, s, w, -float(map_data["map_angle"])
    )
    corners_coords = f"{nw[0]},{nw[1]},{ne[0]},{ne[1]},{se[0]},{se[1]},{sw[0]},{sw[1]}"
    map_model.image.save("imported_image", map_file, save=False)
    map_model.corners_coordinates = corners_coords
    map_model.save()
    return map_model


@background(schedule=0)
def import_single_event_from_sportrec(event_id):
    club = get_sportrec_club()
    r = requests.get(
        f"https://sportrec.eu/ui/nsport_admin/index.php?r=api/competition&id={event_id}"
    )
    if r.status_code != 200:
        raise EventImportError("API returned error code")
    event_data = r.json()
    event_name = event_data["competition"]["title"]
    slug = event_id
    event, created = Event.objects.get_or_create(
        club=club,
        slug=slug,
        defaults={
            "name": event_name,
            "start_date": arrow.get(event_data["competition"]["time_start"]).datetime,
            "end_date": arrow.get(event_data["competition"]["time_finish"]).datetime,
            "privacy": PRIVACY_SECRET,
        },
    )
    if not created:
        return
    map_model = None
    if event_data["hasMap"]:
        map_model = import_map_from_sportrec(
            club, event_id, event_data["track"], event_name
        )
    if map_model:
        event.map = map_model
        event.save()
    data_url = (
        f"https://sportrec.eu/ui/nsport_admin/index.php?r=api/history&id={event_id}"
    )
    response = requests.get(data_url, stream=True)
    if response.status_code != 200:
        event.delete()
        raise EventImportError("API returned error code")
    with tempfile.TemporaryFile() as lf:
        for block in response.iter_content(1024 * 8):
            if not block:
                break
            lf.write(block)
        lf.flush()
        lf.seek(0)
        device_map = {}
        try:
            device_data = json.load(lf)
        except Exception:
            event.delete()
            raise EventImportError("Invalid JSON")
        try:
            for d in device_data["locations"]:
                device_map[d["device_id"]] = [
                    (int(float(x["aq"]) / 1e3), float(x["lat"]), float(x["lon"]))
                    for x in d["locations"]
                ]
        except Exception:
            event.delete()
            raise EventImportError("Unexpected data structure")

    for c_data in event_data["participants"]:
        st = c_data.get("time_start")
        if not st:
            st = event_data["competition"]["time_start"]
        dev = device_map.get(c_data["device_id"])
        dev_model = None
        if dev:
            dev_model = Device.objects.create(
                aid=short_random_key() + "_SPR",
                is_gpx=True,
            )
            dev_model.add_locations(dev)
        Competitor.objects.create(
            name=c_data["fullname"],
            short_name=c_data["shortname"],
            start_time=arrow.get(st).datetime,
            device=dev_model,
            event=event,
        )


def draw_livelox_route(name, club, url, bound, routes, res):
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    r = requests.get(url)
    if r.status_code != 200:
        if created:
            map_model.delete()
        raise MapImportError("API returned error code")
    img_blob = ContentFile(r.content)
    upscale = 4
    with Image.open(img_blob).convert("RGBA") as img:
        course = Image.new(
            "RGBA", (img.size[0] * upscale, img.size[1] * upscale), (255, 255, 255, 0)
        )
        coordinates = [f"{b['latitude']},{b['longitude']}" for b in bound[::-1]]
        map_model.corners_coordinates = ",".join(coordinates)
        map_model.image.save("imported_image", img_blob, save=False)
        draw = ImageDraw.Draw(course)
        circle_size = int(40 * res) * upscale
        line_width = int(8 * res) * upscale
        line_color = (128, 0, 128, 180)
        for route in routes:
            ctrls = [
                map_model.wsg84_to_map_xy(
                    c["control"]["position"]["latitude"],
                    c["control"]["position"]["longitude"],
                )
                for c in route
            ]
            for i in range(len(ctrls) - 1):
                if ctrls[i][0] == ctrls[i + 1][0]:
                    ctrls[i][0] -= 0.0001
                start_from_a = ctrls[i][0] < ctrls[i + 1][0]
                pt_a = ctrls[i] if start_from_a else ctrls[i + 1]
                pt_b = ctrls[i] if not start_from_a else ctrls[i + 1]
                angle = math.atan((pt_b[1] - pt_a[1]) / (pt_b[0] - pt_a[0]))
                if i == 0:
                    pt_s = pt_a if start_from_a else pt_b
                    draw.line(
                        [
                            int(
                                pt_s[0] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.cos(angle)
                            ),
                            int(
                                pt_s[1] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.sin(angle)
                            ),
                            int(
                                pt_s[0] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.cos(angle + 2 * math.pi / 3)
                            ),
                            int(
                                pt_s[1] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.sin(angle + 2 * math.pi / 3)
                            ),
                            int(
                                pt_s[0] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.cos(angle - 2 * math.pi / 3)
                            ),
                            int(
                                pt_s[1] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.sin(angle - 2 * math.pi / 3)
                            ),
                            int(
                                pt_s[0] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.cos(angle)
                            ),
                            int(
                                pt_s[1] * upscale
                                - (-1 if start_from_a else 1)
                                * circle_size
                                * math.sin(angle)
                            ),
                        ],
                        fill=line_color,
                        width=line_width,
                        joint="curve",
                    )
                draw.line(
                    [
                        int(pt_a[0] * upscale + circle_size * math.cos(angle)),
                        int(pt_a[1] * upscale + circle_size * math.sin(angle)),
                        int(pt_b[0] * upscale - circle_size * math.cos(angle)),
                        int(pt_b[1] * upscale - circle_size * math.sin(angle)),
                    ],
                    fill=line_color,
                    width=line_width,
                )
                pt_o = pt_b if start_from_a else pt_a
                draw.ellipse(
                    [
                        int(pt_o[0] * upscale - circle_size),
                        int(pt_o[1] * upscale - circle_size),
                        int(pt_o[0] * upscale + circle_size),
                        int(pt_o[1] * upscale + circle_size),
                    ],
                    outline=line_color,
                    width=line_width,
                )
                if i == (len(ctrls) - 2):
                    inner_circle_size = int(30 * res) * upscale
                    draw.ellipse(
                        [
                            int(pt_o[0] * upscale - inner_circle_size),
                            int(pt_o[1] * upscale - inner_circle_size),
                            int(pt_o[0] * upscale + inner_circle_size),
                            int(pt_o[1] * upscale + inner_circle_size),
                        ],
                        outline=line_color,
                        width=line_width,
                    )
        out_buffer = BytesIO()
        params = {
            "dpi": (72, 72),
        }
        course = course.resize(img.size, resample=Image.Resampling.BICUBIC)
        out = Image.alpha_composite(img, course)
        out.save(out_buffer, "PNG", **params)
        out_buffer.seek(0)
        f_new = ContentFile(out_buffer.read())
        map_model.image.save("imported_image", f_new)
    return map_model


@background(schedule=0)
def import_single_event_from_livelox(class_id, relay_legs=None):
    if relay_legs is None:
        relay_legs = []
    livelox_headers = {
        "content-type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }
    club = get_livelox_club()
    post_data = json.dumps(
        {
            "classIds": [int(class_id)],
            "courseIds": [],
            "relayLegs": relay_legs,
            "relayLegGroupIds": [],
        }
    )
    r_info = requests.post(
        "https://www.livelox.com/Data/ClassInfo",
        data=post_data,
        headers=livelox_headers,
    )

    if r_info.status_code != 200:
        raise EventImportError(f"Can not fetch class info data {r_info.status_code}")
    event_data = r_info.json().get("general", {})
    blob_url = event_data.get("classBlobUrl")
    if not blob_url or not blob_url.startswith("https://livelox.blob.core.windows.net"):
        raise EventImportError(f"Can not fetch data: bad url ({blob_url})")
    r = requests.get(blob_url, headers=livelox_headers)
    if r.status_code != 200:
        raise EventImportError("Can not fetch class blob data")
    data = r.json()
    map_model = None
    map_projection = None

    try:
        map_data = data["map"]
        map_name = f"{map_data['name']} - {data['courses'][0]['name']}"
        map_bound = map_data["boundingQuadrilateral"]["vertices"]
        map_projection = data["map"].get("projection")
    except Exception:
        raise MapImportError("Could not extract basic map info")
    try:
        map_url = f"https://www.livelox.com/Classes/MapImage?classIds={class_id}"
        map_model, created = Map.objects.get_or_create(
            name=map_name,
            club=club,
        )
        if created:
            r = requests.get(map_url, timeout=60)
            if r.status_code != 200:
                map_model.delete()
                raise MapImportError("API returned error code")
            img_blob = ContentFile(r.content)
            coordinates = [f"{b['latitude']},{b['longitude']}" for b in map_bound[::-1]]
            map_model.corners_coordinates = ",".join(coordinates)
            map_model.image.save("imported_image", img_blob)
    except Exception:
        try:
            map_url = map_data["url"]
            map_resolution = map_data["resolution"]
            route_ctrls = [c["controls"] for c in data["courses"]]
            map_model = draw_livelox_route(
                map_name, club, map_url, map_bound, route_ctrls, map_resolution
            )
        except Exception:
            raise MapImportError("Could not get map")

    participant_data = [d for d in data["participants"] if d.get("routeData")]
    time_offset = 22089888e5
    relay_name = "-".join(map(str, relay_legs))
    event_name = (
        f"{event_data['class']['event']['name']} - "
        f"{event_data['class']['name']}"
        f"{(' ' + relay_name) if relay_legs else ''}"
    )
    event_start = arrow.get(
        event_data["class"]["event"]["timeInterval"]["start"]
    ).datetime
    event_end = arrow.get(event_data["class"]["event"]["timeInterval"]["end"]).datetime

    event, created = Event.objects.get_or_create(
        club=club,
        slug=f"{class_id}{('-' + relay_name) if relay_legs else ''}",
        defaults={
            "name": event_name,
            "start_date": event_start,
            "end_date": event_end,
            "map": map_model,
            "privacy": PRIVACY_SECRET,
        },
    )

    # event.competitors.all().delete()
    if not created:
        return

    if map_projection:
        matrix = (
            map_projection["matrix"][0]
            + map_projection["matrix"][1]
            + map_projection["matrix"][2]
        )

    for p in participant_data:
        lat = 0
        lon = 0
        t = -time_offset
        pts = []
        if not p.get("routeData"):
            continue
        p_data = p["routeData"][1:]
        min_t = None
        for i in range((len(p_data) - 1) // 3):
            t += p_data[3 * i]
            lon += p_data[3 * i + 1]
            lat += p_data[3 * i + 2]
            min_t = t if not min_t else min(min_t, t)
            if map_projection:
                px, py = project(matrix, lon / 10, lat / 10)
                latlon = map_model.map_xy_to_wsg84(px, py)
                pts.append((int(t / 1e3), latlon["lat"], latlon["lon"]))
            else:
                pts.append((int(t / 1e3), lat / 1e6, lon / 1e6))
        dev = Device.objects.create(aid=short_random_key() + "_LLX", is_gpx=True)
        if pts:
            dev.add_locations(pts)
        c_name = f"{p.get('firstName')} {p.get('lastName')}"
        c_sname = initial_of_name(c_name)
        Competitor.objects.create(
            name=c_name,
            short_name=c_sname,
            start_time=epoch_to_datetime(min_t / 1e3),
            event=event,
            device=dev,
        )

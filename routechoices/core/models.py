import base64
import bisect
import hashlib
import logging
import math
import os.path
import re
import time
import uuid
from decimal import Decimal
from io import BytesIO
from operator import itemgetter
from zipfile import ZipFile

import cv2
import gps_encoding
import gpxpy
import gpxpy.gpx
import magic
import numpy as np
import orjson as json
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import LinearRing, Polygon
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.core.validators import MinValueValidator, validate_slug
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.timezone import now
from django_hosts.resolvers import reverse
from PIL import Image, ImageDraw

from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import (
    adjugate_matrix,
    delete_domain,
    distance_latlon,
    distance_xy,
    epoch_to_datetime,
    general_2d_projection,
    project,
    random_device_id,
    random_key,
    safe64encode,
    short_random_slug,
    time_base64,
)
from routechoices.lib.storages import OverwriteImageStorage
from routechoices.lib.validators import (
    domain_validator,
    validate_corners_coordinates,
    validate_domain_slug,
    validate_esn,
    validate_imei,
    validate_latitude,
    validate_longitude,
    validate_nice_slug,
)

logger = logging.getLogger(__name__)

GLOBAL_MERCATOR = GlobalMercator()
EVENT_CACHE_INTERVAL = 5

LOCATION_TIMESTAMP_INDEX = 0
LOCATION_LATITUDE_INDEX = 1
LOCATION_LONGITUDE_INDEX = 2


class Point:
    def __init__(self, x, y=None):
        if isinstance(x, tuple):
            self.x = x[0]
            self.y = x[1]
        elif isinstance(x, dict):
            self.x = x.get("x")
            self.y = x.get("y")
        else:
            self.x = x
            self.y = y

    def __repr__(self):
        return f"x: {self.x}, y:{self.y}"


def logo_upload_path(instance=None, file_name=None):
    import os.path

    tmp_path = ["logos"]
    time_hash = time_base64()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0])
    tmp_path.append(basename[1])
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


class Club(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
    )
    creator = models.ForeignKey(
        User,
        related_name="+",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255, unique=True)
    slug = models.CharField(
        max_length=50,
        validators=[
            validate_domain_slug,
        ],
        unique=True,
        help_text=".routechoices.com",
    )
    admins = models.ManyToManyField(User)
    description = models.TextField(
        blank=True,
        default="""# GPS tracking powered by routechoices.com

Browse our events here.""",
        help_text="This text will be displayed on your site frontpage, use markdown formatting",
    )
    domain = models.CharField(
        max_length=128,
        blank=True,
        default="",
        validators=[
            domain_validator,
        ],
    )
    acme_challenge = models.CharField(max_length=128, blank=True)
    website = models.URLField(max_length=200, blank=True)
    logo = models.ImageField(
        upload_to=logo_upload_path,
        null=True,
        blank=True,
        help_text="Square image of width greater or equal to 128px",
        storage=OverwriteImageStorage(aws_s3_bucket_name="routechoices-maps"),
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "club"
        verbose_name_plural = "clubs"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return self.nice_url

    @property
    def use_https(self):
        is_secure = True
        if self.domain:
            cert_path = os.path.join(
                settings.BASE_DIR, "nginx", "certs", f"{self.domain}.crt"
            )
            is_secure = os.path.exists(cert_path)
        return is_secure

    @property
    def url_protocol(self):
        return f"http{'s' if self.use_https else ''}"

    @property
    def nice_url(self):
        if self.domain:
            return f"{self.url_protocol}://{self.domain}/"
        path = reverse(
            "club_view", host="clubs", host_kwargs={"club_slug": self.slug.lower()}
        )
        return f"{self.url_protocol}:{path}"

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = Club.objects.filter(slug__iexact=self.slug)
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            raise ValidationError("Club with this slug already exists.")

    def save(self, *args, **kwargs):
        if self.pk:
            if self.domain:
                self.domain = self.domain.lower()
            old_domain = Club.objects.get(pk=self.pk).domain
            if old_domain and old_domain != self.domain:
                delete_domain(old_domain)
        self.slug = self.slug.lower()
        return super().save(*args, **kwargs)


@receiver(pre_delete, sender=Club, dispatch_uid="club_delete_signal")
def delete_club_receiver(sender, instance, using, **kwargs):
    if instance.domain:
        delete_domain(instance.domain)


def map_upload_path(instance=None, file_name=None):
    import os.path

    tmp_path = ["maps"]
    time_hash = time_base64()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0])
    tmp_path.append(basename[1])
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


class Map(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(Club, related_name="maps", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    image = models.ImageField(
        upload_to=map_upload_path,
        max_length=255,
        height_field="height",
        width_field="width",
        storage=OverwriteImageStorage(aws_s3_bucket_name="routechoices-maps"),
    )
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    corners_coordinates = models.CharField(
        max_length=255,
        help_text="Latitude and longitude of map corners separated by commas "
        "in following order Top Left, Top right, Bottom Right, Bottom left. "
        "eg: 60.519,22.078,60.518,22.115,60.491,22.112,60.492,22.073",
        validators=[validate_corners_coordinates],
    )

    class Meta:
        ordering = ["-creation_date"]
        verbose_name = "map"
        verbose_name_plural = "maps"

    def __str__(self):
        return f"{self.name} ({self.club})"

    @property
    def path(self):
        return self.image.name

    @property
    def data(self):
        with self.image.open("rb") as fp:
            data = fp.read()
        return data

    @property
    def corners_coordinates_short(self):
        coords = ",".join(
            [str(round(Decimal(x), 5)) for x in self.corners_coordinates.split(",")]
        )
        return coords

    @property
    def kmz(self):
        doc_img = self.data
        mime_type = magic.from_buffer(doc_img, mime=True)
        ext = mime_type[6:]
        doc_kml = f"""<?xml version="1.0" encoding="utf-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"
     xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <Folder>
      <name>{self.name}</name>
      <GroundOverlay>
        <name>{self.name}</name>
        <drawOrder>50</drawOrder>
        <Icon>
          <href>files/doc.{ext}</href>
        </Icon>
        <altitudeMode>clampToGround</altitudeMode>
        <gx:LatLonQuad>
          <coordinates>
            {self.bound["bottomLeft"]["lon"]},{self.bound["bottomLeft"]["lat"]} {self.bound["bottomRight"]["lon"]},{self.bound["bottomRight"]["lat"]} {self.bound["topRight"]["lon"]},{self.bound["topRight"]["lat"]} {self.bound["topLeft"]["lon"]},{self.bound["topLeft"]["lat"]}
          </coordinates>
        </gx:LatLonQuad>
      </GroundOverlay>
    </Folder>
  </Document>
</kml>"""
        kmz = BytesIO()
        with ZipFile(kmz, "w") as fp:
            with fp.open("doc.kml", "w") as file1:
                file1.write(doc_kml.encode("utf-8"))
            with fp.open(f"files/doc.{ext}", "w") as file2:
                file2.write(doc_img)
        return kmz.getbuffer()

    @property
    def mime_type(self):
        with self.image.storage.open(self.image.name, mode="rb", nbytes=2048) as fp:
            data = fp.read()
            return magic.from_buffer(data, mime=True)

    @property
    def data_uri(self):
        data = self.data
        mime_type = magic.from_buffer(data, mime=True)
        return f"data:{mime_type};base64,{base64.b64encode(data).decode()}"

    @data_uri.setter
    def data_uri(self, value):
        if not value:
            raise ValueError("Value can not be null")
        data_matched = re.match(
            r"^data:image/(?P<format>jpeg|png|gif);base64,"
            r"(?P<data_b64>(?:[A-Za-z0-9+/]{4})*"
            r"(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)$",
            value,
        )
        if data_matched:
            self.image.save(
                "filename",
                ContentFile(base64.b64decode(data_matched.group("data_b64"))),
                save=False,
            )
            self.image.close()
        else:
            raise ValueError("Not a base 64 encoded data URI of an image")

    @property
    def thumbnail(self):
        orig = self.image.open("rb").read()
        img = Image.open(BytesIO(orig))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = img.transform(
            (1200, 630),
            Image.QUAD,
            (
                int(self.width) / 2 - 300,
                int(self.height) / 2 - 158,
                int(self.width) / 2 - 300,
                int(self.height) / 2 + 157,
                int(self.width) / 2 + 300,
                int(self.height) / 2 + 157,
                int(self.width) / 2 + 300,
                int(self.height) / 2 - 158,
            ),
        )
        return img

    @property
    def size(self):
        return {"width": self.width, "height": self.height}

    @property
    def alignment_points(self):
        r1_a = Point(0, 0)
        r1_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["topLeft"]))
        r2_a = Point(0, self.height)
        r2_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["bottomLeft"]))
        r3_a = Point(self.width, 0)
        r3_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["topRight"]))
        r4_a = Point(self.width, self.height)
        r4_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["bottomRight"]))
        return r1_a, r1_b, r2_a, r2_b, r3_a, r3_b, r4_a, r4_b

    @property
    def matrix_3d(self):
        r1_a, r1_b, r2_a, r2_b, r3_a, r3_b, r4_a, r4_b = self.alignment_points
        m = general_2d_projection(
            r1_a.x,
            r1_a.y,
            r1_b.x,
            r1_b.y,
            r2_a.x,
            r2_a.y,
            r2_b.x,
            r2_b.y,
            r3_a.x,
            r3_a.y,
            r3_b.x,
            r3_b.y,
            r4_a.x,
            r4_a.y,
            r4_b.x,
            r4_b.y,
        )
        if not m[8]:
            return
        for i in range(9):
            m[i] = m[i] / m[8]
        return m

    @property
    def matrix_3d_inverse(self):
        return adjugate_matrix(self.matrix_3d)

    @property
    def map_xy_to_spherical_mercator(self):
        if not self.matrix_3d:
            return lambda x, y: (0, 0)
        return lambda x, y: project(self.matrix_3d, x, y)

    @property
    def spherical_mercator_to_map_xy(self):
        return lambda x, y: project(self.matrix_3d_inverse, x, y)

    def wsg84_to_map_xy(self, lat, lon):
        xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": lat, "lon": lon})
        return self.spherical_mercator_to_map_xy(xy["x"], xy["y"])

    def map_xy_to_wsg84(self, x, y):
        mx, my = self.map_xy_to_spherical_mercator(x, y)
        return GLOBAL_MERCATOR.meters_to_latlon({"x": mx, "y": my})

    @property
    def resolution(self):
        """Return map image resolution in pixels/meters"""
        ll_a = self.map_xy_to_wsg84(0, 0)
        ll_b = self.map_xy_to_wsg84(self.width, self.height)
        return distance_xy(0, 0, self.width, self.height) / distance_latlon(ll_a, ll_b)

    @property
    def max_zoom(self):
        r = self.resolution / 1.193
        return math.ceil(math.log2(r)) + 18

    def create_tile(
        self, output_width, output_height, min_lat, max_lat, min_lon, max_lon, format
    ):
        cache_key = f"tiles_{self.aid}_{self.hash}_{output_width}_{output_height}_{min_lon}_{max_lon}_{min_lat}_{max_lat}_{format}"

        use_cache = getattr(settings, "CACHE_TILES", False)
        cached = None
        if use_cache:
            try:
                cached = cache.get(cache_key)
            except Exception:
                pass
        if use_cache and cached:
            return cached

        if not self.intersects_with_tile(min_lon, max_lon, max_lat, min_lat):
            n_channels = 4
            transparent_img = np.zeros(
                (output_height, output_width, n_channels), dtype=np.uint8
            )
            extra_args = []
            if format == "image/webp":
                extra_args = [int(cv2.IMWRITE_WEBP_QUALITY), 20]
            _, buffer = cv2.imencode(
                ".png" if format == "image/png" else ".webp",
                transparent_img,
                extra_args,
            )
            data_out = BytesIO(buffer).getvalue()
            return data_out

        r_w = (max_lon - min_lon) / output_width
        r_h = (max_lat - min_lat) / output_height

        tl = self.map_xy_to_spherical_mercator(0, 0)
        tr = self.map_xy_to_spherical_mercator(self.width, 0)
        br = self.map_xy_to_spherical_mercator(self.width, self.height)
        bl = self.map_xy_to_spherical_mercator(0, self.height)

        p1 = np.float32(
            [
                [0, 0],
                [self.width, 0],
                [self.width, self.height],
                [0, self.height],
            ]
        )
        p2 = np.float32(
            [
                [(tl[0] - min_lon) / r_w, (max_lat - tl[1]) / r_h],
                [(tr[0] - min_lon) / r_w, (max_lat - tr[1]) / r_h],
                [(br[0] - min_lon) / r_w, (max_lat - br[1]) / r_h],
                [(bl[0] - min_lon) / r_w, (max_lat - bl[1]) / r_h],
            ]
        )
        coeffs = cv2.getPerspectiveTransform(p1, p2)

        orig = self.image.open("rb").read()
        self.image.close()
        img = Image.open(BytesIO(orig)).convert("RGBA")
        img_alpha = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGRA)

        tile_img = cv2.warpPerspective(
            img_alpha,
            coeffs,
            (output_width, output_height),
            flags=cv2.INTER_AREA,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255, 0),
        )
        extra_args = []
        if format == "image/webp":
            extra_args = [int(cv2.IMWRITE_WEBP_QUALITY), 100]
        _, buffer = cv2.imencode(
            ".png" if format == "image/png" else ".webp", tile_img, extra_args
        )
        data_out = BytesIO(buffer).getvalue()
        if use_cache:
            try:
                cache.set(cache_key, data_out, 3600 * 24 * 30)
            except Exception:
                pass
        return data_out

    def intersects_with_tile(self, min_lon, max_lon, min_lat, max_lat):
        tile_bounds_poly = Polygon(
            LinearRing(
                (min_lon, min_lat),
                (min_lon, max_lat),
                (max_lon, max_lat),
                (max_lon, min_lat),
                (min_lon, min_lat),
            )
        )
        map_bounds_poly = Polygon(
            LinearRing(
                self.map_xy_to_spherical_mercator(0, 0),
                self.map_xy_to_spherical_mercator(0, self.height),
                self.map_xy_to_spherical_mercator(self.width, self.height),
                self.map_xy_to_spherical_mercator(self.width, 0),
                self.map_xy_to_spherical_mercator(0, 0),
            )
        )
        tile_bounds_poly_prep = tile_bounds_poly.prepared
        return tile_bounds_poly_prep.intersects(map_bounds_poly)

    def strip_exif(self):
        if self.image.closed:
            self.image.open()
        with Image.open(self.image.file) as image:
            rgba_img = image.convert("RGBA")
            MAX = 3000
            if image.size[0] > MAX and image.size[1] > MAX:
                scale = MAX / min(image.size[0], image.size[1])
                new_w = image.size[0] * scale
                new_h = image.size[1] * scale
                rgba_img.thumbnail((new_w, new_h), Image.ANTIALIAS)
            out_buffer = BytesIO()
            rgb_img = Image.new("RGB", rgba_img.size, (255, 255, 255))
            rgb_img.paste(rgba_img, mask=rgba_img.split()[3])
            params = {
                "dpi": (72, 72),
                "quality": 60,
            }
            rgb_img.save(out_buffer, "JPEG", **params)
            f_new = File(out_buffer, name=self.image.name)
            self.image.save(
                "filename",
                f_new,
                save=False,
            )
        self.image.close()

    @property
    def hash(self):
        h = hashlib.sha256()
        h.update(self.path.encode("utf-8"))
        h.update(self.corners_coordinates.encode("utf-8"))
        return safe64encode(h.digest())

    @property
    def bound(self):
        coords = [float(x) for x in self.corners_coordinates.split(",")]
        return {
            "topLeft": {"lat": coords[0], "lon": coords[1]},
            "topRight": {"lat": coords[2], "lon": coords[3]},
            "bottomRight": {"lat": coords[4], "lon": coords[5]},
            "bottomLeft": {"lat": coords[6], "lon": coords[7]},
        }

    @classmethod
    def from_points(cls, seg):
        new_map = cls()

        min_lat = 90
        max_lat = -90
        min_lon = 180
        max_lon = -180
        for pts in seg:
            lats_lons = list(zip(*pts))
            lats = lats_lons[0]
            lons = lats_lons[1]
            min_lat = min(min_lat, min(lats))
            max_lat = max(max_lat, max(lats))
            min_lon = min(min_lon, min(lons))
            max_lon = max(max_lon, max(lons))

        tl_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": max_lat, "lon": min_lon})
        tr_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": max_lat, "lon": max_lon})
        br_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": min_lat, "lon": max_lon})
        bl_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": min_lat, "lon": min_lon})

        MAX = 2000
        offset = 30
        width = tr_xy["x"] - tl_xy["x"] + offset * 2
        height = tr_xy["y"] - br_xy["y"] + offset * 2

        scale = 1
        if width > MAX or height > MAX:
            scale = max(width, height) / MAX

        tl_latlon = GLOBAL_MERCATOR.meters_to_latlon(
            {"x": tl_xy["x"] - offset * scale, "y": tl_xy["y"] + offset * scale}
        )
        tr_latlon = GLOBAL_MERCATOR.meters_to_latlon(
            {"x": tr_xy["x"] + offset * scale, "y": tr_xy["y"] + offset * scale}
        )
        br_latlon = GLOBAL_MERCATOR.meters_to_latlon(
            {"x": br_xy["x"] + offset * scale, "y": br_xy["y"] - offset * scale}
        )
        bl_latlon = GLOBAL_MERCATOR.meters_to_latlon(
            {"x": bl_xy["x"] - offset * scale, "y": bl_xy["y"] - offset * scale}
        )

        new_map.corners_coordinates = f"{tl_latlon['lat']},{tl_latlon['lon']},{tr_latlon['lat']},{tr_latlon['lon']},{br_latlon['lat']},{br_latlon['lon']},{bl_latlon['lat']},{bl_latlon['lon']}"
        im = Image.new(
            "RGBA", (int(width / scale), int(height / scale)), (255, 255, 255, 0)
        )
        new_map.width = int(width / scale)
        new_map.height = int(height / scale)
        draw = ImageDraw.Draw(im)
        for pts in seg:
            map_pts = [new_map.wsg84_to_map_xy(pt[0], pt[1]) for pt in pts]
            draw.line(map_pts, (255, 0, 0, 200), 15, joint="curve")
            draw.line(map_pts, (255, 255, 255, 200), 10, joint="curve")

        out_buffer = BytesIO()
        im.save(out_buffer, "PNG", dpi=(300, 300))
        f_new = File(out_buffer)
        new_map.image.save(
            "filename",
            f_new,
            save=False,
        )
        return new_map


PRIVACY_PUBLIC = "public"
PRIVACY_SECRET = "secret"
PRIVACY_PRIVATE = "private"
PRIVACY_CHOICES = (
    (PRIVACY_PUBLIC, "Public"),
    (PRIVACY_SECRET, "Secret"),
    (PRIVACY_PRIVATE, "Private"),
)

MAP_BLANK = "blank"
MAP_OSM = "osm"
MAP_GOOGLE_STREET = "gmap-street"
MAP_GOOGLE_SAT = "gmap-hybrid"
MAP_MAPANT_FI = "mapant-fi"
MAP_MAPANT_NO = "mapant-no"
MAP_MAPANT_ES = "mapant-es"
MAP_TOPO_FI = "topo-fi"
MAP_TOPO_NO = "topo-no"
MAP_TOPO_WRLD = "topo-world"

MAP_CHOICES = (
    (MAP_BLANK, "Blank"),
    (MAP_OSM, "Open Street Map"),
    (MAP_GOOGLE_STREET, "Google Map Street"),
    (MAP_GOOGLE_SAT, "Google Map Satellite"),
    (MAP_MAPANT_FI, "Mapant Finland"),
    (MAP_MAPANT_NO, "Mapant Norway"),
    (MAP_MAPANT_ES, "Mapant Spain"),
    (MAP_TOPO_FI, "Topo Finland"),
    (MAP_TOPO_NO, "Topo Norway"),
    (MAP_TOPO_WRLD, "Topo World"),
)


class Event(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
        Club, verbose_name="Club", related_name="events", on_delete=models.CASCADE
    )
    name = models.CharField(verbose_name="Name", max_length=255)
    slug = models.CharField(
        verbose_name="Slug",
        max_length=50,
        validators=[
            validate_nice_slug,
        ],
        db_index=True,
        help_text="This is used to build the url of this event",
        default=short_random_slug,
    )
    start_date = models.DateTimeField(verbose_name="Start Date (UTC)")
    end_date = models.DateTimeField(
        verbose_name="End Date (UTC)",
    )
    privacy = models.CharField(
        max_length=8,
        choices=PRIVACY_CHOICES,
        default=PRIVACY_PUBLIC,
    )
    backdrop_map = models.CharField(
        max_length=16,
        choices=MAP_CHOICES,
        default=MAP_BLANK,
    )
    map = models.ForeignKey(
        Map,
        related_name="+",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    map_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Leave blank if you are not using extra maps",
    )
    extra_maps = models.ManyToManyField(
        Map,
        through="MapAssignation",
        related_name="+",
        through_fields=("event", "map"),
    )
    open_registration = models.BooleanField(
        default=False,
        help_text="Participants can register themselves to the event.",
    )
    allow_route_upload = models.BooleanField(
        default=False,
        help_text="Participants can upload their routes after the event.",
    )
    allow_live_chat = models.BooleanField(
        default=False,
        help_text="Spectator will have a chat enabled during the live.",
    )
    send_interval = models.PositiveIntegerField(
        "Send interval (seconds)",
        default=5,
        help_text="If you use dedicated trackers, enter here the sending interval you set your devices to, if you use the official smartphone app leave the value at 5 seconds",
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["-start_date", "name"]
        unique_together = (("club", "slug"), ("club", "name"))
        verbose_name = "event"
        verbose_name_plural = "events"

    def save(self, *args, **kwargs):
        self.invalidate_cache()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{self.club.nice_url}{self.slug}"

    def get_absolute_map_url(self):
        return f"{self.club.nice_url}{self.slug}/map/"

    def get_absolute_export_url(self):
        return f"{self.club.nice_url}{self.slug}/export"

    @property
    def shortcut(self):
        shortcut_url = getattr(settings, "SHORTCUT_BASE_URL", None)
        if shortcut_url:
            return f"{shortcut_url}{self.aid}"
        return None

    @property
    def hidden(self):
        return self.start_date > now()

    @property
    def started(self):
        return self.start_date <= now()

    @property
    def is_live(self):
        return self.start_date <= now() <= self.end_date

    @property
    def ended(self):
        return self.end_date < now()

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = Event.objects.filter(
            club__slug__iexact=self.club.slug, slug__iexact=self.slug
        )
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            raise ValidationError("Event with this Club and Slug already exists.")

    def invalidate_cache(self):
        t0 = time.time()
        cache_interval = EVENT_CACHE_INTERVAL
        cache_ts = int(t0 // (cache_interval if self.is_live else 7 * 24 * 3600))
        cache_prefix = "live" if self.is_live else "archived"
        cache_key = f"{cache_prefix}_event_data:{self.aid}:{cache_ts}"
        cache.delete(cache_key)

    @property
    def has_notice(self):
        return hasattr(self, "notice")


class Notice(models.Model):
    modification_date = models.DateTimeField(auto_now=True)
    event = models.OneToOneField(Event, related_name="notice", on_delete=models.CASCADE)
    text = models.CharField(
        max_length=280,
        blank=True,
        help_text="Optional text that will be displayed on the event page",
    )

    def __str__(self):
        return self.text


class MapAssignation(models.Model):
    event = models.ForeignKey(
        Event, related_name="map_assignations", on_delete=models.CASCADE
    )
    map = models.ForeignKey(
        Map, related_name="map_assignations", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)

    class Meta:
        unique_together = (("map", "event"), ("event", "title"))
        ordering = ["id"]


class Device(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    aid = models.CharField(
        default=random_device_id,
        max_length=12,
        unique=True,
        validators=[
            validate_slug,
        ],
    )
    user_agent = models.CharField(max_length=200, blank=True)
    is_gpx = models.BooleanField(default=False)
    owners = models.ManyToManyField(
        User,
        through="DeviceOwnership",
        related_name="devices",
        through_fields=("device", "user"),
    )
    locations_raw = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["aid"]
        verbose_name = "device"
        verbose_name_plural = "devices"

    def __str__(self):
        return self.aid

    @property
    def locations(self):
        if not self.locations_raw:
            return {"timestamps": [], "latitudes": [], "longitudes": []}
        return json.loads(self.locations_raw)

    @locations.setter
    def locations(self, locs):
        self.locations_raw = str(json.dumps(locs), "utf-8")

    def get_locations_between_dates(self, from_date, end_date, encoded=False):
        qs = self.locations
        from_ts = from_date.timestamp()
        end_ts = end_date.timestamp()
        locs = zip(qs["timestamps"], qs["latitudes"], qs["longitudes"])
        locs = list(sorted(locs, key=itemgetter(0)))
        from_idx = bisect.bisect_left(locs, from_ts, key=itemgetter(0))
        end_idx = bisect.bisect_right(locs, end_ts, key=itemgetter(0))
        locs = locs[from_idx:end_idx]
        if not encoded:
            return len(locs), locs
        result = gps_encoding.encode_data(locs)
        return len(locs), result

    def add_locations(self, loc_array, save=True, push_forward=True):
        new_ts = []
        new_lat = []
        new_lon = []
        locs = self.locations
        all_ts = set(locs["timestamps"])
        for loc in loc_array:
            ts = int(loc[LOCATION_TIMESTAMP_INDEX])
            lat = loc[LOCATION_LATITUDE_INDEX]
            lon = loc[LOCATION_LONGITUDE_INDEX]
            if ts in all_ts:
                continue
            try:
                validate_latitude(lat)
                validate_longitude(lon)
            except Exception:
                continue
            if isinstance(lat, Decimal):
                lat = float(lat)
            if isinstance(lon, Decimal):
                lon = float(lon)
            all_ts.add(ts)
            new_ts.append(ts)
            new_lat.append(round(lat, 5))
            new_lon.append(round(lon, 5))
        locs["timestamps"] += new_ts
        locs["latitudes"] += new_lat
        locs["longitudes"] += new_lon
        self.locations = locs
        if save:
            self.save()
        new_locs = list(zip(new_ts, new_lat, new_lon))
        new_locs = list(sorted(new_locs, key=itemgetter(0)))
        new_data = gps_encoding.encode_data(new_locs)
        if push_forward:
            try:
                competitor = self.get_competitor(load_event=True)
                if competitor:
                    event = competitor.event.aid
                    if event.is_live:
                        event_id = event.aid
                        requests.post(
                            f"http://127.0.0.1:8010/{event_id}",
                            data=json.dumps(
                                {"competitor": competitor.aid, "data": new_data}
                            ),
                            headers={
                                "Authorization": f"Bearer {settings.LIVESTREAM_INTERNAL_SECRET}"
                            },
                        )
            except Exception:
                pass
        return new_data

    def add_location(self, timestamp, lat, lon, save=True, push_forward=True):
        self.add_locations(
            [
                (timestamp, lat, lon),
            ],
            save,
            push_forward,
        )

    @property
    def location_count(self):
        try:
            return len(self.locations["timestamps"])
        except Exception:
            return 0

    def remove_duplicates(self, save=True):
        if self.location_count == 0:
            return
        qs = self.locations
        d = zip(qs["timestamps"], qs["latitudes"], qs["longitudes"])
        sorted_locs = sorted(d, key=itemgetter(0))
        loc_list = []
        prev_t = None
        for loc in sorted_locs:
            t = int(loc[0])
            if t != prev_t:
                prev_t = t
                loc_list.append([t, round(loc[1], 5), round(loc[2], 5)])
        if len(loc_list) == 0:
            tims, lats, lons = [], [], []
        else:
            tims, lats, lons = zip(*loc_list)
        new_locs = {"timestamps": tims, "latitudes": lats, "longitudes": lons}
        new_raw = str(json.dumps(new_locs), "utf-8")
        if self.locations_raw != new_raw:
            self.locations_raw = new_raw
            if save:
                self.save()

    @cached_property
    def last_location(self):
        if self.location_count == 0:
            return None
        qs = self.locations
        locs = zip(qs["timestamps"], qs["latitudes"], qs["longitudes"])
        locs = list(sorted(locs, key=itemgetter(0)))
        return locs[-1]

    @property
    def last_date_viewed(self):
        loc = self.last_location
        if not loc:
            return None
        t = loc[LOCATION_TIMESTAMP_INDEX]
        return epoch_to_datetime(t)

    @cached_property
    def last_position(self):
        loc = self.last_location
        if not loc:
            return None
        return loc[LOCATION_LATITUDE_INDEX], loc[LOCATION_LONGITUDE_INDEX]

    def get_competitor(self, at=None, load_event=False):
        if not at:
            at = now()
        qs = (
            self.competitor_set.all()
            .filter(start_time__lte=at, event__end_date__gte=at)
            .order_by("-start_time")
        )
        if load_event:
            qs = qs.select_related("event")
        return qs.first()

    def get_event(self, at=None):
        if not at:
            at = now()
        c = self.get_competitor(at, True)
        if c:
            return c.event
        return None

    def get_last_competitor(self, load_event=False):
        qs = self.competitor_set.all().order_by("-start_time")
        if load_event:
            qs = qs.select_related("event")
        return qs.first()

    def get_last_event(self):
        c = self.get_last_competitor(True)
        if c:
            return c.event
        return None


class ImeiDevice(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    imei = models.CharField(
        max_length=32,
        unique=True,
        validators=[
            validate_imei,
        ],
    )
    device = models.OneToOneField(
        Device, related_name="physical_device", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["imei"]
        verbose_name = "imei device"
        verbose_name_plural = "imei devices"

    def __str__(self):
        return self.imei


class DeviceOwnership(models.Model):
    device = models.ForeignKey(
        Device, related_name="ownerships", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, related_name="ownerships", on_delete=models.CASCADE)
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("device", "user"),)


class Competitor(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
    )
    event = models.ForeignKey(
        Event,
        related_name="competitors",
        on_delete=models.CASCADE,
    )
    device = models.ForeignKey(
        Device,
        related_name="competitor_set",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=64)
    short_name = models.CharField(max_length=32)
    start_time = models.DateTimeField(
        verbose_name="Start time (UTC)", null=True, blank=True
    )

    class Meta:
        ordering = ["start_time", "name"]
        verbose_name = "competitor"
        verbose_name_plural = "competitors"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.start_time:
            self.start_time = self.event.start_date
        super().save(*args, **kwargs)

    @property
    def started(self):
        return self.start_time > now()

    @cached_property
    def locations(self):
        if not self.device:
            return []

        from_date = self.event.start_date
        if self.start_time:
            from_date = self.start_time

        next_competitor_start_time = (
            self.device.competitor_set.filter(start_time__gt=from_date)
            .order_by("start_time")
            .values_list("start_time", flat=True)
            .first()
        )

        to_date = min(now(), self.event.end_date)
        if next_competitor_start_time:
            to_date = min(next_competitor_start_time, to_date)
        _, locs = self.device.get_locations_between_dates(from_date, to_date)
        return locs

    @property
    def encoded_data(self):
        result = gps_encoding.encode_data(self.locations)
        return result

    @property
    def gpx(self):
        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)

        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        locs = self.locations
        for location in locs:
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(
                    location[LOCATION_LATITUDE_INDEX],
                    location[LOCATION_LONGITUDE_INDEX],
                    time=epoch_to_datetime(location[LOCATION_TIMESTAMP_INDEX]),
                )
            )
        gpx_track.segments.append(gpx_segment)
        return gpx.to_xml()

    def get_absolute_gpx_url(self):
        return reverse(
            "competitor_gpx_download",
            host="api",
            kwargs={
                "competitor_id": self.aid,
            },
        )


@receiver([post_save, post_delete], sender=Competitor)
def save_profile(sender, instance, **kwargs):
    instance.event.invalidate_cache()


class SpotFeed(models.Model):
    feed_id = models.CharField(
        max_length=64,
        unique=True,
    )


class SpotDevice(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    messenger_id = models.CharField(
        max_length=32,
        unique=True,
        validators=[
            validate_esn,
        ],
    )
    device = models.OneToOneField(
        Device, related_name="spot_device", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["messenger_id"]
        verbose_name = "spot device"
        verbose_name_plural = "spot devices"

    def __str__(self):
        return self.messenger_id


class ChatMessage(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ip_address = models.GenericIPAddressField()
    event = models.ForeignKey(
        Event, related_name="chat_messages", on_delete=models.CASCADE
    )
    nickname = models.CharField(max_length=20)
    message = models.CharField(max_length=100)

    class Meta:
        ordering = ["-creation_date"]
        verbose_name = "chat message"
        verbose_name_plural = "chat messages"

    def __str__(self):
        return f"<{self.nickname}> in {self.event.name}: {self.message}"

    def user_hash(self):
        hash_user = hashlib.sha256()
        hash_user.update(self.nickname.encode("utf-8"))
        hash_user.update(self.ip_address.encode("utf-8"))
        return safe64encode(hash_user.digest())

    def serialize(self):
        return {
            "uuid": safe64encode(self.uuid.bytes),
            "nickname": self.nickname,
            "message": self.message,
            "timestamp": self.creation_date.timestamp(),
            "user_hash": self.user_hash(),
        }

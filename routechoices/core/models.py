import base64
import bisect
import logging
import math
import os.path
import re
import time
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from operator import itemgetter
from zipfile import ZipFile

import cv2
import gps_data_codec
import gpxpy
import gpxpy.gpx
import magic
import numpy as np
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import LinearRing, Polygon
from django.core.cache import cache
from django.core.exceptions import BadRequest, PermissionDenied, ValidationError
from django.core.files.base import ContentFile, File
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.core.validators import MaxValueValidator, MinValueValidator, validate_slug
from django.db import models
from django.db.models import F, Min, Q
from django.db.models.functions import ExtractMonth, ExtractYear, Upper
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django_hosts.resolvers import reverse
from jxlpy import JXLImagePlugin  # noqa: F401
from PIL import Image, ImageDraw
from pillow_heif import register_avif_opener

from routechoices.lib import plausible
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import (
    adjugate_matrix,
    delete_domain,
    distance_latlon,
    distance_xy,
    epoch_to_datetime,
    general_2d_projection,
    get_current_site,
    project,
    random_device_id,
    random_key,
    safe64encodedsha,
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

register_avif_opener()

logger = logging.getLogger(__name__)

GLOBAL_MERCATOR = GlobalMercator()
EVENT_CACHE_INTERVAL = 5

WEBP_MAX_SIZE = 16383

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
    tmp_path = ["logos"]
    time_hash = time_base64()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0])
    tmp_path.append(basename[1])
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


def banner_upload_path(instance=None, file_name=None):
    tmp_path = ["banners"]
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
        db_index=True,
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
    slug_changed_from = models.CharField(
        max_length=50,
        validators=[validate_domain_slug],
        blank=True,
        default="",
        editable=False,
    )
    slug_changed_at = models.DateTimeField(null=True, blank=True, editable=False)
    admins = models.ManyToManyField(User)
    description = models.TextField(
        blank=True,
        default="""## Live GPS Tracking

Follow our events live or replay them later.

*This website is powered by Routechoices.com*""",
        help_text=(
            "This text will be displayed on the club site frontpage, "
            "use markdown formatting"
        ),
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
        help_text="Image of size greater or equal than 128x128 pixels",
        storage=OverwriteImageStorage(aws_s3_bucket_name=settings.AWS_S3_BUCKET),
    )
    banner = models.ImageField(
        upload_to=banner_upload_path,
        null=True,
        blank=True,
        help_text="Image of size greater or equal than 600x315 pixels",
        storage=OverwriteImageStorage(aws_s3_bucket_name=settings.AWS_S3_BUCKET),
    )
    analytics_site = models.URLField(max_length=256, blank=True)

    upgraded = models.BooleanField(default=False)
    upgraded_date = models.DateTimeField(blank=True, null=True)
    order_id = models.CharField(max_length=200, blank=True, default="")
    forbid_invite_request = models.BooleanField(
        "Prevent external users to request admin rights", default=False
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "club"
        verbose_name_plural = "clubs"
        indexes = [
            models.Index(
                Upper("slug"),
                name="core_club_slug_upper_idx",
            ),
            models.Index(
                Upper("domain"),
                name="core_club_domain_upper_idx",
            ),
            models.Index(
                Upper("slug_changed_from"),
                F("slug_changed_at").desc(),
                name="core_club_changed_slug_idx",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk:
            if self.domain:
                self.domain = self.domain.lower()
            old_self = Club.objects.get(pk=self.pk)
            old_domain = old_self.domain
            if old_domain and old_domain != self.domain:
                delete_domain(old_domain)
            if old_self.slug != self.slug:
                self.slug_changed_from = old_self.slug
                self.slug_changed_at = now()

                if self.analytics_site:
                    plausible.change_domain(
                        old_self.analytics_domain, self.analytics_domain
                    )
                    self.analytics_site = ""

        self.slug = self.slug.lower()
        if not self.analytics_site:
            analytics_site, created = plausible.create_shared_link(
                self.analytics_domain, self.name
            )
            if created:
                self.analytics_site = analytics_site
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return self.nice_url

    @property
    def analytics_domain(self):
        return f"{self.slug}.{settings.PARENT_HOST}"

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
        if getattr(settings, "USE_CUSTOM_DOMAIN_PREFIX", True):
            path = reverse(
                "club_view", host="clubs", host_kwargs={"club_slug": self.slug.lower()}
            )
        else:
            path = reverse(
                "site:club:club_view", kwargs={"club_slug": self.slug.lower()}
            )
            path = f"{path}"
        return f"{self.url_protocol}:{path}"

    def logo_scaled(self, width, ext="PNG"):
        logo = None
        if not self.logo:
            return None
        with self.logo.open("rb") as fp:
            logo_b = fp.read()
        logo = Image.open(BytesIO(logo_b))
        logo_s = logo.resize((width, width), Image.BILINEAR)
        buffer = BytesIO()
        logo_s.save(buffer, ext, quality=(40 if ext in ("AVIF", "JXL") else 80))
        return buffer.getvalue()

    @property
    def logo_last_mod(self):
        return f"?v={int(self.modification_date.timestamp())}"

    @property
    def logo_url(self):
        return f"{self.nice_url}logo{self.logo_last_mod}"

    @property
    def banner_url(self):
        return f"{self.nice_url}banner?v={safe64encodedsha(self.banner.name)}"

    def thumbnail(self, mime="image/jpeg"):
        cache_key = f"club:{self.aid}:thumbnail:{self.modification_date}:{mime}"
        if not self.banner:
            cache_key = f"{cache_key}:blank"
            cached = cache.get(cache_key)
            if cached:
                return cached
            img = Image.new("RGB", (1200, 630), "WHITE")
        else:
            banner = self.banner

            cached = cache.get(cache_key)
            if cached:
                return cached
            orig = banner.open("rb").read()
            img = Image.open(BytesIO(orig)).convert("RGBA")
            white_bg_img = Image.new("RGBA", img.size, "WHITE")
            white_bg_img.paste(img, (0, 0), img)
            img = white_bg_img.convert("RGB")
        logo = None
        if self.logo:
            logo_b = self.logo.open("rb").read()
            logo = Image.open(BytesIO(logo_b))
        elif not self.domain:
            logo = Image.open("routechoices/watermark.png")
        if logo:
            logo_f = logo.resize((250, 250), Image.LANCZOS)
            img.paste(logo_f, (int((1200 - 250) / 2), int((630 - 250) / 2)), logo_f)
        buffer = BytesIO()
        img.save(
            buffer,
            mime[6:].upper(),
            quality=(40 if mime in ("image/avif", "image/jxl") else 80),
        )
        data_out = buffer.getvalue()
        cache.set(cache_key, data_out, 31 * 24 * 3600)
        return data_out

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = Club.objects.filter(slug__iexact=self.slug)
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            raise ValidationError("Club with this slug already exists.")


@receiver(pre_delete, sender=Club, dispatch_uid="club_delete_signal")
def delete_club_receiver(sender, instance, using, **kwargs):
    plausible.delete_domain(instance.analytics_domain)
    if instance.domain:
        delete_domain(instance.domain)


def map_upload_path(instance=None, file_name=None):
    tmp_path = ["maps"]
    time_hash = time_base64()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0])
    tmp_path.append(basename[1])
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


NOT_CACHED_TILE = 0
CACHED_TILE = 1
CACHED_BLANK_TILE = 2


class Map(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
        db_index=True,
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
        storage=OverwriteImageStorage(aws_s3_bucket_name=settings.AWS_S3_BUCKET),
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
        return f"{self.name}"

    @property
    def path(self):
        return self.image.name

    @property
    def data(self):
        cache_key = f"map:{self.image.name}:data"
        cached = cache.get(cache_key)
        if cached:
            return cached
        with self.image.open("rb") as fp:
            data = fp.read()
        try:
            cache.set(cache_key, data, 3600)
        except Exception:
            pass
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

        doc_kml = render_to_string(
            "kml.xml", {"name": self.name, "bound": self.bound, "ext": ext}
        )
        kmz = BytesIO()
        with ZipFile(kmz, "w") as fp:
            with fp.open("doc.kml", "w") as file1:
                file1.write(doc_kml.encode("utf-8"))
            with fp.open(f"files/doc.{ext}", "w") as file2:
                file2.write(doc_img)
        return kmz.getbuffer()

    @property
    def mime_type(self):
        cache_key = f"map:{self.image.name}:mime"
        cached = cache.get(cache_key)
        if cached:
            return cached
        with self.image.storage.open(self.image.name, mode="rb", nbytes=2048) as fp:
            data = fp.read()
        mime = magic.from_buffer(data, mime=True)
        try:
            cache.set(cache_key, mime, 3600)
        except Exception:
            pass
        return mime

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
            r"^data:image/(?P<format>jpeg|png|gif|webp);base64,"
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
    def size(self):
        return {"width": self.width, "height": self.height}

    @property
    def min_lon(self):
        return min(
            self.bound["topLeft"]["lon"],
            self.bound["bottomLeft"]["lon"],
            self.bound["bottomRight"]["lon"],
            self.bound["topRight"]["lon"],
        )

    @property
    def max_lon(self):
        return max(
            self.bound["topLeft"]["lon"],
            self.bound["bottomLeft"]["lon"],
            self.bound["bottomRight"]["lon"],
            self.bound["topRight"]["lon"],
        )

    @property
    def min_lat(self):
        return min(
            self.bound["topLeft"]["lat"],
            self.bound["bottomLeft"]["lat"],
            self.bound["bottomRight"]["lat"],
            self.bound["topRight"]["lat"],
        )

    @property
    def max_lat(self):
        return max(
            self.bound["topLeft"]["lat"],
            self.bound["bottomLeft"]["lat"],
            self.bound["bottomRight"]["lat"],
            self.bound["topRight"]["lat"],
        )

    @property
    def max_xy(self):
        return GLOBAL_MERCATOR.latlon_to_meters(
            {"lat": self.max_lat, "lon": self.max_lon}
        )

    @property
    def min_xy(self):
        return GLOBAL_MERCATOR.latlon_to_meters(
            {"lat": self.min_lat, "lon": self.min_lon}
        )

    @property
    def alignment_points(self):
        a1 = Point(0, 0)
        b1 = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["topLeft"]))
        a2 = Point(0, self.height)
        b2 = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["bottomLeft"]))
        a3 = Point(self.width, 0)
        b3 = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["topRight"]))
        a4 = Point(self.width, self.height)
        b4 = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound["bottomRight"]))
        return a1, a2, a3, a4, b1, b2, b3, b4

    @property
    def matrix_3d(self):
        m = general_2d_projection(*self.alignment_points)
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

    def wsg84_to_map_xy(self, lat, lon, round_values=False):
        world_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": lat, "lon": lon})
        map_xy = self.spherical_mercator_to_map_xy(world_xy["x"], world_xy["y"])
        if round_values:
            return round(map_xy[0]), round(map_xy[1])
        return map_xy

    def map_xy_to_wsg84(self, x, y):
        mx, my = self.map_xy_to_spherical_mercator(x, y)
        return GLOBAL_MERCATOR.meters_to_latlon({"x": mx, "y": my})

    @property
    def resolution(self):
        """Return map image resolution in pixels/meters"""
        ll_a = self.map_xy_to_wsg84(0, 0)
        ll_b = self.map_xy_to_wsg84(self.width, 0)
        ll_c = self.map_xy_to_wsg84(self.width, self.height)
        ll_d = self.map_xy_to_wsg84(0, self.height)
        resolution = (
            distance_xy(0, 0, 0, self.height)
            + distance_xy(0, self.height, self.width, self.height)
            + distance_xy(self.width, self.height, self.width, 0)
            + distance_xy(self.width, 0, 0, 0)
        ) / (
            distance_latlon(ll_a, ll_b)
            + distance_latlon(ll_b, ll_c)
            + distance_latlon(ll_c, ll_d)
            + distance_latlon(ll_d, ll_a)
        )
        return round(resolution, 3)

    @property
    def center(self):
        return self.map_xy_to_wsg84(self.width / 2, self.height / 2)

    @property
    def max_zoom(self):
        center_latitude = self.center["lat"]
        meters_per_pixel_at_zoom_18 = (
            40_075_016.686 * math.cos(center_latitude * math.pi / 180) / (2 ** (18 + 8))
        )
        r = self.resolution / meters_per_pixel_at_zoom_18
        return math.floor(math.log2(r)) + 18

    @property
    def rotation(self):
        tl = self.map_xy_to_spherical_mercator(0, 0)
        tr = self.map_xy_to_spherical_mercator(self.width, 0)
        br = self.map_xy_to_spherical_mercator(self.width, self.height)
        bl = self.map_xy_to_spherical_mercator(0, self.height)
        rot = (
            (
                (
                    math.atan2(tr[1] - tl[1], tr[0] - tl[0])
                    + math.atan2(br[1] - bl[1], br[0] - bl[0])
                )
                + (
                    math.atan2(tl[1] - bl[1], tl[0] - bl[0])
                    + math.atan2(tr[1] - br[1], tr[0] - br[0])
                    - math.pi
                )
            )
            / 4
            * 180
            / math.pi
        )
        return round(rot, 2)

    @property
    def north_declination(self):
        rot = self.rotation + 180
        if rot > 45:
            rot = (rot - 45) % 90 - 45
        return round(rot, 2)

    def tile_cache_key(
        self, output_width, output_height, img_mime, min_lon, max_lon, min_lat, max_lat
    ):
        return (
            f"map:{self.aid}:{self.hash}:tile:"
            f"{output_width}x{output_height}:"
            f"{min_lon},{max_lon},{min_lat},{max_lat}:"
            f"{img_mime}"
        )

    def create_tile(
        self,
        output_width,
        output_height,
        img_mime,
        min_x,
        max_x,
        min_y,
        max_y,
    ):
        """
        Coordinates must be given in spherical mercator X Y
        """
        cache_key = self.tile_cache_key(
            output_width, output_height, img_mime, min_x, max_x, min_y, max_y
        )
        use_cache = getattr(settings, "CACHE_TILES", False)
        cached = None
        if use_cache:
            try:
                cached = cache.get(cache_key)
            except Exception:
                pass
            else:
                if cached:
                    return cached, CACHED_TILE

        if not self.intersects_with_tile(min_x, max_x, min_y, max_y):
            blank_cache_key = f"tile:blank:{output_width}x{output_height}:{img_mime}"
            if use_cache:
                try:
                    cached = cache.get(blank_cache_key)
                except Exception:
                    pass
                else:
                    if cached:
                        try:
                            cache.set(cache_key, cached, 3600 * 24 * 30)
                        except Exception:
                            pass
                        return cached, CACHED_BLANK_TILE

            if img_mime in ("image/avif", "image/jxl"):
                buffer = BytesIO()
                pil_image = Image.new(
                    mode="RGBA",
                    size=(output_height, output_width),
                    color=(255, 255, 255, 0),
                )
                pil_image.save(buffer, img_mime[6:].upper(), quality=10)
                data_out = buffer.getvalue()
            else:
                n_channels = 3 if img_mime == "image/jpeg" else 4
                transparent_img = np.zeros(
                    (output_height, output_width, n_channels), dtype=np.uint8
                )
                extra_args = []
                if img_mime == "image/webp":
                    extra_args = [int(cv2.IMWRITE_WEBP_QUALITY), 10]
                elif img_mime == "image/jpeg":
                    transparent_img[:, :] = (255, 255, 255)
                    extra_args = [int(cv2.IMWRITE_JPEG_QUALITY), 10]
                _, buffer = cv2.imencode(
                    f".{img_mime[6:]}",
                    transparent_img,
                    extra_args,
                )
                data_out = BytesIO(buffer).getvalue()
            if use_cache:
                try:
                    cache.set(cache_key, data_out, 3600 * 24 * 30)
                    cache.set(blank_cache_key, data_out, 3600 * 24 * 30)
                except Exception:
                    pass
            return data_out, NOT_CACHED_TILE

        img_alpha = None
        if use_cache:
            try:
                img_alpha = cache.get(f"img_data_{self.image.name}_raw")
            except Exception:
                pass

        if img_alpha is None:
            orig = self.data
            orig_mime_type = magic.from_buffer(orig, mime=True)
            if orig_mime_type == "image/gif":
                img = Image.open(BytesIO(orig)).convert("RGBA")
                img_alpha = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGRA)
            else:
                img_nparr = np.fromstring(orig, np.uint8)
                img = cv2.imdecode(img_nparr, cv2.IMREAD_UNCHANGED)
                img_alpha = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2BGRA)

            if use_cache and not cache.has_key(f"img_data_{self.image.name}_raw"):
                cache.set(f"img_data_{self.image.name}_raw", img_alpha, 3600 * 24 * 30)

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

        scale = 1
        while True:
            r_w = (max_x - min_x) / output_width / scale
            r_h = (max_y - min_y) / output_height / scale

            p2 = np.float32(
                [
                    [(tl[0] - min_x) / r_w, (max_y - tl[1]) / r_h],
                    [(tr[0] - min_x) / r_w, (max_y - tr[1]) / r_h],
                    [(br[0] - min_x) / r_w, (max_y - br[1]) / r_h],
                    [(bl[0] - min_x) / r_w, (max_y - bl[1]) / r_h],
                ]
            )
            coeffs = cv2.getPerspectiveTransform(p1, p2)
            if (
                scale < 2
                and max(
                    abs(coeffs[0][0]),
                    abs(coeffs[0][1]),
                    abs(coeffs[1][0]),
                    abs(coeffs[1][1]),
                )
                < 0.5
            ):
                scale *= 2
            else:
                break

        tile_img = cv2.warpPerspective(
            img_alpha,
            coeffs,
            (int(output_width * scale), int(output_height * scale)),
            flags=cv2.INTER_AREA,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255, 0),
        )
        if scale > 1:
            tile_img = cv2.resize(
                tile_img, (output_width, output_height), interpolation=cv2.INTER_AREA
            )
        extra_args = []
        if img_mime in ("image/avif", "image/jxl"):
            color_coverted = cv2.cvtColor(tile_img, cv2.COLOR_BGRA2RGBA)
            pil_image = Image.fromarray(color_coverted)
            buffer = BytesIO()
            pil_image.save(buffer, img_mime[6:].upper(), quality=80)
            data_out = buffer.getvalue()
        else:
            if img_mime == "image/webp":
                extra_args = [int(cv2.IMWRITE_WEBP_QUALITY), 100]
            elif img_mime == "image/jpeg":
                extra_args = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
            _, buffer = cv2.imencode(f".{img_mime[6:]}", tile_img, extra_args)
            data_out = BytesIO(buffer).getvalue()

        if use_cache:
            try:
                cache.set(cache_key, data_out, 3600 * 24 * 30)
            except Exception:
                pass
        return data_out, NOT_CACHED_TILE

    def intersects_with_tile(self, min_x, max_x, min_y, max_y):
        tile_bounds_poly = Polygon(
            LinearRing(
                (min_x, min_y),
                (min_x, max_y),
                (max_x, max_y),
                (max_x, min_y),
                (min_x, min_y),
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
            img_ext = "WEBP"
            if rgba_img.size[0] > WEBP_MAX_SIZE or rgba_img.size[1] > WEBP_MAX_SIZE:
                img_ext = "PNG"
            out_buffer = BytesIO()
            params = {
                "dpi": (72, 72),
            }
            if img_ext == "WEBP":
                params["quality"] = 80
            rgba_img.save(out_buffer, img_ext, **params)
            f_new = File(out_buffer, name=self.image.name)
            self.image.save(
                "filename",
                f_new,
                save=False,
            )
        self.image.close()

    @property
    def hash(self):
        return safe64encodedsha(f"{self.path}:{self.corners_coordinates}:20230420")

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
    def from_points(cls, seg, waypoints):
        new_map = cls()

        min_lat = 90
        max_lat = -90
        min_lon = 180
        max_lon = -180

        line_color = (0xF5, 0x2F, 0xE4, 160)

        all_segs = seg
        if waypoints:
            all_segs = seg + [
                waypoints,
            ]

        for pts in all_segs:
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

        res_scale = 4
        MAX_SIZE = 4000
        offset = 100
        width = tr_xy["x"] - tl_xy["x"]
        height = tr_xy["y"] - br_xy["y"]

        scale = 1
        if width > MAX_SIZE or height > MAX_SIZE:
            scale = max(width, height) / MAX_SIZE

        width = (tr_xy["x"] - tl_xy["x"]) / scale + 2 * offset
        height = (tr_xy["y"] - br_xy["y"]) / scale + 2 * offset

        corners = [
            GLOBAL_MERCATOR.meters_to_latlon(
                {"x": tl_xy["x"] - offset * scale, "y": tl_xy["y"] + offset * scale}
            ),
            GLOBAL_MERCATOR.meters_to_latlon(
                {"x": tr_xy["x"] + offset * scale, "y": tr_xy["y"] + offset * scale}
            ),
            GLOBAL_MERCATOR.meters_to_latlon(
                {"x": br_xy["x"] + offset * scale, "y": br_xy["y"] - offset * scale}
            ),
            GLOBAL_MERCATOR.meters_to_latlon(
                {"x": bl_xy["x"] - offset * scale, "y": bl_xy["y"] - offset * scale}
            ),
        ]

        new_map.corners_coordinates = ",".join(
            f"{round(c['lat'], 5)},{round(c['lon'], 5)}" for c in corners
        )

        im = Image.new(
            "RGBA",
            (int(width * res_scale), int(height * res_scale)),
            (255, 255, 255, 0),
        )
        new_map.width = int(width * res_scale)
        new_map.height = int(height * res_scale)
        draw = ImageDraw.Draw(im)
        for pts in seg:
            map_pts = [
                new_map.wsg84_to_map_xy(pt[0], pt[1], round_values=True) for pt in pts
            ]
            draw.line(map_pts, (255, 255, 255, 200), 22 * res_scale, joint="curve")
            draw.line(map_pts, line_color, 16 * res_scale, joint="curve")
        for pt in waypoints:
            map_pt = new_map.wsg84_to_map_xy(pt[0], pt[1], round_values=True)
            widths = [66, 63]
            thicknesses = [22, 16]

            colors = [(255, 255, 255, 200), line_color]
            for i, w in enumerate(widths):
                wr = w * res_scale
                draw.ellipse(
                    (
                        map_pt[0] - wr,
                        map_pt[1] - wr,
                        map_pt[0] + wr,
                        map_pt[1] + wr,
                    ),
                    outline=colors[i],
                    width=int(thicknesses[i] * res_scale),
                )

        im = im.resize((int(width), int(height)), resample=Image.Resampling.BICUBIC)
        out_buffer = BytesIO()
        im.save(out_buffer, "WEBP", dpi=(72, 72), quality=80)
        f_new = File(out_buffer)
        new_map.image.save(
            "filename",
            f_new,
            save=False,
        )
        return new_map

    @property
    def area(self):
        # Area in km^2
        ll_a = self.map_xy_to_wsg84(0, 0)
        ll_b = self.map_xy_to_wsg84(self.width, 0)
        ll_c = self.map_xy_to_wsg84(self.width, self.height)
        ll_d = self.map_xy_to_wsg84(0, self.height)
        return round(
            (distance_latlon(ll_a, ll_b) + distance_latlon(ll_c, ll_d))
            / 2
            * (+distance_latlon(ll_a, ll_c) + distance_latlon(ll_b, ll_d))
            / 2
            / 1000
            / 1000,
            3,
        )


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
MAP_GOOGLE_TERRAIN = "gmap-terrain"
MAP_MAPANT_CH = "mapant-ch"
MAP_MAPANT_FI = "mapant-fi"
MAP_MAPANT_NO = "mapant-no"
MAP_MAPANT_ES = "mapant-es"
MAP_MAPANT_SV = "mapant-se"
MAP_TOPO_FI = "topo-fi"
MAP_TOPO_FR = "topo-fr"
MAP_TOPO_NO = "topo-no"
MAP_TOPO_UK = "topo-uk"
MAP_TOPO_WRLD = "topo-world"
MAP_TOPO_WRLD_ALT = "topo-world-alt"

MAP_CHOICES = (
    (MAP_BLANK, "Blank"),
    (MAP_OSM, "Open Street Map"),
    (MAP_GOOGLE_STREET, "Google Map Street"),
    (MAP_GOOGLE_SAT, "Google Map Satellite"),
    (MAP_GOOGLE_TERRAIN, "Google Map Terrain"),
    (MAP_MAPANT_FI, "Mapant Finland"),
    (MAP_MAPANT_NO, "Mapant Norway"),
    (MAP_MAPANT_ES, "Mapant Spain"),
    (MAP_MAPANT_SV, "Mapant Sweden"),
    (MAP_MAPANT_CH, "Mapant Switzerland"),
    (MAP_TOPO_FI, "Topo Finland"),
    (MAP_TOPO_FR, "Topo France"),
    (MAP_TOPO_NO, "Topo Norway"),
    (MAP_TOPO_UK, "Topo UK"),
    (MAP_TOPO_WRLD, "Topo World (OpenTopo)"),
    (MAP_TOPO_WRLD_ALT, "Topo World (ArcGIS)"),
)


class BackroundMapChoicesField(models.CharField):
    def __init__(self, **kwargs):
        kwargs["max_length"] = 16
        kwargs["choices"] = MAP_CHOICES
        kwargs["default"] = MAP_BLANK
        super().__init__(**kwargs)

    def deconstruct(self):  # pragma: no cover
        # only run when creating migrations, so no-cover
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop("choices", None)
        return (name, path, args, kwargs)


class EventSet(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
        db_index=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
        Club, verbose_name="Club", related_name="event_sets", on_delete=models.CASCADE
    )
    name = models.CharField(verbose_name="Name", max_length=255)
    create_page = models.BooleanField(
        default=False,
        help_text="Whether a page with all the events of the set will be generated",
    )
    slug = models.CharField(
        verbose_name="Slug",
        max_length=50,
        validators=[
            validate_nice_slug,
        ],
        db_index=True,
        help_text="This is used to build the url of the page",
        null=True,
        blank=True,
        default="",
    )
    list_secret_events = models.BooleanField(
        default=False,
        help_text="Whether the page lists the secret events of the event set",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text=(
            "This text will be displayed on the event set page, "
            "use markdown formatting"
        ),
    )

    def save(self, *args, **kwargs):
        if not self.create_page:
            self.slug = ""
            self.list_secret_events = False
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-creation_date", "name"]
        unique_together = (("club", "name"),)

    def __str__(self):
        return self.name

    @property
    def url(self):
        if self.create_page:
            return f"{self.club.nice_url}{self.slug}"
        return ""

    @property
    def shortcut(self):
        shortcut_url = getattr(settings, "SHORTCUT_BASE_URL", None)
        if shortcut_url:
            return f"{shortcut_url}{self.club.slug}/{self.slug}"
        return None

    @property
    def shortcut_text(self):
        shortcut_url = self.shortcut
        if shortcut_url:
            return shortcut_url.partition("://")[2]
        return None

    @property
    def hide_secret_events(self):
        return not self.list_secret_events

    def validate_unique(self, exclude=None):
        errors = []
        qs = EventSet.objects.filter(club_id=self.club_id, name__iexact=self.name)
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            errors.append("Event Set with this Club and Name already exists.")

        if self.create_page:
            qs = EventSet.objects.filter(
                club_id=self.club_id, create_page=True, slug__iexact=self.slug
            )
            if self.id:
                qs = qs.exclude(id=self.id)
            if qs.exists():
                errors.append("Event Set with this Club and Slug already exists.")
            elif Event.objects.filter(
                club_id=self.club_id, slug__iexact=self.slug
            ).exists():
                errors.append("Event with this Club and Slug already exists.")
        if errors:
            raise ValidationError(errors)
        super().validate_unique(exclude)

    def extract_event_lists(self, request):
        event_qs = self.events.select_related("club", "event_set").prefetch_related(
            "competitors"
        )
        if self.list_secret_events:
            event_qs = event_qs.exclude(privacy=PRIVACY_PRIVATE)
        else:
            event_qs = event_qs.filter(privacy=PRIVACY_PUBLIC)
        past_event_qs = event_qs.filter(end_date__lt=now())
        live_events_qs = event_qs.filter(start_date__lte=now(), end_date__gte=now())
        upcoming_events_qs = event_qs.filter(
            start_date__gt=now(), start_date__lte=now() + timedelta(hours=24)
        )

        def events_to_sets(qs, type="past"):
            all_events_w_set = event_qs.order_by("-start_date", "name")
            if type == "live":
                all_events_w_set = all_events_w_set.filter(
                    start_date__lte=now(), end_date__gte=now()
                )
            elif type == "upcoming":
                all_events_w_set = all_events_w_set.filter(
                    start_date__gt=now(),
                    start_date__lte=now() + timedelta(hours=24),
                ).order_by("start_date", "name")
            else:
                all_events_w_set = all_events_w_set.filter(end_date__lt=now())
            if not all_events_w_set.exists():
                return []
            events = [
                {
                    "name": self.name,
                    "events": all_events_w_set,
                    "fake": False,
                }
            ]
            return events

        all_past_events = past_event_qs
        past_events = events_to_sets(all_past_events)

        all_live_events = live_events_qs
        live_events = events_to_sets(all_live_events, type="live")

        all_upcoming_events = upcoming_events_qs
        upcoming_events = events_to_sets(all_upcoming_events, type="upcoming")

        return {
            "event_set": self,
            "event_set_page": True,
            "club": self.club,
            "events": past_events,
            "live_events": live_events,
            "upcoming_events": upcoming_events,
            "years": [],
            "months": [],
            "year": None,
            "month": None,
            "search_text": None,
            "month_names": [],
        }


class Event(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
        db_index=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
        Club,
        verbose_name="Club",
        related_name="events",
        on_delete=models.CASCADE,
        db_index=True,
    )
    name = models.CharField(verbose_name="Name", max_length=255)
    slug = models.CharField(
        verbose_name="Slug",
        max_length=50,
        validators=[validate_nice_slug],
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
        help_text=(
            "Public: Listed on your club's front page | "
            "Secret: Can be opened with a link, however not listed on frontpage | "
            "Private: Only a logged in admin of the club can access the page"
        ),
    )
    list_on_routechoices_com = models.BooleanField(
        "Listed on Routechoices.com events page",
        default=True,
    )
    backdrop_map = BackroundMapChoicesField(verbose_name="Background map")
    map = models.ForeignKey(
        Map,
        related_name="events_main_map",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    map_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Leave blank if not using extra maps",
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
        help_text="Participants can add their GPS trace from a file after the event.",
    )
    send_interval = models.PositiveIntegerField(
        "Send interval (seconds)",
        default=5,
        help_text=(
            "If using dedicated trackers, enter here the sending "
            "interval set for the devices to, if using the "
            "official smartphone app leave the value at 5 seconds"
        ),
        validators=[MinValueValidator(1)],
    )
    tail_length = models.PositiveIntegerField(
        "Tail length (seconds)",
        default=60,
        help_text=(
            "Default tail length when a user open the event. "
            "Can be overriden by the viewers in the event page settings tab."
        ),
    )
    event_set = models.ForeignKey(
        EventSet,
        null=True,
        blank=True,
        verbose_name="Event Set",
        related_name="events",
        on_delete=models.SET_NULL,
        help_text=(
            "Events within the same event set will be grouped together "
            "on the event listing page."
        ),
        db_index=True,
    )
    emergency_contact = models.EmailField(
        default="",
        blank=True,
        help_text=(
            "Email address of a person available to respond in the case a competitor "
            "carrying a GPS tracker with SOS feature enabled triggers the SOS button."
        ),
    )

    class Meta:
        ordering = ["-start_date", "name"]
        unique_together = (
            ("club", "event_set", "name"),
            ("club", "slug"),
        )
        verbose_name = "event"
        verbose_name_plural = "events"
        indexes = [
            models.Index(
                Upper("slug"),
                name="core_event_slug_upper_idx",
            ),
            models.Index(
                "privacy",
                "list_on_routechoices_com",
                "end_date",
                "event_set_id",
                name="core_event_list_frontpage_idx",
            ),
            models.Index(
                "privacy",
                "club_id",
                "end_date",
                "event_set_id",
                name="core_event_list_clubpage_idx",
            ),
            models.Index(
                "privacy",
                "list_on_routechoices_com",
                "end_date",
                name="core_event_listing_idx",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.invalidate_cache()
        super().save(*args, **kwargs)

    def check_user_permission(self, user):
        if self.privacy == PRIVACY_PRIVATE and (
            not user.is_authenticated
            or not self.club.admins.filter(id=user.id).exists()
        ):
            raise PermissionDenied

    @classmethod
    def get_public_map_at_index(cls, user, event_id, map_index, load_competitors=False):
        """map_index is 1 based"""
        event_qs = (
            cls.objects.all()
            .select_related("club")
            .filter(
                start_date__lt=now(),
            )
        )
        if load_competitors:
            event_qs = event_qs.prefetch_related(
                "competitors",
            )
        try:
            map_index = int(map_index)
            if map_index <= 0:
                raise ValueError()
        except Exception:
            raise Http404

        map_index -= 1
        if map_index == 0:
            event_qs = event_qs.select_related("map")
        elif map_index > 0:
            event_qs = event_qs.prefetch_related(
                models.Prefetch(
                    "map_assignations",
                    queryset=MapAssignation.objects.select_related("map"),
                )
            )

        event = get_object_or_404(event_qs, aid=event_id)

        if (
            not event
            or (map_index == 0 and not event.map_id)
            or (map_index > 0 and map_index > event.map_assignations.all().count())
        ):
            raise Http404

        event.check_user_permission(user)

        if map_index == 0:
            raster_map = event.map
        else:
            raster_map = event.map_assignations.all()[map_index - 1].map
        return event, raster_map

    @classmethod
    def extract_event_lists(cls, request, club=None):
        page = request.GET.get("page")
        selected_year = request.GET.get("year")
        selected_month = request.GET.get("month")
        search_text_raw = request.GET.get("q", "").strip()

        event_qs = (
            cls.objects.filter(privacy=PRIVACY_PUBLIC)
            .select_related("club", "event_set")
            .prefetch_related("competitors")
        )
        if club is None:
            event_qs = event_qs.filter(list_on_routechoices_com=True)
        else:
            event_qs = event_qs.filter(club=club)

        past_event_qs = event_qs.filter(end_date__lt=now())
        live_events_qs = event_qs.filter(start_date__lte=now(), end_date__gte=now())
        upcoming_events_qs = event_qs.filter(
            start_date__gt=now(), start_date__lte=now() + timedelta(hours=24)
        ).order_by("start_date", "name")
        if search_text_raw:
            search_text = search_text_raw
            quoted_terms = re.findall(r"\"(.+?)\"", search_text)
            if quoted_terms:
                search_text = re.sub(r"\"(.+?)\"", "", search_text)
            search_terms = search_text.split(" ")
            search_text_query = Q()
            for search_term in search_terms + quoted_terms:
                key_name = "name__icontains"
                key_club_name = "club__name__icontains"
                key_set_name = "event_set__name__icontains"
                search_text_query &= (
                    Q(**{key_name: search_term})
                    | Q(**{key_club_name: search_term})
                    | Q(**{key_set_name: search_term})
                )
            past_event_qs = past_event_qs.filter(search_text_query)

        months = None
        years = list(
            past_event_qs.annotate(year=ExtractYear("start_date"))
            .values_list("year", flat=True)
            .order_by("-year")
            .distinct()
        )
        if selected_year:
            try:
                selected_year = int(selected_year)
            except Exception:
                raise BadRequest("Invalid year")
        if selected_year:
            past_event_qs = past_event_qs.filter(start_date__year=selected_year)
            months = list(
                past_event_qs.annotate(month=ExtractMonth("start_date"))
                .values_list("month", flat=True)
                .order_by("-month")
                .distinct()
            )
            if selected_month:
                try:
                    selected_month = int(selected_month)
                    if selected_month < 1 or selected_month > 12:
                        raise ValueError()
                except Exception:
                    raise BadRequest("Invalid month")
            if selected_month:
                past_event_qs = past_event_qs.filter(start_date__month=selected_month)

        def list_events_sets(qs, decreasing_order=True):
            events_without_sets = qs.filter(event_set__isnull=True)
            order = "-start_date" if decreasing_order else "start_date"
            first_events_of_each_set = (
                qs.filter(event_set__isnull=False)
                .order_by("event_set_id", order, "name")
                .distinct("event_set_id")
            )
            return events_without_sets.union(first_events_of_each_set).order_by(
                order, "name"
            )

        def events_to_sets(qs, type="past"):
            events_set_ids = [e.event_set_id for e in qs if e.event_set_id]
            events_by_set = {}
            if events_set_ids:
                all_events_w_set = (
                    cls.objects.select_related("club")
                    .prefetch_related("competitors")
                    .filter(event_set_id__in=events_set_ids, privacy=PRIVACY_PUBLIC)
                    .order_by("-start_date", "name")
                )
                if not club:
                    all_events_w_set = all_events_w_set.filter(
                        list_on_routechoices_com=True
                    )
                if type == "live":
                    all_events_w_set = all_events_w_set.filter(
                        start_date__lte=now(), end_date__gte=now()
                    )
                elif type == "upcoming":
                    all_events_w_set = all_events_w_set.filter(
                        start_date__gt=now(),
                        start_date__lte=now() + timedelta(hours=24),
                    ).order_by("start_date", "name")
                else:
                    all_events_w_set = all_events_w_set.filter(end_date__lt=now())
                    if selected_year:
                        all_events_w_set = all_events_w_set.filter(
                            start_date__year=selected_year
                        )
                        if selected_month:
                            all_events_w_set = all_events_w_set.filter(
                                start_date__month=selected_month
                            )
                    if search_text_raw:
                        all_events_w_set = all_events_w_set.filter(search_text_query)
                for e in all_events_w_set:
                    events_by_set.setdefault(e.event_set_id, [])
                    events_by_set[e.event_set_id].append(e)

            events = []
            for event in qs:
                event_set = event.event_set
                if event_set is None:
                    events.append(
                        {
                            "name": event.name,
                            "events": [
                                event,
                            ],
                            "fake": True,
                        }
                    )
                else:
                    events.append(
                        {
                            "name": event_set.name,
                            "data": event_set,
                            "events": events_by_set[event_set.id],
                            "fake": False,
                        }
                    )
            return events

        all_past_events = list_events_sets(past_event_qs)
        paginator = Paginator(all_past_events, 25)
        past_events_page = paginator.get_page(page)
        past_events = events_to_sets(past_events_page)

        if past_events_page.number == 1 and not selected_year and not search_text_raw:
            all_live_events = list_events_sets(live_events_qs)
            live_events = events_to_sets(all_live_events, type="live")

            all_upcoming_events = list_events_sets(upcoming_events_qs, False)
            upcoming_events = events_to_sets(all_upcoming_events, type="upcoming")
        else:
            live_events = upcoming_events = cls.objects.none()

        return {
            "club": club,
            "events": past_events,
            "events_page": past_events_page,
            "live_events": live_events,
            "upcoming_events": upcoming_events,
            "years": years,
            "months": months,
            "year": selected_year,
            "month": selected_month,
            "search_text": search_text_raw,
            "month_names": [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
        }

    def get_absolute_url(self):
        return f"{self.club.nice_url}{self.slug}"

    def get_absolute_map_url(self):
        return f"{self.club.nice_url}{self.slug}/map/"

    def get_absolute_export_url(self):
        return f"{self.club.nice_url}{self.slug}/export"

    @property
    def duration(self):
        return self.end_date - self.start_date

    @property
    def shortcut(self):
        shortcut_url = getattr(settings, "SHORTCUT_BASE_URL", None)
        if shortcut_url:
            return f"{shortcut_url}{self.club.slug}/{self.slug}"
        return None

    @property
    def shortcut_text(self):
        shortcut_url = self.shortcut
        if shortcut_url:
            return shortcut_url.partition("://")[2]
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
        errors = []
        qs = Event.objects.filter(
            club_id=self.club_id, event_set_id=self.event_set_id, name__iexact=self.name
        )
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            errors.append("Event with this Club, Event Set, and Name already exists.")

        qs = Event.objects.filter(club_id=self.club_id, slug__iexact=self.slug)
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            errors.append("Event with this Club and Slug already exists.")
        elif EventSet.objects.filter(
            club_id=self.club_id, create_page=True, slug__iexact=self.slug
        ).exists():
            errors.append("Event Set with this Club and Slug already exists.")
        if errors:
            raise ValidationError(errors)
        super().validate_unique(exclude)

    def invalidate_cache(self):
        t0 = time.time()
        cache_interval = EVENT_CACHE_INTERVAL
        for cache_suffix in ("live", "archived"):
            cache_ts = int(
                t0 // (cache_interval if cache_suffix == "live" else 7 * 24 * 3600)
            )
            cache_key = f"event:{self.aid}:data:{cache_ts}:{cache_suffix}"
            cache.delete(cache_key)
            cache_key = f"event:{self.aid}:data:{cache_ts - 1}:{cache_suffix}"
            cache.delete(cache_key)

    @property
    def has_notice(self):
        return hasattr(self, "notice")

    def thumbnail(self, display_logo, mime="image/jpeg"):
        if self.start_date > now() or not self.map:
            cache_key = (
                f"map:{self.aid}:blank:thumbnail:{display_logo}"
                f":{self.club.modification_date}:{mime}"
            )
            cached = cache.get(cache_key)
            if cached:
                return cached
            img = Image.new("RGB", (1200, 630), "WHITE")
        else:
            raster_map = self.map
            cache_key = (
                f"map:{self.aid}:{raster_map.hash}:thumbnail:{display_logo}"
                f":{self.club.modification_date}:{mime}"
            )
            cached = cache.get(cache_key)
            if cached:
                return cached
            orig = raster_map.data
            img = Image.open(BytesIO(orig)).convert("RGBA")
            white_bg_img = Image.new("RGBA", img.size, "WHITE")
            white_bg_img.paste(img, (0, 0), img)
            img = white_bg_img.convert("RGB")
            img = img.rotate(round(self.map.rotation / 90) * 90)
            img_width, img_height = img.size
            is_portrait = img_height > img_width
            if is_portrait:
                w = int(img_width / 3)
            else:
                w = int(img_height / 3)
            h = w * 21 / 40
            img = img.transform(
                (1200, 630),
                Image.QUAD,
                (
                    int(img_width / 2) - w,
                    int(img_height / 2) - h,
                    int(img_width / 2) - w,
                    int(img_height / 2) + h,
                    int(img_width / 2) + w,
                    int(img_height / 2) + h,
                    int(img_width / 2) + w,
                    int(img_height / 2) - h,
                ),
            )
        if display_logo:
            logo = None
            if self.club.logo:
                logo_b = self.club.logo.open("rb").read()
                logo = Image.open(BytesIO(logo_b))
            elif not self.club.domain:
                logo = Image.open("routechoices/watermark.png")
            if logo:
                logo_f = logo.resize((250, 250), Image.LANCZOS)
                img.paste(logo_f, (int((1200 - 250) / 2), int((630 - 250) / 2)), logo_f)
        buffer = BytesIO()
        img.save(
            buffer,
            mime[6:].upper(),
            quality=(40 if mime in ("image/avif", "image/jxl") else 80),
        )
        data_out = buffer.getvalue()
        cache.set(cache_key, data_out, 31 * 24 * 3600)
        return data_out


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
        db_index=True,
        validators=[
            validate_slug,
        ],
    )
    user_agent = models.CharField(max_length=200, blank=True)
    is_gpx = models.BooleanField(default=False)
    owners = models.ManyToManyField(
        Club,
        through="DeviceClubOwnership",
        related_name="devices",
        through_fields=("device", "club"),
    )
    locations_encoded = models.TextField(blank=True, default="")
    battery_level = models.PositiveIntegerField(
        null=True, default=None, validators=[MaxValueValidator(100)], blank=True
    )

    _last_location_datetime = models.DateTimeField(
        null=True, blank=True, editable=False
    )
    _last_location_latitude = models.DecimalField(
        null=True, blank=True, editable=False, max_digits=10, decimal_places=5
    )
    _last_location_longitude = models.DecimalField(
        null=True, blank=True, editable=False, max_digits=10, decimal_places=5
    )
    _location_count = models.PositiveIntegerField(editable=False, default=0)

    class Meta:
        ordering = ["aid"]
        verbose_name = "device"
        verbose_name_plural = "devices"

    def __str__(self):
        return self.aid

    def get_display_str(self, club=None):
        original_device = self.get_original_device()
        if original_device:
            device = original_device
        else:
            device = self

        owner = None
        # Use this instead of .filter(club=club).first()
        # as club_ownership are already loaded avoiding n+1 query
        for ownership in device.club_ownerships.all():
            if ownership.club_id == club.id:
                owner = ownership
                break
        return (
            f"{device.aid} {f'({owner.nickname})' if owner and owner.nickname else ''}"
            f"{'*' if original_device else ''}"
        )

    def get_nickname(self, club):
        original_device = self.get_original_device()
        if original_device:
            device = original_device
        else:
            device = self
        owner = None
        # Use this instead of .filter(club=club).first()
        # as club_ownership are already loaded avoiding n+1 query
        for ownership in device.club_ownerships.all():
            if ownership.club_id == club.id:
                owner = ownership
                break
        if owner and owner.nickname:
            return owner.nickname
        return ""

    @property
    def battery_level_0_4(self):
        # 0: 0-15
        # 1: 15-35
        # 2: 35-55
        # 3: 55-75
        # 4: 75-100
        return min(4, round((self.battery_level - 5) / 20))

    @property
    def battery_level_text(self):
        return ["empty", "quarter", "half", "three-quarters", "full"][
            self.battery_level_0_4
        ]

    @property
    def locations_series(self):
        if not self.locations_encoded:
            return []
        return gps_data_codec.decode(self.locations_encoded)

    @locations_series.setter
    def locations_series(self, locations_list):
        sorted_locations = list(
            sorted(locations_list, key=itemgetter(LOCATION_TIMESTAMP_INDEX))
        )
        self.locations_encoded = gps_data_codec.encode(sorted_locations)
        self.update_cached_data()

    @property
    def locations(self):
        if not self.locations_encoded:
            return {"timestamps": [], "latitudes": [], "longitudes": []}
        locs = self.locations_series
        data = list(zip(*locs))
        return {
            "timestamps": list(data[LOCATION_TIMESTAMP_INDEX]),
            "latitudes": list(data[LOCATION_LATITUDE_INDEX]),
            "longitudes": list(data[LOCATION_LONGITUDE_INDEX]),
        }

    @locations.setter
    def locations(self, locations_dict):
        locations_list = list(
            zip(
                locations_dict["timestamps"],
                locations_dict["latitudes"],
                locations_dict["longitudes"],
            )
        )
        self.locations_series = locations_list

    def update_cached_data(self):
        self._location_count = self.location_count
        if self._location_count > 0:
            last_loc = self.locations_series[-1]
            self._last_location_datetime = epoch_to_datetime(
                last_loc[LOCATION_TIMESTAMP_INDEX]
            )
            self._last_location_latitude = last_loc[LOCATION_LATITUDE_INDEX]
            self._last_location_longitude = last_loc[LOCATION_LONGITUDE_INDEX]
        else:
            self._last_location_datetime = None
            self._last_location_latitude = None
            self._last_location_longitude = None

    def get_locations_between_dates(self, from_date, end_date, /, *, encode=False):
        from_ts = from_date.timestamp()
        end_ts = end_date.timestamp()
        locs = self.locations_series
        from_idx = bisect.bisect_left(locs, from_ts, key=itemgetter(0))
        end_idx = bisect.bisect_right(locs, end_ts, key=itemgetter(0))
        locs = locs[from_idx:end_idx]
        if not encode:
            return locs, len(locs)
        encoded_locs = gps_data_codec.encode(locs)
        return encoded_locs, len(locs)

    def add_locations(self, loc_array, /, *, save=True):
        if len(loc_array) == 0:
            return
        new_pts = []
        locations = self.locations_series
        all_ts = set()
        max_ts = None
        if locations:
            all_ts = set(list(zip(*locations))[LOCATION_TIMESTAMP_INDEX])
            max_ts = max(all_ts)
        for loc in loc_array:
            ts = int(loc[LOCATION_TIMESTAMP_INDEX])
            lat = loc[LOCATION_LATITUDE_INDEX]
            lon = loc[LOCATION_LONGITUDE_INDEX]
            if max_ts and ts <= max_ts and ts in all_ts:
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
            if not max_ts:
                max_ts = ts
            else:
                max_ts = max(ts, max_ts)
            new_pts.append((ts, lat, lon))

        if len(new_pts) == 0:
            return

        locations += new_pts
        self.locations_series = locations

        if save:
            self.save()

        new_pts = list(sorted(new_pts, key=itemgetter(LOCATION_TIMESTAMP_INDEX)))
        archived_events_affected = self.get_events_between_dates(
            epoch_to_datetime(new_pts[0][LOCATION_TIMESTAMP_INDEX]),
            epoch_to_datetime(new_pts[-1][LOCATION_TIMESTAMP_INDEX]),
            should_be_ended=True,
        )
        for archived_event_affected in archived_events_affected:
            archived_event_affected.invalidate_cache()

    def add_location(self, timestamp, lat, lon, /, *, save=True):
        self.add_locations(
            [
                (timestamp, lat, lon),
            ],
            save=save,
        )

    @property
    def location_count(self):
        # This use a property of the GPS encoding format
        n = 0
        encoded = self.locations_encoded
        for x in encoded:
            if ord(x) - 63 < 0x20:
                n += 1
        return n // 3

    def remove_duplicates(self, save=True):
        loc_count = self.location_count
        if loc_count == 0:
            return

        orig_locations = self.locations_series
        unique_ts = set(list(zip(*orig_locations))[LOCATION_TIMESTAMP_INDEX])
        if len(unique_ts) == loc_count:
            return

        updated_locations_list = []
        prev_t = None
        for loc in orig_locations:
            t = loc[LOCATION_TIMESTAMP_INDEX]
            if t == prev_t:
                continue
            updated_locations_list.append(
                (
                    t,
                    round(loc[LOCATION_LATITUDE_INDEX], 5),
                    round(loc[LOCATION_LONGITUDE_INDEX], 5),
                )
            )
            prev_t = t

        updated_encoded = gps_data_codec.encode(updated_locations_list)
        if self.locations_encoded != updated_encoded:
            self.locations_series = updated_locations_list
            if save:
                self.save()

    @property
    def last_location(self):
        if not self._location_count:
            return None
        return (
            self._last_location_datetime.timestamp(),
            self._last_location_latitude,
            self._last_location_longitude,
        )

    @property
    def last_location_timestamp(self):
        if self._location_count == 0:
            return None
        return self.last_location[LOCATION_TIMESTAMP_INDEX]

    @property
    def last_location_datetime(self):
        return self._last_location_datetime

    def get_competitors_at_date(self, at, /, *, load_events=False):
        qs = (
            self.competitor_set.all()
            .filter(start_time__lte=at, event__end_date__gte=at)
            .annotate(min_start=Min("start_time"))
            .filter(start_time=F("min_start"))
        )
        if load_events:
            qs = qs.select_related("event")
        return qs

    def get_events_at_date(self, at):
        competitors = self.get_competitors_at_date(at, load_events=True)
        return {c.event for c in competitors}

    def get_events_between_dates(self, from_date, to_date, /, *, should_be_ended=False):
        qs = (
            self.competitor_set.all()
            .filter(
                event__end_date__gte=from_date,
                start_time__lte=to_date,
            )
            .select_related("event")
            .order_by("start_time")
        )
        if should_be_ended:
            qs = qs.filter(event__end_date__lt=now())
        return {c.event for c in qs}

    def get_last_competitor(self, load_event=False):
        qs = self.competitor_set.all().order_by("-start_time")
        if load_event:
            qs = qs.select_related("event")
        return qs.first()

    def get_last_event(self):
        c = self.get_last_competitor(load_event=True)
        if c:
            return c.event
        return None

    def get_original_device(self):
        if (
            self.aid.endswith("_ARC")
            and hasattr(self, "original_ref")
            and self.original_ref is not None
        ):
            return self.original_ref.original
        return None

    def send_sos(self):
        lat = None
        lon = None

        competitors = self.get_competitors_at_date(now(), load_events=True)

        if self.last_location:
            _, lat, lon = self.last_location

        if not competitors:
            return self.aid, lat, lon, None
        all_to_emails = set()
        for competitor in competitors:
            event = competitor.event
            to_emails = set()
            if event.emergency_contact:
                to_emails.add(event.emergency_contact)
            else:
                club = event.club
                admin_ids = list(club.admins.all().values_list("id", flat=True))
                to_emails = list(
                    EmailAddress.objects.filter(
                        primary=True, user__in=admin_ids
                    ).values_list("email", flat=True)
                )
            if to_emails:
                msg = EmailMessage(
                    (
                        f"Routechoices.com - SOS from competitor {competitor.name}"
                        f" in event {event.name} [{now().isoformat()}]"
                    ),
                    (
                        f"Competitor {competitor.name} has triggered the SOS button"
                        f" of his GPS tracker during event {event.name}\r\n\r\n"
                        "His latest known location is latitude, longitude: "
                        f"{lat}, {lon}"
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    list(to_emails),
                )
                msg.send()
            all_to_emails = all_to_emails.union(to_emails)
        return self.aid, lat, lon, list(all_to_emails)


class DeviceArchiveReference(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    archive = models.OneToOneField(
        Device, related_name="original_ref", on_delete=models.CASCADE
    )
    original = models.ForeignKey(
        Device, related_name="archives_ref", on_delete=models.CASCADE
    )


class ImeiDevice(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    imei = models.CharField(
        max_length=32,
        unique=True,
        validators=[
            validate_imei,
        ],
        db_index=True,
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


class DeviceClubOwnership(models.Model):
    device = models.ForeignKey(
        Device, related_name="club_ownerships", on_delete=models.CASCADE
    )
    club = models.ForeignKey(
        Club, related_name="device_ownerships", on_delete=models.CASCADE
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    nickname = models.CharField(max_length=12, default="")

    class Meta:
        unique_together = (("device", "club"),)
        verbose_name = "Device ownership"
        verbose_name_plural = "Device ownerships"


class Competitor(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
        db_index=True,
    )
    event = models.ForeignKey(
        Event,
        related_name="competitors",
        on_delete=models.CASCADE,
        db_index=True,
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
        new_event = self.event
        new_event.invalidate_cache()
        current_self = None
        if self.pk:
            current_self = Competitor.objects.get(id=self.id)
            new_device = self.device
            new_start = self.start_time
            old_device = current_self.device
            old_start = current_self.start_time
            old_event = current_self.event
            # We proceed the future device before save so we can properly fetch
            # data as they are before update
            if new_device and new_device != old_device:
                if new_start != old_start:
                    from_time = min(old_start, new_start)
                    to_time = max(old_start, new_start)
                    events_between_old_and_new_starts = (
                        new_device.get_events_between_dates(from_time, to_time)
                    )
                    for event_in_range in events_between_old_and_new_starts:
                        event_in_range.invalidate_cache()
                else:
                    events_at_start = new_device.get_events_at_date(new_start)
                    for event_then in events_at_start:
                        event_then.invalidate_cache()
        super().save(*args, **kwargs)
        if current_self:
            if old_event != new_event:
                old_event.invalidate_cache()
            # We proceed the old device after save so we can properly fetch
            # data as they are after update
            if old_device:
                if new_start != old_start:
                    from_time = min(old_start, new_start)
                    to_time = max(old_start, new_start)
                    events_between_old_and_new_starts = (
                        old_device.get_events_between_dates(from_time, to_time)
                    )
                    for event_in_range in events_between_old_and_new_starts:
                        event_in_range.invalidate_cache()
                else:
                    events_at_start = old_device.get_events_at_date(new_start)
                    for event_then in events_at_start:
                        event_then.invalidate_cache()

    @property
    def start_datetime(self):
        from_date = self.event.start_date
        if self.start_time:
            from_date = self.start_time
        return from_date

    @property
    def started(self):
        return self.start_datetime > now()

    @property
    def end_datetime(self):
        from_date = self.start_datetime
        end_time = min(now(), self.event.end_date)
        next_competitor_start_time = (
            self.device.competitor_set.filter(
                start_time__gt=from_date, start_time__lt=end_time
            )
            .order_by("start_time")
            .values_list("start_time", flat=True)
            .first()
        )
        if next_competitor_start_time:
            end_time = next_competitor_start_time
        return end_time

    @cached_property
    def locations(self):
        if not self.device:
            return []
        locs, _ = self.device.get_locations_between_dates(
            self.start_datetime, self.end_datetime
        )
        return locs

    @property
    def encoded_data(self):
        result = gps_data_codec.encode(self.locations)
        return result

    @property
    def gpx(self):
        current_site = get_current_site()
        gpx = gpxpy.gpx.GPX()
        gpx.creator = current_site.name
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


@receiver([post_delete], sender=Competitor)
def invalidate_competitor_event_cache(sender, instance, **kwargs):
    instance.event.invalidate_cache()
    if instance.device:
        start_time = instance.start_time
        if not start_time:
            start_time = instance.event.start_date
        new_events_for_device = instance.device.get_events_at_date(start_time)
        for event in new_events_for_device:
            event.invalidate_cache()


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


class TcpDeviceCommand(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    target = models.ForeignKey(
        ImeiDevice, related_name="commands", on_delete=models.CASCADE
    )
    sent = models.BooleanField(default=False)
    command = models.TextField()

    class Meta:
        ordering = ["-modification_date"]
        verbose_name = "TCP Device command"
        verbose_name_plural = "TCP Devices commands"

    def __str__(self):
        return f"Command for imei {self.target}"


class IndividualDonator(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    upgraded = models.BooleanField(default=False)
    upgraded_date = models.DateTimeField(blank=True, null=True)
    order_id = models.CharField(max_length=200, blank=True, default="")

    def __str__(self):
        return self.name

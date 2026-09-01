import base64
import logging
import math
import os.path
import re
import socket
import time
import uuid
from datetime import timedelta
from io import BytesIO
from operator import itemgetter
from urllib.parse import urlparse
from zipfile import ZipFile

import cv2
import flag
import gps_data_codec
import gpxpy
import gpxpy.gpx
import magic
import numpy as np
import orjson as json
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import BadRequest, PermissionDenied, ValidationError
from django.core.files.base import ContentFile, File
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.core.validators import MaxValueValidator, MinValueValidator, validate_slug
from django.db import models
from django.db.models import Case, F, Max, Prefetch, Q, When
from django.db.models.functions import ExtractMonth, ExtractYear, Upper
from django.db.models.signals import post_delete, pre_delete, pre_save
from django.dispatch import receiver
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django_hosts.resolvers import reverse
from PIL import Image, ImageDraw, ImageFile
from shapely.geometry import LinearRing, Polygon
from staticmap import CircleMarker, StaticMap

from routechoices.lib import cache, plausible
from routechoices.lib.duration_constants import DURATION_ONE_MINUTE, DURATION_ONE_MONTH
from routechoices.lib.geojson import get_geojson_coordinates
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import (
    COUNTRIES,
    Point,
    Wgs84Coordinate,
    XYMeters,
    adjugate_matrix,
    avg_angles,
    calibration_string_from_wgs84_bound,
    country_code_at_coords,
    delete_domain,
    distance_between_locations,
    epoch_to_datetime,
    flatten,
    general_2d_projection,
    get_current_site,
    git_master_hash,
    gpsseuranta_encode_data,
    meters_to_wgs84,
    project,
    random_device_id,
    random_key,
    safe64encodedsha,
    short_random_key,
    short_random_slug,
    shortsafe64encodedsha,
    simplify_line,
    simplify_periods,
    time_base32,
    triangle_area,
    wgs84_to_meters,
)
from routechoices.lib.slippy_tiles import (
    latlon_to_tile_xy,
    tile_xy_to_north_west_latlon,
)
from routechoices.lib.storages import OverwriteImageStorage
from routechoices.lib.validators import (
    color_hex_validator,
    validate_calibration_string,
    validate_domain_name,
    validate_domain_slug,
    validate_emails,
    validate_imei,
    validate_latitude,
    validate_longitude,
    validate_nice_slug,
)

logger = logging.getLogger(__name__)

EVENT_CACHE_INTERVAL_LIVE = 5
EVENT_CACHE_INTERVAL_ARCHIVED = 7 * 24 * 3600

WEBP_MAX_SIZE = 16383

LOCATION_TIMESTAMP_INDEX = 0
LOCATION_LATITUDE_INDEX = 1
LOCATION_LONGITUDE_INDEX = 2

TOP_LEFT = 0
TOP_RIGHT = 1
BOTTOM_RIGHT = 2
BOTTOM_LEFT = 3

TAGS_SEPARATOR = "\u2063"

GLOBAL_MERCATOR = GlobalMercator()


class TooEarly(Exception):
    """Raised when an query is made too early."""


def list_events_sets(qs, decreasing_order=True):
    events_without_sets = qs.filter(event_set__isnull=True)
    order = "-start_date" if decreasing_order else "start_date"
    first_events_of_each_set = (
        qs.filter(event_set__isnull=False)
        .order_by("event_set_id", order)
        .distinct("event_set_id")
    )
    return list(
        events_without_sets.union(first_events_of_each_set)
        .order_by(order)
        .values_list("id", "event_set_id")
    )


def events_to_sets_for_type(
    first_event_of_each_set,
    type,
    club=None,
    selected_year=None,
    selected_month=None,
    search_text_query=None,
):
    event_ids = {e[0] for e in first_event_of_each_set}
    event_set_ids = {e[1] for e in first_event_of_each_set}

    event_list_by_set = {}
    if event_set_ids:
        all_events_with_set = (
            Event.objects.filter(event_set_id__in=event_set_ids, privacy=PRIVACY_PUBLIC)
            .select_related("event_set", "club", "map")
            .prefetch_related(
                Prefetch(
                    "competitors",
                    queryset=Competitor.objects.select_related("device").defer(
                        "device__locations_encoded"
                    ),
                )
            )
        )
        if not club:
            all_events_with_set = all_events_with_set.filter(featured=True)

        if type == "upcoming":
            all_events_with_set = (
                all_events_with_set.annotate(
                    visibility_date=Case(
                        When(visibility=VISIBILITY_REPLAY, then=F("end_date")),
                        default=F("start_date"),
                    )
                )
                .filter(
                    visibility_date__gt=now(),
                    visibility_date__lte=now() + timedelta(hours=24),
                )
                .order_by("visibility_date", "name")
            )

        elif type == "live":
            all_events_with_set = all_events_with_set.filter(
                start_date__lte=now(), end_date__gte=now()
            ).order_by("-start_date", "name")

        elif type == "closed":
            all_events_with_set = all_events_with_set.filter(end_date__lt=now())
            if selected_year:
                all_events_with_set = all_events_with_set.filter(
                    start_date__year=selected_year
                )
                if selected_month:
                    all_events_with_set = all_events_with_set.filter(
                        start_date__month=selected_month
                    )
            if search_text_query:
                all_events_with_set = all_events_with_set.filter(search_text_query)

            all_events_with_set = all_events_with_set.order_by("-start_date", "name")

        for event in all_events_with_set:
            event_list_by_set.setdefault(event.event_set_id, [])
            event_list_by_set[event.event_set_id].append(event)

    sets = []
    events = (
        Event.objects.filter(id__in=event_ids)
        .select_related("event_set", "event_set__club", "club", "map")
        .prefetch_related(
            Prefetch(
                "competitors",
                queryset=Competitor.objects.select_related("device").defer(
                    "device__locations_encoded"
                ),
            )
        )
    )
    for event in events:
        event_set = event.event_set
        if event.event_set is None:
            sets.append(
                {
                    "name": event.name,
                    "events": [
                        event,
                    ],
                    "fake": True,
                }
            )
        else:
            sets.append(
                {
                    "name": event_set.name,
                    "data": event_set,
                    "events": event_list_by_set[event_set.id],
                    "fake": False,
                }
            )
    return sets


class SomewhereOnEarth:
    def get_earth_coords(self):
        raise NotImplementedError("You must implement the get_earth_coords method")

    @property
    def country_code(self):
        if coords := self.earth_coords:
            return country_code_at_coords(Wgs84Coordinate(coords))
        return None

    @property
    def country_name(self):
        if cc := self.country_code:
            return COUNTRIES.get(cc, "")
        return "Unknown"

    @property
    def country_flag(self):
        if cc := self.country_code:
            return flag.flag(cc)
        return "🌍"


class GPSSeurantaClient:
    def connect(self):
        if not settings.GPSSEURANTA_SERVER_ADDR:
            return
        location = urlparse(settings.GPSSEURANTA_SERVER_ADDR)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((location.hostname, location.port))

    def send(self, device_id, locations):
        if not settings.GPSSEURANTA_SERVER_ADDR:
            return
        data_to_relay = gpsseuranta_encode_data(device_id, locations)
        attempt = 0
        while attempt < 2:
            attempt += 1
            try:
                self.socket.sendall(data_to_relay.encode("ascii"))
            except Exception:
                self.connect()
            else:
                break


gpsseuranta_client = GPSSeurantaClient()


def logo_upload_path(instance=None, file_name=None):
    tmp_path = ["logos"]
    time_hash = time_base32()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0].upper())
    tmp_path.append(basename[1].upper())
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


def banner_upload_path(instance=None, file_name=None):
    tmp_path = ["banners"]
    time_hash = time_base32()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0].upper())
    tmp_path.append(basename[1].upper())
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


def geojson_upload_path(instance=None, file_name=None):
    tmp_path = ["geojson"]
    time_hash = time_base32()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0].upper())
    tmp_path.append(basename[1].upper())
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
        editable=False,
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
            validate_domain_name,
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
    subscription_paused_at = models.DateTimeField(blank=True, null=True)

    forbid_invite_request = models.BooleanField(
        "Prevent external users from requesting admin rights", default=False
    )

    frontpage_featured = models.BooleanField("Featured on frontpage", default=False)

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
            models.Index("frontpage_featured", name="core_on_frontpage_idx"),
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

    def is_admin(self, user):
        return user.is_authenticated and self.admins.filter(id=user.id).exists()

    @property
    def free_trial_end(self):
        return self.creation_date + timedelta(days=2)

    @property
    def free_trial_active(self):
        return now() < self.free_trial_end

    @property
    def subscription_paused(self):
        return (
            self.subscription_paused_at is not None
            and self.subscription_paused_at < now()
        )

    @property
    def is_on_free_trial(self):
        return self.free_trial_active and not (
            self.upgraded and not self.subscription_paused
        )

    @property
    def can_modify_events(self):
        return self.free_trial_active or (
            self.upgraded and not self.subscription_paused
        )

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

    @cached_property
    def nice_url(self):
        if self.domain:
            return f"{self.url_protocol}://{self.domain}/"
        path = reverse(
            "club_view", host="clubs", host_kwargs={"club_slug": self.slug.lower()}
        )
        return f"{self.url_protocol}:{path}"

    def logo_scaled(self, width, ext="PNG"):
        if not self.logo:
            return None
        with self.logo.open("rb") as fp:
            logo_b = fp.read()
        logo = Image.open(BytesIO(logo_b))
        logo_squared = logo.resize((width, width), Image.BILINEAR)
        buffer = BytesIO()
        logo_squared.save(
            buffer,
            ext,
            optimize=True,
            quality=(40 if ext == "AVIF" else 80),
        )
        return buffer.getvalue()

    @property
    def logo_hash(self):
        if not self.logo:
            return safe64encodedsha(str(self.modification_date.timestamp()))
        return safe64encodedsha(self.logo.name)

    @property
    def logo_url(self):
        return f"{self.nice_url}logo?v={self.logo_hash}"

    @property
    def logo_url_www(self):
        return f"https:{reverse("site:landing_page", host="www")}{self.slug}/logo?v{self.logo_hash}"

    @property
    def banner_url(self):
        return f"{self.nice_url}banner?v={shortsafe64encodedsha(self.banner.name)}"

    def thumbnail(self, mime="image/jpeg"):
        cache_key = (
            f"club:{self.aid}:thumbnail:{self.modification_date.timestamp()}:{mime}"
        )
        if cached := cache.get(cache_key):
            return cached
        if not self.banner:
            img = Image.new("RGB", (1200, 630), "WHITE")
        else:
            banner = self.banner
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
            logo = Image.open("routechoices/assets/images/watermark.png")
        if logo:
            logo_f = logo.resize((250, 250), Image.LANCZOS)
            img.paste(logo_f, (int((1200 - 250) / 2), int((630 - 250) / 2)), logo_f)
        buffer = BytesIO()

        img.save(
            buffer,
            mime[6:].upper(),
            optimize=True,
            quality=(80 if mime == "image/jpeg" else 40),
        )
        data_out = buffer.getvalue()
        cache.set(cache_key, data_out, DURATION_ONE_MONTH)
        return data_out

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = Club.objects.filter(slug__iexact=self.slug)
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            raise ValidationError("Slug already used by another club.")


@receiver(pre_delete, sender=Club, dispatch_uid="club_delete_signal")
def delete_club_receiver(sender, instance, using, **kwargs):
    plausible.delete_domain(instance.analytics_domain)
    if instance.domain:
        delete_domain(instance.domain)


def can_user_create_club(user):
    user_free_clubs_count = Club.objects.filter(
        upgraded=False, admins__id=user.id
    ).count()
    return user_free_clubs_count == 0


User.add_to_class("can_create_club", property(can_user_create_club))


def map_upload_path(instance=None, file_name=None):
    tmp_path = ["maps"]
    time_hash = time_base32()
    basename = instance.aid + "_" + time_hash
    tmp_path.append(basename[0].upper())
    tmp_path.append(basename[1].upper())
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


NOT_CACHED_TILE = 0
CACHED_TILE = 1
CACHED_BLANK_TILE = 2


class Map(models.Model, SomewhereOnEarth):
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
        Club, related_name="maps", on_delete=models.CASCADE, editable=False
    )
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
    calibration_string_raw = models.CharField(
        max_length=255,
        help_text="Latitude and longitude of map corners separated by commas "
        "in following order Top Left, Top right, Bottom Right, Bottom left. "
        "eg: 60.519,22.078,60.518,22.115,60.491,22.112,60.492,22.073",
        validators=[validate_calibration_string],
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
        if not self.image:
            return None
        cache_key = f"map:{self.image.name}:data"
        if cached := cache.get(cache_key):
            return cached
        with self.image.open("rb") as fp:
            data = fp.read()
        cache.set(cache_key, data, DURATION_ONE_MONTH)
        return data

    @cached_property
    def quick_size(self):
        if self.width:
            return self.width, self.height
        p = ImageFile.Parser()
        p.feed(self.data)
        return p.image.size

    @property
    def mime_type(self):
        cache_key = f"map:{self.image.name}:mime"
        if cached := cache.get(cache_key):
            return cached
        with self.image.storage.open(self.image.name, mode="rb", nbytes=2048) as fp:
            data = fp.read()
        mime = magic.from_buffer(data, mime=True)
        cache.set(cache_key, mime, DURATION_ONE_MONTH)
        return mime

    @property
    def data_uri(self):
        if data := self.data:
            mime_type = magic.from_buffer(data, mime=True)
            return f"data:{mime_type};base64,{base64.b64encode(data).decode()}"
        return None

    @data_uri.setter
    def data_uri(self, value):
        if self.data_uri == value:
            return

        data_matched = re.match(
            r"^data:image/(?P<extension>jpeg|png|gif|webp);base64,"
            r"(?P<data_b64>(?:[A-Za-z0-9+/]{4})*"
            r"(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)$",
            value,
        )
        if not data_matched:
            raise ValueError(
                "Not a valid base64 encoded image data URI (jpeg, png, gif or webp)"
            )

        file = ContentFile(base64.b64decode(data_matched.group("data_b64")))
        with Image.open(file) as image:
            rgba_img = image.convert("RGBA")
            format = "WEBP"
            if max(rgba_img.size[0], rgba_img.size[1]) > WEBP_MAX_SIZE:
                format = "PNG"
            out_buffer = BytesIO()
            params = {
                "dpi": (72, 72),
            }
            if format == "WEBP":
                params["quality"] = 80
            rgba_img.save(out_buffer, format, optimize=True, **params)
            file_safe = File(out_buffer)
            self.image.save(
                f"{uuid.uuid4()}.{data_matched.group("extension")}",
                file_safe,
                save=False,
            )
            self.image.close()

    @property
    def cv2image(self):
        src_img = self.data
        src_mime = magic.from_buffer(src_img, mime=True)
        if src_mime == "image/gif":
            pil_img = Image.open(BytesIO(src_img)).convert("RGBA")
            cv2_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGRA)
        else:
            src_bytes = np.frombuffer(src_img, np.uint8)
            cv2_img_raw = cv2.imdecode(src_bytes, cv2.IMREAD_UNCHANGED)
            cv2_img = cv2.cvtColor(np.array(cv2_img_raw), cv2.COLOR_BGR2BGRA)
        return cv2_img

    def get_image_as_mime(self, mime):
        if mime[:6] != "image/":
            raise ValueError("Invalid mime type requested")
        file_path = self.image.name
        cache_key = f"map:image:{file_path}:mime:{mime}"

        if image := cache.get(cache_key):
            return image

        img_data = self.data
        pil_image = Image.open(BytesIO(img_data)).convert("RGBA")

        out_buffer = BytesIO()
        pil_image.save(
            out_buffer,
            mime[6:].upper(),
            optimize=True,
            quality=(40 if mime in ("image/webp", "image/avif") else 80),
        )
        image = out_buffer.getvalue()
        cache.set(cache_key, image, DURATION_ONE_MONTH)
        return image

    @property
    def hash(self):
        return shortsafe64encodedsha(f"{self.path}:{self.calibration_string_raw}")

    @property
    def calibration_values(self):
        return [float(x) for x in self.calibration_string_raw.split(",")]

    def get_calibration_string(self, separator="_", precision=5):
        return np.array2string(
            np.array(self.calibration_values), separator=separator, precision=precision
        )[1:-1]

    @property
    def bound(self):
        vals = self.calibration_values
        return [Wgs84Coordinate(vals[2 * i : 2 * i + 2]) for i in range(4)]

    @bound.setter
    def bound(self, value):
        self.calibration_string_raw = calibration_string_from_wgs84_bound(value)

    @property
    def bound_api(self):
        coords = self.calibration_values
        return {
            "top_left": {"lat": coords[0], "lon": coords[1]},
            "top_right": {"lat": coords[2], "lon": coords[3]},
            "bottom_right": {"lat": coords[4], "lon": coords[5]},
            "bottom_left": {"lat": coords[6], "lon": coords[7]},
        }

    @bound_api.setter
    def bound_api(self, value):
        wgs84_bound = [
            Wgs84Coordinate(value[corner]["lat"], value[corner]["lon"])
            for corner in ("top_left", "top_right", "bottom_right", "bottom_left")
        ]
        self.bound = wgs84_bound

    @property
    def size(self):
        width, height = self.quick_size
        return {"width": width, "height": height}

    @property
    def min_lon(self):
        return min(
            self.bound[TOP_LEFT].longitude,
            self.bound[BOTTOM_LEFT].longitude,
            self.bound[BOTTOM_RIGHT].longitude,
            self.bound[TOP_RIGHT].longitude,
        )

    @property
    def max_lon(self):
        return max(
            self.bound[TOP_LEFT].longitude,
            self.bound[BOTTOM_LEFT].longitude,
            self.bound[BOTTOM_RIGHT].longitude,
            self.bound[TOP_RIGHT].longitude,
        )

    @property
    def min_lat(self):
        return min(
            self.bound[TOP_LEFT].latitude,
            self.bound[BOTTOM_LEFT].latitude,
            self.bound[BOTTOM_RIGHT].latitude,
            self.bound[TOP_RIGHT].latitude,
        )

    @property
    def max_lat(self):
        return max(
            self.bound[TOP_LEFT].latitude,
            self.bound[BOTTOM_LEFT].latitude,
            self.bound[BOTTOM_RIGHT].latitude,
            self.bound[TOP_RIGHT].latitude,
        )

    @property
    def max_xy(self):
        return wgs84_to_meters(Wgs84Coordinate(self.max_lat, self.max_lon))

    @property
    def min_xy(self):
        return wgs84_to_meters(Wgs84Coordinate(self.min_lat, self.min_lon))

    @property
    def alignment_points(self):
        width, height = self.quick_size
        map_corners = (
            Point(0, 0),
            Point(0, height),
            Point(width, height),
            Point(width, 0),
        )
        map_corners_xy_meters = (
            wgs84_to_meters(self.bound[TOP_LEFT]),
            wgs84_to_meters(self.bound[BOTTOM_LEFT]),
            wgs84_to_meters(self.bound[BOTTOM_RIGHT]),
            wgs84_to_meters(self.bound[TOP_RIGHT]),
        )
        return map_corners, map_corners_xy_meters

    @property
    def matrix_3d(self):
        m = general_2d_projection(*self.alignment_points)
        for i in range(9):
            m[i] = m[i] / m[8]
        return m

    @property
    def matrix_3d_inverse(self):
        return adjugate_matrix(self.matrix_3d)

    @property
    def map_xy_to_spherical_mercator(self):
        return lambda xy: project(self.matrix_3d, Point(xy))

    @property
    def spherical_mercator_to_map_xy(self):
        return lambda xy: project(self.matrix_3d_inverse, Point(xy))

    def wsg84_to_map_xy(self, wgs84_coordinate, round_values=False):
        xy_meter = Wgs84Coordinate(wgs84_coordinate).xy_meters
        image_xy = self.spherical_mercator_to_map_xy(xy_meter)
        if round_values:
            return image_xy.round(5)
        return image_xy

    def map_xy_to_wsg84(self, xy):
        xy_meters = XYMeters(self.map_xy_to_spherical_mercator(Point(xy)))
        return xy_meters.wgs84_coordinate

    @property
    def center(self):
        width, height = self.quick_size
        return self.map_xy_to_wsg84((width / 2, height / 2))

    @property
    def earth_coords(self):
        center = self.center
        return [center.latitude, center.longitude]

    @cached_property
    def area(self):
        # Area in m^2
        tl, tr, bl, br = self.bound

        side_a = distance_between_locations(tl, tr)
        side_b = distance_between_locations(tr, br)
        side_c = distance_between_locations(br, bl)
        side_d = distance_between_locations(bl, tl)
        diagonal = distance_between_locations(tl, br)
        triangle_a = (side_a, side_b, diagonal)
        triangle_b = (side_c, side_d, diagonal)

        return triangle_area(triangle_a) + triangle_area(triangle_b)

    @cached_property
    def resolution(self):
        """Return map image resolution in meters/pixel."""
        width, height = self.quick_size
        return max(
            distance_between_locations(self.bound[0], self.bound[3]) / height,
            distance_between_locations(self.bound[0], self.bound[1]) / width,
        )

    @property
    def max_zoom(self):
        return math.ceil(
            math.log2(
                156543.03392804097
                * math.cos(self.center.latitude * math.pi / 180)
                / self.resolution
            )
        )

    @cached_property
    def rotation(self):
        tl, tr, br, bl = (corner.xy_meters for corner in self.bound)

        left_diff = Point(tl.x - bl.x, tl.y - bl.y)
        left_rot = (math.atan2(*left_diff.xy[::-1]) - math.pi / 2) * 180 / math.pi

        right_diff = Point(tr.x - br.x, tr.y - br.y)
        right_rot = (math.atan2(*right_diff.xy[::-1]) - math.pi / 2) * 180 / math.pi

        top_diff = Point(tr.x - tl.x, tr.y - tl.y)
        top_rot = (math.atan2(*top_diff.xy[::-1])) * 180 / math.pi

        bottom_diff = Point(br.x - bl.x, br.y - bl.y)
        bottom_rot = (math.atan2(*bottom_diff.xy[::-1])) * 180 / math.pi

        vertical_rot = (avg_angles(left_rot, right_rot)) % 360
        horizontal_rot = (avg_angles(top_rot, bottom_rot)) % 360
        return round(avg_angles(vertical_rot, horizontal_rot), 2)

    @property
    def north_declination(self):
        rot = self.rotation + 90
        if rot > 45:
            rot = (rot - 45) % 90 - 45
        return round(rot, 2)

    @property
    def tiled_kmz(self):
        min_lat = self.min_lat
        max_lat = self.max_lat

        min_lon = self.min_lon
        max_lon = self.max_lon

        zoom = self.max_zoom - 3

        min_x, min_y = latlon_to_tile_xy(max_lat, min_lon, zoom)
        max_x, max_y = latlon_to_tile_xy(min_lat, max_lon, zoom)

        kmz = BytesIO()
        with ZipFile(kmz, "w") as fp:
            tiles = []
            x = min_x
            while x <= max_x:
                y = min_y
                while y <= max_y:
                    max_lat, min_lon = tile_xy_to_north_west_latlon(x, y, zoom)
                    min_lat, max_lon = tile_xy_to_north_west_latlon(x + 1, y + 1, zoom)
                    min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                        {"lat": min_lat, "lon": min_lon}
                    )
                    max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                        {"lat": max_lat, "lon": max_lon}
                    )
                    bound_xy = {
                        "min_x": min_xy["x"],
                        "max_x": max_xy["x"],
                        "min_y": min_xy["y"],
                        "max_y": max_xy["y"],
                    }
                    bound_latlon = {
                        "min_lat": min_lat,
                        "max_lat": max_lat,
                        "min_lon": min_lon,
                        "max_lon": max_lon,
                    }
                    img_data, _ = self.get_tile(
                        256,
                        256,
                        "image/jpeg",
                        bound_xy["min_x"],
                        bound_xy["max_x"],
                        bound_xy["min_y"],
                        bound_xy["max_y"],
                    )
                    filename = f"files/img_{x}_{y}_{zoom}.jpeg"

                    tiles.append({"filename": filename, "bound": bound_latlon})
                    with fp.open(filename, "w") as tile_fp:
                        tile_fp.write(img_data)
                    y += 1
                x += 1
            doc_kml = render_to_string(
                "tiled_kml.xml",
                {"name": self.name, "tiles": tiles},
            )
            with fp.open("doc.kml", "w") as doc_fp:
                doc_fp.write(doc_kml.encode("utf-8"))
        return kmz.getvalue()

    @property
    def kmz(self):
        mime_type = "image/png"

        doc_img = self.get_image_as_mime(mime_type)
        extension = mime_type[6:]

        doc_kml = render_to_string(
            "kml.xml",
            {"name": self.name, "bound": self.bound_api, "extension": extension},
        )
        kmz = BytesIO()
        with ZipFile(kmz, "w") as fp:
            with fp.open("doc.kml", "w") as file1:
                file1.write(doc_kml.encode("utf-8"))
            with fp.open(f"files/doc.{extension}", "w") as file2:
                file2.write(doc_img)
        return kmz.getvalue()

    def get_tile_cache_key(
        self, output_width, output_height, img_mime, min_lon, max_lon, min_lat, max_lat
    ):
        return (
            f"map:{self.aid}:{self.hash}:tile:"
            f"{output_width}x{output_height}:"
            f"{min_lon},{max_lon},{min_lat},{max_lat}:"
            f"{img_mime}"
        )

    @classmethod
    def get_blank_tile(cls, output_width, output_height, img_mime, src_cache_key):
        cache_key = f"tile:blank:{output_width}x{output_height}:{img_mime}"
        if cached := cache.get(cache_key):
            return cached, CACHED_BLANK_TILE

        blank_image = Image.new(
            mode=("RGB" if img_mime == "image/jpeg" else "RGBA"),
            size=(output_height, output_width),
            color=((255, 255, 255) if img_mime == "image/jpeg" else (255, 255, 255, 0)),
        )
        buffer = BytesIO()
        blank_image.save(
            buffer,
            img_mime[6:].upper(),
            optimize=True,
            quality=10,
        )
        data_out = buffer.getvalue()

        cache.set(cache_key, data_out, DURATION_ONE_MONTH)

        return data_out, NOT_CACHED_TILE

    def get_tile(
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
        cache_key = self.get_tile_cache_key(
            output_width, output_height, img_mime, min_x, max_x, min_y, max_y
        )

        if cached := cache.get(cache_key):
            return cached, CACHED_TILE

        if not self.do_intersects_with_tile(min_x, max_x, min_y, max_y):
            # Out of map bounds, return blank tile
            tile, cache_status = self.get_blank_tile(
                output_width, output_height, img_mime, cache_key
            )
            cache.set(cache_key, tile, DURATION_ONE_MONTH)
            return tile, cache_status

        width, height = self.quick_size
        tl = self.map_xy_to_spherical_mercator((0, 0))
        tr = self.map_xy_to_spherical_mercator((width, 0))
        br = self.map_xy_to_spherical_mercator((width, height))
        bl = self.map_xy_to_spherical_mercator((0, height))

        p1 = np.float32(
            [
                [0, 0],
                [width, 0],
                [width, height],
                [0, height],
            ]
        )

        scale = 1
        while True:
            r_w = (max_x - min_x) / output_width / scale
            r_h = (max_y - min_y) / output_height / scale

            p2 = np.float32(
                [
                    [(tl.x - min_x) / r_w, (max_y - tl.y) / r_h],
                    [(tr.x - min_x) / r_w, (max_y - tr.y) / r_h],
                    [(br.x - min_x) / r_w, (max_y - br.y) / r_h],
                    [(bl.x - min_x) / r_w, (max_y - bl.y) / r_h],
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

        cv2_img = self.cv2image
        tile_img = cv2.warpPerspective(
            cv2_img,
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
        if img_mime == "image/avif":
            color_converted = cv2.cvtColor(tile_img, cv2.COLOR_BGRA2RGBA)
            pil_image = Image.fromarray(color_converted)
            buffer = BytesIO()
            pil_image.save(buffer, img_mime[6:].upper(), optimize=True, quality=40)
            data_out = buffer.getvalue()
        else:
            if img_mime == "image/webp":
                extra_args = [int(cv2.IMWRITE_WEBP_QUALITY), 40]
            elif img_mime == "image/jpeg":
                extra_args = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            _, buffer = cv2.imencode(f".{img_mime[6:]}", tile_img, extra_args)
            data_out = BytesIO(buffer).getvalue()

        cache.set(cache_key, data_out, DURATION_ONE_MONTH)

        return data_out, NOT_CACHED_TILE

    def do_intersects_with_tile(self, min_x, max_x, min_y, max_y):
        width, height = self.quick_size
        tile_bounds_poly = Polygon(
            LinearRing(
                (
                    (min_x, min_y),
                    (min_x, max_y),
                    (max_x, max_y),
                    (max_x, min_y),
                    (min_x, min_y),
                )
            )
        )
        map_bounds_poly = Polygon(
            LinearRing(
                (
                    self.map_xy_to_spherical_mercator((0, 0)).xy,
                    self.map_xy_to_spherical_mercator((0, height)).xy,
                    self.map_xy_to_spherical_mercator((width, height)).xy,
                    self.map_xy_to_spherical_mercator((width, 0)).xy,
                    self.map_xy_to_spherical_mercator((0, 0)).xy,
                )
            )
        )
        return tile_bounds_poly.intersects(map_bounds_poly)

    @classmethod
    def from_points(cls, seg, waypoints):

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

        tl_xy = wgs84_to_meters((max_lat, min_lon))
        tr_xy = wgs84_to_meters((max_lat, max_lon))
        br_xy = wgs84_to_meters((min_lat, max_lon))
        bl_xy = wgs84_to_meters((min_lat, min_lon))

        res_scale = 4
        MAX_SIZE = 4000
        offset = 100
        width = tr_xy.x - tl_xy.x
        height = tr_xy.y - br_xy.y

        scale = 1
        if width > MAX_SIZE or height > MAX_SIZE:
            scale = max(width, height) / MAX_SIZE

        width = (tr_xy.x - tl_xy.x) / scale + 2 * offset
        height = (tr_xy.y - br_xy.y) / scale + 2 * offset

        new_map = cls()
        new_map.bound = [
            meters_to_wgs84([tl_xy.x - offset * scale, tl_xy.y + offset * scale]),
            meters_to_wgs84([tr_xy.x + offset * scale, tr_xy.y + offset * scale]),
            meters_to_wgs84([br_xy.x + offset * scale, br_xy.y - offset * scale]),
            meters_to_wgs84([bl_xy.x - offset * scale, bl_xy.y - offset * scale]),
        ]

        im = Image.new(
            "RGBA",
            (int(width * res_scale), int(height * res_scale)),
            (255, 255, 255, 0),
        )
        new_map.width = int(width * res_scale)
        new_map.height = int(height * res_scale)
        draw = ImageDraw.Draw(im)
        for pts in seg:
            map_pts = simplify_line(
                [new_map.wsg84_to_map_xy(pt, round_values=True) for pt in pts]
            )
            draw.line(map_pts, (255, 255, 255, 200), 22 * res_scale, joint="curve")
            draw.line(map_pts, line_color, 16 * res_scale, joint="curve")
        for pt in waypoints:
            map_pt = new_map.wsg84_to_map_xy(pt, round_values=True)
            widths = [66, 63, 11, 8]
            thicknesses = [22, 16, 22, 16]
            fills = [
                (0, 0, 0, 0),
                None,
                None,
                line_color,
            ]
            colors = [
                (255, 255, 255, 200),
                line_color,
                (255, 255, 255, 200),
                line_color,
            ]

            for w, color, thickness, fill in zip(widths, colors, thicknesses, fills):
                wr = w * res_scale
                draw.ellipse(
                    (
                        map_pt.x - wr,
                        map_pt.y - wr,
                        map_pt.x + wr,
                        map_pt.y + wr,
                    ),
                    outline=color,
                    fill=fill,
                    width=int(thickness * res_scale),
                )

        im = im.resize((int(width), int(height)), resample=Image.Resampling.BICUBIC)
        out_buffer = BytesIO()
        im.save(out_buffer, "WEBP", dpi=(72, 72), optimize=True, quality=80)
        f_new = File(out_buffer)
        new_map.image.save(
            "filename",
            f_new,
            save=False,
        )
        return new_map

    def overlay(self, *other_maps):
        if not other_maps:
            return self
        width, height = self.quick_size
        new_image = Image.open(BytesIO(self.data)).convert("RGBA")
        for i, other_map in enumerate(other_maps):
            w, h = other_map.quick_size
            p1 = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

            bound = other_map.bound
            p2 = np.float32([self.wsg84_to_map_xy(bound[i]).xy for i in range(4)])

            coeffs = cv2.getPerspectiveTransform(p1, p2)

            src_data = other_map.data
            src_mime = magic.from_buffer(src_data, mime=True)
            if src_mime == "image/gif":
                pil_src_img = Image.open(BytesIO(src_data)).convert("RGBA")
                cv2_img = cv2.cvtColor(np.array(pil_src_img), cv2.COLOR_RGB2BGRA)
            else:
                img_bytes = np.frombuffer(src_data, np.uint8)
                cv2_img_raw = cv2.imdecode(img_bytes, cv2.IMREAD_UNCHANGED)
                cv2_img = cv2.cvtColor(np.array(cv2_img_raw), cv2.COLOR_BGR2BGRA)
            img_warped = cv2.warpPerspective(
                cv2_img,
                coeffs,
                (width, height),
                flags=cv2.INTER_AREA,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255, 0),
            )
            pil_img_warped = Image.fromarray(
                cv2.cvtColor(img_warped, cv2.COLOR_BGRA2RGBA)
            )
            new_image.alpha_composite(pil_img_warped, (0, 0))
        params = {
            "dpi": (72, 72),
            "quality": 40,
        }
        out_buffer = BytesIO()
        new_image.save(out_buffer, "WEBP", **params)
        out_file = ContentFile(out_buffer.getvalue())

        map_obj = Map(name=self.name)
        map_obj.image.save("imported_image", out_file, save=False)
        map_obj.width = width
        map_obj.height = height
        map_obj.calibration_string_raw = self.calibration_string_raw
        return map_obj

    def merge(self, *other_maps):
        if not other_maps:
            return self
        width, height = self.quick_size

        min_x = 0
        min_y = 0
        max_x = width
        max_y = height

        all_corners = []
        for i, other_map in enumerate(other_maps):
            bound = other_map.bound
            corners = [self.wsg84_to_map_xy(bound[i]) for i in range(4)]
            all_corners.append(corners)

        all_x = []
        all_y = []
        for corners in all_corners:
            for corner in corners:
                all_x.append(corner.x)
                all_y.append(corner.y)

        min_x = min(min_x, *all_x)
        min_y = min(min_y, *all_y)
        max_x = max(max_x, *all_x)
        max_y = max(max_y, *all_y)

        new_width = max_x - min_x
        new_height = max_y - min_y

        img = Image.open(BytesIO(self.data)).convert("RGBA")
        if new_width * new_height > Image.MAX_IMAGE_PIXELS:
            max_width = math.floor(Image.MAX_IMAGE_PIXELS / new_height)
            scale = max_width / new_width

            w = width * scale
            h = height * scale
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            out_buffer = BytesIO()
            img.save(out_buffer, "WEBP")
            out_file = ContentFile(out_buffer.getvalue())

            map_obj = Map(name=self.name)
            map_obj.image.save("imported_image", out_file, save=False)
            map_obj.width = w
            map_obj.height = h
            map_obj.calibration_string_raw = self.calibration_string_raw
            return map_obj.merge(*other_maps)

        new_image = Image.new(
            mode="RGBA", size=(int(new_width), int(new_height)), color=(0, 0, 0, 0)
        )
        new_image.alpha_composite(img, (round(-min_x), round(-min_y)))

        params = {
            "dpi": (72, 72),
            "quality": 40,
        }
        out_buffer = BytesIO()
        new_image.save(out_buffer, "WEBP", **params)
        out_file = ContentFile(out_buffer.getvalue())

        map_obj = Map(name=self.name)
        map_obj.image.save("imported_image", out_file, save=False)
        map_obj.width = new_image.width
        map_obj.height = new_image.height
        map_obj.bound = (
            self.map_xy_to_wsg84((min_x, min_y)),
            self.map_xy_to_wsg84((max_x, min_y)),
            self.map_xy_to_wsg84((max_x, max_y)),
            self.map_xy_to_wsg84((min_x, max_y)),
        )
        return map_obj.overlay(*other_maps)


PRIVACY_PUBLIC = "public"
PRIVACY_SECRET = "secret"
PRIVACY_PRIVATE = "private"
PRIVACY_CHOICES = (
    (PRIVACY_PUBLIC, "Published"),
    (PRIVACY_SECRET, "Secret"),
    (PRIVACY_PRIVATE, "Staff Only"),
)


VISIBILITY_LIVE = "live"
VISIBILITY_PREVIEW = "preview"
VISIBILITY_REPLAY = "replay"
VISIBILITY_CHOICES = (
    (VISIBILITY_LIVE, "From start date"),
    (VISIBILITY_REPLAY, "After completion"),
    (VISIBILITY_PREVIEW, "Always available"),
)


MAP_BLANK = "blank"
MAP_OSM = "osm"
MAP_GOOGLE_STREET = "gmap-street"
MAP_GOOGLE_SAT = "gmap-hybrid"
MAP_GOOGLE_TERRAIN = "gmap-terrain"
MAP_MAPANT_CH = "mapant-ch"
MAP_MAPANT_EE = "mapant-ee"
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
    (MAP_MAPANT_EE, "Mapant Estonia"),
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


class EventSet(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
        db_index=True,
    )
    external_id = models.CharField(
        max_length=128,
        editable=False,
        blank=True,
        default="",
        null=False,
        db_index=True,
    )
    external_metadata = models.JSONField(editable=False, null=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
        Club,
        verbose_name="Club",
        related_name="event_sets",
        on_delete=models.CASCADE,
        editable=False,
    )
    name = models.CharField(verbose_name="Name", max_length=255)
    create_page = models.BooleanField(
        default=False,
        help_text="Creates a page with all the events of the bundle listed",
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
    list_secret_events = models.BooleanField(default=False)
    description = models.TextField(
        blank=True,
        default="",
        help_text=("Text displayed on the page, use markdown formatting"),
    )

    def save(self, *args, **kwargs):
        if not self.create_page:
            self.slug = ""
            self.list_secret_events = False
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-creation_date", "name"]
        constraints = [
            models.UniqueConstraint(
                name="event_set_name_club_uc", fields=("name", "club")
            )
        ]
        verbose_name = "Bundle"

    def __str__(self):
        return self.name

    @property
    def url(self):
        if self.create_page:
            return f"{self.club.nice_url}{self.slug}"
        return ""

    def can_edit(self, user=None):
        return not self.external_id

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

    def events_to_sets_for_type(self, events, event_type):
        if event_type == "live":
            events = events.filter(start_date__lte=now(), end_date__gte=now()).order_by(
                "-start_date", "name"
            )

        elif event_type == "upcoming":
            events = events.filter(start_date__gt=now()).order_by(
                "visibility_date", "name"
            )

        elif event_type == "closed":
            events = events.filter(end_date__lt=now()).order_by("-start_date", "name")

        events = events.all()
        if not events:
            return []
        sets = [
            {
                "name": self.name,
                "events": events,
                "fake": False,
            }
        ]
        return sets

    def extract_event_lists(self, request):
        events_in_set = self.events.select_related(
            "event_set", "event_set__club", "club", "map"
        ).prefetch_related(
            Prefetch(
                "competitors",
                queryset=Competitor.objects.select_related("device").defer(
                    "device__locations_encoded"
                ),
            )
        )
        if self.list_secret_events:
            event_in_set = events_in_set.exclude(privacy=PRIVACY_PRIVATE)
        else:
            event_in_set = events_in_set.filter(privacy=PRIVACY_PUBLIC)

        closed_events = event_in_set.filter(end_date__lt=now())
        live_events = event_in_set.filter(start_date__lte=now(), end_date__gte=now())
        upcoming_events = event_in_set.annotate(
            visibility_date=Case(
                When(visibility=VISIBILITY_REPLAY, then=F("end_date")),
                default=F("start_date"),
            )
        ).filter(visibility_date__gt=now())

        closed_events = self.events_to_sets_for_type(closed_events, "closed")
        live_events = self.events_to_sets_for_type(live_events, "live")
        upcoming_events = self.events_to_sets_for_type(upcoming_events, "upcoming")

        return {
            "event_set": self,
            "event_set_page": True,
            "club": self.club,
            "events": closed_events,
            "live_events": live_events,
            "upcoming_events": upcoming_events,
            "years": [],
            "months": [],
            "year": None,
            "month": None,
            "search_text": None,
            "month_names": [],
        }


class Event(models.Model, SomewhereOnEarth):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
        db_index=True,
    )
    external_id = models.CharField(
        max_length=128,
        editable=False,
        blank=True,
        default="",
        null=False,
        db_index=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
        Club,
        verbose_name="Club",
        related_name="events",
        on_delete=models.CASCADE,
        editable=False,
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
    start_date = models.DateTimeField(
        verbose_name="Start Date",
        db_index=True,
    )
    end_date = models.DateTimeField(
        verbose_name="Closing Date",
    )
    privacy = models.CharField(
        max_length=8,
        choices=PRIVACY_CHOICES,
        default=PRIVACY_PUBLIC,
        verbose_name="Visibility",
        help_text=(
            "Controls how we show the event, if it is published on our pages, or if it is kept secret while accessible to all, or if it is accessible only to its authenticated club staff members."
        ),
    )
    visibility = models.CharField(
        max_length=8,
        verbose_name="Availability",
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_LIVE,
        help_text=("Controls when this event becomes visible to users."),
    )
    featured = models.BooleanField(
        "Featured",
        default=False,
    )
    backdrop_map = models.CharField(
        verbose_name="Background map",
        max_length=16,
        choices=MAP_CHOICES,
        default=MAP_BLANK,
    )
    map = models.ForeignKey(
        Map,
        verbose_name="Default map",
        related_name="events_main_map",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    map_title = models.CharField(
        verbose_name="Default map title",
        max_length=255,
        blank=True,
        default="",
        help_text="Leave blank if not using extra maps",
    )
    map_tags = models.CharField(
        verbose_name="Default map categories",
        max_length=256,
        blank=True,
        default="",
    )
    extra_maps = models.ManyToManyField(
        Map,
        through="MapAssignation",
        related_name="+",
        through_fields=("event", "map"),
    )
    open_registration = models.BooleanField(
        default=False,
        help_text="Allow anyone to register themselves as participants of this event.",
    )
    acceptable_tags = models.CharField(
        verbose_name="Participants accepted categories upon registration",
        max_length=256,
        blank=True,
        default="",
    )
    allow_route_upload = models.BooleanField(
        default=False,
        help_text="Allows the registered participants to upload their GPS file.",
    )
    send_interval = models.PositiveIntegerField(
        "Live upload interval (seconds)",
        default=5,
        help_text=(
            "If using live GPS trackers, enter here the upload "
            "interval setting of your devices, when using one of the "
            "official app, leave the value at 5 seconds"
        ),
        validators=[MinValueValidator(1)],
    )
    tail_length = models.PositiveIntegerField(
        "Tail length (seconds)",
        default=60,
        help_text=(
            "Set the length of the tails displayed on the map when user open the event page."
        ),
    )
    event_set = models.ForeignKey(
        EventSet,
        verbose_name="bundle",
        null=True,
        blank=True,
        related_name="events",
        on_delete=models.SET_NULL,
        help_text=("Event within the same bundle are listed together on our pages."),
    )
    emergency_contacts = models.TextField(
        default="",
        blank=True,
        help_text=(
            "Email addresses of people that will be contacted if a runner "
            "carrying a GPS tracker triggers an SOS signal. (Device specific feature)"
        ),
        validators=[validate_emails],
    )
    geojson_layer = models.FileField(
        "GeoJSON Layer",
        upload_to=geojson_upload_path,
        null=True,
        blank=True,
        help_text='A <a href="//www.routechoices.com/guide/geojson" target="_blank" rel="nofollow noopener">GeoJSON CSS</a> file.',
        storage=OverwriteImageStorage(aws_s3_bucket_name=settings.AWS_S3_BUCKET),
    )

    class Meta:
        ordering = ["-start_date", "name"]
        verbose_name = "event"
        verbose_name_plural = "events"
        indexes = [
            models.Index(
                Upper("slug"),
                name="core_event_slug_upper_idx",
            ),
            models.Index(
                "privacy",
                "featured",
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
                "featured",
                "end_date",
                name="core_event_listing_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(backdrop_map__in=next(zip(*MAP_CHOICES))),
                name="%(app_label)s_%(class)s_bgmap_valid",
            ),
            models.UniqueConstraint(
                name="event_name_event_set_club_uc",
                fields=("club", "event_set", "name"),
            ),
            models.UniqueConstraint(name="event_slug_club_uc", fields=("club", "slug")),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from routechoices.lib.rastilippu import RASTILIPPU_PREFIX

        if self.privacy != PRIVACY_PUBLIC:
            self.featured = False

        send_to_rastilippu = False
        if self.external_id.startswith(RASTILIPPU_PREFIX) and self.pk:
            original = Event.objects.get(id=self.pk)
            if original.map_id != self.map_id:
                send_to_rastilippu = True

        self.invalidate_cache()
        super().save(*args, **kwargs)
        if send_to_rastilippu:
            from .bg_tasks import rastilippu_update_event_url

            rastilippu_update_event_url(self.id)

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = EventSet.objects.filter(club_id=self.club_id, slug__iexact=self.slug)
        if qs.exists():
            raise ValidationError("A Bundle with this URL already exists.")

    def can_edit(self, user=None):
        return not self.external_id

    def could_display_maps(self, user=None):
        t = now()
        return bool(
            (
                user
                and user.is_authenticated
                and self.club.admins.filter(id=user.id).exists()
            )
            or self.visibility == VISIBILITY_PREVIEW
            or (self.visibility == VISIBILITY_LIVE and self.start_date < t)
            or (self.visibility == VISIBILITY_REPLAY and self.end_date < t)
        )

    def can_display_maps(self):
        return self.could_display_maps() and self.map

    def check_user_permission(self, user):
        if self.privacy == PRIVACY_PRIVATE and (
            not user.is_authenticated
            or not self.club.admins.filter(id=user.id).exists()
        ):
            raise PermissionDenied

    @property
    def acceptable_categories(self):
        if not self.acceptable_tags:
            return []
        return self.acceptable_tags.split(TAGS_SEPARATOR)

    def map_categories(self, idx=0):
        if idx == 0:
            if not self.map or not self.map_tags:
                return []
            return self.map_tags.split(TAGS_SEPARATOR)
        elif idx > 0:
            extra_map = self.map_assignations.all()[idx - 1]
            if not extra_map.tags:
                return []
            return extra_map.tags.split(TAGS_SEPARATOR)

    def enumerate_maps(self):
        if self.map:
            yield (self.map, self.map_title, self.map_tags)
            for i, other_map in enumerate(self.map_assignations.all()):
                yield (other_map.map, other_map.title, other_map.tags)

    @cached_property
    def categories(self):
        if self.pk:
            tags = set(self.competitors.exclude(tags="").values_list("tags", flat=True))
            return sorted(set(flatten([tag.split(TAGS_SEPARATOR) for tag in tags])))
        return []

    def get_competitors_in_category(self, category):
        filter_regex = rf"^([^{TAGS_SEPARATOR}]+{TAGS_SEPARATOR})?"
        filter_regex += re.escape(category)
        filter_regex += rf"$({TAGS_SEPARATOR}[^{TAGS_SEPARATOR}]+)?"
        return self.competitors.filter(tags__iregex=filter_regex)

    @classmethod
    def get_by_url(cls, url):
        if url.startswith(settings.SHORTCUT_URL):
            url = url[len(settings.SHORTCUT_URL) :]
            o = urlparse(url)
            club_slug, slug = o.path.split("/", 1)
            filters = {"slug": slug, "club__slug": club_slug}
        else:
            o = urlparse(url)
            domain = o.netloc
            filters = {"slug": o.path[1:]}
            if domain.endswith(f".{settings.PARENT_HOST}"):
                filters["club__slug"] = domain[: -len(f".{settings.PARENT_HOST}")]
            else:
                filters["club__domain"] = domain
        return cls.objects.filter(**filters).first()

    def iterate_competitors(self, category=None):
        if category is None:
            competitors = (
                self.competitors.select_related("device")
                .all()
                .order_by("start_time", "name")
            )
        else:
            competitors = (
                self.get_competitors_in_category(category)
                .select_related("device")
                .order_by("start_time", "name")
            )
        # We need this to determine the end time of each of this event's competitors
        # For each devices used in the event we fetch all the competitors that starts during this event's span
        # We order the device's competitors by their start time
        # We then pick and for each of this event competitor the other competitor that comes after its own start time
        max_end_date = min(self.end_date, now())
        devices_used = (
            competitor.device_id for competitor in competitors if competitor.device_id
        )
        competitors_for_devices_during_event = (
            Competitor.objects.filter(
                start_time__gte=self.start_date,
                start_time__lte=max_end_date,
                device_id__in=devices_used,
            )
            .only("device_id", "start_time")
            .order_by("start_time")
        )
        start_times_by_device = {}
        for competitor in competitors_for_devices_during_event:
            start_times_by_device.setdefault(competitor.device_id, [])
            start_times_by_device[competitor.device_id].append(competitor.start_time)

        for competitor in competitors:
            from_date = competitor.start_time
            end_date = max_end_date
            if competitor.device_id:
                for start_time in start_times_by_device.get(competitor.device_id, []):
                    if from_date < start_time < end_date:
                        end_date = start_time
                        break
            yield (competitor, from_date, end_date)

    @classmethod
    def get_map_at_index(cls, user, event_id, map_index, load_competitors=False):
        """map_index is 1 based"""
        event_qs = cls.objects.all().select_related("club")

        extra_query = (
            Q(visibility=VISIBILITY_PREVIEW)
            | Q(visibility=VISIBILITY_LIVE, start_date__lt=now())
            | Q(visibility=VISIBILITY_REPLAY, end_date__lt=now())
        )
        if user and user.is_authenticated:
            extra_query |= Q(club__in=user.club_set.all())

        event_qs = event_qs.filter(extra_query)

        if load_competitors:
            event_qs = event_qs.prefetch_related(
                "competitors",
            )
        try:
            map_index = int(map_index)
            if map_index <= 0:
                raise ValueError()
        except Exception:
            raise Http404()

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
            or (map_index > 0 and map_index > event.map_assignations.count())
        ):
            raise Http404

        event.check_user_permission(user)
        assignation = None
        if map_index == 0:
            raster_map = event.map
            title = event.map_title or "Main map"
        else:
            assignation = event.map_assignations.all()[map_index - 1]
            raster_map = assignation.map
            title = assignation.title
        return event, raster_map, title, assignation

    @classmethod
    def extract_event_lists(cls, request, club=None):
        page = request.GET.get("page")
        selected_year = request.GET.get("year")
        selected_month = request.GET.get("month")
        search_text_raw = request.GET.get("q", "").strip()

        event_qs = cls.objects.filter(privacy=PRIVACY_PUBLIC)

        if club is None:
            event_qs = event_qs.filter(featured=True)
        else:
            event_qs = event_qs.filter(club=club)

        closed_events_qs = event_qs.filter(end_date__lt=now())

        search_text_query = Q()
        if search_text_raw:
            search_text = search_text_raw
            quoted_terms = re.findall(r"\"(.+?)\"", search_text)
            if quoted_terms:
                search_text = re.sub(r"\"(.+?)\"", "", search_text)
            search_terms = search_text.split(TAGS_SEPARATOR)
            for search_term in search_terms + quoted_terms:
                key_name = "name__icontains"
                key_club_name = "club__name__icontains"
                key_set_name = "event_set__name__icontains"
                search_text_query &= (
                    Q(**{key_name: search_term})
                    | Q(**{key_club_name: search_term})
                    | Q(**{key_set_name: search_term})
                )
            closed_events_qs = closed_events_qs.filter(search_text_query)

        months = None
        years = list(
            closed_events_qs.annotate(year=ExtractYear("start_date"))
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
            closed_events_qs = closed_events_qs.filter(start_date__year=selected_year)
            months = list(
                closed_events_qs.annotate(month=ExtractMonth("start_date"))
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
                closed_events_qs = closed_events_qs.filter(
                    start_date__month=selected_month
                )

        all_closed_event_sets = list_events_sets(closed_events_qs)
        paginator = Paginator(all_closed_event_sets, 25)
        closed_events_page = paginator.get_page(page)

        closed_events_sets = events_to_sets_for_type(
            closed_events_page.object_list,
            club=club,
            type="closed",
            selected_year=selected_year,
            selected_month=selected_month,
            search_text_query=search_text_query,
        )

        if closed_events_page.number == 1 and not selected_year and not search_text_raw:
            live_events_qs = event_qs.filter(
                start_date__lte=now(), end_date__gte=now()
            ).exclude(visibility=VISIBILITY_REPLAY)

            upcoming_events_qs = (
                event_qs.annotate(
                    visibility_date=Case(
                        When(visibility=VISIBILITY_REPLAY, then=F("end_date")),
                        default=F("start_date"),
                    )
                )
                .filter(
                    visibility_date__gt=now(),
                    visibility_date__lte=now() + timedelta(hours=24),
                )
                .order_by("visibility_date", "name")
            )

            all_live_events = list_events_sets(live_events_qs)
            live_events = events_to_sets_for_type(
                all_live_events, type="live", club=club
            )

            all_upcoming_events = list_events_sets(upcoming_events_qs, False)
            upcoming_events = events_to_sets_for_type(
                all_upcoming_events, type="upcoming", club=club
            )
        else:
            live_events = upcoming_events = cls.objects.none()

        return {
            "club": club,
            "events": closed_events_sets,
            "events_page": closed_events_page,
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

    @property
    def map_upload_url(self):
        return reverse(
            "dashboard_club:event:map_edit_view",
            host="dashboard",
            kwargs={"event_id": self.aid, "club_slug": self.club.slug},
            scheme="https",
        )

    def get_absolute_url(self):
        return f"{self.club.nice_url}{self.slug}"

    def get_absolute_map_url(self):
        return f"{self.club.nice_url}{self.slug}/map"

    def get_geojson_url(self):
        return (
            reverse(
                "event_geojson_download",
                host="api",
                kwargs={"event_id": self.aid},
            )
            + f"?v={shortsafe64encodedsha(self.geojson_layer.name)}"
        )

    def get_absolute_export_url(self):
        return f"{self.club.nice_url}{self.slug}/export"

    def get_api_detail_url(self):
        return reverse("event_detail", host="api", kwargs={"event_id": self.aid})

    def get_api_data_url(self):
        return reverse("event_data", host="api", kwargs={"event_id": self.aid})

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

    def invalidate_cache(self):
        t0 = time.time()
        for cache_suffix in ("live", "archived"):
            cache_ts = int(
                t0
                // (
                    EVENT_CACHE_INTERVAL_LIVE
                    if cache_suffix == "live"
                    else EVENT_CACHE_INTERVAL_ARCHIVED
                )
            )
            for offset in range(0, -2, -1):
                for tag in self.categories + [""]:
                    cache_key = f"event:{self.aid}:tag:{tag}:data:{cache_ts + offset}:{cache_suffix}"
                cache.delete(cache_key)
        cache.set(
            f"event:{self.aid}:is_public",
            self.privacy != PRIVACY_PRIVATE,
            DURATION_ONE_MONTH,
        )

    @property
    def has_notice(self):
        return hasattr(self, "notice")

    def get_featured_image(self):
        if self.can_display_maps():
            raster_map = self.map
            cache_key = f"event:{self.aid}:map:{raster_map.hash}"
            if cached := cache.get(cache_key):
                return cached
            orig = raster_map.data
            img = Image.open(BytesIO(orig)).convert("RGBA")
            white_bg_img = Image.new("RGBA", img.size, "WHITE")
            white_bg_img.paste(img, (0, 0), img)
            img = white_bg_img.convert("RGB")
            rot = (math.floor((raster_map.rotation + 45) / 90)) % 4
            img_width, img_height = img.size
            if rot in (1, 3):
                h = int(img_height / 3)
                w = h * 21 / 40
            else:
                w = int(img_width / 3)
                h = w * 21 / 40

            t = (
                int(img_width / 2) - w,
                int(img_height / 2) - h,
                int(img_width / 2) - w,
                int(img_height / 2) + h,
                int(img_width / 2) + w,
                int(img_height / 2) + h,
                int(img_width / 2) + w,
                int(img_height / 2) - h,
            )
            t = t[(-2 * rot) :] + t[: (-2 * rot)]

            img = img.transform(
                (1200, 630),
                Image.QUAD,
                t,
            )
            cache.set(cache_key, img, DURATION_ONE_MONTH)
            return img

        if center := self.earth_coords:
            cache_key = f"coords_map:{center[0]}-{center[1]}"
            if cached := cache.get(cache_key):
                return cached
            raster_map = StaticMap(
                1200,
                630,
                10,
                url_template=settings.THUMBNAIL_URL_TEMPLATE,
                headers={
                    "User-Agent": f"Routechoices Live GPS Server {git_master_hash()} (https://www.routechoices.com; contact@routechoices.com)",
                    "X-Requested-With": "StaticMap",
                },
            )
            marker = CircleMarker((float(center[1]), float(center[0])), "#00000000", 10)
            raster_map.add_marker(marker)
            img = raster_map.render(zoom=13)
            cache.set(cache_key, img, DURATION_ONE_MONTH)
            return img

        return Image.new("RGB", (1200, 630), "WHITE")

    def thumbnail(self, display_logo, mime="image/jpeg"):
        image_key = "blank"
        if self.can_display_maps():
            image_key = f"map:{self.map.hash}"
        elif center := self.earth_coords:
            image_key = f"coords:{center[0]}-{center[1]}"

        logo_key = "without_logo"
        if display_logo:
            logo_key = f"logo:{self.club.modification_date.timestamp()}"

        cache_key = f"event:{self.aid}:thumbnail:{image_key}:{logo_key}:{mime}"
        if cached := cache.get(cache_key):
            return cached

        img = self.get_featured_image()

        if display_logo:
            logo = None
            if self.club.logo:
                logo_b = self.club.logo.open("rb").read()
                logo = Image.open(BytesIO(logo_b))
            elif not self.club.domain:
                logo = Image.open("routechoices/assets/images/watermark.png")
            if logo:
                logo_f = logo.resize((250, 250), Image.LANCZOS)
                img.paste(logo_f, (int((1200 - 250) / 2), int((630 - 250) / 2)), logo_f)
        buffer = BytesIO()
        img.save(
            buffer,
            mime[6:].upper(),
            optimize=True,
            quality=(40 if mime in ("image/webp", "image/avif") else 80),
        )

        data_out = buffer.getvalue()
        cache.set(cache_key, data_out, DURATION_ONE_MONTH)

        return data_out

    @property
    def earth_coords(self):
        if self.map:
            return self.map.earth_coords
        if self.geojson_layer:
            cache_key = f"geojson:{self.geojson_layer.name}:coords"
            if cached := cache.get(cache_key):
                return cached
            if geojson_raw := self.geojson_layer.read():
                geojson = json.loads(geojson_raw)
                if pt := get_geojson_coordinates(geojson):
                    coords = [pt[1], pt[0]]
                    cache.set(cache_key, coords, DURATION_ONE_MONTH)
                    return coords

        sample_competitors = self.competitors.all()
        for competitor in sample_competitors:
            if (device := competitor.device) and device._location_count != 0:
                return [
                    device._last_location_latitude,
                    device._last_location_longitude,
                ]
        return None

    @classmethod
    def get_current_data(cls, event_id, tag, viewer):
        """Return event data at current time, alond with cache_status"""
        event = None
        # check if event is public, if not do the checks
        is_public_cache_key = f"event:{event_id}:is_public"
        if (is_public := cache.get(is_public_cache_key)) is None:
            event = Event.objects.select_related("club").get(aid=event_id)
            is_public = event.privacy != PRIVACY_PRIVATE
            cache.set(is_public_cache_key, is_public, DURATION_ONE_MONTH)
        if not is_public:
            if not event:
                event = Event.objects.select_related("club").get(aid=event_id)
            event.check_user_permission(viewer)

        # permissions are checked, check for cache
        t0 = time.time()
        cache_ts = int(t0 // EVENT_CACHE_INTERVAL_LIVE)
        cache_key = f"event:{event_id}:tag:{tag or ""}:data:{cache_ts}:live"
        if data := cache.get(cache_key):
            return data, True, is_public
            cache_ts = int(t0 // EVENT_CACHE_INTERVAL_LIVE)

        if not event:
            event = Event.objects.select_related("club").get(aid=event_id)

        if event.start_date > now() or not event.could_display_maps():
            raise TooEarly()

        if not event.is_live:
            cache_ts = int(t0 // EVENT_CACHE_INTERVAL_ARCHIVED)
            cache_key = f"event:{event_id}:tag:{tag or ""}:data:{cache_ts}:archived"
            if data := cache.get(cache_key):
                return data, True, is_public

        # No cache, fetch the data
        total_nb_pts = 0
        competitors_data = []
        for competitor, from_date, end_date in event.iterate_competitors(tag):
            encoded_data = ""
            if competitor.device_id:
                encoded_data, nb_pts = competitor.device.get_locations_between_dates(
                    from_date, end_date, encode=True
                )
                total_nb_pts += nb_pts
            competitor_data = {
                "id": competitor.aid,
                "encoded_data": encoded_data,
                "name": competitor.name,
                "short_name": competitor.short_name,
                "start_time": competitor.start_time,
            }
            if competitor.tags:
                competitor_data["categories"] = competitor.categories
            if competitor.color:
                competitor_data["color"] = competitor.color
            if event.is_live and competitor.device_id:
                competitor_data["battery_level"] = competitor.device.battery_level
            competitors_data.append(competitor_data)

        response = {"competitors": competitors_data}
        if event.is_live:
            response["next"] = reverse(
                "event_data_delta",
                host="api",
                kwargs={"event_id": event.aid, "previous_key": cache_ts},
            )

        cache_duration = DURATION_ONE_MINUTE + (
            EVENT_CACHE_INTERVAL_LIVE
            if event.is_live
            else EVENT_CACHE_INTERVAL_ARCHIVED
        )
        cache.set(cache_key, response, cache_duration)
        return response, False, is_public


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
    tags = models.CharField(
        verbose_name="Categories",
        max_length=256,
        blank=True,
        default="",
    )

    @property
    def categories(self):
        if not self.tags:
            return []
        return self.tags.split(TAGS_SEPARATOR)

    class Meta:
        ordering = ["id"]


class Device(models.Model, SomewhereOnEarth):
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
    virtual = models.BooleanField(default=False, editable=False)
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
    gpsseuranta_known = models.BooleanField(default=False)
    gpsseuranta_relay_until = models.DateTimeField(null=True, blank=True)

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
        verbose_name = "GPS device"
        verbose_name_plural = "GPS devices"

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
        if owner and owner.nickname:
            return f"@ {owner.nickname}{' (Archive)' if original_device else ''}"
        if original_device:
            return "Live Data Archive"
        if self.virtual:
            return "GPS File"
        else:
            return f"{device.aid}"

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
    def locations(self):
        if not self.locations_encoded:
            return []
        return gps_data_codec.decode(self.locations_encoded)

    def erase_locations(self):
        self.locations_encoded = ""
        self._last_location_datetime = None
        self._last_location_latitude = None
        self._last_location_longitude = None
        self._location_count = 0

    def update_cached_data(self):
        self._location_count = self.location_count
        if self._location_count > 0:
            last_loc = gps_data_codec.decode_last_location(self.locations_encoded)
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
        from_ts = round(from_date.timestamp())
        end_ts = round(end_date.timestamp())

        encoded, nb_pts = gps_data_codec.extract_encoded_interval(
            self.locations_encoded, from_ts, end_ts
        )
        if encode:
            return encoded, nb_pts

        if not encoded:
            return [], 0
        return gps_data_codec.decode(encoded), nb_pts

    def get_active_periods(self):
        periods_used = []
        competitors = self.competitor_set.all()
        for competitor in competitors:
            event = competitor.event
            start = event.start_date
            if competitor.start_time:
                start = competitor.start_time
            periods_used.append((start, event.end_date))
        return simplify_periods(periods_used)

    def remove_unused_location(self, /, *, until, save=False):
        location_count = self.location_count
        if location_count == 0:
            return
        periods_used = [(until, max(now(), self.last_location_datetime))]
        periods_used += self.get_active_periods()
        periods_to_keep = simplify_periods(periods_used)

        valid_locs = self.get_locations_over_periods(periods_to_keep)
        deleted_location_count = location_count - len(valid_locs)
        if deleted_location_count:
            self.add_locations(valid_locs, reset=True, save=save)

    def get_locations_over_periods(self, periods):
        locs = []
        for period in periods:
            p_locs, _ = self.get_locations_between_dates(*period)
            locs += p_locs
        return locs

    def gpx(self, from_date, end_date):
        current_site = get_current_site()
        gpx = gpxpy.gpx.GPX()
        gpx.creator = current_site.name
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)

        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        locs, _ = self.get_locations_between_dates(from_date, end_date)
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

    def add_locations(self, new_locations, /, *, reset=False, save=True):
        if reset:
            self.erase_locations()

        if not new_locations:
            if save:
                self.save()
            return

        sorted_new_locations = sorted(
            new_locations, key=itemgetter(LOCATION_TIMESTAMP_INDEX)
        )
        freshness_cutoff = None
        if self._last_location_datetime:
            freshness_cutoff = self._last_location_datetime.timestamp()

        fresh_new_locs = []
        old_new_locs = []
        prev_ts = None
        country = None
        for loc in sorted_new_locations:
            try:
                ts = int(loc[LOCATION_TIMESTAMP_INDEX])
            except Exception:
                continue
            if ts == prev_ts:
                continue
            try:
                lat = round(float(loc[LOCATION_LATITUDE_INDEX]), 5)
                lon = round(float(loc[LOCATION_LONGITUDE_INDEX]), 5)
                validate_latitude(lat)
                validate_longitude(lon)
            except Exception:
                continue
            if not country:
                country = country_code_at_coords(Wgs84Coordinate(lat, lon))
                if country in getattr(settings, "BANNED_COUNTRIES", []):
                    return
            prev_ts = ts

            validated_loc = (ts, lat, lon)
            if freshness_cutoff is not None and ts <= freshness_cutoff:
                old_new_locs.append(validated_loc)
            else:
                fresh_new_locs.append(validated_loc)

        if not fresh_new_locs and not old_new_locs:
            if save:
                self.save()
            return

        cleaned_old_new_locs = []
        if old_new_locs:
            locations = self.locations
            existing_ts = set(list(zip(*locations))[LOCATION_TIMESTAMP_INDEX])
            for loc in old_new_locs:
                ts = int(loc[LOCATION_TIMESTAMP_INDEX])
                if ts in existing_ts:
                    continue
                cleaned_old_new_locs.append(loc)
                existing_ts.add(ts)
            if cleaned_old_new_locs:
                locations += cleaned_old_new_locs
                sorted_locations = sorted(
                    locations, key=itemgetter(LOCATION_TIMESTAMP_INDEX)
                )
                self.locations_encoded = gps_data_codec.encode(sorted_locations)
        if fresh_new_locs:
            # Only fresher points, can append string
            locs_to_encode = []
            if self.last_location is not None:
                locs_to_encode = [self.last_location]
            # Encoding magic
            locs_to_encode += fresh_new_locs
            encoded_addition = gps_data_codec.encode(locs_to_encode)
            if self.last_location is not None:
                offset = 0
                number_count = 0
                for i, character in enumerate(encoded_addition):
                    if ord(character) - 63 < 0x20:
                        number_count += 1
                        if number_count == 3:
                            offset = i + 1
                            break
                encoded_addition = encoded_addition[offset:]
            self.locations_encoded += encoded_addition
            # Updating cache
            new_last_loc = fresh_new_locs[-1]
            self._last_location_datetime = epoch_to_datetime(
                new_last_loc[LOCATION_TIMESTAMP_INDEX]
            )
            self._last_location_latitude = new_last_loc[LOCATION_LATITUDE_INDEX]
            self._last_location_longitude = new_last_loc[LOCATION_LONGITUDE_INDEX]

        added_locs = cleaned_old_new_locs + fresh_new_locs
        if added_locs:
            self._location_count += len(added_locs)
            if save:
                self.save()
            archived_events_affected = self.get_events_between_dates(
                epoch_to_datetime(added_locs[0][LOCATION_TIMESTAMP_INDEX]),
                epoch_to_datetime(added_locs[-1][LOCATION_TIMESTAMP_INDEX]),
                should_be_ended=True,
            )
            for archived_event_affected in archived_events_affected:
                archived_event_affected.invalidate_cache()
            if self.should_relay_to_gpsseuranta:
                gpsseuranta_client.send(f"rc{self.aid}", added_locs)
        elif save:
            self.save()

    @property
    def should_relay_to_gpsseuranta(self):
        return (
            self.gpsseuranta_known
            and self.gpsseuranta_relay_until
            and now() <= self.gpsseuranta_relay_until
        )

    def add_location(self, timestamp, lat, lon, /, *, reset=False, save=True):
        self.add_locations(
            [
                (timestamp, lat, lon),
            ],
            reset=reset,
            save=save,
        )

    @property
    def location_count(self):
        # This use a property of the GPS encoding format
        return gps_data_codec.location_count(self.locations_encoded)

    @property
    def first_location(self):
        if not self._location_count:
            return None
        return gps_data_codec.decode_first_location(self.locations_encoded[:25])

    @property
    def last_location(self):
        if not self._location_count:
            return None
        return (
            int(self._last_location_datetime.timestamp()),
            self._last_location_latitude,
            self._last_location_longitude,
        )

    @property
    def first_location_datetime(self):
        if first_loc := self.first_location:
            return epoch_to_datetime(first_loc[LOCATION_TIMESTAMP_INDEX])
        return None

    @property
    def last_location_datetime(self):
        return self._last_location_datetime

    @property
    def earth_coords(self):
        if loc := self.last_location:
            return [loc[LOCATION_LATITUDE_INDEX], loc[LOCATION_LONGITUDE_INDEX]]
        return None

    def get_competitors_at_date(self, at, /, *, load_events=False):
        qs = (
            self.competitor_set.all()
            .filter(start_time__lte=at, event__end_date__gte=at)
            .annotate(max_start=Max("start_time"))
            .filter(start_time=F("max_start"))
        )
        if load_events:
            qs = qs.select_related("event")
        return qs

    def get_events_between_dates(self, from_date, to_date, /, *, should_be_ended=False):
        if not self.pk:
            return []
        qs = (
            self.competitor_set.all()
            .filter(
                event__end_date__gte=from_date,
                start_time__lte=to_date,
            )
            .select_related("event")
            .only("event")
            .order_by("start_time")
        )
        if should_be_ended:
            qs = qs.filter(event__end_date__lt=now())
        return {c.event for c in qs}

    def get_events_at_date(self, at):
        return self.get_events_between_dates(at, at)

    def get_last_competitor(self, load_event=False):
        qs = self.competitor_set.order_by("-start_time")
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
            if event.emergency_contacts:
                to_emails = event.emergency_contacts.split(" ")
            else:
                club = event.club
                admin_ids = list(club.admins.values_list("id", flat=True))
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
                        "Latest SOS known location is latitude, longitude: "
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

    class Meta:
        ordering = ["-creation_date"]

    def __str__(self):
        return f"Archive {self.archive.aid} of {self.original.aid}"


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
        verbose_name = "IMEI"
        verbose_name_plural = "IMEIs"

    def __str__(self):
        return self.imei


class DeviceClubOwnership(models.Model):
    device = models.ForeignKey(
        Device,
        verbose_name="Tracker",
        related_name="club_ownerships",
        on_delete=models.CASCADE,
    )
    club = models.ForeignKey(
        Club, related_name="device_ownerships", on_delete=models.CASCADE, db_index=True
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    nickname = models.CharField(max_length=12, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="device_club_ownership_club_device_uc",
                fields=("device", "club"),
            )
        ]
        verbose_name = "Device ownership"
        verbose_name_plural = "Device ownerships"

    def __str__(self):
        return f"{self.device.aid} for {self.club.name}"


class Competitor(models.Model, SomewhereOnEarth):
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
    start_time = models.DateTimeField(verbose_name="Start time", null=True, blank=True)
    user = models.ForeignKey(
        User,
        related_name="participations",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    color = models.CharField(
        verbose_name="Color",
        max_length=7,
        blank=True,
        default="",
        validators=[color_hex_validator],
    )
    tags = models.CharField(
        verbose_name="Categories",
        max_length=256,
        blank=True,
        default="",
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
        instance_before = None
        if self.pk:
            instance_before = Competitor.objects.only("device", "start_time").get(
                pk=self.pk
            )
        super().save(*args, **kwargs)
        if (
            instance_before
            and instance_before.device
            and self.device != instance_before.device
        ):
            events_affected = instance_before.device.get_events_at_date(
                instance_before.start_time
            )
            for event in events_affected:
                event.invalidate_cache()

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
    def locations_encoded(self):
        result = gps_data_codec.encode(self.locations)
        return result

    def archive_device(self, save=True):
        if not self.device:
            return
        original = self.device
        archive = Device(
            aid=f"{short_random_key()}_ARC",
            virtual=True,
        )
        archive.add_locations(self.locations, save=False)
        self.device = archive
        if save:
            if archive.locations_encoded != "":
                archive.save()
                self.device.save()
                self.save()
                DeviceArchiveReference.objects.create(
                    original=original, archive=archive
                )
            else:
                self.device = original
                self.device.save()
                self.save()

    @property
    def gpx(self):
        if not self.device:
            return ""
        return self.device.gpx(self.start_datetime, self.end_datetime)

    def get_absolute_gpx_url(self):
        return reverse(
            "competitor_gpx_download",
            host="api",
            kwargs={
                "competitor_id": self.aid,
            },
        )

    @property
    def categories(self):
        if not self.tags:
            return []
        return self.tags.split(TAGS_SEPARATOR)

    @property
    def earth_coords(self):
        if locs := self.locations:
            loc = locs[0]
            return [loc[1], loc[2]]
        return None

    @property
    def duration(self):
        if locations := self.locations:
            return (
                locations[-1][LOCATION_TIMESTAMP_INDEX]
                - locations[0][LOCATION_TIMESTAMP_INDEX]
            )
        return 0

    @property
    def distance(self):
        if locations := self.locations:
            return 0
            distance = 0
            prev_pt = locations[0]
            rad = math.pi / 180
            for pt in locations[1:]:
                dlat = pt[LOCATION_LATITUDE_INDEX] - prev_pt[LOCATION_LATITUDE_INDEX]
                dlon = pt[LOCATION_LONGITUDE_INDEX] - prev_pt[LOCATION_LONGITUDE_INDEX]
                alpha = (
                    math.sin(rad * dlat / 2) ** 2
                    + math.cos(rad * pt[LOCATION_LATITUDE_INDEX])
                    * math.cos(rad * prev_pt[LOCATION_LATITUDE_INDEX])
                    * math.sin(rad * dlon / 2) ** 2
                )
                distance += 12756274 * math.atan2(
                    math.sqrt(alpha), math.sqrt(1 - alpha)
                )
                prev_pt = pt
        return distance

    @property
    def locations_hash(self):
        return shortsafe64encodedsha(self.locations_encoded)


@receiver([pre_save, post_delete], sender=Competitor)
def invalidate_competitor_event_cache(sender, instance, **kwargs):
    if not instance.start_time:
        instance.start_time = instance.event.start_date
    instance.event.invalidate_cache()
    if instance.device:
        events_affected = instance.device.get_events_at_date(instance.start_time)
        for event in events_affected:
            event.invalidate_cache()


class TcpDeviceCommand(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    target = models.ForeignKey(
        ImeiDevice, related_name="commands", on_delete=models.CASCADE
    )
    sent = models.BooleanField(default=False)
    command = models.TextField()
    comment = models.CharField(blank=True, default="")

    class Meta:
        ordering = ["-modification_date"]
        verbose_name = "TCP command"
        verbose_name_plural = "TCP commands"

    def __str__(self):
        return f"Command for IMEI {self.target}"


class FrontPageFeedback(models.Model):
    content = models.TextField()
    stars = models.PositiveIntegerField(validators=[MaxValueValidator(5)])
    name = models.CharField(max_length=50)
    club_name = models.CharField(max_length=50)

    class Meta:
        verbose_name = "feedback"
        verbose_name_plural = "feedbacks"

    def __str__(self):
        return f"Feedback from {self.name} ({self.club_name})"


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    default_device = models.ForeignKey(
        Device,
        related_name="default_user_set",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    default_name = models.CharField(max_length=64, null=True, blank=True)
    default_short_name = models.CharField(max_length=32, null=True, blank=True)
    third_party_oauth_credentials = models.JSONField(
        null=False,
        blank=False,
        default=dict,
    )

    class Meta:
        verbose_name = "user settings"
        verbose_name_plural = "user settings"


User.settings = property(lambda u: UserSettings.objects.get_or_create(user=u)[0])

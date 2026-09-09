import logging
import re
import time
import urllib.parse
from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile

import arrow
import gps_data_codec
import orjson as json
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geoip2 import GeoIP2
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django_hosts.resolvers import reverse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import renderers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from routechoices.core.models import (
    BOTTOM_LEFT,
    EVENT_CACHE_INTERVAL_LIVE,
    LOCATION_LATITUDE_INDEX,
    LOCATION_LONGITUDE_INDEX,
    LOCATION_TIMESTAMP_INDEX,
    MAP_BLANK,
    MAP_CHOICES,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    PRIVACY_SECRET,
    TAGS_SEPARATOR,
    TOP_LEFT,
    TOP_RIGHT,
    VISIBILITY_LIVE,
    VISIBILITY_PREVIEW,
    VISIBILITY_REPLAY,
    Club,
    Competitor,
    Device,
    DeviceClubOwnership,
    Event,
    EventSet,
    ImeiDevice,
    Map,
    MapAssignation,
    TooEarly,
)
from routechoices.lib import cache
from routechoices.lib.duration_constants import DURATION_ONE_MINUTE, DURATION_ONE_MONTH
from routechoices.lib.helpers import (
    epoch_to_datetime,
    get_image_mime_from_request,
    git_master_hash,
    initial_of_name,
    random_device_id,
    safe64encodedsha,
    set_content_disposition,
    short_random_key,
    short_random_slug,
)
from routechoices.lib.s3 import serve_from_s3, serve_image_from_s3
from routechoices.lib.streaming_response import StreamingHttpRangeResponse
from routechoices.lib.validators import (
    color_hex_validator,
    validate_imei,
    validate_latitude,
    validate_longitude,
    validate_nice_slug,
)
from routechoices.site.views import CustomLoginView

logger = logging.getLogger(__name__)

api_GET_view = api_view(["GET", "HEAD"])
api_GET_POST_view = api_view(["GET", "HEAD", "POST"])
api_POST_view = api_view(["POST"])


class PostDataThrottle(UserRateThrottle):
    rate = "60/min"

    def allow_request(self, request, view):
        if request.method == "GET":
            return True
        return super().allow_request(request, view)


club_param = openapi.Parameter(
    "club",
    openapi.IN_QUERY,
    description="Filter by this club slug",
    type=openapi.TYPE_STRING,
)

event_param = openapi.Parameter(
    "event",
    openapi.IN_QUERY,
    description="Filter by this event slug or url",
    type=openapi.TYPE_STRING,
)


def serialize_map(event, index, raster_map, title, tags=None):
    if not tags:
        tags = []
    else:
        tags = tags.split(TAGS_SEPARATOR)
    ext = raster_map.mime_type.split("/")[1]
    if ext not in ("jpeg", "png", "webp", "avif"):
        ext = "webp"
    url = reverse(
        "event_map_download_with_format",
        host="api",
        kwargs={
            "event_id": event.aid,
            "index": index + 1,
            "extension": ext,
        },
    )
    return {
        "title": title,
        "coordinates": raster_map.bound_api,
        "rotation": raster_map.north_declination,
        "hash": raster_map.hash,
        "max_zoom": raster_map.max_zoom,
        "modification_date": raster_map.modification_date,
        "default": index == 0,
        "tags": tags,
        "id": raster_map.aid,
        "url": url,
        "wms": True,
    }


@swagger_auto_schema(
    method="post",
    auto_schema=None,
)
@api_POST_view
@permission_classes([IsAuthenticated])
def event_set_creation(request):
    club_slug = request.data.get("club_slug")
    name = request.data.get("name")
    if not name or not club_slug:
        raise ValidationError("Missing parameter")
    club = Club.objects.filter(admins=request.user, slug__iexact=club_slug).first()
    if not club:
        raise ValidationError("club not found")
    event_set, _ = EventSet.objects.get_or_create(club=club, name=name)
    return Response(
        {
            "value": event_set.id,
            "text": name,
        }
    )


@swagger_auto_schema(
    method="get",
    operation_id="events_list",
    operation_description=(
        "List all public events sorted by decreasing start date. "
        "If you are identified it will list also all your events you have created,"
        " no matter their privacy settings. "
        "Will also list a secret event if its url is specified in the event parameter."
    ),
    tags=["Events"],
    manual_parameters=[club_param, event_param],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": [
                    {
                        "id": "PlCG3xFS-f4",
                        "name": "Jukola 2019 - 1st Leg",
                        "start_date": "2019-06-15T20:00:00Z",
                        "end_date": "2019-06-16T00:00:00Z",
                        "slug": "Jukola-2019-1st-leg",
                        "club": {
                            "name": "Kangasala SK",
                            "slug": "ksk",
                        },
                        "privacy": "public",
                        "visibility": "live",
                        "backdrop": "blank",
                        "open_registration": False,
                        "acceptable_tags": [],
                        "open_route_upload": False,
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-1st-leg",
                    },
                    {
                        "id": "ohFYzJep1hI",
                        "name": "Jukola 2019 - 2nd Leg",
                        "start_date": "2019-06-15T21:00:00Z",
                        "end_date": "2019-06-16T00:00:00Z",
                        "slug": "Jukola-2019-2nd-leg",
                        "club": {
                            "name": "Kangasala SK",
                            "slug": "ksk",
                        },
                        "privacy": "public",
                        "visibility": "live",
                        "open_registration": False,
                        "acceptable_tags": [],
                        "open_route_upload": False,
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-2nd-leg",
                    },
                    "...",
                ]
            },
        ),
    },
)
@swagger_auto_schema(
    method="post",
    operation_id="event_create",
    operation_description="Create an event. This endpoint requires you to be identified.",
    tags=["Events"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "club_slug": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Club Slug",
            ),
            "name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Event name. Default to "Untitled + random string"',
            ),
            "slug": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="URL path name. Default random",
            ),
            "start_date": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Start time (YYYY-MM-DDThh:mm:ssZ). Default to now",
            ),
            "end_date": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "End time, must be after the start_date (YYYY-MM-DDThh:mm:ssZ)"
                ),
            ),
            "privacy": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "Privacy level (PUBLIC, SECRET or PRIVATE). Default to SECRET",
                ),
            ),
            "visibility": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "Visibility setting (PREVIEW, LIVE or REPLAY). Default to LIVE",
                ),
            ),
            "backdrop": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    f"Backdrop map: one of {', '.join(m[0] for m in MAP_CHOICES)}."
                    " Default blank"
                ),
            ),
            "open_registration": openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description=(
                    "Can public register themselves to the event. Default False"
                ),
            ),
            "acceptable_tags": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "If an event has open registration, a space separated list of categories that users can create competitor within"
                ),
            ),
            "open_route_upload": openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description=(
                    "Can public upload their route to the event from GPS files,"
                    " Default False"
                ),
            ),
        },
        required=["club_slug", "end_date"],
    ),
    responses={
        "201": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "id": "PlCG3xFS-f4",
                    "name": "Jukola 2019 - 1st Leg",
                    "start_date": "2019-06-15T20:00:00Z",
                    "end_date": "2019-06-16T00:00:00Z",
                    "slug": "Jukola-2019-1st-leg",
                    "club": {
                        "name": "Kangasala SK",
                        "slug": "ksk",
                    },
                    "privacy": "public",
                    "visibility": "live",
                    "backdrop": "blank",
                    "open_registration": False,
                    "acceptable_tags": [],
                    "open_route_upload": False,
                    "url": "http://www.routechoices.com/ksk/Jukola-2019-1st-leg",
                },
            },
        ),
    },
)
@api_GET_POST_view
def event_list(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        club_slug = request.data.get("club_slug")
        if not club_slug:
            raise ValidationError("club_slug is required")
        club = Club.objects.filter(admins=request.user, slug__iexact=club_slug).first()
        if not club:
            raise ValidationError("club not found")
        if not club.can_modify_events:
            if club.subscription_paused:
                raise ValidationError("subscription paused")
            raise ValidationError("free trial expired")
        name = f"Untitled {short_random_slug()}"
        name_raw = request.data.get("name")
        if name_raw:
            name = name_raw

        slug = short_random_slug()
        slug_raw = request.data.get("slug")
        if slug_raw:
            try:
                validate_nice_slug(slug_raw)
            except Exception:
                raise ValidationError("Invalid slug")
            else:
                slug = slug_raw

        start_date = arrow.now().datetime
        start_date_raw = request.data.get("start_date")
        if start_date_raw:
            try:
                start_date = arrow.get(start_date_raw).datetime
            except Exception:
                raise ValidationError("Invalid start_date")

        end_date_raw = request.data.get("end_date")
        if not end_date_raw:
            raise ValidationError("end_date is required")
        try:
            end_date = arrow.get(end_date_raw).datetime
        except Exception:
            raise ValidationError("Invalid end_date")
        else:
            if end_date <= start_date:
                raise ValidationError("Invalid end_date, should be after start_date")

        backdrop_map = request.data.get("backdrop", MAP_BLANK)
        if backdrop_map not in (m[0] for m in MAP_CHOICES):
            raise ValidationError("Invalid backdrop")

        privacy = request.data.get("privacy", PRIVACY_SECRET)
        if privacy.lower() not in (PRIVACY_PUBLIC, PRIVACY_SECRET, PRIVACY_PRIVATE):
            raise ValidationError("Invalid privacy")

        visibility = request.data.get("visibility", VISIBILITY_LIVE)
        if visibility.lower() not in (
            VISIBILITY_LIVE,
            VISIBILITY_PREVIEW,
            VISIBILITY_REPLAY,
        ):
            raise ValidationError("Invalid visibility")

        open_registration = False
        acceptable_tags = ""
        open_registration_raw = request.data.get("open_registration")
        if open_registration_raw:
            open_registration = True
            if acceptable_tags_raw := request.data.get("acceptable_tags", ""):
                try:
                    acceptable_tags = TAGS_SEPARATOR.join(
                        acceptable_tags_raw.split(TAGS_SEPARATOR)
                    )
                except Exception:
                    raise ValidationError("Invalid acceptable_tags")

        allow_route_upload = False
        allow_route_upload_raw = request.data.get("allow_route_upload")
        if allow_route_upload_raw:
            allow_route_upload = True

        event = Event(
            club=club,
            slug=slug,
            name=name,
            start_date=start_date,
            end_date=end_date,
            privacy=privacy,
            visibility=visibility,
            backdrop_map=backdrop_map,
            open_registration=open_registration,
            acceptable_tags=acceptable_tags,
            allow_route_upload=allow_route_upload,
        )
        try:
            event.full_clean()
        except Exception as e:
            raise ValidationError(e)
        event.save()
        output = {
            "id": event.aid,
            "name": event.name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "slug": event.slug,
            "club": {
                "name": club.name,
                "slug": club.slug.lower(),
            },
            "privacy": event.privacy,
            "backdrop": event.backdrop_map,
            "open_registration": event.open_registration,
            "acceptable_tags": event.acceptable_categories,
            "open_route_upload": event.allow_route_upload,
            "url": request.build_absolute_uri(event.get_absolute_url()),
        }
        return Response(output, status=status.HTTP_201_CREATED)

    club_slug = request.GET.get("club")
    event_slug = request.GET.get("event")
    event_url = None

    if event_slug and "/" in event_slug:
        event_url = event_slug
        event_slug = None

    if (event_slug and club_slug) or event_url:
        privacy_arg = {"privacy__in": [PRIVACY_PUBLIC, PRIVACY_SECRET]}
    else:
        privacy_arg = {"privacy": PRIVACY_PUBLIC}

    headers = {}
    if request.user.is_authenticated:
        clubs = Club.objects.filter(admins=request.user)
        events = Event.objects.filter(
            Q(**privacy_arg) | Q(club__in=clubs)
        ).select_related("club")
        headers["Cache-Control"] = "Private"
    else:
        events = Event.objects.filter(**privacy_arg).select_related("club")

    if club_slug:
        events = events.filter(club__slug__iexact=club_slug)
    if event_slug:
        events = events.filter(slug__iexact=event_slug)
    if event_url:
        url = urllib.parse.urlparse(event_url)
        domain = url.netloc
        if domain.endswith(f".{settings.PARENT_HOST}"):
            club_slug = domain[: -(len(settings.PARENT_HOST) + 1)]
            events.filter(club__slug__iexact=club_slug)
        else:
            events.filter(club__domain__iexact=domain)
        event_slug = url.path[1:]
        event_slug = event_slug.removesuffix("/")
        events = events.filter(slug__iexact=event_slug)
    output = []
    for event in events:
        output.append(
            {
                "id": event.aid,
                "name": event.name,
                "start_date": event.start_date,
                "end_date": event.end_date,
                "slug": event.slug,
                "club": {
                    "name": event.club.name,
                    "slug": event.club.slug.lower(),
                },
                "privacy": event.privacy,
                "visibility": event.visibility,
                "backdrop": event.backdrop_map,
                "open_registration": event.open_registration,
                "acceptable_tags": event.acceptable_categories,
                "open_route_upload": event.allow_route_upload,
                "url": request.build_absolute_uri(event.get_absolute_url()),
            }
        )
    return Response(output, headers=headers)


@swagger_auto_schema(
    method="get",
    operation_id="club_list",
    operation_description="List all your clubs.",
    tags=["Clubs"],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": [
                    {
                        "name": "Kangasala SK",
                        "slug": "ksk",
                        "url": "https://ksk.routechoices.com/",
                        "owner": False,
                    },
                    {
                        "name": "Kimito SK",
                        "slug": "kimito-sk",
                        "url": "https://gps.haldensk.no/",
                        "owner": True,
                    },
                    "...",
                ]
            },
        ),
    },
)
@api_GET_view
@permission_classes([IsAuthenticated])
def club_list_view(request):
    clubs = Club.objects.filter(admins=request.user)
    output = []
    for club in clubs:
        output.append(
            {
                "name": club.name,
                "slug": club.slug,
                "url": club.nice_url,
            }
        )
    return Response(output, headers={"Cache-Control": "Private"})


@swagger_auto_schema(
    method="get",
    operation_id="event_detail",
    operation_description=(
        "Read an event details. For private events you need "
        "to be identified as an admin of the event organiser to be able to get a valid answer."
    ),
    tags=["Events"],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "event": {
                        "id": "PlCG3xFS-f4",
                        "name": "Jukola 2019 - 1st Leg",
                        "start_date": "2019-06-15T20:00:00Z",
                        "end_date": "2019-06-16T00:00:00Z",
                        "slug": "Jukola-2019-1st-leg",
                        "club": {
                            "name": "Kangasala SK",
                            "slug": "ksk",
                        },
                        "privacy": "public",
                        "visibility": "live",
                        "open_registration": False,
                        "acceptable_tags": [],
                        "open_route_upload": False,
                        "url": "https://ksk.routechoices.com/Jukola-2019-1st-leg",
                        "shortcut": "https://routechoic.es/ksk/Jukola-2019-1st-leg",
                        "backdrop": "osm",
                        "send_interval": 5,
                        "tail_length": 60,
                    },
                    "data_url": (
                        "https://www.routechoices.com/api/events/PlCG3xFS-f4/data/"
                    ),
                    "announcement": "",
                    "maps": [
                        {
                            "coordinates": {
                                "top_left": {"lat": 61.45075, "lon": 24.18994},
                                "top_right": {"lat": 61.44656, "lon": 24.24721},
                                "bottom_right": {"lat": 61.42094, "lon": 24.23851},
                                "bottom_left": {"lat": 61.42533, "lon": 24.18156},
                            },
                            "rotation": 3.25,
                            "url": (
                                "https://api.routechoices.com/events/PlCG3xFS-f4/map.webp"
                            ),
                            "title": "",
                            "hash": "u8cWoEiv",
                            "max_zoom": 18,
                            "modification_date": "2019-06-10T17:21:52.417000Z",
                            "default": True,
                            "tags": [],
                            "id": "or6tmT19cfk",
                        }
                    ],
                }
            },
        ),
    },
)
@swagger_auto_schema(
    method="delete",
    operation_id="event_delete",
    operation_description="Delete an event. You need to be identified as an event organiser admin to get a valid answer.",
    tags=["Events"],
    responses={
        "204": openapi.Response(
            description="Success response", examples={"application/json": ""}
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_view(["GET", "DELETE"])
def event_detail(request, event_id):
    # TODO: Implement PATCH method
    if request.method == "DELETE" and not request.user.is_authenticated:
        raise NotAuthenticated()

    event = (
        Event.objects.select_related("club", "notice", "map")
        .prefetch_related(
            Prefetch(
                "map_assignations",
                queryset=MapAssignation.objects.select_related("map"),
            )
        )
        .filter(aid=event_id)
        .first()
    )
    if not event:
        raise Http404()

    event.check_user_permission(request.user)
    is_event_admin = event.club.is_admin(request.user)

    if request.method == "DELETE":
        if not is_event_admin:
            raise PermissionDenied()
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    output = {
        "event": {
            "id": event.aid,
            "name": event.name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "slug": event.slug,
            "club": {
                "name": event.club.name,
                "slug": event.club.slug.lower(),
            },
            "privacy": event.privacy,
            "visibility": event.visibility,
            "open_registration": event.open_registration,
            "acceptable_tags": event.acceptable_categories,
            "open_route_upload": event.allow_route_upload,
            "url": request.build_absolute_uri(event.get_absolute_url()),
            "shortcut": event.shortcut,
            "backdrop": event.backdrop_map,
            "send_interval": event.send_interval,
            "tail_length": event.tail_length,
        },
        "data_url": request.build_absolute_uri(
            reverse("event_data", host="api", kwargs={"event_id": event.aid})
        ),
    }

    output["announcement"] = event.notice.text if event.has_notice else ""

    maps = []
    if event.could_display_maps(request.user):
        for i, (raster_map, title, tags) in enumerate(event.enumerate_maps()):
            maps.append(serialize_map(event, i, raster_map, title, tags))

        if event.geojson_layer:
            output["geojson_url"] = event.get_geojson_url()

    output["maps"] = maps

    headers = {"ETag": f'W/"{safe64encodedsha(json.dumps(output))}"'}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    return Response(output, headers=headers)


@swagger_auto_schema(
    method="post",
    operation_id="competitor_create",
    operation_description="Create a competitor for a given event. Only those identified as admins of the event organiser can set the competitor color.",
    tags=["Competitors"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "event_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Event ID",
            ),
            "name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Full name",
            ),
            "short_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Short version of the name",
            ),
            "start_time": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "Start time, must be within the event schedule if provided"
                    " (YYYY-MM-DDThh:mm:ssZ)"
                ),
            ),
            "device_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Tracker ID",
            ),
            "color": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Color, hexadecimal format, e.g. #ff9900",
            ),
            "tag": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Category, must be listed as an acceptable registration category if you are not an event administrator",
            ),
        },
        required=["event_id", "name"],
    ),
    responses={
        "201": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "id": "<id>",
                    "name": "<name>",
                    "short_name": "<short_name>",
                    "start_time": "<start_time>",
                    "device_id": "<device_id>",
                    "color": "<color>",
                    "tag": "<tag>",
                }
            },
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_POST_view
def create_competitor(request):
    event_id = request.data.get("event_id")
    if not event_id:
        raise ValidationError("Event ID is missing")
    event = Event.objects.select_related("club").filter(aid=event_id).first()
    if not event:
        raise ValidationError("No event matches this ID")

    is_event_admin = event.club.is_admin(request.user)

    errors = []

    tag = ""
    if not event.open_registration and not is_event_admin:
        raise PermissionDenied()
    else:
        tag = request.data.get("tag", "")
        if tag and not is_event_admin and tag not in event.acceptable_categories:
            errors.append("Invalid category")

    if event.end_date < now() and not event.allow_route_upload:
        raise ValidationError("Registration is closed")

    name = request.data.get("name")

    if not name:
        errors.append("Name is missing")

    short_name = request.data.get("short_name")
    if name and not short_name:
        short_name = initial_of_name(name)

    start_time_query = request.data.get("start_time")
    if start_time_query:
        try:
            start_time = arrow.get(start_time_query).datetime
        except Exception:
            start_time = None
            errors.append("Start time could not be parsed")
    elif event.start_date < now() < event.end_date:
        start_time = now()
    else:
        start_time = event.start_date
    event_start = event.start_date
    event_end = event.end_date

    if start_time and (event_start > start_time or start_time > event_end):
        errors.append("Competitor start time should be during the event time")

    device_id = request.data.get("device_id")
    device = Device.objects.filter(aid=device_id).defer("locations_encoded").first()

    if not device and device_id:
        errors.append("Tracker ID not found")

    if not is_event_admin:
        if event.competitors.filter(name=name).exists():
            errors.append("Name already in use in this event")

        if event.competitors.filter(
            short_name=short_name
        ).exists() and request.data.get("short_name"):
            errors.append("Short name already in use in this event")
        if (
            device
            and Competitor.objects.filter(
                start_time=start_time, device_id=device.id
            ).exists()
        ):
            errors.append("This device is already registered for this same start time")

    if not is_event_admin:
        color = ""
    else:
        color = request.data.get("color", "")

    if color:
        try:
            color_hex_validator(color)
        except Exception:
            color = ""

    if errors:
        raise ValidationError(errors)

    user = None
    if request.user.is_authenticated:
        user = request.user

    comp = Competitor.objects.create(
        name=name,
        event=event,
        short_name=short_name,
        start_time=start_time,
        device=device,
        user=user,
        color=color,
        tags=tag,
    )

    output = {
        "id": comp.aid,
        "name": name,
        "short_name": short_name,
        "start_time": start_time,
    }
    if color:
        output["color"] = color

    if device:
        output["device_id"] = device.aid

    return Response(
        output,
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method="patch",
    operation_id="competitor_update",
    operation_description="Edit a competitor. Only those identified as admins of the event organiser can set the competitor color. You need to be identified as the user that created the competitor or as an events organiser admin to get a valid answer.",
    tags=["Competitors"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Tracker ID",
            ),
            "name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Full name",
            ),
            "short_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Short version of the name",
            ),
            "color": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Color, hexadecimal format, e.g. #ff9900",
            ),
            "tag": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="List of categories separated by spaces",
            ),
        },
    ),
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={"application/json": {"status": "ok"}},
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@swagger_auto_schema(
    method="delete",
    operation_id="competitor_delete",
    operation_description="Delete a competitor. You need to be identified as the user that created the competitor or as an event organiser admin to get a valid answer.",
    tags=["Competitors"],
    responses={
        "204": openapi.Response(
            description="Success response", examples={"application/json": ""}
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated])
def competitor_api(request, competitor_id):
    competitor = (
        Competitor.objects.select_related("event", "event__club")
        .filter(aid=competitor_id)
        .first()
    )
    if not competitor:
        res = {"error": "No competitor matches this ID"}
        return Response(res)

    event = competitor.event
    other_competitors = event.competitors.exclude(id=competitor.id)

    is_user_event_admin = event.club.admins.filter(id=request.user.id).exists()
    if not is_user_event_admin and competitor.user != request.user:
        raise PermissionDenied()

    if request.method == "DELETE":
        competitor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    new_name = request.data.get("name")
    new_short_name = request.data.get("short_name")
    new_device_id = request.data.get("device_id")
    new_tags = request.data.get("tags")

    if is_user_event_admin:
        new_color = request.data.get("color")
    else:
        new_color = None

    if new_name:
        new_name = new_name[:64]
    if new_short_name == "":
        new_short_name = initial_of_name(competitor.name)
    if new_short_name:
        new_short_name = new_short_name[:32]

    new_device = None
    if new_device_id:
        dev = Device.objects.filter(aid=new_device_id).first()
        if not dev:
            raise ValidationError("Invalid device ID")
        new_device = dev

    tags = None
    if new_tags is not None:
        new_tags = new_tags[:256]
        tags = new_tags.split(TAGS_SEPARATOR)

    if new_color is not None:
        try:
            color_hex_validator(new_color)
        except Exception:
            new_color = ""

    if not is_user_event_admin:
        if new_name and other_competitors.filter(name=new_name).exists():
            raise ValidationError("Name already in use in this event")

        if (
            new_short_name
            and request.data.get("short_name")
            and other_competitors.filter(short_name=new_short_name).exists()
        ):
            raise ValidationError("Short name already in use in this event")

        if (
            new_device
            and Competitor.objects.exclude(id=competitor.id)
            .filter(
                device_id=new_device.id,
                start_time=competitor.start_time,
            )
            .exists()
        ):
            raise ValidationError(
                "This device is already registered for the same start time"
            )
        if tags is not None:
            for tag in tags:
                if tag and tag not in event.acceptable_categories:
                    raise ValidationError("Tag not accepted")

    if new_name:
        competitor.name = new_name
    if new_short_name:
        competitor.short_name = new_short_name
    if new_device:
        competitor.device = new_device
    if new_color:
        competitor.color = new_color
    if tags is not None:
        competitor.tags = TAGS_SEPARATOR.join(tags)

    if new_name or new_short_name or new_device_id or new_color:
        competitor.save()
        return Response({"status": "ok"})
    else:
        raise ValidationError("No data submitted")


@swagger_auto_schema(
    method="post",
    operation_id="competitor_route_upload",
    operation_description=(
        "Upload a full route for an existing competitor (Deletes existing location data). You need to be identified as the user that created the competitor or as an event organiser admin to get a valid answer unless the events allow route upload and that the competitor has no locations data yet assigned."
    ),
    tags=["Competitors"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "latitudes": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "A list of locations latitudes (in degrees) separated by commas"
                ),
                example="60.12345,60.12346,60.12347",
            ),
            "longitudes": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "A list of locations longitudes (in degrees) separated by commas"
                ),
                example="20.12345,20.12346,20.12347",
            ),
            "timestamps": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "A list of locations timestamps "
                    "(UNIX epoch in seconds) separated by commas"
                ),
                example="1661489045,1661489046,1661489047",
            ),
        },
        required=["latitudes", "longitudes", "timestamps"],
    ),
    responses={
        "201": openapi.Response(
            description="Success response",
            examples={"application/json": {"status": "ok", "location_count": "3"}},
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_POST_view
def competitor_route_upload(request, competitor_id):
    competitor = (
        Competitor.objects.select_related("event", "event__club", "device")
        .filter(aid=competitor_id)
        .first()
    )
    if not competitor:
        res = {"error": "No competitor matches this ID"}
        return Response(res)
    event = competitor.event

    is_event_admin = (
        request.user.is_authenticated
        and event.club.admins.filter(id=request.user.id).exists()
    )

    is_event_admin_or_user = request.user.is_authenticated and (
        is_event_admin or request.user == competitor.user
    )

    if not event.allow_route_upload and not is_event_admin:
        raise PermissionDenied()

    if not is_event_admin_or_user and competitor.locations:
        raise ValidationError("Competitor already assigned a route")

    if event.start_date > now():
        raise ValidationError("Event has not yet started")

    try:
        lats = [float(x) for x in request.data.get("latitudes", "").split(",") if x]
        lons = [float(x) for x in request.data.get("longitudes", "").split(",") if x]
        times = [
            int(float(x)) for x in request.data.get("timestamps", "").split(",") if x
        ]
    except ValueError:
        raise ValidationError("Invalid data format")

    if not ((loc_count := len(lats)) == len(lons) == len(times)):
        raise ValidationError(
            "Latitudes, longitudes, and timestamps, should have same amount of points"
        )

    if loc_count == 0:
        raise ValidationError("No locations sent")

    loc_array = []
    start_time = None
    for tim, lat, lon in zip(times, lats, lons):
        if tim and lat and lon:
            try:
                validate_longitude(lon)
            except Exception:
                raise ValidationError("Invalid longitude value")
            try:
                validate_latitude(lat)
            except Exception:
                raise ValidationError("Invalid latitude value")
            try:
                int(tim)
            except Exception:
                raise ValidationError("Invalid time value")
            if event.start_date.timestamp() <= tim <= event.end_date.timestamp():
                if not start_time or tim < start_time:
                    start_time = int(tim)
                loc_array.append((int(tim), lat, lon))

    device = None
    if len(loc_array) > 0:
        device = Device.objects.create(
            aid=f"{short_random_key()}_GPX",
            user_agent=request.session.user_agent[:200],
            virtual=True,
        )
        device.add_locations(loc_array)
        competitor.device = device
        competitor.start_time = epoch_to_datetime(start_time)
        competitor.save()
        competitor.event.invalidate_cache()

    if len(loc_array) == 0:
        raise ValidationError("No locations within event's schedule were detected")

    return Response(
        {
            "id": competitor.aid,
            "location_count": len(loc_array),
        },
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method="get",
    operation_id="event_data",
    operation_description="Read competitors data from an event. You need to be identified as event organiser admin to list private events data.",
    tags=["Events"],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "competitors": [
                        {
                            "id": "pwaCro4TErI",
                            "encoded_data": "<encoded data>",
                            "name": "Olav Lundanes (Kimito SK)",
                            "short_name": "Kimito SK",
                            "start_time": "2019-06-15T20:00:00Z",
                            "battery_level": 84,
                            "color": "#ff0000",
                            "categories": ["Black", "HE"],
                        }
                    ],
                    "next": "//api.routechoices.com/events/pwaCro4TErI/data/1234",
                }
            },
        ),
    },
)
@api_GET_view
def event_data(request, event_id):
    tag = request.GET.get("category")
    try:
        response, was_cached, is_public = Event.get_current_data(
            event_id, tag, request.user
        )
    except Event.DoesNotExist:
        raise Http404()
    except TooEarly:
        return Response(status=status.HTTP_425_TOO_EARLY)

    headers = {"ETag": f'W/"{safe64encodedsha(json.dumps(response))}"'}
    if was_cached:
        headers["X-Cache-Hit"] = 1
    if not is_public:
        headers["Cache-Control"] = "Private"

    return Response(response, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def event_data_delta(request, event_id, previous_key):
    # check if event is public, if not do the checks
    event = None
    is_public_cache_key = f"event:{event_id}:is_public"
    if (is_public := cache.get(is_public_cache_key)) is None:
        event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)
        is_public = event.privacy != PRIVACY_PRIVATE
        cache.set(is_public_cache_key, is_public, DURATION_ONE_MONTH)
    if not is_public:
        if not event:
            event = get_object_or_404(
                Event.objects.select_related("club"), aid=event_id
            )
        event.check_user_permission(request.user)

    t0 = time.time()
    cache_ts = int(t0 // EVENT_CACHE_INTERVAL_LIVE)
    # If previous key is same as current key, diff is empty
    if cache_ts == previous_key:
        response = {
            "competitors": [],
            "next": reverse(
                "event_data_delta",
                host="api",
                kwargs={"event_id": event_id, "previous_key": cache_ts},
            ),
            "partial": 1,
        }
        headers = {"ETag": f'W/"{safe64encodedsha(json.dumps(response))}"'}
        if not is_public:
            headers["Cache-Control"] = "Private"
        return Response(response, headers=headers)

    tag = request.GET.get("category")
    # Retrieve straight from cache if possible
    cache_key = f"event:{event_id}:tag:{tag or ""}:data-diff:{previous_key}:{cache_ts}"
    if cached_resp := cache.get(cache_key):
        headers = {
            "ETag": f'W/"{safe64encodedsha(json.dumps(cached_resp))}"',
            "X-Cache-Hit": 1,
        }
        if not is_public:
            headers["Cache-Control"] = "Private"
        return Response(cached_resp, headers=headers)

    # Retrieve previous state
    partial = False
    src_cache_key = f"event:{event_id}:tag:{tag or ""}:data:{previous_key}:live"
    prev_data = cache.get(src_cache_key)
    if prev_data:
        partial = True

    try:
        current_data, _, _ = Event.get_current_data(event_id, tag, request.user)
    except Event.DoesNotExist:
        raise Http404()
    except TooEarly:
        return Response(status=status.HTTP_425_TOO_EARLY)

    if not partial:
        response = current_data
        headers = {"ETag": f'W/"{safe64encodedsha(json.dumps(response))}"'}
        if not is_public:
            headers["Cache-Control"] = "Private"
        return Response(response)

    # Do the diff
    prev_competitors = {}
    for competitor in prev_data.get("competitors", []):
        prev_competitors[competitor["id"]] = competitor

    competitors_data = []
    for competitor in current_data.get("competitors", []):
        if categories := competitor.get("categories"):
            competitor["categories"] = TAGS_SEPARATOR.join(categories)
        if old_match := prev_competitors.get(competitor["id"]):
            if categories := old_match.get("categories"):
                old_match["categories"] = TAGS_SEPARATOR.join(categories)

            old_version = set(old_match.items())
            new_version = set(competitor.items())
            diff = dict(new_version - old_version)

            if not diff:
                continue

            diff["id"] = competitor.get("id")
            if "categories" in diff:
                diff["categories"] = diff["categories"].split(TAGS_SEPARATOR)
            if "encoded_data" in diff:
                if old_encoded_locations := old_match.get("encoded_data"):
                    diff["encoded_data"] = gps_data_codec.encoded_diff(
                        old_encoded_locations, competitor.get("encoded_data")
                    )
                else:
                    diff["encoded_data"] = competitor.get("encoded_data")
            competitors_data.append(diff)
        else:
            competitors_data.append(competitor)

    # Return the response
    response = {
        "competitors": competitors_data,
        "next": current_data.get("next"),
        "partial": True,
    }

    headers = {"ETag": f'W/"{safe64encodedsha(json.dumps(response))}"'}
    if not is_public:
        headers["Cache-Control"] = "Private"

    cache.set(cache_key, response, DURATION_ONE_MINUTE)

    return Response(response, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def event_zip(request, event_id):
    event = (
        Event.objects.select_related("club")
        .filter(aid=event_id)
        .select_related("map")
        .prefetch_related(
            Prefetch(
                "map_assignations",
                queryset=MapAssignation.objects.select_related("map"),
            )
        )
        .first()
    )
    if not event:
        raise Http404()

    event.check_user_permission(request.user)
    is_event_admin = event.club.is_admin(request.user)

    archive = BytesIO()
    with ZipFile(archive, "w") as fp:
        for i, (competitor, from_date, end_date) in enumerate(
            event.iterate_competitors()
        ):
            if competitor.device_id:
                data = competitor.device.gpx(from_date, end_date)
                filename = (
                    f"gpx/[{i + 1}] {competitor.name} - {competitor.short_name}.gpx"
                )
                with fp.open(filename, "w") as gpx_file:
                    gpx_file.write(data.encode("utf-8"))

        if event.could_display_maps(request.user):
            raster_maps = []
            if event.map:
                raster_maps.append((event.map, event.map_title or "Main map"))
                for ass in event.map_assignations.all():
                    raster_maps.append((ass.map, ass.title))
            for raster_map, title in raster_maps:
                data = raster_map.kmz
                filename = f"kmz/{title}.kmz"
                with fp.open(filename, "w") as kmz_file:
                    kmz_file.write(data)
            if event.geojson_layer:
                filename = f"{event.name}.geojson"
                data = event.geojson_layer.file.read()
                with fp.open(filename, "w") as geojson_file:
                    geojson_file.write(data)

    response_data = archive.getvalue()

    headers = {"ETag": f'W/"{safe64encodedsha(response_data)}"'}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    response = StreamingHttpRangeResponse(
        request, response_data, content_type="application/zip", headers=headers
    )
    response["Content-Disposition"] = set_content_disposition(f"{event.name}.zip")
    return response


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def ip_latlon(request):
    try:
        g = GeoIP2()
        lat, lon = g.lat_lon(request.META["REMOTE_ADDR"])
        response = {"status": "success", "lat": lat, "lon": lon}
    except Exception:
        response = {"status": "fail"}
    return Response(response, headers={"Cache-Control": "Private"})


@swagger_auto_schema(
    method="post",
    operation_id="device_add_locations",
    operation_description="Uploads some locations for a given device. You need to be identified to get a valid answer.",
    tags=["Devices"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="<device id>",
            ),
            "latitudes": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "List of locations latitudes (in degrees) separated by commas"
                ),
                example="60.12345,60.12346,60.12347",
            ),
            "longitudes": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "List of locations longitudes (in degrees) separated by commas"
                ),
                example="20.12345,20.12346,20.12347",
            ),
            "timestamps": openapi.Schema(
                type=openapi.TYPE_STRING,
                description=(
                    "List of locations timestamps "
                    "(UNIX epoch in seconds) separated by commas"
                ),
                example="1661489045,1661489046,1661489047",
            ),
            "battery": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Battery load percentage value",
                example="85",
            ),
        },
        required=["device_id", "latitudes", "longitudes", "timestamps"],
    ),
    responses={
        "201": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "status": "ok",
                    "device_id": "<device id>",
                    "location_count": "3",
                }
            },
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_POST_view
@throttle_classes([PostDataThrottle])
def locations_api_gw(request):
    secret_provided = request.data.get(
        "secret"
    )  # secret was used in legacy apps before v1.6.0
    battery_level_posted = request.data.get("battery")
    device_id = request.data.get("device_id")
    if not device_id:
        raise ValidationError("Missing device_id parameter")
    device_id = str(device_id)
    if (
        re.match(r"^[0-9]+$", device_id)
        and secret_provided not in settings.POST_LOCATION_SECRETS
        and (not request.user.is_authenticated or not request.user.is_superuser)
    ):
        raise PermissionDenied("Authentication Failed. Only validated apps are allowed")

    device = Device.objects.filter(aid=device_id).first()
    if not device:
        raise ValidationError("No such device ID")

    device_user_agent = request.session.user_agent[:200]
    if not device.user_agent or device_user_agent != device.user_agent:
        device.user_agent = device_user_agent

    try:
        lats = [float(x) for x in request.data.get("latitudes", "").split(",") if x]
        lons = [float(x) for x in request.data.get("longitudes", "").split(",") if x]
        times = [
            int(float(x)) for x in request.data.get("timestamps", "").split(",") if x
        ]
    except ValueError:
        raise ValidationError("Invalid data format")
    if not (len(lats) == len(lons) == len(times)):
        raise ValidationError(
            "Latitudes, longitudes, and timestamps, should have same amount of points"
        )
    loc_array = []
    for tim, lat, lon in zip(times, lats, lons):
        if tim and lat and lon:
            try:
                validate_longitude(lon)
            except DjangoValidationError:
                raise ValidationError("Invalid longitude value")
            try:
                validate_latitude(lat)
            except DjangoValidationError:
                raise ValidationError("Invalid latitude value")
            loc_array.append((tim, lat, lon))

    if battery_level_posted:
        try:
            battery_level = int(battery_level_posted)
        except Exception:
            pass
            # raise ValidationError("Invalid battery_level value type")
            # Do not raise exception to stay compatible with legacy apps
        else:
            if battery_level < 0 or battery_level > 100:
                # raise ValidationError("battery_level value not in 0-100 range")
                # Do not raise exception to stay compatible with legacy apps
                pass
            else:
                device.battery_level = battery_level

    if len(loc_array) > 0:
        device.add_locations(loc_array, save=False)
    device.save()
    return Response(
        {"status": "ok", "location_count": len(loc_array), "device_id": device.aid},
        status=status.HTTP_201_CREATED,
    )


class DataRenderer(renderers.BaseRenderer):
    media_type = "application/download"
    format = "raw"
    charset = None
    render_style = "binary"

    def render(self, data, media_type=None, renderer_context=None):
        return data


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def get_version(request):
    return Response({"v": git_master_hash()})


@swagger_auto_schema(
    method="post",
    operation_id="device_create",
    operation_description="Request a tracker ID. You need to be identified to get a valid answer unless you provide a valid IMEI.",
    tags=["Devices"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "imei": openapi.Schema(
                type=openapi.TYPE_STRING,
                example="<IMEI>",
                description="Dedicated GPS tracking device IMEI (Optional)",
            ),
        },
        required=[],
    ),
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "status": "ok",
                    "imei": "<IMEI>",
                    "device_id": "<device_id>",
                }
            },
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_POST_view
@throttle_classes([PostDataThrottle])
def create_device_id(request):
    imei = request.data.get("imei")
    if imei:
        try:
            validate_imei(imei)
        except Exception as e:
            raise ValidationError(str(e.message))
        status_code = status.HTTP_200_OK
        try:
            idevice = (
                ImeiDevice.objects.select_related("device")
                .defer("device__locations_encoded")
                .get(imei=imei)
            )
        except ImeiDevice.DoesNotExist:
            device = Device.objects.create()
            idevice = ImeiDevice.objects.create(imei=imei, device=device)
            status_code = status.HTTP_201_CREATED
        else:
            device = idevice.device
            if (
                re.search(r"[^0-9]", device.aid)
                and not device.competitor_set.filter(
                    event__end_date__gte=now()
                ).exists()
            ):
                device.aid = random_device_id()
                status_code = status.HTTP_201_CREATED
        return Response(
            {"status": "ok", "device_id": device.aid, "imei": imei}, status=status_code
        )
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise PermissionDenied(
            "Authentication Failed, Only validated apps can generate Tracker IDs"
        )
    device = Device.objects.create(user_agent=request.session.user_agent[:200])
    return Response(
        {"status": "ok", "device_id": device.aid}, status=status.HTTP_201_CREATED
    )


@swagger_auto_schema(
    method="get",
    operation_id="server_time_get",
    operation_description="Return the server unix epoch time.",
    tags=["Miscellaneous"],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={"application/json": {"time": 1615987017.7934635}},
        ),
    },
)
@swagger_auto_schema(
    method="post",
    operation_id="server_time_post",
    operation_description="Return the server unix epoch time.",
    tags=["Miscellaneous"],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={"application/json": {"time": 1615987017.7934635}},
        ),
    },
)
@api_GET_POST_view
def get_time(request):
    return Response({"time": time.time()}, headers={"Cache-Control": "no-cache"})


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
@permission_classes([IsAuthenticated])
def user_search(request):
    # TODO: Remove this endpoint
    users = []
    q = request.GET.get("q")
    if q and len(q) > 2:
        users = User.objects.filter(username__icontains=q).values_list(
            "id", "username"
        )[:10]
    return Response({"results": [{"id": u[0], "username": u[1]} for u in users]})


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
@permission_classes([IsAuthenticated])
def user_view(request):
    user = request.user
    clubs = Club.objects.filter(admins=user)
    output = {
        "username": user.username,
        "clubs": [{"name": c.name, "slug": c.slug} for c in clubs],
    }
    return Response(output, headers={"Cache-Control": "Private"})


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def device_search(request):
    devices = []
    aid = request.GET.get("aid", "") == "true"
    q = request.GET.get("q")
    if q and len(q) > 4:
        devices = Device.objects.filter(aid__startswith=q, virtual=False).values_list(
            "id", "aid"
        )[:10]
    return Response(
        {"results": [{"id": d[1 if aid else 0], "device_id": d[1]} for d in devices]}
    )


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def device_registrations(request, device_id):
    device = get_object_or_404(Device, aid=device_id, virtual=False)
    competitors = device.competitor_set.filter(event__end_date__gte=now())
    return Response({"count": 1 if competitors.exists() else 0})


@swagger_auto_schema(
    methods=["patch", "delete"],
    auto_schema=None,
)
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def device_ownership_api_view(request, club_slug, device_id):
    # TODO: Implement GET method, make sure it does not create then if ownership missing
    club = get_object_or_404(Club, slug__iexact=club_slug)

    is_club_admin = club.is_admin(request.user)
    if not is_club_admin:
        raise PermissionDenied()

    device = get_object_or_404(Device, aid=device_id, virtual=False)

    ownership, created = DeviceClubOwnership.objects.get_or_create(
        device=device, club=club
    )

    info = {
        "nickname": ownership.nickname,
    }

    if device.gpsseuranta_relay_until:
        info["gpsseuranta_until"] = device.gpsseuranta_relay_until

    if request.method == "PATCH":
        nick = request.data.get("nickname")
        if nick and len(nick) > 12:
            if created:
                ownership.delete()
            raise ValidationError("Can not be more than 12 characters")

        activate_gpsseuranta = request.data.get("activate-gpsseuranta-relay")
        deactivate_gpsseuranta = request.data.get("deactivate-gpsseuranta-relay")
        if (
            activate_gpsseuranta or deactivate_gpsseuranta
        ) and not device.gpsseuranta_known:
            raise ValidationError("Device is not known by GPSSeuranta.net")

        if activate_gpsseuranta:
            device.gpsseuranta_relay_until = now() + timedelta(hours=24)
            device.save()
            info["gpsseuranta_until"] = device.gpsseuranta_relay_until
        elif deactivate_gpsseuranta:
            device.gpsseuranta_relay_until = now()
            device.save()
            info["gpsseuranta_until"] = device.gpsseuranta_relay_until
        if nick:
            ownership.nickname = nick
            ownership.save()
            info["nickname"] = nick

    if request.method == "DELETE":
        ownership.delete()
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)

    headers = {}
    if is_club_admin:
        headers["Cache-Control"] = "Private"

    return Response(info, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@swagger_auto_schema(
    method="post",
    auto_schema=None,
)
@api_GET_POST_view
def event_map_list(request, event_id):
    if request.method == "POST" and not request.user.is_authenticated:
        raise NotAuthenticated()

    event = (
        Event.objects.select_related("club", "notice", "map")
        .prefetch_related(
            Prefetch(
                "map_assignations",
                queryset=MapAssignation.objects.select_related("map"),
            )
        )
        .filter(aid=event_id)
        .first()
    )
    if not event:
        raise Http404()

    event.check_user_permission(request.user)
    is_event_admin = event.club.is_admin(request.user)

    if request.method == "POST":
        if not is_event_admin:
            raise PermissionDenied()

        if not isinstance(request.data, dict):
            raise ValidationError("Invalid data type")

        coordinates_input = request.data.get("coordinates")
        image_input = request.data.get("url")
        title_input = request.data.get("title")

        if not coordinates_input:
            raise ValidationError("Missing coordinates value")
        if not title_input:
            raise ValidationError("Missing title value")
        if not image_input:
            raise ValidationError("Missing url value")

        raster_map = Map(club_id=event.club_id)
        try:
            raster_map.bound_api = coordinates_input
        except Exception:
            raise ValidationError("Invalid coordinates value")

        try:
            raster_map.data_uri = image_input
        except Exception:
            if not image_input.startswith("data:"):
                raise ValidationError("Invalid url value (Only data URI are accepted)")
            raise ValidationError("Invalid url value")

        if not isinstance(title_input, str):
            raise ValidationError("Invalid title value (Should be a string)")
        if len(title_input) > 255:
            raise ValidationError("Invalid title value (Too long)")

        other_titles = {title for _, title, _ in event.enumerate_maps()}
        if title_input in other_titles:
            raise ValidationError(
                "Invalid title value (Event can not include 2 maps with same title)"
            )

        raster_map.name = f"{event.name} - {title_input}"
        raster_map.save()

        index = 0
        if not event.map:
            event.map = raster_map
            event.map_title = title_input
            event.save()
        else:
            index = len(event.map_assignations.all()) + 1
            MapAssignation.objects.create(
                event=event, map=raster_map, title=title_input
            )
        map_data = serialize_map(event, index, raster_map, title_input)
        return Response(map_data, status=status.HTTP_201_CREATED)

    if not event.could_display_maps(request.user):
        return Response(status=status.HTTP_425_TOO_EARLY)

    maps = []
    for i, (raster_map, title, tags) in enumerate(event.enumerate_maps()):
        maps.append(serialize_map(event, i, raster_map, title, tags))

    headers = {}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    return Response(maps, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@swagger_auto_schema(
    method="patch",
    auto_schema=None,
)
@swagger_auto_schema(
    method="delete",
    auto_schema=None,
)
@api_view(["GET", "HEAD", "PATCH", "DELETE"])
def event_map_detail(request, event_id, index="1", **kwargs):
    if request.method in ("PATCH", "DELETE") and not request.user.is_authenticated:
        raise NotAuthenticated()

    event, raster_map, _, assignation = Event.get_map_at_index(
        request.user, event_id, index
    )
    is_event_admin = event.club.is_admin(request.user)

    if request.method == "DELETE":
        if not is_event_admin:
            raise PermissionDenied()
        # We actually just unassign the map from the event
        # We must re-assign the main map of event if there is many maps
        if event.map_id in raster_map.id:
            event.map = None
            event.map_title = ""
            next_map_assigment = event.map_assignations.first()
            if next_map_assigment:
                event.map = next_map_assigment.map
                event.map_title = next_map_assigment.title
                next_map_assigment.delete()
            event.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if request.method == "PATCH":
        if not is_event_admin:
            raise PermissionDenied()
        coordinates_input = request.data.get("coordinates")
        image_input = request.data.get("url")
        title_input = request.data.get("title")

        if coordinates_input:
            try:
                raster_map.bound_api = coordinates_input
            except Exception:
                raise ValidationError("Invalid coordinates value")

        if image_input:
            try:
                raster_map.data_uri = image_input
            except Exception:
                if not image_input.startswith("data:"):
                    raise ValidationError(
                        "Invalid url value (Only data URI are accepted)"
                    )
                raise ValidationError("Invalid url value")

        if title_input:
            if not isinstance(title_input, str):
                raise ValidationError("Invalid title value")
            if len(title_input) > 255:
                raise ValidationError("Invalid title value (Too long)")

            all_titles = [title for _, title, _ in event.enumerate_maps()]
            all_titles.pop(int(index) - 1)
            other_titles = set(all_titles)
            if title_input in other_titles:
                raise ValidationError(
                    "Invalid title value (Event can not include 2 maps with same title)"
                )

        if image_input or coordinates_input:
            raster_map.save()

        if title_input:
            if assignation:
                current_title = assignation.title
            else:
                current_title = event.map_title

            if title_input != current_title:
                if assignation:
                    assignation.title = title_input
                    assignation.save()
                else:
                    event.map_title = title_input
                    event.save()

    map_data = serialize_map(
        event,
        int(index) - 1,
        raster_map,
        event.map_title if not assignation else assignation.title,
    )

    headers = {}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"
    return Response(map_data, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def event_map_download(request, event_id, index="1", **kwargs):
    event, raster_map, title, _ = Event.get_map_at_index(request.user, event_id, index)

    is_event_admin = event.club.is_admin(request.user)

    headers = {}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    if kwargs.get("extension") == "kmz":
        kmz_data = raster_map.kmz

        filename = f"{event.name} - {title}.kmz"
        response = StreamingHttpRangeResponse(
            request,
            kmz_data,
            content_type="application/vnd.google-earth.kmz",
            headers=headers,
        )
        response["Content-Disposition"] = set_content_disposition(filename)
        return response

    mime = get_image_mime_from_request(kwargs.get("extension"), raster_map.mime_type)

    resp = serve_image_from_s3(
        request,
        raster_map.image,
        (f"{event.name} - {title}_" f"{raster_map.get_calibration_string()}_"),
        mime=mime,
        headers=headers,
    )
    return resp


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def event_geojson_download(request, event_id):
    # TODO: Implement POST to set geojson AND DELETE to remove the geojson
    event = get_object_or_404(
        Event.objects.exclude(geojson_layer="").exclude(geojson_layer__isnull=True),
        aid=event_id,
    )

    event.check_user_permission(request.user)
    is_event_admin = event.club.is_admin(request.user)
    if not event.could_display_maps(request.user):
        raise Response(status=status.HTTP_425_TOO_EARLY)

    headers = {}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    filename = f"{event.name}.geojson"
    return serve_from_s3(
        settings.AWS_S3_BUCKET,
        request,
        event.geojson_layer.file.name,
        filename=filename,
        mime="application/json",
        headers=headers,
    )


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def competitor_gpx_download(request, competitor_id):
    competitor = get_object_or_404(
        Competitor.objects.select_related("event", "event__club", "device"),
        aid=competitor_id,
    )

    event = competitor.event

    event.check_user_permission(request.user)
    is_event_admin = event.club.is_admin(request.user)
    if competitor.start_time > now() or not event.could_display_maps(request.user):
        raise Response(status=status.HTTP_425_TOO_EARLY)

    gpx_data = competitor.gpx

    headers = {}
    if is_event_admin or event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    response = StreamingHttpRangeResponse(
        request,
        gpx_data.encode(),
        content_type="application/gpx+xml",
        headers=headers,
    )
    filename = f"{competitor.event.name} - {competitor.name}.gpx"
    response["Content-Disposition"] = set_content_disposition(filename)
    return response


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def two_d_rerun_race_status(request):
    args = request.GET.get("eventid", "")
    args_match = re.match(
        r"^(?P<event_id>[^\/]+)(\/(?P<map_idx>[1-9][\d]*))?(\/(?P<category>.+))?$", args
    )
    if not args_match:
        raise Http404()

    event_id = args_match.group("event_id")
    map_idx = int(args_match.group("map_idx") or 1)
    tag = args_match.group("category")

    event, raster_map, _, _ = Event.get_map_at_index(request.user, event_id, map_idx)

    event.check_user_permission(request.user)

    if event.start_date > now() or not event.could_display_maps():
        return Response(status=status.HTTP_425_TOO_EARLY)

    map_url = reverse(
        "event_map_download_with_format",
        host="api",
        kwargs={
            "event_id": event.aid,
            "index": map_idx,
            "extension": "webp",
        },
    )

    response_json = {
        "status": "OK",
        "racename": event.name,
        "racestarttime": event.start_date,
        "raceendtime": event.end_date,
        "mapurl": f"https:{map_url}?.jpg",
        "caltype": "3point",
        "mapw": raster_map.width,
        "maph": raster_map.height,
        "calibration": [
            [
                raster_map.bound[TOP_LEFT].longitude,
                raster_map.bound[TOP_LEFT].latitude,
                0,
                0,
            ],
            [
                raster_map.bound[TOP_RIGHT].longitude,
                raster_map.bound[TOP_RIGHT].latitude,
                raster_map.width,
                0,
            ],
            [
                raster_map.bound[BOTTOM_LEFT].longitude,
                raster_map.bound[BOTTOM_LEFT].latitude,
                0,
                raster_map.height,
            ],
        ],
        "competitors": [],
    }

    if tag is None:
        competitors = event.competitors.all()
    else:
        competitors = event.get_competitors_in_category(tag)
    for competitor in competitors:
        response_json["competitors"].append(
            [competitor.aid, competitor.name, competitor.start_time]
        )

    response_raw = str(json.dumps(response_json), "utf-8")
    content_type = "application/json"
    callback = request.GET.get("callback")
    if callback:
        response_raw = f"/**/{callback}({response_raw});"
        content_type = "text/javascript; charset=utf-8"

    headers = {}
    if event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    return HttpResponse(response_raw, content_type=content_type, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_GET_view
def two_d_rerun_race_data(request):
    args = request.GET.get("eventid", "")
    args_match = re.match(
        r"^(?P<event_id>[^\/]+)(\/(?P<map_idx>[1-9][\d]*))?(\/(?P<category>.+))?$", args
    )
    if not args_match:
        raise Http404()

    event_id = args_match.group("event_id")
    tag = args_match.group("category")

    event = get_object_or_404(
        Event.objects.prefetch_related(
            Prefetch(
                "competitors",
                queryset=Competitor.objects.select_related("device").order_by(
                    "start_time", "name"
                ),
            )
        ),
        aid=event_id,
    )

    event.check_user_permission(request.user)

    if event.start_date > now() or not event.could_display_maps():
        return Response(status=status.HTTP_425_TOO_EARLY)

    total_nb_pts = 0
    results = []
    for competitor, from_date, end_date in event.iterate_competitors(tag):
        if competitor.device_id:
            locations, nb_pts = competitor.device.get_locations_between_dates(
                from_date, end_date
            )
            total_nb_pts += nb_pts
            results += [
                [
                    competitor.aid,
                    location[LOCATION_LATITUDE_INDEX],
                    location[LOCATION_LONGITUDE_INDEX],
                    0,
                    epoch_to_datetime(location[LOCATION_TIMESTAMP_INDEX]),
                ]
                for location in locations
            ]
    response_json = {
        "containslastpos": 1,
        "lastpos": total_nb_pts,
        "status": "OK",
        "data": results,
    }
    response_raw = str(json.dumps(response_json), "utf-8")
    content_type = "application/json"
    callback = request.GET.get("callback")
    if callback:
        response_raw = f"/**/{callback}({response_raw});"
        content_type = "text/javascript; charset=utf-8"

    headers = {}
    if event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    return HttpResponse(
        response_raw,
        content_type=content_type,
        headers=headers,
    )


class CustomApiLoginView(CustomLoginView):
    login_url = "/login/"

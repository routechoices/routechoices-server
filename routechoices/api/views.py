import hashlib
import logging
import re
import time
import urllib.parse
import uuid
from datetime import timedelta

import arrow
import orjson as json
import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.gis.geoip2 import GeoIP2
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.http.response import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.views.decorators.http import etag, last_modified
from django_hosts.resolvers import reverse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import renderers, status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from routechoices.core.models import (
    EVENT_CACHE_INTERVAL,
    LOCATION_LATITUDE_INDEX,
    LOCATION_LONGITUDE_INDEX,
    LOCATION_TIMESTAMP_INDEX,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    PRIVACY_SECRET,
    ChatMessage,
    Club,
    Competitor,
    Device,
    DeviceClubOwnership,
    Event,
    ImeiDevice,
    Map,
)
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import (
    epoch_to_datetime,
    escape_filename,
    initial_of_name,
    random_device_id,
    safe64decode,
    safe64encode,
)
from routechoices.lib.s3 import s3_object_url
from routechoices.lib.validators import (
    validate_imei,
    validate_latitude,
    validate_longitude,
)

logger = logging.getLogger(__name__)
# API_LOCATION_TIMESTAMP_MAX_AGE = 60 * 10
GLOBAL_MERCATOR = GlobalMercator()


class PostDataThrottle(AnonRateThrottle):
    rate = "70/min"

    def allow_request(self, request, view):
        if request.method == "GET":
            return True
        return super().allow_request(request, view)


def serve_from_s3(
    bucket, request, path, filename="", mime="application/force-download", headers=None
):
    path = re.sub(r"^/internal/", "", path)
    url = s3_object_url(path, bucket)
    url = f"/s3{url[len(settings.AWS_S3_ENDPOINT_URL):]}"

    response_status = status.HTTP_200_OK
    if request.method == "GET":
        response_status = status.HTTP_206_PARTIAL_CONTENT

    response = HttpResponse("", status=response_status, headers=headers)

    if request.method == "GET":
        response["X-Accel-Redirect"] = urllib.parse.quote(url.encode("utf-8"))
        response["X-Accel-Buffering"] = "no"
    response["Accept-Ranges"] = "bytes"
    response["Content-Type"] = mime
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{escape_filename(filename)}"'
    return response


club_param = openapi.Parameter(
    "club",
    openapi.IN_QUERY,
    description="filter with this club slug",
    type=openapi.TYPE_STRING,
)
event_param = openapi.Parameter(
    "event",
    openapi.IN_QUERY,
    description="filter with this event slug",
    type=openapi.TYPE_STRING,
)


@swagger_auto_schema(
    method="get",
    operation_id="events_list",
    operation_description="list events",
    tags=["events"],
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
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "open_registration": False,
                        "open_route_upload": False,
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-1st-leg",
                    },
                    {
                        "id": "ohFYzJep1hI",
                        "name": "Jukola 2019 - 2nd Leg",
                        "start_date": "2019-06-15T21:00:00Z",
                        "end_date": "2019-06-16T00:00:00Z",
                        "slug": "Jukola-2019-2nd-leg",
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "open_registration": False,
                        "open_route_upload": False,
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-2nd-leg",
                    },
                    "...",
                ]
            },
        ),
    },
)
@api_view(["GET"])
def event_list(request):
    club_slug = request.GET.get("club")
    event_slug = request.GET.get("event")
    if event_slug and club_slug:
        privacy_arg = {"privacy__in": [PRIVACY_PUBLIC, PRIVACY_SECRET]}
    else:
        privacy_arg = {"privacy": PRIVACY_PUBLIC}

    if request.user.is_authenticated:
        clubs = Club.objects.filter(admins=request.user)
        events = Event.objects.filter(
            Q(**privacy_arg) | Q(club__in=clubs)
        ).select_related("club")
    else:
        events = Event.objects.filter(**privacy_arg).select_related("club")

    if club_slug:
        events = events.filter(club__slug__iexact=club_slug)
    if event_slug:
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
                "club": event.club.name,
                "club_slug": event.club.slug.lower(),
                "open_registration": event.open_registration,
                "open_route_upload": event.allow_route_upload,
                "url": request.build_absolute_uri(event.get_absolute_url()),
            }
        )
    return Response(output)


@swagger_auto_schema(
    method="get",
    operation_id="event_detail",
    operation_description="read an event detail",
    tags=["events"],
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
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "open_registration": False,
                        "open_route_upload": False,
                        "url": "https://www.routechoices.com/ksk/Jukola-2019-1st-leg",
                        "shortcut": "https://routechoic.es/PlCG3xFS-f4",
                        "backdrop": "osm",
                        "send_interval": 5,
                        "tail_length": 60,
                    },
                    "competitors": [
                        {
                            "id": "pwaCro4TErI",
                            "name": "Olav Lundanes (Halden SK)",
                            "short_name": "Halden SK",
                            "start_time": "2019-06-15T20:00:00Z",
                        },
                        "...",
                    ],
                    "data": "https://www.routechoices.com/api/events/PlCG3xFS-f4/data",
                    "announcement": "",
                    "maps": [
                        {
                            "coordinates": {
                                "topLeft": {"lat": "61.45075", "lon": "24.18994"},
                                "topRight": {"lat": "61.44656", "lon": "24.24721"},
                                "bottomRight": {"lat": "61.42094", "lon": "24.23851"},
                                "bottomLeft": {"lat": "61.42533", "lon": "24.18156"},
                            },
                            "url": "https://www.routechoices.com/api/events/PlCG3xFS-f4/map",
                            "title": "",
                            "hash": "u8cWoEiv2z1Cz2bjjJ66b2EF4groSULVlzKg9HGE1gM=",
                            "last_mod": "2019-06-10T17:21:52.417000Z",
                            "default": True,
                        }
                    ],
                }
            },
        ),
    },
)
@api_view(["GET"])
def event_detail(request, event_id):
    event = get_object_or_404(
        Event.objects.select_related("club", "notice").prefetch_related(
            "competitors",
        ),
        aid=event_id,
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    output = {
        "event": {
            "id": event.aid,
            "name": event.name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "slug": event.slug,
            "club": event.club.name,
            "club_slug": event.club.slug.lower(),
            "open_registration": event.open_registration,
            "open_route_upload": event.allow_route_upload,
            "chat_enabled": event.allow_live_chat,
            "url": request.build_absolute_uri(event.get_absolute_url()),
            "shortcut": event.shortcut,
            "backdrop": event.backdrop_map,
            "send_interval": event.send_interval,
            "tail_length": event.tail_length,
        },
        "competitors": [],
        "data": request.build_absolute_uri(
            reverse("event_data", host="api", kwargs={"event_id": event.aid})
        ),
        "announcement": "",
        "maps": [],
    }
    if event.start_date < now():
        output["announcement"] = event.notice.text if event.has_notice else ""
        for c in event.competitors.all():
            output["competitors"].append(
                {
                    "id": c.aid,
                    "name": c.name,
                    "short_name": c.short_name,
                    "start_time": c.start_time,
                }
            )
        if event.map:
            output["maps"].append(
                {
                    "title": event.map_title,
                    "coordinates": event.map.bound,
                    "url": request.build_absolute_uri(
                        reverse(
                            "event_map_download",
                            host="api",
                            kwargs={"event_id": event.aid},
                        )
                    ),
                    "hash": event.map.hash,
                    "last_mod": event.map.modification_date,
                    "default": True,
                }
            )
        for i, m in enumerate(event.map_assignations.all().select_related("map")):
            output["maps"].append(
                {
                    "title": m.title,
                    "coordinates": m.map.bound,
                    "url": request.build_absolute_uri(
                        reverse(
                            "event_map_download",
                            host="api",
                            kwargs={"event_id": event.aid, "map_index": (i + 1)},
                        )
                    ),
                    "hash": m.map.hash,
                    "last_mod": m.map.modification_date,
                    "default": False,
                }
            )
    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return Response(output, headers=headers)


@swagger_auto_schema(
    method="post",
    auto_schema=None,
)
@swagger_auto_schema(
    method="delete",
    auto_schema=None,
)
@api_view(["POST", "DELETE"])
@throttle_classes(
    [
        PostDataThrottle,
    ]
)
def event_chat(request, event_id):
    event = get_object_or_404(
        Event,
        aid=event_id,
        start_date__lte=now(),
        allow_live_chat=True,
    )

    if request.method == "DELETE":
        if not request.user.is_superuser:
            if (
                not request.user.is_authenticated
                or not event.club.admins.filter(id=request.user.id).exists()
            ):
                raise PermissionDenied()
        msg_uuid = request.data.get("uuid")
        if not msg_uuid:
            raise ValidationError("Missing parameter")
        msg = ChatMessage.objects.get(
            uuid=uuid.UUID(bytes=safe64decode(request.data.get("uuid")))
        )
        if msg:
            msg.delete()
            try:
                requests.delete(
                    f"http://127.0.0.1:8009/{event_id}",
                    data=json.dumps(msg.serialize()),
                    headers={
                        "Authorization": f"Bearer {settings.CHAT_INTERNAL_SECRET}"
                    },
                )
            except Exception:
                pass
        return Response({"status": "deleted"}, status=201)

    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()

    if event.end_date <= now():
        raise Http404()

    nickname = request.data.get("nickname")
    message = request.data.get("message")
    if not nickname or not message:
        raise ValidationError("Missing parameter")

    remote_ip = request.META["REMOTE_ADDR"]

    msg = ChatMessage.objects.create(
        nickname=nickname, message=message, ip_address=remote_ip, event=event
    )
    try:
        requests.post(
            f"http://127.0.0.1:8009/{event_id}",
            data=json.dumps(msg.serialize()),
            headers={"Authorization": f"Bearer {settings.CHAT_INTERNAL_SECRET}"},
        )
    except Exception:
        pass
    return Response({"status": "sent"}, status=201)


@swagger_auto_schema(
    method="post",
    operation_id="event_register",
    operation_description="register a competitor to a given event",
    tags=["events"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="device id",
            ),
            "name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="full name",
            ),
            "short_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="short version of the name displayed on the map",
            ),
            "start_time": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="start time, must be within the event schedule if provided (YYYY-MM-DDThh:mm:ssZ)",
            ),
        },
        required=["device_id", "name"],
    ),
    responses={
        "201": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "id": "<id>",
                    "device_id": "<device_id>",
                    "name": "<name>",
                    "short_name": "<short_name>",
                    "start_time": "<start_time>",
                }
            },
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_view(["POST"])
def event_register(request, event_id):
    event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)

    if not event.open_registration or event.end_date < now():
        raise PermissionDenied()

    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        is_user_event_admin = (
            request.user.is_authenticated
            and event.club.admins.filter(id=request.user.id).exists()
        )
        if not is_user_event_admin:
            raise PermissionDenied()

    device_id = request.data.get("device_id")
    device = Device.objects.filter(aid=device_id).first()

    lang = request.GET.get("lang", "en")
    if lang not in ("en", "es", "fi", "fr", "nl", "sv"):
        lang = "en"

    err_messages = {
        "en": {
            "no-device-id": "Device ID not found",
            "no-name": "Name is missing",
            "invalid-start-time": "Start time could not be parsed",
            "bad-start-time": "Competitor start time should be during the event time",
            "bad-name": "Competitor with same name already registered",
            "bad-sname": "Competitor with same short name already registered",
        },
        "es": {
            "no-device-id": "ID del dispositivo no encontrado",
            "no-name": "Falta el nombre",
            "invalid-start-time": "La hora de inicio no pudo ser analizada",
            "bad-start-time": "La hora de inicio del competidor debe ser durante la hora del evento.",
            "bad-name": "Competidor con el mismo nombre ya registrado",
            "bad-sname": "Competidor con el mismo nombre corto ya registrado",
        },
        "fr": {
            "no-device-id": "Identifiant de l'appareil introuvable",
            "no-name": "Nom est manquant",
            "invalid-start-time": "Impossible d'extraire l'heure de début",
            "bad-start-time": "L'heure de départ du concurrent doit être durant l'événement",
            "bad-name": "Participant avec le même nom déjà inscrit",
            "bad-sname": "Participant avec le même nom court déjà inscrit",
        },
        "fi": {
            "no-device-id": "Laitetunnusta ei löydy",
            "no-name": "Nimi puuttuu",
            "invalid-start-time": "Aloitusaikaa ei voitu jäsentää",
            "bad-start-time": "Kilpailijan aloitusajan tulee olla tapahtuman aikana",
            "bad-name": "Kilpailija samalla nimellä jo rekisteröitynyt",
            "bad-sname": "Kilpailija samalla lyhyellä nyhyelläimellä jo rekisteröitynyt",
        },
        "nl": {
            "no-device-id": "Toestel ID niet gevonden",
            "no-name": "Naam ontbreekt",
            "invalid-start-time": "Start tijd kan niet worden ontleed",
            "bad-start-time": "Starttijd van de atleet is tijdens de event tijd",
            "bad-name": "Atleet met zelfde naam bestaat al",
            "bad-sname": "Atleet met zelfde korte naam bestaat al",
        },
        "sv": {
            "no-device-id": "Enhets-ID hittades inte",
            "no-name": "Namn saknas",
            "invalid-start-time": "Starttiden kunde inte hittas",
            "bad-start-time": "Tävlandes starttid bör vara under evenemangstiden",
            "bad-name": "Tävlande med samma namn är redan registrerad",
            "bad-sname": "Tävlande med samma förkortning är redan registrerad",
        },
    }

    errs = []

    if not device:
        errs.append(err_messages[lang]["no-device-id"])

    name = request.data.get("name")

    if not name:
        errs.append(err_messages[lang]["no-name"])
    short_name = request.data.get("short_name")
    if not short_name:
        short_name = initial_of_name(name)
    start_time = request.data.get("start_time")
    if start_time:
        try:
            start_time = arrow.get(start_time).datetime
        except Exception:
            start_time = None
            errs.append(err_messages[lang]["invalid-start-time"])
    elif event.start_date < now():
        start_time = now()
    else:
        start_time = event.start_date
    event_start = event.start_date
    event_end = event.end_date

    if start_time and (event_start > start_time or start_time > event_end):
        errs.append(err_messages[lang]["bad-start-time"])

    if event.competitors.filter(name=name).exists():
        errs.append(err_messages[lang]["bad-name"])

    if event.competitors.filter(short_name=short_name).exists():
        errs.append(err_messages[lang]["bad-sname"])

    if errs:
        raise ValidationError(errs)

    comp = Competitor.objects.create(
        name=name,
        event=event,
        short_name=short_name,
        start_time=start_time,
        device=device,
    )

    return Response(
        {
            "id": comp.aid,
            "device_id": device.aid,
            "name": name,
            "short_name": short_name,
            "start_time": start_time,
        },
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method="delete",
    operation_id="event_delete_competitor",
    operation_description="delete a competitor from a given event",
    tags=["events"],
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
@api_view(["DELETE"])
@login_required
def event_delete_competitor(request, event_id, competitor_id):
    event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)
    is_user_event_admin = request.user.is_superuser or (
        request.user.is_authenticated
        and event.club.admins.filter(id=request.user.id).exists()
    )
    if not is_user_event_admin:
        raise PermissionDenied()
    c = event.competitors.filter(aid=competitor_id).first()
    if not c:
        raise ValidationError("no such competitor in this event")
    c.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(
    method="post",
    operation_id="event_upload_route",
    operation_description="register a competitor to a given event and upload its positions",
    tags=["events"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="full name",
            ),
            "short_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="short version of the name displayed on the map",
            ),
            "start_time": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="start time, must be within the event schedule if provided (YYYY-MM-DDThh:mm:ssZ)",
            ),
            "latitudes": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="a list of locations latitudes (in degrees) separated by commas",
            ),
            "longitudes": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="a list of locations longitudes (in degrees) separated by commas",
            ),
            "timestamps": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="a list of locations timestamps (UNIX epoch in seconds) separated by commas",
            ),
        },
        required=["name"],
    ),
    responses={
        "201": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "id": "<id>",
                    "device_id": "<device_id>",
                    "name": "<name>",
                    "short_name": "<short_name>",
                    "start_time": "<start_time>",
                }
            },
        ),
        "400": openapi.Response(
            description="Validation Error",
            examples={"application/json": ["<error message>"]},
        ),
    },
)
@api_view(["POST"])
def event_upload_route(request, event_id):
    event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)
    is_user_event_admin = (
        request.user.is_authenticated
        and event.club.admins.filter(id=request.user.id).exists()
    )
    if not is_user_event_admin:
        if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
            raise PermissionDenied()
        if not event.allow_route_upload or event.start_date > now():
            raise PermissionDenied()
    errs = []

    name = request.data.get("name")

    if not name:
        errs.append("Property name is missing")
    short_name = request.data.get("short_name")
    if not short_name:
        short_name = initial_of_name(name)

    if event.competitors.filter(name=name).exists():
        errs.append("Competitor with same name already registered")

    if event.competitors.filter(short_name=short_name).exists():
        errs.append("Competitor with same short name already registered")

    lats = request.data.get("latitudes", "").split(",")
    lons = request.data.get("longitudes", "").split(",")
    times = request.data.get("timestamps", "").split(",")
    if len(lats) != len(lons) != len(times):
        raise ValidationError(
            "latitudes, longitudes, and timestamps, should have same ammount of points"
        )
    loc_array = []
    start_pt_ts = (event.end_date + timedelta(seconds=1)).timestamp()
    for i in range(len(times)):
        if times[i] and lats[i] and lons[i]:
            try:
                lat = float(lats[i])
                lon = float(lons[i])
                tim = int(float(times[i]))
                start_pt_ts = min(tim, start_pt_ts)
            except ValueError:
                continue
            loc_array.append((tim, lat, lon))

    start_pt_dt = epoch_to_datetime(start_pt_ts)
    if event.start_date > start_pt_dt or start_pt_dt > event.end_date:
        start_pt_dt = event.start_date
    start_time = request.data.get("start_time")
    if start_time:
        try:
            start_time = arrow.get(start_time).datetime
        except Exception:
            errs.append("Start time could not be parsed")
    else:
        start_time = start_pt_dt

    event_start = event.start_date
    event_end = event.end_date

    if start_time and (event_start > start_time or start_time > event_end):
        errs.append("Competitor start time should be during the event time")

    if errs:
        raise ValidationError("\r\n".join(errs))

    device = None
    if len(loc_array) > 0:
        device = Device.objects.create(
            user_agent=request.session.user_agent[:200], is_gpx=True
        )
        device.add_locations(loc_array, push_forward=False)

    comp = Competitor.objects.create(
        name=name,
        event=event,
        short_name=short_name,
        start_time=start_time,
        device=device,
    )

    return Response(
        {
            "id": comp.aid,
            "device_id": device.aid if device else "",
            "name": name,
            "short_name": short_name,
            "start_time": start_time,
        },
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method="get",
    operation_id="event_data",
    operation_description="read competitor data associated to an event",
    tags=["events"],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": {
                    "competitors": [
                        {
                            "id": "pwaCro4TErI",
                            "encoded_data": "<encoded data>",
                            "name": "Olav Lundanes (Halden SK)",
                            "short_name": "Halden SK",
                            "start_time": "2019-06-15T20:00:00Z",
                        }
                    ],
                    "nb_points": 0,
                    "duration": 0.009621381759643555,
                    "timestamp": 1615986763.638066,
                }
            },
        ),
    },
)
@api_view(["GET"])
def event_data(request, event_id):
    t0 = time.time()
    # First check if we have a live event cache
    # if we do return cache
    cache_interval = EVENT_CACHE_INTERVAL
    use_cache = getattr(settings, "CACHE_EVENT_DATA", False)
    live_cache_ts = int(t0 // cache_interval)
    live_cache_key = f"live_event_data:{event_id}:{live_cache_ts}"
    live_cached_res = cache.get(live_cache_key)
    if use_cache and live_cached_res:
        return Response(live_cached_res)

    event = get_object_or_404(
        Event.objects.select_related("club"), aid=event_id, start_date__lt=now()
    )

    cache_ts = int(t0 // (cache_interval if event.is_live else 7 * 24 * 3600))
    cache_prefix = "live" if event.is_live else "archived"
    cache_key = f"{cache_prefix}_event_data:{event_id}:{cache_ts}"
    prev_cache_key = f"{cache_prefix}_event_data:{event_id}:{cache_ts - 1}"
    # then if we have a cache for that
    # return it if we do
    cached_res = None
    if use_cache and not event.is_live:
        try:
            cached_res = cache.get(cache_key)
        except Exception:
            pass
        else:
            if cached_res:
                return Response(cached_res)
    # If we dont have cache check if we are currently generating cache
    # if so return previous cache data if available
    elif use_cache and cache.get(f"{cache_key}:processing"):
        try:
            cached_res = cache.get(prev_cache_key)
        except Exception:
            pass
        else:
            if cached_res:
                return Response(cached_res)
    # else generate data and set that we are generating cache
    if use_cache:
        try:
            cache.set(f"{cache_key}:processing", 1, 15)
        except Exception:
            pass
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    competitors = (
        event.competitors.select_related("device").all().order_by("start_time", "name")
    )
    devices = (c.device_id for c in competitors)
    all_devices_competitors = (
        Competitor.objects.filter(
            start_time__gte=event.start_date, device_id__in=devices
        )
        .only("device_id", "start_time")
        .order_by("start_time")
    )
    start_times_by_device = {}
    for c in all_devices_competitors:
        start_times_by_device.setdefault(c.device_id, [])
        start_times_by_device[c.device_id].append(c.start_time)
    nb_points = 0
    results = []
    for c in competitors:
        from_date = c.start_time
        next_competitor_start_time = None
        if c.device_id:
            for nxt in start_times_by_device.get(c.device_id, []):
                if nxt > c.start_time:
                    next_competitor_start_time = nxt
                    break
        end_date = now()
        if next_competitor_start_time:
            end_date = min(next_competitor_start_time, end_date)
        end_date = min(event.end_date, end_date)
        nb, encoded_data = (0, "")
        if c.device_id:
            nb, encoded_data = c.device.get_locations_between_dates(
                from_date, end_date, encoded=True
            )
        nb_points += nb
        results.append(
            {
                "id": c.aid,
                "encoded_data": encoded_data,
                "name": c.name,
                "short_name": c.short_name,
                "start_time": c.start_time,
            }
        )
    res = {
        "competitors": results,
        "nb_points": nb_points,
        "duration": (time.time() - t0),
        "timestamp": time.time(),
    }
    if use_cache:
        try:
            cache.set(cache_key, res, 20 if event.is_live else 7 * 24 * 3600 + 60)
        except Exception:
            pass
    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return Response(res, headers=headers)


def event_data_load_test(request, event_id):
    event_data(request, event_id)
    return HttpResponse("ok")


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def ip_latlon(request):
    g = GeoIP2()
    headers = {"Cache-Control": "Private"}
    try:
        lat, lon = g.lat_lon(request.META["REMOTE_ADDR"])
    except Exception:
        return Response({"status": "fail"}, headers=headers)
    return Response({"status": "success", "lat": lat, "lon": lon}, headers=headers)


@swagger_auto_schema(
    method="post",
    auto_schema=None,
)
@api_view(["POST"])
@throttle_classes([PostDataThrottle])
def locations_api_gw(request):
    secret_provided = request.data.get("secret")
    battery_level = request.data.get("battery")
    device_id = request.data.get("device_id")
    if not device_id:
        raise ValidationError("Missing device_id parameter")
    if (
        re.match(r"^[0-9]+$", device_id)
        and secret_provided not in settings.POST_LOCATION_SECRETS
    ):
        raise PermissionDenied("Invalid secret")
    devices = Device.objects.filter(aid=device_id)
    if not devices.exists():
        raise ValidationError("No such device ID")
    device = devices.first()
    if not device.user_agent:
        device.user_agent = request.session.user_agent[:200]
    try:
        lats = [float(x) for x in request.data.get("latitudes", "").split(",") if x]
        lons = [float(x) for x in request.data.get("longitudes", "").split(",") if x]
        times = [
            int(float(x)) for x in request.data.get("timestamps", "").split(",") if x
        ]
    except ValueError:
        raise ValidationError("Invalid data format")
    if len(lats) != len(lons) != len(times):
        raise ValidationError(
            "Latitudes, longitudes, and timestamps, should have same amount of points"
        )
    loc_array = []
    for i in range(len(times)):
        if times[i] and lats[i] and lons[i]:
            lat = lats[i]
            lon = lons[i]
            tim = times[i]
            try:
                validate_longitude(lon)
            except DjangoValidationError:
                raise ValidationError("Invalid longitude value")
            try:
                validate_latitude(lat)
            except DjangoValidationError:
                raise ValidationError("Invalid latitude value")
            loc_array.append((tim, lat, lon))
    if battery_level:
        try:
            battery_level = int(battery_level)
        except Exception:
            battery_level = None
        else:
            if battery_level < 0 or battery_level > 100:
                battery_level = None
    else:
        battery_level = None
    device.battery_level = battery_level
    if len(loc_array) > 0:
        device.add_locations(loc_array, save=False)
    device.save()
    return Response({"status": "ok", "n": len(loc_array)})


class DataRenderer(renderers.BaseRenderer):
    media_type = "application/download"
    format = "raw"
    charset = None
    render_style = "binary"

    def render(self, data, media_type=None, renderer_context=None):
        return data


@swagger_auto_schema(
    method="post",
    auto_schema=None,
)
@api_view(["POST"])
def get_device_id(request):
    device = Device.objects.create(user_agent=request.session.user_agent[:200])
    return Response({"status": "ok", "device_id": device.aid})


@swagger_auto_schema(
    method="post",
    operation_id="create_imei_device_id",
    operation_description="create a device id for a specific imei",
    tags=["device"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "imei": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="your gps tracking device IMEI",
            ),
        },
        required=["imei"],
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
@api_view(["POST"])
def get_device_for_imei(request):
    imei = request.data.get("imei")
    if not imei:
        raise ValidationError("No IMEI")
    try:
        validate_imei(imei)
    except Exception as e:
        raise ValidationError(str(e.message))
    try:
        idevice = ImeiDevice.objects.select_related("device").get(imei=imei)
    except ImeiDevice.DoesNotExist:
        device = Device.objects.create()
        idevice = ImeiDevice.objects.create(imei=imei, device=device)
    else:
        device = idevice.device
        if re.search(r"[^0-9]", device.aid):
            if not device.competitor_set.filter(event__end_date__gte=now()).exists():
                device.aid = random_device_id()
    return Response({"status": "ok", "device_id": device.aid, "imei": imei})


@swagger_auto_schema(
    method="get",
    operation_id="server_time",
    operation_description="read the server time",
    tags=[],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={"application/json": {"time": 1615987017.7934635}},
        ),
    },
)
@api_view(["GET"])
def get_time(request):
    return Response({"time": time.time()}, headers={"Cache-Control": "no-cache"})


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
@login_required
def user_search(request):
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
@api_view(["GET"])
def device_search(request):
    devices = []
    q = request.GET.get("q")
    if q and len(q) > 4:
        devices = Device.objects.filter(aid__startswith=q, is_gpx=False).values_list(
            "id", "aid"
        )[:10]
    return Response({"results": [{"id": d[0], "device_id": d[1]} for d in devices]})


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def device_info(request, device_id):
    device = get_object_or_404(Device, aid=device_id, is_gpx=False)
    return Response(
        {
            "id": device.aid,
            "last_position": {
                "timestamp": device.last_date_viewed,
                "coordinates": {
                    "latitude": device.last_position[0],
                    "longitude": device.last_position[1],
                },
            }
            if device.last_location
            else None,
        }
    )


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def device_registrations(request, device_id):
    device = get_object_or_404(Device, aid=device_id, is_gpx=False)
    competitors = device.competitor_set.filter(event__end_date__gte=now())
    return Response({"count": competitors.count()})


@swagger_auto_schema(
    methods=["patch", "delete"],
    auto_schema=None,
)
@api_view(["PATCH", "DELETE"])
@login_required
def device_ownership_api_view(request, club_id, device_id):
    if not request.user.is_superuser:
        club = get_object_or_404(Club, admins=request.user, aid=club_id)
    else:
        club = get_object_or_404(Club, aid=club_id)
    device = get_object_or_404(Device, aid=device_id, is_gpx=False)
    ownership = get_object_or_404(DeviceClubOwnership, device=device, club=club)
    if request.method == "PATCH":
        nick = request.data.get("nickname", "")
        if nick and len(nick) > 12:
            raise ValidationError("Can not be more than 12 characters")

        ownership.nickname = nick
        ownership.save()
        return Response({"nickname": nick})
    elif request.method == "DELETE":
        ownership.delete()
        return HttpResponse(status=204)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def event_map_download(request, event_id, map_index="0"):
    event = get_object_or_404(
        Event.objects.all().select_related("club", "map"),
        aid=event_id,
        start_date__lt=now(),
    )
    if map_index == "0" and not event.map:
        raise Http404
    elif event.extra_maps.all().count() < int(map_index):
        raise Http404

    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    if map_index == "0":
        raster_map = event.map
    else:
        raster_map = (
            event.map_assignations.select_related("map").all()[int(map_index) - 1].map
        )
    file_path = raster_map.path
    mime_type = raster_map.mime_type

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return serve_from_s3(
        settings.AWS_S3_BUCKET,
        request,
        "/internal/" + file_path,
        filename=f"{raster_map.name}_{raster_map.corners_coordinates_short.replace(',', '_')}_.{mime_type[6:]}",
        mime=mime_type,
        headers=headers,
    )


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def event_map_thumb_download(request, event_id):
    event = get_object_or_404(
        Event.objects.all().select_related("club", "map"),
        aid=event_id,
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    data_out = event.thumbnail()
    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}

    return HttpResponse(data_out, content_type="image/jpeg", headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def event_kmz_download(request, event_id, map_index="0"):
    event = get_object_or_404(
        Event.objects.all().select_related("club", "map"),
        aid=event_id,
        start_date__lt=now(),
    )
    if map_index == "0" and not event.map:
        raise Http404
    elif event.extra_maps.all().count() < int(map_index):
        raise Http404

    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    if map_index == "0":
        raster_map = event.map
    else:
        raster_map = (
            event.map_assignations.select_related("map").all()[int(map_index) - 1].map
        )
    kmz_data = raster_map.kmz

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    response = HttpResponse(
        kmz_data, content_type="application/vnd.google-earth.kmz", headers=headers
    )
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{escape_filename(raster_map.name)}.kmz"'
    return response


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
@login_required
def map_kmz_download(request, map_id, *args, **kwargs):
    if request.user.is_superuser:
        raster_map = get_object_or_404(
            Map,
            aid=map_id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        raster_map = get_object_or_404(Map, aid=map_id, club__in=club_list)
    kmz_data = raster_map.kmz
    response = HttpResponse(
        kmz_data,
        content_type="application/vnd.google-earth.kmz",
        headers={"Cache-Control": "Private"},
    )
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{escape_filename(raster_map.name)}.kmz"'
    return response


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def competitor_gpx_download(request, competitor_id):
    competitor = get_object_or_404(
        Competitor.objects.all().select_related("event", "event__club"),
        aid=competitor_id,
        start_time__lt=now(),
    )
    event = competitor.event
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    gpx_data = competitor.gpx
    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    response = HttpResponse(
        gpx_data,
        content_type="application/gpx+xml",
        headers=headers,
    )
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{escape_filename(competitor.event.name)} - {escape_filename(competitor.name)}.gpx"'
    return response


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def two_d_rerun_race_status(request):
    """

    http://3drerun.worldofo.com/2d/?server=wwww.routechoices.com/api/woo&eventid={event.aid}&liveid=1

    /**/jQuery17036881551647526467_1620995291937(
        {
            "status":"OK",
            "racename":"RELAY Leg 1 WOMEN",
            "racestarttime":"2021-05-13T14:40:00.000Z",
            "raceendtime":"2021-05-13T15:10:00.000Z",
            "mapurl":"https://live.tractrac.com/events/event_20210430_EGKEuropea1/maps/c0c1bcb0-952d-0139-f8bb-10bf48d758ce/original_gabelungen-sprintrelay-neuchatel-women-with-forking-names.jpg",
            "caltype":"3point",
            "mapw":3526,
            "maph":2506,
            "calibration":[
                [6.937006566873767,46.99098930845227,1316,1762],
                [6.94023934338905,46.99479213285202,2054,518],
                [6.943056285345106,46.99316207691443,2682,1055]
            ],
            "competitors":[
                ["5bc546e0-960e-0139-fc65-10bf48d758ce","01 SUI Aebersold",null],
                ["5bc7dde0-960e-0139-fc66-10bf48d758ce","02 SWE Strand",null],
                ["5bca9e30-960e-0139-fc67-10bf48d758ce","03 NOR Haestad Bjornstad",null],
                ["5bcbc240-960e-0139-fc68-10bf48d758ce","04 CZE Knapova",null],
                ["5bccf5c0-960e-0139-fc69-10bf48d758ce","05 AUT Nilsson Simkovics",null],
                ["5bcdd230-960e-0139-fc6a-10bf48d758ce","07 DEN Lind",null],
                ["5bce9aa0-960e-0139-fc6b-10bf48d758ce","08 RUS Ryabkina",null],
                ["5bcf6450-960e-0139-fc6c-10bf48d758ce","09 FIN Klemettinen",null],
                ["5bd04a50-960e-0139-fc6d-10bf48d758ce","10 ITA Dallera",null],
                ["5bd15890-960e-0139-fc6e-10bf48d758ce","11 LAT Grosberga",null],
                ["5bd244b0-960e-0139-fc6f-10bf48d758ce","12 EST Kaasiku",null],
                ["5bd31de0-960e-0139-fc70-10bf48d758ce","13 FRA Basset",null],
                ["5bd3e5a0-960e-0139-fc71-10bf48d758ce","14 UKR Babych",null],
                ["5bd4b6d0-960e-0139-fc72-10bf48d758ce","15 LTU Gvildyte",null],
                ["5bd58cf0-960e-0139-fc73-10bf48d758ce","16 GER Winkler",null],
                ["5bd662f0-960e-0139-fc74-10bf48d758ce","17 BUL Gotseva",null],
                ["5bd73b60-960e-0139-fc75-10bf48d758ce","18 POR Rodrigues",null],
                ["5bd81980-960e-0139-fc76-10bf48d758ce","19 BEL de Smul",null],
                ["5bda1a60-960e-0139-fc77-10bf48d758ce","20 ESP Garcia Castro",null],
                ["5bdb05e0-960e-0139-fc78-10bf48d758ce","21 HUN Weiler",null],
                ["5bdc1870-960e-0139-fc79-10bf48d758ce","22 POL Wisniewska",null],
                ["5bdcfd50-960e-0139-fc7a-10bf48d758ce","23 TUR Bozkurt",null]
            ],
            "controls":[]
        }
    );
    """

    event_id = request.GET.get("eventid")
    if not event_id:
        raise Http404()
    event = get_object_or_404(
        Event.objects.all()
        .select_related("club", "map")
        .prefetch_related(
            "competitors",
        ),
        aid=event_id,
        start_date__lt=now(),
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    response_json = {
        "status": "OK",
        "racename": event.name,
        "racestarttime": event.start_date,
        "raceendtime": event.end_date,
        "mapurl": f"{event.get_absolute_map_url()}?.jpg",
        "caltype": "3point",
        "mapw": event.map.width,
        "maph": event.map.height,
        "calibration": [
            [
                event.map.bound["topLeft"]["lon"],
                event.map.bound["topLeft"]["lat"],
                0,
                0,
            ],
            [
                event.map.bound["topRight"]["lon"],
                event.map.bound["topRight"]["lat"],
                event.map.width,
                0,
            ],
            [
                event.map.bound["bottomLeft"]["lon"],
                event.map.bound["bottomLeft"]["lat"],
                0,
                event.map.height,
            ],
        ],
        "competitors": [],
    }
    for c in event.competitors.all():
        response_json["competitors"].append([c.aid, c.name, c.start_time])

    response_raw = str(json.dumps(response_json), "utf-8")
    content_type = "application/json"
    callback = request.GET.get("callback")
    if callback:
        response_raw = f"/**/{callback}({response_raw});"
        content_type = "text/javascript; charset=utf-8"

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return HttpResponse(response_raw, content_type=content_type, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def two_d_rerun_race_data(request):
    event_id = request.GET.get("eventid")
    if not event_id:
        raise Http404()
    event = get_object_or_404(
        Event.objects.all().prefetch_related(
            "competitors",
        ),
        aid=event_id,
        start_date__lt=now(),
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied()
    competitors = (
        event.competitors.select_related("device").all().order_by("start_time", "name")
    )
    nb_points = 0
    results = []
    for c in competitors:
        locations = c.locations
        nb_points += len(locations)
        results += [
            [
                c.aid,
                location[LOCATION_LATITUDE_INDEX],
                location[LOCATION_LONGITUDE_INDEX],
                0,
                epoch_to_datetime(location[LOCATION_TIMESTAMP_INDEX]),
            ]
            for location in locations
        ]
    response_json = {
        "containslastpos": 1,
        "lastpos": nb_points,
        "status": "OK",
        "data": results,
    }
    response_raw = str(json.dumps(response_json), "utf-8")
    content_type = "application/json"
    callback = request.GET.get("callback")
    if callback:
        response_raw = f"/**/{callback}({response_raw});"
        content_type = "text/javascript; charset=utf-8"

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return HttpResponse(
        response_raw,
        content_type=content_type,
        headers=headers,
    )


def tile_etag(request):
    if "GetMap" in [request.GET.get("request"), request.GET.get("REQUEST")]:
        layers_raw = request.GET.get("layers", request.GET.get("LAYERS"))
        bbox_raw = request.GET.get("bbox", request.GET.get("BBOX"))
        width_raw = request.GET.get("width", request.GET.get("WIDTH"))
        heigth_raw = request.GET.get("height", request.GET.get("HEIGHT"))

        http_accept = request.META.get("HTTP_ACCEPT", "")
        if "image/avif" in http_accept.split(","):
            img_mime = "image/avif"
        elif "image/webp" in http_accept.split(","):
            img_mime = "image/webp"
        else:
            img_mime = "image/png"

        best_mime = None
        if "image/avif" in http_accept.split(","):
            best_mime = "image/avif"
        elif "image/webp" in http_accept.split(","):
            best_mime = "image/webp"

        asked_mime = request.GET.get("format", request.GET.get("FORMAT", img_mime))
        if asked_mime in ("image/apng", "image/png", "image/webp", "image/avif"):
            img_mime = asked_mime
            if img_mime == "image/apng":
                img_mime = "image/png"
        elif asked_mime == "image/jpeg" and not best_mime:
            img_mime = "image/jpeg"
        elif best_mime:
            img_mime = best_mime
        else:
            return None

        if not layers_raw or not bbox_raw or not width_raw or not heigth_raw:
            return None
        try:
            min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox_raw.split(","))
            srs = request.GET.get("SRS", request.GET.get("srs"))
            if srs in ("CRS:84", "EPSG:4326"):
                min_lat, min_lon, max_lat, max_lon = (
                    float(x) for x in bbox_raw.split(",")
                )
                if srs == "EPSG:4326":
                    min_lon, min_lat, max_lon, max_lat = (
                        float(x) for x in bbox_raw.split(",")
                    )
                min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                    {"lat": min_lat, "lon": min_lon}
                )
                max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                    {"lat": max_lat, "lon": max_lon}
                )
                min_lat = min_xy["y"]
                min_lon = min_xy["x"]
                max_lat = max_xy["y"]
                max_lon = max_xy["x"]
            elif srs != "EPSG:3857":
                return None
            out_w, out_h = int(width_raw), int(heigth_raw)
            if "/" in layers_raw:
                layer_id, map_index = layers_raw.split("/")
                map_index = int(map_index)
            else:
                layer_id = layers_raw
                map_index = 0
        except Exception:
            return None

        event = get_object_or_404(Event.objects.select_related("club"), aid=layer_id)
        if map_index == 0 and not event.map:
            return None
        elif map_index > event.extra_maps.all().count():
            return None

        if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
            if (
                not request.user.is_authenticated
                or not event.club.admins.filter(id=request.user.id).exists()
            ):
                raise None
        if map_index == 0:
            raster_map = event.map
        else:
            raster_map = (
                event.map_assignations.select_related("map")
                .all()[int(map_index) - 1]
                .map
            )
        etag = raster_map.tile_cache_key(
            out_w, out_h, min_lat, max_lat, min_lon, max_lon, img_mime
        )
        h = hashlib.sha256()
        h.update(etag.encode("utf-8"))
        return safe64encode(h.digest())
    return None


def tile_latest_modification(request):
    if "GetMap" in [request.GET.get("request"), request.GET.get("REQUEST")]:
        layers_raw = request.GET.get("layers", request.GET.get("LAYERS"))
        if not layers_raw:
            return None
        try:
            if "/" in layers_raw:
                layer_id, map_index = layers_raw.split("/")
                map_index = int(map_index)
            else:
                layer_id = layers_raw
                map_index = 0
        except Exception:
            return None

        event = get_object_or_404(Event.objects.select_related("club"), aid=layer_id)
        if map_index == 0 and not event.map:
            return None
        elif map_index > event.extra_maps.all().count():
            return None

        if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
            if (
                not request.user.is_authenticated
                or not event.club.admins.filter(id=request.user.id).exists()
            ):
                return None
        if map_index == 0:
            raster_map = event.map
        else:
            raster_map = (
                event.map_assignations.select_related("map")
                .all()[int(map_index) - 1]
                .map
            )
        return max(raster_map.modification_date, event.modification_date)
    return None


@etag(tile_etag)
@last_modified(tile_latest_modification)
def wms_service(request):
    if "WMS" not in [request.GET.get("service"), request.GET.get("SERVICE")]:
        return HttpResponseBadRequest("Service must be WMS")
    if "GetMap" in [request.GET.get("request"), request.GET.get("REQUEST")]:
        layers_raw = request.GET.get("layers", request.GET.get("LAYERS"))
        bbox_raw = request.GET.get("bbox", request.GET.get("BBOX"))
        width_raw = request.GET.get("width", request.GET.get("WIDTH"))
        heigth_raw = request.GET.get("height", request.GET.get("HEIGHT"))

        http_accept = request.META.get("HTTP_ACCEPT", "")
        best_mime = None
        if "image/avif" in http_accept.split(","):
            best_mime = "image/avif"
        elif "image/webp" in http_accept.split(","):
            best_mime = "image/webp"

        asked_mime = request.GET.get("format", request.GET.get("FORMAT"))
        if asked_mime in ("image/apng", "image/png", "image/webp", "image/avif"):
            img_mime = asked_mime
            if img_mime == "image/apng":
                img_mime = "image/png"
        elif asked_mime == "image/jpeg" and not best_mime:
            img_mime = "image/jpeg"
        elif best_mime:
            img_mime = best_mime
        else:
            return HttpResponseBadRequest("invalid format")

        if not layers_raw or not bbox_raw or not width_raw or not heigth_raw:
            return HttpResponseBadRequest("missing mandatory parameters")
        try:
            min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox_raw.split(","))
            srs = request.GET.get("SRS", request.GET.get("srs"))
            if srs in ("CRS:84", "EPSG:4326"):
                min_lat, min_lon, max_lat, max_lon = (
                    float(x) for x in bbox_raw.split(",")
                )
                if srs == "EPSG:4326":
                    min_lon, min_lat, max_lon, max_lat = (
                        float(x) for x in bbox_raw.split(",")
                    )
                min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                    {"lat": min_lat, "lon": min_lon}
                )
                max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                    {"lat": max_lat, "lon": max_lon}
                )
                min_lat = min_xy["y"]
                min_lon = min_xy["x"]
                max_lat = max_xy["y"]
                max_lon = max_xy["x"]
            elif srs != "EPSG:3857":
                return HttpResponseBadRequest("SRS not supported")
            out_w, out_h = int(width_raw), int(heigth_raw)
            if "/" in layers_raw:
                layer_id, map_index = layers_raw.split("/")
                map_index = int(map_index)
            else:
                layer_id = layers_raw
                map_index = 0
        except Exception:
            return HttpResponseBadRequest("invalid parameters")

        event = get_object_or_404(Event.objects.select_related("club"), aid=layer_id)
        if map_index == 0 and not event.map:
            raise Http404
        elif map_index > event.extra_maps.all().count():
            raise Http404

        if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
            if (
                not request.user.is_authenticated
                or not event.club.admins.filter(id=request.user.id).exists()
            ):
                raise PermissionDenied()
        if map_index == 0:
            raster_map = event.map
        else:
            raster_map = (
                event.map_assignations.select_related("map")
                .all()[int(map_index) - 1]
                .map
            )

        try:
            data_out = raster_map.create_tile(
                out_w, out_h, min_lat, max_lat, min_lon, max_lon, img_mime
            )
        except Exception as e:
            raise e
        headers = None
        if event.privacy == PRIVACY_PRIVATE:
            headers = {"Cache-Control": "Private"}
        return HttpResponse(data_out, content_type=img_mime, headers=headers)
    elif "GetCapabilities" in [request.GET.get("request"), request.GET.get("REQUEST")]:
        max_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": 89.9, "lon": 180})
        min_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": -89.9, "lon": -180})

        events = (
            Event.objects.filter(privacy=PRIVACY_PUBLIC)
            .select_related("club", "map")
            .prefetch_related("map_assignations")
        )
        layers_xml = ""

        def add_layer_xml(layer_id, event, name, layer):
            min_lon = min(
                layer.bound["topLeft"]["lon"],
                layer.bound["bottomLeft"]["lon"],
                layer.bound["bottomRight"]["lon"],
                layer.bound["topRight"]["lon"],
            )
            max_lon = max(
                layer.bound["topLeft"]["lon"],
                layer.bound["bottomLeft"]["lon"],
                layer.bound["bottomRight"]["lon"],
                layer.bound["topRight"]["lon"],
            )
            min_lat = min(
                layer.bound["topLeft"]["lat"],
                layer.bound["bottomLeft"]["lat"],
                layer.bound["bottomRight"]["lat"],
                layer.bound["topRight"]["lat"],
            )
            max_lat = max(
                layer.bound["topLeft"]["lat"],
                layer.bound["bottomLeft"]["lat"],
                layer.bound["bottomRight"]["lat"],
                layer.bound["topRight"]["lat"],
            )
            l_max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                {"lat": max_lat, "lon": max_lon}
            )
            l_min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                {"lat": min_lat, "lon": min_lon}
            )
            return f"""<Layer queryable="0" opaque="0" cascaded="0">
  <Name>{layer_id}</Name>
  <Title>{name} of {event.name} by {event.club}</Title>
    <SRS>EPSG:3857</SRS>
    <SRS>EPSG:4326</SRS>
    <SRS>CRS:84</SRS>
    <EX_GeographicBoundingBox>
      <westBoundLongitude>{min_lon}</westBoundLongitude>
      <eastBoundLongitude>{max_lon}</eastBoundLongitude>
      <southBoundLatitude>{min_lon}</southBoundLatitude>
      <northBoundLatitude>{max_lat}</northBoundLatitude>
    </EX_GeographicBoundingBox>
    <LatLonBoundingBox minx="{min_lat}" miny="{min_lon}" maxx="{max_lat}" maxy="{max_lon}"/>
    <BoundingBox SRS="EPSG:3857" minx="{l_min_xy['x']}" miny="{l_min_xy['y']}" maxx="{l_max_xy['x']}" maxy="{l_max_xy['y']}"/>
    <BoundingBox SRS="EPSG:4326" minx="{min_lat}" miny="{min_lon}" maxx="{max_lat}" maxy="{max_lon}"/>
    <BoundingBox SRS="CRS:84" minx="{min_lon}" miny="{min_lat}" maxx="{max_lon}" maxy="{max_lat}"/>
  </Layer>"""

        for event in events:
            if event.map:
                layers_xml += add_layer_xml(
                    event.aid,
                    event,
                    event.map_title if event.map_title else "Main map",
                    event.map,
                )
                count_layer = 0
                for layer in event.map_assignations.all():
                    count_layer += 1
                    layers_xml += add_layer_xml(
                        f"{event.aid}/{count_layer}", event, layer.title, layer.map
                    )
        data_xml = f"""<?xml version='1.0' encoding="UTF-8" standalone="no" ?>
<!DOCTYPE WMT_MS_Capabilities SYSTEM "http://schemas.opengis.net/wms/1.1.1/WMS_MS_Capabilities.dtd"
 [
 <!ELEMENT VendorSpecificCapabilities EMPTY>
 ]>  <!-- end of DOCTYPE declaration -->
<WMT_MS_Capabilities version="1.1.1">
<Service>
  <Name>OGC:WMS</Name>
  <Title>Routechoices - WMS</Title>
  <Abstract>Routechoices WMS server</Abstract>
  <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href=""/>
  <Fees>none</Fees>
  <AccessConstraints>none</AccessConstraints>
  <MaxWidth>10000</MaxWidth>
  <MaxHeight>10000</MaxHeight>
</Service>
<Capability>
  <Request>
    <GetCapabilities>
      <Format>application/vnd.ogc.wms_xml</Format>
      <DCPType>
        <HTTP>
          <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms?"/></Get>
        </HTTP>
      </DCPType>
    </GetCapabilities>
    <GetMap>
      <Format>image/jpeg</Format>
      <Format>image/png</Format>
      <Format>image/avif</Format>
      <Format>image/webp</Format>
      <DCPType>
        <HTTP>
          <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms?"/></Get>
        </HTTP>
      </DCPType>
    </GetMap>
  </Request>
  <Exception>
    <Format>application/vnd.ogc.se_xml</Format>
  </Exception>
  <Layer>
    <Name>all</Name>
    <Title>Routechoices Maps</Title>
    <SRS>EPSG:3857</SRS>
    <SRS>EPSG:4326</SRS>
    <SRS>CRS:84</SRS>
    <EX_GeographicBoundingBox>
      <westBoundLongitude>-180</westBoundLongitude>
      <eastBoundLongitude>180</eastBoundLongitude>
      <southBoundLatitude>-90</southBoundLatitude>
      <northBoundLatitude>90</northBoundLatitude>
    </EX_GeographicBoundingBox>
    <LatLonBoundingBox minx="-180" miny="-85.0511287798" maxx="180" maxy="85.0511287798" />
    <BoundingBox SRS="EPSG:3857" minx="{min_xy['x']}" miny="{min_xy['y']}" maxx="{max_xy['x']}" maxy="{max_xy['y']}"/>
    <BoundingBox SRS="EPSG:4326" minx="-180.0" miny="-85.0511287798" maxx="180.0" maxy="85.0511287798" />
    <BoundingBox SRS="CRS:84" minx="-90" miny="-180" maxx="90" maxy="-180"/>
    {layers_xml}
  </Layer>
</Capability>
</WMT_MS_Capabilities>
"""
        return HttpResponse(data_xml, content_type="text/xml")
    return HttpResponse(status_code=501)

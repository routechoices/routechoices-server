import logging
import re
import time
import urllib.parse

import arrow
import orjson as json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.gis.geoip2 import GeoIP2
from django.core.cache import cache
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
from rest_framework.decorators import api_view, renderer_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from routechoices.core.models import (
    EVENT_CACHE_INTERVAL,
    LOCATION_LATITUDE_INDEX,
    LOCATION_LONGITUDE_INDEX,
    LOCATION_TIMESTAMP_INDEX,
    MAP_BLANK,
    MAP_CHOICES,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    PRIVACY_SECRET,
    Club,
    Competitor,
    Device,
    DeviceClubOwnership,
    Event,
    EventSet,
    ImeiDevice,
    Map,
    MapAssignation,
)
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import (
    epoch_to_datetime,
    initial_of_name,
    random_device_id,
    set_content_disposition,
    short_random_key,
    short_random_slug,
)
from routechoices.lib.s3 import s3_object_url
from routechoices.lib.streaming_response import StreamingHttpRangeResponse
from routechoices.lib.validators import (
    validate_imei,
    validate_latitude,
    validate_longitude,
    validate_nice_slug,
)

logger = logging.getLogger(__name__)
GLOBAL_MERCATOR = GlobalMercator()


class PostDataThrottle(AnonRateThrottle):
    rate = "70/min"

    def allow_request(self, request, view):
        if request.method == "GET":
            return True
        return super().allow_request(request, view)


def serve_from_s3(
    bucket,
    request,
    path,
    filename="",
    mime="application/force-download",
    headers=None,
    dl=True,
):
    url = s3_object_url(path, bucket)
    url = url[len(settings.AWS_S3_ENDPOINT_URL) :]

    response_status = status.HTTP_200_OK
    if request.method == "GET":
        response_status = status.HTTP_206_PARTIAL_CONTENT

    response = HttpResponse("", status=response_status, headers=headers)

    if request.method == "GET":
        response["X-Accel-Redirect"] = urllib.parse.quote(f"/s3{url}".encode("utf-8"))
        response["X-Accel-Buffering"] = "no"
    response["Content-Type"] = mime
    response["Content-Disposition"] = set_content_disposition(filename, dl=dl)
    return response


club_param = openapi.Parameter(
    "club",
    openapi.IN_QUERY,
    description="Filter by this club slug",
    type=openapi.TYPE_STRING,
)

event_param = openapi.Parameter(
    "event",
    openapi.IN_QUERY,
    description="Filter by this event slug",
    type=openapi.TYPE_STRING,
)

mine_param = openapi.Parameter(
    "mine",
    openapi.IN_QUERY,
    description="Filter weither you own it",
    type=openapi.TYPE_BOOLEAN,
)


@swagger_auto_schema(
    method="post",
    auto_schema=None,
)
@login_required
@api_view(["POST"])
def event_set_creation(request):
    club_id = request.data.get("club_id")
    club = Club.objects.filter(aid=club_id).first()
    name = request.data.get("name")
    if not name or not club:
        raise ValidationError("Missing parameter")
    is_user_event_admin = (
        request.user.is_superuser or club.admins.filter(id=request.user.id).exists()
    )
    if not is_user_event_admin:
        raise PermissionDenied("not club admin")
    event_set, created = EventSet.objects.get_or_create(club=club, name=name)
    return Response(
        {
            "value": event_set.id,
            "text": name,
        }
    )


@swagger_auto_schema(
    method="get",
    operation_id="events_list",
    operation_description="List events",
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
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "privacy": "public",
                        "backdrop": "blank",
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
                        "privacy": "public",
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
@swagger_auto_schema(
    method="post",
    operation_id="create_event",
    operation_description="Create event",
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
                    "club": "Kangasala SK",
                    "club_slug": "ksk",
                    "privacy": "public",
                    "backdrop": "blank",
                    "open_registration": False,
                    "open_route_upload": False,
                    "url": "http://www.routechoices.com/ksk/Jukola-2019-1st-leg",
                },
            },
        ),
    },
)
@api_view(["GET", "POST"])
def event_list(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            raise ValidationError("authentication required")
        club_slug = request.data.get("club_slug")
        if not club_slug:
            raise ValidationError("club_slug is required")
        if request.user.is_superuser:
            club = Club.objects.filter(slug__iexact=club_slug).first()
        else:
            club = Club.objects.filter(
                admins=request.user, slug__iexact=club_slug
            ).first()
        if not club:
            raise ValidationError("club not found")

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
                raise ValidationError("slug invalid")
            else:
                slug = slug_raw

        start_date = arrow.now().datetime
        start_date_raw = request.data.get("start_date")
        if start_date_raw:
            try:
                start_date = arrow.get(start_date_raw).datetime
            except Exception:
                raise ValidationError("start_date invalid")

        end_date_raw = request.data.get("end_date")
        if not end_date_raw:
            raise ValidationError("end_date is required")
        try:
            end_date = arrow.get(end_date_raw).datetime
        except Exception:
            raise ValidationError("end_date_invalid")
        else:
            if end_date <= start_date:
                raise ValidationError("end_date invalid, should be after start_date")

        backdrop_map = request.data.get("backdrop", MAP_BLANK)
        if backdrop_map not in (m[0] for m in MAP_CHOICES):
            raise ValidationError("backdrop invalid")

        privacy = request.data.get("privacy", PRIVACY_SECRET)
        if privacy.lower() not in (PRIVACY_PUBLIC, PRIVACY_SECRET, PRIVACY_PRIVATE):
            raise ValidationError("privacy invalid")

        open_registration = False
        open_registration_raw = request.data.get("open_registration")
        if open_registration_raw:
            open_registration = True

        allow_route_upload = False
        allow_route_upload_raw = request.data.get("allow_route_upload")
        if allow_route_upload_raw:
            allow_route_upload = True

        event = Event(
            club=club,
            name=name,
            slug=slug,
            start_date=start_date,
            end_date=end_date,
            privacy=privacy,
            backdrop_map=backdrop_map,
            open_registration=open_registration,
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
            "club": club.name,
            "club_slug": club.slug.lower(),
            "privacy": event.privacy,
            "backdrop": event.backdrop_map,
            "open_registration": event.open_registration,
            "open_route_upload": event.allow_route_upload,
            "url": request.build_absolute_uri(event.get_absolute_url()),
        }
        return Response(output, status=status.HTTP_201_CREATED)

    club_slug = request.GET.get("club")
    event_slug = request.GET.get("event")

    if event_slug and club_slug:
        privacy_arg = {"privacy__in": [PRIVACY_PUBLIC, PRIVACY_SECRET]}
    else:
        privacy_arg = {"privacy": PRIVACY_PUBLIC}

    if request.user.is_authenticated:
        if request.user.is_superuser:
            clubs = Club.objects.all()
        else:
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
                "privacy": event.privacy,
                "backdrop": event.backdrop_map,
                "open_registration": event.open_registration,
                "open_route_upload": event.allow_route_upload,
                "url": request.build_absolute_uri(event.get_absolute_url()),
            }
        )
    return Response(output)


@swagger_auto_schema(
    method="get",
    operation_id="clubs_list",
    operation_description="List clubs",
    tags=["Clubs"],
    manual_parameters=[mine_param],
    responses={
        "200": openapi.Response(
            description="Success response",
            examples={
                "application/json": [
                    {
                        "id": "PlCG3xFS-f4",
                        "name": "Kangasala SK",
                        "slug": "ksk",
                        "url": "https://ksk.routechoices.com/",
                        "owner": False,
                    },
                    {
                        "id": "ohFYzJep1hI",
                        "name": "Halden SK",
                        "slug": "halden-sk",
                        "url": "https://gps.haldensk.no/",
                        "owner": True,
                    },
                    "...",
                ]
            },
        ),
    },
)
@api_view(["GET"])
def club_list(request):
    only_yours = request.GET.get("mine")
    clubs = Club.objects.all()
    owned_clubs = Club.objects.none()
    if request.user.is_superuser:
        owned_clubs = clubs
    elif request.user.is_authenticated:
        owned_clubs = clubs.filter(admins=request.user)

    if only_yours and not request.user.is_superuser:
        clubs = clubs.filter(admins=request.user)

    output = []
    for club in clubs:
        data = {
            "id": club.aid,
            "name": club.name,
            "slug": club.slug,
            "url": club.nice_url,
            "owned": only_yours or request.user.is_superuser or (club in owned_clubs),
        }
        if not only_yours or data["owned"]:
            output.append(data)
    return Response(output)


@swagger_auto_schema(
    method="get",
    operation_id="event_detail",
    operation_description="Read an event detail",
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
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "privacy": "public",
                        "open_registration": False,
                        "open_route_upload": False,
                        "url": "https://www.routechoices.com/ksk/Jukola-2019-1st-leg",
                        "shortcut": "https://routechoic.es/PlCG3xFS-f4",
                        "backdrop": "osm",
                        "send_interval": 5,
                        "tail_length": 60,
                    },
                    "data_url": (
                        "https://www.routechoices.com/api/events/PlCG3xFS-f4/data"
                    ),
                    "announcement": "",
                    "maps": [
                        {
                            "coordinates": {
                                "topLeft": {"lat": 61.45075, "lon": 24.18994},
                                "topRight": {"lat": 61.44656, "lon": 24.24721},
                                "bottomRight": {"lat": 61.42094, "lon": 24.23851},
                                "bottomLeft": {"lat": 61.42533, "lon": 24.18156},
                            },
                            "rotation": 3.25,
                            "url": (
                                "https://www.routechoices.com/api/events/PlCG3xFS-f4/map",
                            ),
                            "title": "",
                            "hash": "u8cWoEiv2z1Cz2bjjJ66b2EF4groSULVlzKg9HGE1gM=",
                            "max_zoom": 18,
                            "modification_date": "2019-06-10T17:21:52.417000Z",
                            "default": True,
                            "id": "or6tmT19cfk",
                        }
                    ],
                }
            },
        ),
    },
)
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def event_detail(request, event_id):
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
        res = {"error": "No event match this id"}
        return Response(res)

    is_user_club_admin = (
        request.user.is_superuser
        or event.club.admins.filter(id=request.user.id).exists()
    )

    if event.privacy == PRIVACY_PRIVATE and not is_user_club_admin:
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
            "privacy": event.privacy,
            "open_registration": event.open_registration,
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
        "announcement": "",
        "maps": [],
    }

    if event.start_date < now():
        output["announcement"] = event.notice.text if event.has_notice else ""

        if event.map:
            map_data = {
                "title": event.map_title,
                "coordinates": event.map.bound,
                "rotation": event.map.rotation,
                "hash": event.map.hash,
                "max_zoom": event.map.max_zoom,
                "modification_date": event.map.modification_date,
                "default": True,
                "id": event.map.aid,
                "url": request.build_absolute_uri(
                    reverse(
                        "event_map_download",
                        host="api",
                        kwargs={"event_id": event.aid},
                    )
                ),
            }
            output["maps"].append(map_data)
        for i, m in enumerate(event.map_assignations.all()):
            map_data = {
                "title": m.title,
                "coordinates": m.map.bound,
                "rotation": m.map.rotation,
                "hash": m.map.hash,
                "max_zoom": m.map.max_zoom,
                "modification_date": m.map.modification_date,
                "default": False,
                "id": m.map.aid,
                "url": request.build_absolute_uri(
                    reverse(
                        "event_map_download",
                        host="api",
                        kwargs={"event_id": event.aid, "map_index": (i + 1)},
                    )
                ),
            }
            output["maps"].append(map_data)

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return Response(output, headers=headers)


@swagger_auto_schema(
    method="post",
    operation_id="register_competitor",
    operation_description="Register a competitor to a given event",
    tags=["Events"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Device id",
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
        },
        required=["name"],
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
    event = Event.objects.select_related("club").filter(aid=event_id).first()
    if not event:
        res = {"error": "No event match this id"}
        return Response(res)

    if not event.open_registration:
        if not request.user.is_authenticated or (
            not request.user.is_superuser
            and request.user not in event.club.admins.all()
        ):
            raise PermissionDenied()

    lang = request.GET.get("lang", "en")
    if lang not in ("en", "es", "fi", "fr", "nl", "sv"):
        lang = "en"

    err_messages = {
        "en": {
            "no-device-id": "Device ID not found",
            "no-name": "Name is missing",
            "invalid-start-time": "Start time could not be parsed",
            "bad-start-time": "Competitor start time should be during the event time",
            "bad-name": "Name already in use in this event",
            "bad-sname": "Short name already in use in this event",
            "registration-closed": "Registration is closed",
        },
        "es": {
            "no-device-id": "ID del dispositivo no encontrado",
            "no-name": "Falta el nombre",
            "invalid-start-time": "La hora de inicio no pudo ser analizada",
            "bad-start-time": (
                "La hora de inicio del competidor debe ser durante la hora del evento."
            ),
            "bad-name": "Nombre ya en uso en este evento",
            "bad-sname": "Nombre corto ya en uso en este evento",
            "registration-closed": "Las inscripciones están cerradas",
        },
        "fr": {
            "no-device-id": "Identifiant de l'appareil introuvable",
            "no-name": "Nom est manquant",
            "invalid-start-time": "Impossible d'extraire l'heure de début",
            "bad-start-time": (
                "L'heure de départ du concurrent doit être durant l'événement"
            ),
            "bad-name": "Nom déjà utilisé dans cet événement",
            "bad-sname": "Nom abrégé déjà utilisé dans cet événement",
            "registration-closed": "Les inscriptions sont closes",
        },
        "fi": {
            "no-device-id": "Laitetunnusta ei löydy",
            "no-name": "Nimi puuttuu",
            "invalid-start-time": "Aloitusaikaa ei voitu jäsentää",
            "bad-start-time": "Kilpailijan aloitusajan tulee olla tapahtuman aikana",
            "bad-name": "Nimi on jo käytössä tässä tapahtumassa",
            "bad-sname": "Lyhyt nimi jo käytössä tässä tapahtumassa",
            "registration-closed": "Ilmoittautumiset on suljettu",
        },
        "nl": {
            "no-device-id": "Toestel ID niet gevonden",
            "no-name": "Naam ontbreekt",
            "invalid-start-time": "Start tijd kan niet worden ontleed",
            "bad-start-time": "Starttijd van de atleet is tijdens de event tijd",
            "bad-name": "Naam al in gebruik in dit evenement",
            "bad-sname": "Korte naam al in gebruik in dit evenement",
            "registration-closed": "Inschrijvingen zijn gesloten",
        },
        "sv": {
            "no-device-id": "Enhets-ID hittades inte",
            "no-name": "Namn saknas",
            "invalid-start-time": "Starttiden kunde inte hittas",
            "bad-start-time": "Tävlandes starttid bör vara under evenemangstiden",
            "bad-name": "Namnet används redan i det här evenemanget",
            "bad-sname": "Kortnamn används redan i det här evenemanget",
            "registration-closed": "Anmälningarna är stängda",
        },
    }

    if event.end_date < now() and not event.allow_route_upload:
        raise ValidationError(err_messages[lang]["registration-closed"])

    errs = []

    name = request.data.get("name")

    if not name:
        errs.append(err_messages[lang]["no-name"])
    short_name = request.data.get("short_name")
    if not short_name:
        short_name = initial_of_name(name)
    start_time_query = request.data.get("start_time")
    if start_time_query:
        try:
            start_time = arrow.get(start_time_query).datetime
        except Exception:
            start_time = None
            errs.append(err_messages[lang]["invalid-start-time"])
    elif event.start_date < now() < event.end_date:
        start_time = now()
    else:
        start_time = event.start_date
    event_start = event.start_date
    event_end = event.end_date

    if start_time and (event_start > start_time or start_time > event_end):
        errs.append(err_messages[lang]["bad-start-time"])

    if event.competitors.filter(name=name).exists():
        errs.append(err_messages[lang]["bad-name"])

    if event.competitors.filter(short_name=short_name).exists() and request.data.get(
        "short_name"
    ):
        errs.append(err_messages[lang]["bad-sname"])

    device_id = request.data.get("device_id")
    device = Device.objects.filter(aid=device_id).first()

    if not device and device_id:
        errs.append(err_messages[lang]["no-device-id"])

    if errs:
        raise ValidationError(errs)

    comp = Competitor.objects.create(
        name=name,
        event=event,
        short_name=short_name,
        start_time=start_time,
        device=device,
    )

    output = {
        "id": comp.aid,
        "name": name,
        "short_name": short_name,
        "start_time": start_time,
    }
    if device:
        output["device_id"] = device.aid

    return Response(
        output,
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method="delete",
    operation_id="delete_competitor",
    operation_description="Delete a competitor",
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
@api_view(["DELETE"])
@login_required
def competitor_api(request, competitor_id):
    competitor = (
        Competitor.objects.select_related("event", "event__club")
        .filter(aid=competitor_id)
        .first()
    )
    if not competitor:
        res = {"error": "No competitor match this id"}
        return Response(res)

    event = competitor.event

    is_user_event_admin = (
        request.user.is_superuser
        or event.club.admins.filter(id=request.user.id).exists()
    )
    if not is_user_event_admin:
        raise PermissionDenied()

    competitor.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(
    method="post",
    operation_id="competitor_route_upload",
    operation_description=(
        "Upload route for an existing competitor (Delete existing data)"
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
@api_view(["POST"])
def competitor_route_upload(request, competitor_id):
    competitor = (
        Competitor.objects.select_related("event", "event__club", "device")
        .filter(aid=competitor_id)
        .first()
    )
    if not competitor:
        res = {"error": "No competitor match this id"}
        return Response(res)
    event = competitor.event

    is_user_event_admin = (
        request.user.is_authenticated
        and event.club.admins.filter(id=request.user.id).exists()
    ) or request.user.is_superuser

    if not event.allow_route_upload:
        raise PermissionDenied()

    if (
        not is_user_event_admin
        and competitor.device
        and competitor.device.location_count != 0
    ):
        raise ValidationError("Competitor already assigned a route")

    if event.start_date > now():
        raise ValidationError("Event not yet started")

    try:
        lats = [float(x) for x in request.data.get("latitudes", "").split(",") if x]
        lons = [float(x) for x in request.data.get("longitudes", "").split(",") if x]
        times = [float(x) for x in request.data.get("timestamps", "").split(",") if x]
    except ValueError:
        raise ValidationError("Invalid data format")

    if not (len(lats) == len(lons) == len(times)):
        raise ValidationError(
            "Latitudes, longitudes, and timestamps, should have same amount of points"
        )

    if len(lats) < 2:
        raise ValidationError("Minimum amount of locations is 2")

    loc_array = []
    for i in range(len(times)):
        if times[i] and lats[i] and lons[i]:
            lat = lats[i]
            lon = lons[i]
            tim = times[i]
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
                loc_array.append((int(tim), lat, lon))

    device = None
    if len(loc_array) > 0:
        device = Device.objects.create(
            aid=f"{short_random_key()}_GPX",
            user_agent=request.session.user_agent[:200],
            is_gpx=True,
        )
        device.add_locations(loc_array, push_forward=False)
        competitor.device = device
        competitor.save()

    if len(loc_array) == 0:
        raise ValidationError("No locations within event schedule were detected")

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
    operation_description="Read competitors data from an event",
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
                            "name": "Olav Lundanes (Halden SK)",
                            "short_name": "Halden SK",
                            "start_time": "2019-06-15T20:00:00Z",
                            "battery_level": 84,
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
    cache_key_found = None
    event = None

    use_cache = getattr(settings, "CACHE_EVENT_DATA", False)
    if not use_cache:
        return None

    cache_interval = EVENT_CACHE_INTERVAL
    live_cache_ts = int(t0 // cache_interval)
    live_cache_key = f"live_event_data:{event_id}:{live_cache_ts}"
    if use_cache and cache.has_key(live_cache_key):
        cache_key_found = live_cache_key
        try:
            data = cache.get(cache_key_found)
        except Exception:
            pass
        else:
            return Response(data, headers={"X-Cache-Hit": 1})

    event = (
        Event.objects.select_related("club")
        .filter(aid=event_id, start_date__lt=now())
        .first()
    )
    if not event:
        res = {"error": "No event match this id"}
        return Response(res)

    cache_ts = int(t0 // (cache_interval if event.is_live else 7 * 24 * 3600))
    cache_prefix = "live" if event.is_live else "archived"
    cache_key = f"{cache_prefix}_event_data:{event_id}:{cache_ts}"
    prev_cache_key = f"{cache_prefix}_event_data:{event_id}:{cache_ts - 1}"
    # then if we have a cache for that
    # return it if we do
    if use_cache and not event.is_live and cache.has_key(cache_key):
        cache_key_found = cache_key

    # If we dont have cache check if we are currently generating cache
    # if so return previous cache data if available
    elif (
        use_cache
        and cache.has_key(f"{cache_key}:processing")
        and cache.has_key(prev_cache_key)
    ):
        cache_key_found = prev_cache_key

    if cache_key_found:
        try:
            data = cache.get(cache_key_found)
        except Exception:
            pass
        else:
            return Response(data, headers={"X-Cache-Hit": 1})

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
    devices = (c.device_id for c in competitors if c.device_id)

    # we need this to determine the end time of the competitor device stream
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
        c_data = {
            "id": c.aid,
            "encoded_data": encoded_data,
            "name": c.name,
            "short_name": c.short_name,
            "start_time": c.start_time,
        }
        if event.is_live and c.device_id:
            c_data["battery_level"] = c.device.battery_level
        results.append(c_data)
    res = {
        "competitors": results,
        "nb_points": nb_points,
        "duration": (time.time() - t0),
        "timestamp": time.time(),
    }

    headers = {}
    if event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    if use_cache:
        try:
            cache.set(cache_key, res, 20 if event.is_live else 7 * 24 * 3600 + 60)
        except Exception:
            pass

    return Response(res, headers=headers)


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
    operation_id="upload_device_locations",
    operation_description="Upload a list of device location",
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
@api_view(["POST"])
@throttle_classes([PostDataThrottle])
def locations_api_gw(request):
    secret_provided = request.data.get(
        "secret"
    )  # secret was used in legacy apps before v1.6.0
    battery_level_posted = request.data.get("battery")
    device_id = request.data.get("device_id")
    if not device_id:
        raise ValidationError("Missing device_id parameter")
    if (
        not request.user.is_authenticated
        and re.match(r"^[0-9]+$", device_id)
        and secret_provided not in settings.POST_LOCATION_SECRETS
    ):
        raise PermissionDenied("Authentication Failed")

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
    method="post",
    auto_schema=None,
)
@api_view(["POST"])
def get_device_id(request):
    device = Device.objects.create(user_agent=request.session.user_agent[:200])
    return Response({"status": "ok", "device_id": device.aid})


@swagger_auto_schema(
    method="post",
    operation_id="create_device_id",
    operation_description="Create a device id",
    tags=["Devices"],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "imei": openapi.Schema(
                type=openapi.TYPE_STRING,
                example="<IMEI>",
                description="Hardware GPS tracking device IMEI (Optional)",
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
@api_view(["POST"])
def create_device_id(request):
    imei = request.data.get("imei")
    if imei:
        try:
            validate_imei(imei)
        except Exception as e:
            raise ValidationError(str(e.message))
        status_code = status.HTTP_200_OK
        try:
            idevice = ImeiDevice.objects.select_related("device").get(imei=imei)
        except ImeiDevice.DoesNotExist:
            device = Device.objects.create()
            idevice = ImeiDevice.objects.create(imei=imei, device=device)
            status_code = status.HTTP_201_CREATED
        else:
            device = idevice.device
            if re.search(r"[^0-9]", device.aid):
                if not device.competitor_set.filter(
                    event__end_date__gte=now()
                ).exists():
                    device.aid = random_device_id()
                    status_code = status.HTTP_201_CREATED
        return Response(
            {"status": "ok", "device_id": device.aid, "imei": imei}, status=status_code
        )
    if not request.user.is_authenticated:
        raise PermissionDenied("Authentication Failed")
    device = Device.objects.create(user_agent=request.session.user_agent[:200])
    return Response(
        {"status": "ok", "device_id": device.aid}, status=status.HTTP_201_CREATED
    )


@swagger_auto_schema(
    method="post",
    auto_schema=None,
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
    operation_description="Return the server epoch time",
    tags=["Miscellaneous"],
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
@login_required
def user_view(request):
    user = request.user
    if user.is_superuser:
        clubs = Club.objects.all()
    else:
        clubs = Club.objects.filter(admins=user)

    output = {
        "username": user.username,
        "clubs": [{"name": c.name, "slug": c.slug} for c in clubs],
    }
    return Response(output)


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
    device = Device.objects.filter(aid=device_id, is_gpx=False).first()
    if not device:
        res = {"error": "No device match this id"}
        return Response(res)

    return Response(
        {
            "id": device.aid,
            "last_position": {
                "timestamp": device.last_location_timestamp,
                "coordinates": {
                    "latitude": device.last_location[LOCATION_LATITUDE_INDEX],
                    "longitude": device.last_location[LOCATION_LONGITUDE_INDEX],
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

    ownership, _created = DeviceClubOwnership.objects.get_or_create(
        device=device, club=club
    )
    if request.method == "PATCH":
        nick = request.data.get("nickname", "")
        if nick and len(nick) > 12:
            raise ValidationError("Can not be more than 12 characters")

        ownership.nickname = nick
        ownership.save()
        return Response({"nickname": nick})
    elif request.method == "DELETE":
        ownership.delete()
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def event_map_download(request, event_id, map_index="0"):
    event, raster_map = Event.get_public_map_at_index(request.user, event_id, map_index)
    file_path = raster_map.path
    mime_type = raster_map.mime_type

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return serve_from_s3(
        settings.AWS_S3_BUCKET,
        request,
        file_path,
        filename=(
            f"{raster_map.name}_"
            f"{raster_map.corners_coordinates_short.replace(',', '_')}_."
            f"{mime_type[6:]}"
        ),
        mime=mime_type,
        headers=headers,
        dl=False,
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

    return StreamingHttpRangeResponse(request, data_out, headers=headers)


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def event_kmz_download(request, event_id, map_index="0"):
    event, raster_map = Event.get_public_map_at_index(request.user, event_id, map_index)
    kmz_data = raster_map.kmz

    headers = None
    if event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    response = StreamingHttpRangeResponse(
        request,
        kmz_data,
        content_type="application/vnd.google-earth.kmz",
        headers=headers,
    )
    filename = f"{raster_map.name}.kmz"
    response["Content-Disposition"] = set_content_disposition(filename)
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
    response = StreamingHttpRangeResponse(
        request,
        kmz_data,
        content_type="application/vnd.google-earth.kmz",
        headers={"Cache-Control": "Private"},
    )
    filename = f"{raster_map.name}.kmz"
    response["Content-Disposition"] = set_content_disposition(filename)
    return response


@swagger_auto_schema(
    method="get",
    auto_schema=None,
)
@api_view(["GET"])
def competitor_gpx_download(request, competitor_id):
    competitor = get_object_or_404(
        Competitor.objects.all().select_related("event", "event__club", "device"),
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
@api_view(["GET"])
def two_d_rerun_race_status(request):
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
            Prefetch(
                "competitors",
                queryset=Competitor.objects.select_related("device").order_by(
                    "start_time", "name"
                ),
            )
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

    competitors = event.competitors.all()
    devices = (c.device_id for c in competitors if c.device_id)
    # we need this to determine the end time of the competitor device stream
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
        nb, locations = (0, "")
        if c.device_id:
            nb, locations = c.device.get_locations_between_dates(from_date, end_date)
        nb_points += nb
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

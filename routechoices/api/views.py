import logging
import os.path
import re
import time
import urllib.parse
import arrow
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.urls import reverse
from django.views.decorators.cache import cache_page

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ratelimit.decorators import ratelimit

from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    Event,
    ImeiDevice,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    PRIVACY_SECRET,
)
from routechoices.lib.helper import short_random_key, initial_of_name
from routechoices.lib.gps_data_encoder import GeoLocationSeries
from routechoices.lib.validators import validate_imei
from routechoices.lib.s3 import s3_object_url

from rest_framework import renderers, status
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    PermissionDenied
)
from rest_framework.response import Response


logger = logging.getLogger(__name__)
API_LOCATION_TIMESTAMP_MAX_AGE = 60 * 10


def x_accel_redirect(request, path, filename='',
                     mime='application/force-download'):
    if settings.DEBUG:
        from wsgiref.util import FileWrapper
        path = os.path.join(settings.MEDIA_ROOT, path)
        if not os.path.exists(path):
            raise NotFound()
        wrapper = FileWrapper(open(path, 'rb'))
        response = HttpResponse(wrapper)
        response['Content-Length'] = os.path.getsize(path)
    else:
        path = os.path.join('/internal/', path)
        response = HttpResponse('', status=status.HTTP_206_PARTIAL_CONTENT)
        response['X-Accel-Redirect'] = urllib.parse.quote(path.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
        response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        filename.replace('\\', '_').replace('"', '\\"')
    ).encode('utf-8')
    return response


def serve_from_s3(bucket, request, path, filename='',
                  mime='application/force-download'):
    path = re.sub(r'^/internal/', '', path)
    url = s3_object_url(path, bucket)
    url = '/s3{}'.format(url[len(settings.AWS_S3_ENDPOINT_URL):])

    response_status = status.HTTP_200_OK
    if request.method == 'GET':
        response_status = status.HTTP_206_PARTIAL_CONTENT

    response = HttpResponse('', status=response_status)

    if request.method == 'GET':
        response['X-Accel-Redirect'] = urllib.parse.quote(url.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
    response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        filename.replace('\\', '_').replace('"', '\\"')
    ).encode('utf-8')
    return response


club_param = openapi.Parameter(
    'club',
    openapi.IN_QUERY,
    description='filter with this club slug',
    type=openapi.TYPE_STRING
)
event_param = openapi.Parameter(
    'event',
    openapi.IN_QUERY,
    description='filter with this event slug',
    type=openapi.TYPE_STRING
)


@swagger_auto_schema(
    method='get',
    operation_id='events_list',
    operation_description='list events',
    tags=['events'],
    manual_parameters=[club_param, event_param],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': [
                    {
                        "id": "PlCG3xFS-f4",
                        "name": "Jukola 2019 - 1st Leg",
                        "start_date": "2019-06-15T20:00:00Z",
                        "end_date": None,
                        "slug": "Jukola-2019-1st-leg",
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "open_registration": False,
                        "open_route_upload": False,
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-1st-leg"
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
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-2nd-leg"
                    },
                    '...'
                ]
            }
        ),
    }
)
@api_view(['GET'])
def event_list(request):
    club_slug = request.GET.get('club')
    event_slug = request.GET.get('event')
    if event_slug and club_slug:
        privacy_arg = {
            'privacy__in': [PRIVACY_PUBLIC, PRIVACY_SECRET]
        }
    else:
        privacy_arg = {
            'privacy': PRIVACY_PUBLIC
        }

    if request.user.is_authenticated:
        clubs = Club.objects.filter(admins=request.user)
        events = Event.objects.filter(
            Q(**privacy_arg) | Q(club__in=clubs)
        ).select_related('club')
    else:
        events = Event.objects.filter(
            **privacy_arg
        ).select_related('club')

    if club_slug:
        events = events.filter(club__slug__iexact=club_slug)
    if event_slug:
        events = events.filter(slug__iexact=event_slug)

    output = []
    for event in events:
        output.append({
            'id': event.aid,
            'name': event.name,
            'start_date': event.start_date,
            'end_date': (event.end_date if event.end_date else None),
            'slug': event.slug,
            'club': event.club.name,
            'club_slug': event.club.slug,
            'open_registration': event.open_registration,
            'open_route_upload': event.allow_route_upload,
            'url': request.build_absolute_uri(event.get_absolute_url()),
        })
    return Response(output)


@swagger_auto_schema(
    method='get',
    operation_id='event_detail',
    operation_description='read an event detail',
    tags=['events'],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    "event": {
                        "id": "PlCG3xFS-f4",
                        "name": "Jukola 2019 - 1st Leg",
                        "start_date": "2019-06-15T20:00:00Z",
                        "end_date": None,
                        "slug": "Jukola-2019-1st-leg",
                        "club": "Kangasala SK",
                        "club_slug": "ksk",
                        "open_registration": False,
                        "open_route_upload": False,
                        "url": "http://www.routechoices.com/ksk/Jukola-2019-1st-leg"
                    },
                    "competitors": [
                        {
                            "id": "pwaCro4TErI",
                            "name": "Olav Lundanes (Halden SK)",
                            "short_name": "Halden SK",
                            "start_time": "2019-06-15T20:00:00Z"
                        },
                        '...'
                    ],
                    "data": "http://www.routechoices.com/api/events/PlCG3xFS-f4/data",
                    "announcement": "",
                    "extra_maps": [],
                    "map": {
                        "coordinates": {
                            "topLeft": {
                                "lat": "61.45075",
                                "lon": "24.18994"
                            },
                            "topRight": {
                                "lat": "61.44656",
                                "lon": "24.24721"
                            },
                            "bottomRight": {
                                "lat": "61.42094",
                                "lon": "24.23851"
                            },
                            "botttomLeft": {
                                "lat": "61.42533",
                                "lon": "24.18156"
                            }
                        },
                        "url": "http://www.routechoices.com/api/events/PlCG3xFS-f4/map",
                        "title": ""
                    }
                }
            }
        ),
    }
)
@api_view(['GET'])
def event_detail(request, event_id):
    event = get_object_or_404(
        Event.objects.select_related(
            'club', 'notice'
        ).prefetch_related(
            'competitors',
            'extra_maps',
            'map_assignations'
        ),
        aid=event_id,
        start_date__lt=now()
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    output = {
        'event': {
            'id': event.aid,
            'name': event.name,
            'start_date': event.start_date,
            'end_date': (event.end_date if event.end_date else None),
            'slug': event.slug,
            'club': event.club.name,
            'club_slug': event.club.slug,
            'open_registration': event.open_registration,
            'open_route_upload': event.allow_route_upload,
            'url': request.build_absolute_uri(event.get_absolute_url()),
        },
        'competitors': [],
        'data': request.build_absolute_uri(
            reverse('api:event_data', kwargs={'event_id': event.aid})
        ),
        'announcement': event.notice.text,
        'extra_maps': [],
    }
    for c in event.competitors.all():
        output['competitors'].append({
            'id': c.aid,
            'name': c.name,
            'short_name': c.short_name,
            'start_time': c.start_time,
        })
    for i, m in enumerate(event.map_assignations.all()):
        output['extra_maps'].append({
            'title': m.title,
            'coordinates': m.map.bound,
            'url': request.build_absolute_uri(reverse(
                'api:event_extra_map_download',
                kwargs={'event_id': event.aid, 'map_index': (i+1)}
            )),
        })
    output['map'] = {
        'coordinates': event.map.bound,
        'url': request.build_absolute_uri(
            reverse('api:event_map_download', kwargs={'event_id': event.aid})
        ),
        'title': event.map_title,
    } if event.map else None

    return Response(output)


@swagger_auto_schema(
    method='post',
    operation_id='event_register',
    operation_description='register a competitor to a given event',
    tags=['events'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'device_id': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='device id',
            ),
            'name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='full name',
            ),
            'short_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='short version of the name displayed on the map',
            ),
            'start_time': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='start time, must be with the event schedule if provided (YYYY-MM-DDThh:mm:ssZ)',
            ),
        },
        required=['device_id', 'name'],
    ),
    responses={
        '201': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    'id': '<id>',
                    'device_id': '<device_id>',
                    'name': '<name>',
                    'short_name': '<short_name>',
                    'start_time': '<start_time>',
                }
            }
        ),
        '400': openapi.Response(
            description='Validation Error',
            examples={
                'application/json': [
                    '<error message>'
                ]
            }
        ),
    }
)
@api_view(['POST'])
def event_register(request, event_id):
    event = get_object_or_404(
        Event.objects.select_related(
            'club'
        ),
        aid=event_id
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    if not event.open_registration or event.end_date < now():
        raise PermissionDenied()
    device_id = request.data.get('device_id')
    devices = Device.objects.filter(aid=device_id)
    if devices.count() == 0:
        raise ValidationError('No such device ID')
    name = request.data.get('name')
    if not name:
        raise ValidationError('Property name is missing')
    short_name = request.data.get('short_name')
    if not short_name:
        short_name = initial_of_name(name)
    start_time = request.data.get('start_time')
    if start_time:
        try:
            start_time = arrow.get(start_time).datetime
        except Exception:
            raise ValidationError('Property start_time could not be parsed')
    elif event.start_date < now():
        start_time = now()
    else:
        start_time = event.start_date
    event_start = event.start_date
    event_end = event.end_date
    if start_time and (
        (not event_end and event_start > start_time)
            or (event_end and (event_start > start_time
                               or start_time > event_end))):
        raise ValidationError(
            'Competitor start time should be during the event time'
        )
    comp = Competitor.objects.create(
        name=name,
        event=event,
        short_name=short_name,
        start_time=start_time,
        device=devices.first(),
    )
    return Response({
        'id': comp.aid,
        'device_id': device_id,
        'name': name,
        'short_name': short_name,
        'start_time': start_time,
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_id='event_data',
    operation_description='read competitor data associated to an event',
    tags=['events'],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    "competitors": [
                        {
                            "id": "pwaCro4TErI",
                            "encoded_data": "<encoded data>",
                            "name": "Olav Lundanes (Halden SK)",
                            "short_name": "Halden SK",
                            "start_time": "2019-06-15T20:00:00Z"
                        }
                    ],
                    "nb_points": 0,
                    "duration": 0.009621381759643555,
                    "timestamp": 1615986763.638066
                }
            }
        ),
    }
)
@cache_page(15)
@api_view(['GET'])
def event_data(request, event_id):
    t0 = time.time()
    event = get_object_or_404(
        Event.objects.select_related('club').prefetch_related('competitors'),
        aid=event_id,
        start_date__lt=now()
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    competitors = event.competitors.select_related('device')\
        .all().order_by('start_time', 'name')

    nb_points = 0
    results = []
    for c in competitors:
        locations = c.locations
        nb_points += len(locations)
        results.append({
            'id': c.aid,
            'encoded_data': c.encoded_data,
            'name': c.name,
            'short_name': c.short_name,
            'start_time': c.start_time,
        })
    return Response({
        'competitors': results,
        'nb_points': nb_points,
        'duration': (time.time()-t0),
        'timestamp': arrow.utcnow().timestamp(),
    })


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def event_map_details(request, event_id):
    event = get_object_or_404(
        Event.objects.all().select_related('club', 'map'),
        aid=event_id,
        start_date__lt=now()
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    if not event.map:
        return Response({
            'hash': '',
            'last_mod': '',
            'corners_coordinates': '',
        })
    rmap = event.map
    return Response({
        'hash': rmap.hash,
        'last_mod': rmap.modification_date,
        'corners_coordinates': rmap.corners_coordinates,
    })


@swagger_auto_schema(
    method='get',
    operation_id='event_announcement',
    operation_description='read the announcement associated to an event',
    tags=['events'],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    "updated": "2021-03-08T08:10:08.795905Z",
                    "text": "Mass start at 9pm"
                }
            }
        ),
    }
)
@api_view(['GET'])
def event_announcement(request, event_id):
    event = get_object_or_404(
        Event.objects.all().select_related('notice'),
        aid=event_id,
        start_date__lt=now()
    )
    if event.has_notice:
        return Response({
            'updated': event.notice.modification_date,
            'text': event.notice.text,
        })
    return Response({})


def traccar_ratelimit_key(group, request):
    return request.META['REMOTE_ADDR'] + request.query_params.get('id', '')


@swagger_auto_schema(
    method='post',
    operation_id='traccar_gateway',
    operation_description='gateway for posting data from traccar application',
    tags=['post locations'],
    manual_parameters=[
        openapi.Parameter(
            'id',
            openapi.IN_QUERY,
            description='your device id',
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'lat',
            openapi.IN_QUERY,
            description='a single location latitudes (in degrees)',
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'lon',
            openapi.IN_QUERY,
            description='a single location longitude (in degrees)',
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'timestamp',
            openapi.IN_QUERY,
            description='a single location timestamp (UNIX epoch in seconds)',
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    'status': 'ok',
                }
            }
        ),
        '400': openapi.Response(
            description='Validation Error',
            examples={
                'application/json': [
                    '<error message>'
                ]
            }
        ),
    }
)
@api_view(['POST'])
@ratelimit(key=traccar_ratelimit_key, rate='70/m')
def traccar_api_gw(request):
    traccar_id = request.query_params.get('id')
    if not traccar_id:
        raise ValidationError('Use Traccar App on android or IPhone')
    device_id = traccar_id
    devices = Device.objects.filter(aid=device_id)
    if devices.count() == 0:
        raise ValidationError('No such device ID')
    device = devices.first()
    lat = request.query_params.get('lat')
    lon = request.query_params.get('lon')
    tim = request.query_params.get('timestamp')
    try:
        lat = float(lat)
        lon = float(lon)
        tim = int(float(tim))
    except ValueError:
        logger.debug('Wrong data format')
        raise ValidationError({
            'status': 'error',
            'message': 'Invalid data format'
        })

    if abs(time.time() - tim) > API_LOCATION_TIMESTAMP_MAX_AGE:
        logger.debug('Too old position')
        raise ValidationError('Position too old to add from API')

    if lat and lon and tim:
        device.add_location(lat, lon, tim)
        return Response({'status': 'ok'})
    if not lat:
        logger.debug('No lat')
    if not lon:
        logger.debug('No lon')
    if not tim:
        logger.debug('No timestamp')
    raise ValidationError('Missing lat, lon, or time')


def garmin_ratelimit_key(group, request):
    return request.META['REMOTE_ADDR'] + request.data.get('device_id', '')


@swagger_auto_schema(
    method='post',
    operation_id='garmin_gateway',
    operation_description='gateway for posting data from garmin application, allows multiple locations at once',
    tags=['post locations'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'device_id': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='your device id',
            ),
            'latitudes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='a list of locations latitudes (in degrees) separated by commas',
            ),
            'longitudes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='a list of locations longitudes (in degrees) separated by commas',
            ),
            'timestamps': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='a list of locations timestamps (UNIX epoch in seconds) separated by commas',
            ),
        },
        required=['device_id', 'latitudes', 'longitudes', 'timestamps'],
    ),
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    'status': 'ok',
                    'n': '<number of locations posted>',
                }
            }
        ),
        '400': openapi.Response(
            description='Validation Error',
            examples={
                'application/json': [
                    '<error message>'
                ]
            }
        ),
    }
)
@api_view(['POST'])
@ratelimit(key=garmin_ratelimit_key, rate='70/m')
def garmin_api_gw(request):
    device_id = request.data.get('device_id')
    if not device_id:
        raise ValidationError('Missing device_id parameter')
    devices = Device.objects.filter(aid=device_id)
    if devices.count() == 0:
        raise ValidationError('No such device ID')
    device = devices.first()
    lats = request.data.get('latitudes', '').split(',')
    lons = request.data.get('longitudes', '').split(',')
    times = request.data.get('timestamps', '').split(',')
    if len(lats) != len(lons) != len(times):
        raise ValidationError('Data error')
    loc_array = []
    for i in range(len(times)):
        if times[i] and lats[i] and lons[i]:
            try:
                lat = float(lats[i])
                lon = float(lons[i])
                tim = int(float(times[i]))
            except ValueError:
                continue
            if abs(time.time() - tim) > API_LOCATION_TIMESTAMP_MAX_AGE:
                continue
            loc_array.append({
                'timestamp': tim,
                'latitude': lat,
                'longitude': lon,
            })
    if len(loc_array) > 0:
        device.add_locations(loc_array)
    return Response({'status': 'ok', 'n': len(loc_array)})


@swagger_auto_schema(
    method='post',
    operation_id='pwa_gateway',
    operation_description='gateway for posting data from the pwa application',
    tags=['post locations'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'device_id': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='your device id',
            ),
            'raw_data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='a list of locations within last 10 minutes encoded according to our propriatery format',
            ),
        },
        required=['device_id', 'raw_data'],
    ),
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    'status': 'ok',
                    'n': '<number of locations posted>'
                }
            }
        ),
        '400': openapi.Response(
            description='Validation Error',
            examples={
                'application/json': [
                    '<error message>'
                ]
            }
        ),
    }
)
@api_view(['POST'])
@ratelimit(key=garmin_ratelimit_key, rate='70/m')
def pwa_api_gw(request):
    device_id = request.data.get('device_id')
    if not device_id:
        raise ValidationError(
            'Missing device_id parameter'
        )
    devices = Device.objects.filter(aid=device_id)
    if devices.count() == 0:
        raise ValidationError('No such device ID')
    device = devices.first()
    raw_data = request.data.get('raw_data')
    if not raw_data:
        raise ValidationError('Missing raw_data argument')
    locations = GeoLocationSeries(raw_data)
    loc_array = []
    for location in locations:
        dtime = abs(time.time() - int(location.timestamp))
        if dtime > API_LOCATION_TIMESTAMP_MAX_AGE:
            continue
        loc_array.append({
            'timestamp': int(location.timestamp),
            'latitude': location.coordinates.latitude,
            'longitude': location.coordinates.longitude,
        })
    if len(loc_array) > 0:
        device.add_locations(loc_array)
    return Response({'status': 'ok', 'n': len(locations)})


class DataRenderer(renderers.BaseRenderer):
    media_type = 'application/download'
    format = 'raw'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data


GPS_SEURANTA_URL_RE = r'^https?://(gps|www)\.tulospalvelu\.fi/gps/(.*)$'


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
@renderer_classes((DataRenderer, ))
def gps_seuranta_proxy(request):
    url = request.GET.get('url')
    if not url or not re.match(GPS_SEURANTA_URL_RE, url):
        raise ValidationError('Not a gps seuranta url')
    response = requests.get(url)
    return Response(response.content)


@swagger_auto_schema(
    method='post',
    operation_id='create_device_id',
    operation_description='create a device id',
    tags=['device'],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    'status': 'ok',
                    'device_id': '<device_id>',
                }
            }
        ),
    }
)
@api_view(['POST'])
@ratelimit(key='ip', rate='10/m')
def get_device_id(request):
    device = Device.objects.create()
    return Response({'status': 'ok', 'device_id': device.aid})


@swagger_auto_schema(
    method='post',
    operation_id='create_imei_device_id',
    operation_description='create a device id for a specific imei',
    tags=['device'],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'imei': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='your gps tracking device IMEI',
            ),
        },
        required=['imei'],
    ),
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    'status': 'ok',
                    'imei': '<IMEI>',
                    'device_id': '<device_id>',
                }
            }
        ),
        '400': openapi.Response(
            description='Validation Error',
            examples={
                'application/json': [
                    '<error message>'
                ]
            }
        ),
    }
)
@api_view(['POST'])
@ratelimit(key='ip', rate='60/m')
def get_device_for_imei(request):
    imei = request.data.get('imei')
    if not imei:
        raise ValidationError('No imei')
    try:
        validate_imei(imei)
    except Exception:
        raise ValidationError('Invalid imei')
    idevice = None
    try:
        idevice = ImeiDevice.objects.get(imei=imei)
    except ImeiDevice.DoesNotExist:
        d = Device(aid=short_random_key()+'_i')
        d.save()
        idevice = ImeiDevice(imei=imei, device=d)
        idevice.save()
    return Response({
        'status': 'ok',
        'device_id': d.aid,
        'imei': imei
    })


@swagger_auto_schema(
    method='get',
    operation_id='server_time',
    operation_description='read the server time',
    tags=[],
    responses={
        '200': openapi.Response(
            description='Success response',
            examples={
                'application/json': {
                    "time": 1615987017.7934635
                }
            }
        ),
    }
)
@api_view(['GET'])
def get_time(request):
    return Response({'time': time.time()})


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
@login_required
def user_search(request):
    users = []
    q = request.GET.get('q')
    if q and len(q) > 2:
        users = User.objects.filter(username__icontains=q)\
            .values_list('id', 'username')[:10]
    return Response({
        'results': [{'id': u[0], 'username': u[1]} for u in users]
    })


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def device_search(request):
    devices = []
    q = request.GET.get('q')
    if q and len(q) > 2:
        devices = Device.objects.filter(aid__startswith=q, is_gpx=False) \
            .values_list('id', 'aid')[:10]
    return Response({
        'results': [{'id': d[0], 'device_id': d[1]} for d in devices]
    })


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def event_map_download(request, event_id):
    event = get_object_or_404(
        Event.objects.all().select_related('club', 'map'),
        aid=event_id,
        start_date__lt=now()
    )
    if not event.map:
        raise NotFound()
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    raster_map = event.map
    file_path = raster_map.path
    mime_type = raster_map.mime_type
    return serve_from_s3(
        'routechoices-maps',
        request,
        '/internal/' + file_path,
        filename='{}_{}_.{}'.format(
            raster_map.name,
            raster_map.corners_coordinates.replace(',', '_'),
            mime_type[6:]
        ),
        mime=mime_type
    )


@api_view(['GET'])
def event_map_thumb_download(request, event_id):
    event = get_object_or_404(
        Event.objects.all().select_related('club', 'map'),
        aid=event_id,
        start_date__lt=now()
    )
    if not event.map:
        raise NotFound()
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    raster_map = event.map
    response = HttpResponse(content_type='image/jpeg')
    raster_map.thumbnail.save(response, 'JPEG', quality=80)
    return response


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def event_extra_map_download(request, event_id, map_index):
    event = get_object_or_404(
        Event.objects.all().select_related('club', 'map'),
        aid=event_id,
        start_date__lt=now()
    )
    if event.extra_maps.all().count() < int(map_index) or int(map_index) == 0:
        raise NotFound()
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    raster_map = event.extra_maps.all()[int(map_index)-1]
    file_path = raster_map.path
    mime_type = raster_map.mime_type
    return serve_from_s3(
        'routechoices-maps',
        request,
        '/internal/' + file_path,
        filename='{}_{}_.{}'.format(
            raster_map.name,
            raster_map.corners_coordinates.replace(',', '_'),
            mime_type[6:]
        ),
        mime=mime_type
    )


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def competitor_gpx_download(request, competitor_id):
    competitor = get_object_or_404(
        Competitor.objects.all().select_related('event', 'event__club'),
        aid=competitor_id,
        start_time__lt=now()
    )
    event = competitor.event
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    gpx_data = competitor.gpx
    response = HttpResponse(
        gpx_data,
        content_type='application/gpx+xml'
    )
    response['Content-Disposition'] = 'attachment; filename="{}.gpx"'.format(
        competitor.event.name.replace('\\', '_').replace('"', '\\"') + ' - ' +
        competitor.name
    )
    return response

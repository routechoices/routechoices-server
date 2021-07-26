import logging
import os.path
import re
import time
import urllib.parse
import orjson as json
from io import BytesIO
from PIL import Image
import arrow
import requests

from django.contrib.sites.models import Site
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q, Case, When
from django.http import HttpResponse
from django.http.response import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django_hosts.resolvers import reverse
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
    Map,
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    PRIVACY_SECRET,
)
from routechoices.lib.helper import short_random_key, initial_of_name
from routechoices.lib.globalmaptiles import GlobalMercator
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
# API_LOCATION_TIMESTAMP_MAX_AGE = 60 * 10
GLOBAL_MERCATOR = GlobalMercator()


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
                            "bottomLeft": {
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
            reverse('event_data', host='api', kwargs={'event_id': event.aid})
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
                'event_extra_map_download',
                host='api',
                kwargs={'event_id': event.aid, 'map_index': (i+1)}
            )),
        })
    output['map'] = {
        'coordinates': event.map.bound,
        'url': request.build_absolute_uri(
            reverse(
                'event_map_download',
                host='api', 
                kwargs={'event_id': event.aid}
            )
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
                description='start time, must be within the event schedule if provided (YYYY-MM-DDThh:mm:ssZ)',
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
    if not event.open_registration or (event.end_date and event.end_date < now()):
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
@api_view(['GET'])
def event_data(request, event_id):
    t0 = time.time()

    cache_ts = t0 // 7.5
    cache_key = f'event_data:{event_id}:{request.GET.get("t", -1)}:{cache_ts}'
    prev_cache_key = f'event_data:{event_id}:{request.GET.get("t", -1)}:{cache_ts - 1}'

    cached_res = cache.get(cache_key)
    if cached_res:
        return Response(cached_res)
    elif cache.get(f'{cache_key}:processing'):
        cached_res = cache.get(prev_cache_key)
        if cached_res:
            return Response(cached_res)
    cache.set(f'{cache_key}:processing', 1, 15)

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
    devices = (c.device_id for c in competitors)
    all_devices_competitors = Competitor.objects.filter(start_time__gte=event.start_date, device_id__in=devices)
    competitors_by_device = {}
    for c in all_devices_competitors:
        start_times_by_device.setdefault(c.device_id, [])
        start_times_by_device[c.device_id].append(c.start_time)
        start_times_by_device[c.device_id] = sorted(competitors_by_device[c.device_id])
    nb_points = 0
    results = []
    for c in competitors:
        from_date = c.start_time
        next_competitor_start_time = None
        for nxt in start_times_by_device.get(c.device_id, []):
            if nxt > c.start_time:
                next_competitor_start_time = nxt
                break
        end_date = now()
        if next_competitor_start_time:
            end_date = min(
                next_competitor_start_time,
                end_date
            )
        if event.end_date:
            end_date = min(
                event.end_date,
                end_date
            )
        nb, encoded_data = (0, "")
        if c.device_id:
            nb, encoded_data = c.device.get_locations_between_dates(from_date, to_date, encoded=True)
        nb_points += nb
        results.append({
            'id': c.aid,
            'encoded_data': encoded_data,
            'name': c.name,
            'short_name': c.short_name,
            'start_time': c.start_time,
        })
    res = {
        'competitors': results,
        'nb_points': nb_points,
        'duration': (time.time()-t0),
        'timestamp': arrow.utcnow().timestamp(),
    }
    cache.set(cache_key, res, 20)
    return Response(res)


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

    # if abs(time.time() - tim) > API_LOCATION_TIMESTAMP_MAX_AGE:
    #    logger.debug('Too old position')
    #    raise ValidationError('Position too old to add from API')

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
    operation_id='locations_gateway',
    operation_description='gateway for posting locations data, allows multiple locations at once',
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
def locations_api_gw(request):
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
            # if abs(time.time() - tim) > API_LOCATION_TIMESTAMP_MAX_AGE:
            #     continue
            loc_array.append({
                'timestamp': tim,
                'latitude': lat,
                'longitude': lon,
            })
    if len(loc_array) > 0:
        device.add_locations(loc_array)
    return Response({'status': 'ok', 'n': len(loc_array)})


def garmin_api_gw(request):
    return locations_api_gw(request)


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
                description='a list of locations within last 10 minutes encoded according to our proprietary format',
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
        # dtime = abs(time.time() - int(location.timestamp))
        # if dtime > API_LOCATION_TIMESTAMP_MAX_AGE:
        #     continue
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
    except Exception as e:
        raise ValidationError('Invalid imei '+str(e))
    idevice = None
    try:
        idevice = ImeiDevice.objects.get(imei=imei)
        device = idevice.device
    except ImeiDevice.DoesNotExist:
        device = Device(aid=short_random_key()+'_i')
        device.save()
        idevice = ImeiDevice(imei=imei, device=device)
        idevice.save()
    return Response({
        'status': 'ok',
        'device_id': device.aid,
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
            raster_map.corners_coordinates_short.replace(',', '_'),
            mime_type[6:]
        ),
        mime=mime_type
    )


@swagger_auto_schema(
    method='get',
    auto_schema=None,
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
def event_kmz_download(request, event_id):
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
    kmz_data = raster_map.kmz
    response = HttpResponse(
        kmz_data,
        content_type='application/vnd.google-earth.kmz'
    )
    response['Content-Disposition'] = 'attachment; filename="{}.kmz"'.format(
        raster_map.name.replace('\\', '_').replace('"', '\\"')
    )
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
    if event.extra_maps.all().count() < int(map_index):
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
            raster_map.corners_coordinates_short.replace(',', '_'),
            mime_type[6:]
        ),
        mime=mime_type
    )


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def event_extra_kmz_download(request, event_id, map_index):
    event = get_object_or_404(
        Event.objects.all().select_related('club', 'map'),
        aid=event_id,
        start_date__lt=now()
    )
    if event.extra_maps.all().count() < int(map_index):
        raise NotFound()
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    raster_map = event.extra_maps.all()[int(map_index)-1]
    kmz_data = raster_map.kmz
    response = HttpResponse(
        kmz_data,
        content_type='application/vnd.google-earth.kmz'
    )
    response['Content-Disposition'] = 'attachment; filename="{}.kmz"'.format(
        raster_map.name.replace('\\', '_').replace('"', '\\"')
    )
    return response


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@login_required
@api_view(['GET'])
def map_kmz_download(request, map_id, *args, **kwargs):
    if request.user.is_superuser:
        raster_map = get_object_or_404(
            Map,
            aid=map_id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        raster_map = get_object_or_404(
            Map,
            aid=map_id,
            club__in=club_list
        )
    kmz_data = raster_map.kmz
    response = HttpResponse(
        kmz_data,
        content_type='application/vnd.google-earth.kmz'
    )
    response['Content-Disposition'] = 'attachment; filename="{}.kmz"'.format(
        raster_map.name.replace('\\', '_').replace('"', '\\"')
    )
    return response


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
        competitor.name.replace('\\', '_').replace('"', '\\"')
    )
    return response


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def two_d_rerun_race_status(request):
    '''

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
    '''

    event_id = request.GET.get('eventid')
    if not event_id:
        raise Http404()
    event = get_object_or_404(
        Event.objects.all()
        .select_related('club', 'map')
        .prefetch_related(
            'competitors',
        ),
        aid=event_id,
        start_date__lt=now()
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    response_json = {
        'status': 'OK',
        'racename': event.name,
        'racestarttime': event.start_date,
        'raceendtime': event.end_date,
        'mapurl': f'https:{event.get_absolute_map_url()}?.jpg',
        'caltype': '3point',
        'mapw': event.map.width,
        'maph': event.map.height,
        'calibration': [
            [
                event.map.bound['topLeft']['lon'],
                event.map.bound['topLeft']['lat'],
                0,
                0
            ],
            [
                event.map.bound['topRight']['lon'],
                event.map.bound['topRight']['lat'],
                event.map.width,
                0
            ],
            [
                event.map.bound['bottomLeft']['lon'],
                event.map.bound['bottomLeft']['lat'],
                0, 
                event.map.height
            ]
        ],
        'competitors': []
    }
    for c in event.competitors.all():
        response_json['competitors'].append(
            [c.aid, c.name, c.start_time]
        )

    response_raw = str(json.dumps(response_json), 'utf-8')
    content_type = 'application/json'
    callback = request.GET.get('callback')
    if callback:
        response_raw = f'/**/{callback}({response_raw});'
        content_type = 'text/javascript; charset=utf-8'
    return HttpResponse(response_raw, content_type=content_type)


@swagger_auto_schema(
    method='get',
    auto_schema=None,
)
@api_view(['GET'])
def two_d_rerun_race_data(request):
    event_id = request.GET.get('eventid')
    if not event_id:
        raise Http404()
    event = get_object_or_404(
        Event.objects.all()
        .prefetch_related(
            'competitors',
        ),
        aid=event_id,
        start_date__lt=now()
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    cached_result = cache.get(f'woo:{event.aid}:data')
    if not cached_result:
        competitors = event.competitors.select_related('device')\
            .all().order_by('start_time', 'name')
        nb_points = 0
        results = []
        for c in competitors:
            locations = c.locations
            nb_points += len(locations)
            results += [[
                c.aid,
                ll['latitude'],
                ll['longitude'],
                0,
                arrow.get(ll['timestamp']).datetime
            ] for ll in c.locations]
        response_json = {
            'containslastpos': 1,
            'lastpos': nb_points,
            'status': 'OK',
            'data': results,
        }
        cache.set(f'woo:{event.aid}:data', response_json, 15)
    else:
        response_json = cached_result
    response_raw = str(json.dumps(response_json), 'utf-8')
    content_type = 'application/json'
    callback = request.GET.get('callback')
    if callback:
        response_raw = f'/**/{callback}({response_raw});'
        content_type = 'text/javascript; charset=utf-8'
    return HttpResponse(
        response_raw,
        content_type=content_type,
    )


@cache_page(3600)
def wms_service(request):
    if 'WMS' not in [request.GET.get('service'), request.GET.get('SERVICE')]:
        return HttpResponseBadRequest('Service must be WMS')
    if 'GetMap' in [request.GET.get('request'),
                    request.GET.get('REQUEST')]:
        layers_raw = request.GET.get('layers', request.GET.get('LAYERS'))
        bbox_raw = request.GET.get('bbox', request.GET.get('BBOX'))
        width_raw = request.GET.get('width', request.GET.get('WIDTH'))
        heigth_raw = request.GET.get('height', request.GET.get('HEIGHT'))
        if not layers_raw or not bbox_raw or not width_raw or not heigth_raw:
            return HttpResponseBadRequest('missing mandatory parameters')
        layers_id = layers_raw.split(',')
        try:
            min_lat, min_lon, max_lat, max_lon = (float(x) for x in bbox_raw.split(','))
            if request.GET.get('SRS', request.GET.get('crs')) == 'CRS:84':
                min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox_raw.split(','))
                min_xy = GLOBAL_MERCATOR.latlon_to_meters({'lat': min_lat, 'lon': min_lon})
                max_xy = GLOBAL_MERCATOR.latlon_to_meters({'lat': max_lat, 'lon': max_lon})
                min_lon = min_xy['y']
                min_lat = min_xy['x']
                max_lon = max_xy['y']
                max_lat = max_xy['x']
            out_w, out_h = int(width_raw), int(heigth_raw)
        except Exception:
            return HttpResponseBadRequest('invalid parameters')
        if 'all' in layers_id:
            layers = Map.objects.all()
        else:
            order = Case(
                *[When(aid=aid, then=pos) for pos, aid in enumerate(layers_id)]
            )
            layers = Map.objects.filter(aid__in=layers_id).order_by(order)
        out_image = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 0))
        for layer in layers:
            try:
                layer_raster = layer.create_tile(
                    out_w, out_h, min_lon, max_lon, min_lat, max_lat
                )
                out_image.paste(
                    layer_raster,
                    (0, 0),
                    layer_raster
                )
            except Exception as e:
                raise e
                continue
        output = BytesIO()
        out_image.save(output, format='png')
        data_out = output.getvalue()
        return HttpResponse(
            data_out,
            content_type='image/png'
        )
    elif 'GetCapabilities' in [request.GET.get('request'),
                               request.GET.get('REQUEST')]:
        max_xy = GLOBAL_MERCATOR.latlon_to_meters({'lat': 89.9, 'lon': 180})
        min_xy = GLOBAL_MERCATOR.latlon_to_meters({'lat': -89.9, 'lon': -180})

        layers = Map.objects.all().select_related('club')
        layers_xml = ''
        for layer in layers:
            min_lon = min(
                layer.bound['topLeft']['lon'],
                layer.bound['bottomLeft']['lon'],
                layer.bound['bottomRight']['lon'],
                layer.bound['topRight']['lon'],
            )
            max_lon = max(
                layer.bound['topLeft']['lon'],
                layer.bound['bottomLeft']['lon'],
                layer.bound['bottomRight']['lon'],
                layer.bound['topRight']['lon'],
            )
            min_lat = min(
                layer.bound['topLeft']['lat'],
                layer.bound['bottomLeft']['lat'],
                layer.bound['bottomRight']['lat'],
                layer.bound['topRight']['lat'],
            )
            max_lat = max(
                layer.bound['topLeft']['lat'],
                layer.bound['bottomLeft']['lat'],
                layer.bound['bottomRight']['lat'],
                layer.bound['topRight']['lat'],
            )

            l_max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                {'lat': max_lat, 'lon': max_lon}
            )
            l_min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                {'lat': min_lat, 'lon': min_lon}
            )

            layers_xml += f'''
    <Layer queryable="0" opaque="0" cascaded="0">
      <Name>{layer.aid}</Name>
      <Title>{layer.name} by {layer.club}</Title>
      <CRS>EPSG:3857</CRS>
      <CRS>CRS:84</CRS>
      <EX_GeographicBoundingBox>
        <westBoundLongitude>{min_lon}</westBoundLongitude>
        <eastBoundLongitude>{max_lon}</eastBoundLongitude>
        <southBoundLatitude>{min_lon}</southBoundLatitude>
        <northBoundLatitude>{max_lat}</northBoundLatitude>
      </EX_GeographicBoundingBox>
      <BoundingBox CRS="EPSG:3857" minx="{l_min_xy['x']}" miny="{l_min_xy['y']}" maxx="{l_max_xy['x']}" maxy="{l_max_xy['y']}"/>
      <BoundingBox CRS="EPSG:3857" minx="{min_lon}" miny="{min_lat}" maxx="{max_lon}" maxy="{max_lat}"/>
    </Layer>
            '''
        return HttpResponse(
            f'''<?xml version='1.0' encoding="UTF-8" standalone="no" ?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ms="http://mapserver.gis.umn.edu/mapserver" xsi:schemaLocation="http://www.opengis.net/wms http://schemas.opengis.net/wms/1.3.0/capabilities_1_3_0.xsd">
<Service>
  <Name>WMS</Name>
  <Title>Routechoices</Title>
  <Abstract>Routechoices server</Abstract>
  <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms"/>
  <ContactInformation>
  </ContactInformation>
  <MaxWidth>10000</MaxWidth>
  <MaxHeight>10000</MaxHeight>
</Service>
<Capability>
  <Request>
    <GetCapabilities>
      <Format>text/xml</Format>
      <DCPType>
        <HTTP>
          <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms"/></Get>
          <Post><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms"/></Post>
        </HTTP>
      </DCPType>
    </GetCapabilities>
    <GetMap>
      <Format>image/png</Format>
      <DCPType>
        <HTTP>
          <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms"/></Get>
          <Post><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://routechoices.com/api/wms"/></Post>
        </HTTP>
      </DCPType>
    </GetMap>
  </Request>
  <Exception>
    <Format>XML</Format>
    <Format>INIMAGE</Format>
    <Format>BLANK</Format>
  </Exception>
  <Layer>
    <Name>all</Name>
    <Title>Routechoices Maps</Title>
    <CRS>EPSG:3857</CRS>
    <CRS>CRS:84</CRS>
    <EX_GeographicBoundingBox>
      <westBoundLongitude>-180</westBoundLongitude>
      <eastBoundLongitude>180</eastBoundLongitude>
      <southBoundLatitude>-90</southBoundLatitude>
      <northBoundLatitude>90</northBoundLatitude>
    </EX_GeographicBoundingBox>
    <BoundingBox CRS="EPSG:3857" minx="{min_xy['x']}" miny="{min_xy['y']}" maxx="{max_xy['x']}" maxy="{max_xy['y']}"/>
    <BoundingBox CRS="CRS:84" minx="-180" miny="-90" maxx="180" maxy="90"/>
    {layers_xml}
  </Layer>
</Capability>
</WMS_Capabilities>
            ''',
            content_type='text/xml'
        )

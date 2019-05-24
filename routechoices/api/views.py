import logging
import os.path
import re
import time
import urllib.parse
from itertools import chain

import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now

from routechoices.core.models import (
    Event,
    Location,
    Device,
    Competitor,
    PRIVACY_PRIVATE,
)
from routechoices.lib.gps_data_encoder import GeoLocationSeries

from rest_framework import renderers, status
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    PermissionDenied
)
from rest_framework.response import Response


logger = logging.getLogger(__name__)


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


@api_view(['GET'])
def api_root(request):
    return Response()


@api_view(['GET'])
def event_data(request, aid):
    t0 = time.time()
    event = get_object_or_404(Event, aid=aid, start_date__lt=now())
    if event.privacy == PRIVACY_PRIVATE:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    competitors = event.competitors.all()

    nb_points = 0
    results = []
    for c in competitors:
        nb_points += c.locations.count()
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
        'duration': (time.time()-t0)
    })


@api_view(['GET'])
def event_rg_data(request, aid):
    t0 = time.time()
    event = get_object_or_404(Event, aid=aid, start_date__lt=now())
    if event.privacy == PRIVACY_PRIVATE:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    competitors = event.competitors.all()
    competitor_values = competitors.values_list(
        'id',
        'name',
        'short_name',
        'aid'
    )
    competitor_data = {}
    for c in competitor_values:
        competitor_data[c[0]] = {
            'aid': c[3],
            'name': c[1],
            'short_name': c[2]
        }
    locations = Location.objects.none()
    for competitor in competitors:
        locations = list(chain(locations, competitor.locations))
    response_data = []
    locations = sorted(locations, key=lambda l: l.datetime)
    for location in locations:
        response_data.append({
            'id': competitor_data[location.competitor]['aid'],
            'name': competitor_data[location.competitor]['name'],
            'lat': location.latitude,
            'lon': location.longitude,
            'sec': location.timestamp,
        })
    response_data.append({'n': len(locations), 'duration': time.time()-t0})
    return Response(response_data)


@api_view(['GET', 'POST'])
def traccar_api_gw(request):
    traccar_id = request.query_params.get('id')
    if not traccar_id:
        logger.error('No traccar_id')
        raise ValidationError('Use Traccar App on android or IPhone')
    device_id = traccar_id
    device = get_object_or_404(Device, aid=device_id)
    lat = request.query_params.get('lat')
    lon = request.query_params.get('lon')
    tim = request.query_params.get('timestamp')
    if lat and lon and tim:
        device.add_location(float(lat), float(lon), int(float(tim)))
    else:
        if not lat:
            logger.error('No lat')
        if not lon:
            logger.error('No lon')
        if not tim:
            logger.error('No timestamp')
        raise ValidationError('Missing lat, lon or timestamp argument')
    return Response({'status': 'ok'})


@api_view(['POST'])
def garmin_api_gw(request):
    device_id = request.data.get('device_id')
    if not device_id:
        logger.error('No device_id')
        raise ValidationError('Use Garmin App from Connect IQ store')
    device = get_object_or_404(Device, aid=device_id)
    lats = request.data.get('latitudes', '').split(',')
    lons = request.data.get('longitudes', '').split(',')
    times = request.data.get('timestamps', '').split(',')
    if len(lats) != len(lons) != len(times):
        raise ValidationError('Data error')
    for i in range(len(times)):
        if times[i] and lats[i] and lons[i]:
            device.add_location(float(lats[i]), float(lons[i]), int(float(times[i])))
    return Response({'status': 'ok'})


@api_view(['POST'])
def pwa_api_gw(request):
    device_id = request.POST.get('id')
    if not device_id:
        raise ValidationError(
            'Use the official Routechoices.com Tracker web app'
        )
    device = get_object_or_404(Device, aid=device_id)

    raw_data = request.POST.get('raw_data')
    if raw_data:
        locations = GeoLocationSeries(raw_data)
        for location in locations:
            device.add_location(
                location.coordinates.latitude,
                location.coordinates.longitude,
                location.timestamp
            )
    else:
        raise ValidationError('Missing raw_data argument')
    return Response({'status': 'ok', 'n': len(locations)})


class DataRenderer(renderers.BaseRenderer):
    media_type = 'application/download'
    format = 'raw'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data


GPS_SEURANTA_URL_RE = r'^https?://(gps|www)\.tulospalvelu\.fi/gps/(.*)$'


@api_view(['GET'])
@renderer_classes((DataRenderer, ))
def gps_seuranta_proxy(request):
    url = request.GET.get('url')
    if not url or not re.match(GPS_SEURANTA_URL_RE, url):
        raise ValidationError('Not a gps seuranta url')
    response = requests.get(url)
    return Response(response.content)


@api_view(['POST'])
def get_device_id(request):
    device = Device.objects.create()
    return Response({'device_id': device.aid})


@api_view(['GET'])
def get_time(request):
    return Response({'time': time.time()})


@api_view(['GET'])
@login_required
def user_search(request):
    users = []
    q = request.GET.get('q')
    if q and len(q) > 2:
        users = User.objects.filter(username__icontains=q)\
            .values_list('id', 'username')[:10]
    return Response({'results': [{'id': u[0], 'username': u[1]} for u in users]})


@api_view(['GET'])
@login_required
def device_search(request):
    devices = []
    q = request.GET.get('q')
    if q and len(q) > 2:
        devices = Device.objects.filter(aid__startswith=q, is_gpx=False) \
            .values_list('id', 'aid')[:10]
    return Response({'results': [{'id': d[0], 'aid': d[1]} for d in devices]})


@api_view(['GET'])
def event_map_download(request, aid):
    event = get_object_or_404(Event, aid=aid, start_date__lt=now())
    if not event.map:
        raise NotFound()
    if event.privacy == PRIVACY_PRIVATE:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied()
    file_path = event.map.path
    return x_accel_redirect(
        request,
        file_path,
        filename='{}.{}'.format(event.map.name, event.map.mime_type[6:]),
        mime=event.map.mime_type
    )


@api_view(['GET'])
def competitor_gpx_download(request, aid):
    competitor = get_object_or_404(
        Competitor,
        aid=aid,
        start_time__lt=now()
    )
    event = competitor.event
    if event.privacy == PRIVACY_PRIVATE:
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

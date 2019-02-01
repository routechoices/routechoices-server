import re
import time
import urllib
from itertools import chain

import requests
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseNotFound, \
    HttpResponseForbidden, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now

from rest_framework import generics, permissions, renderers
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    NotAuthenticated,
    PermissionDenied
)
from rest_framework.response import Response


from routechoices.core.models import Event, Location, Device, Club, Competitor


def x_accel_redirect(dummy_request, path, filename='',
                     mime='application/force-download'):
    if settings.DEBUG:
        from wsgiref.util import FileWrapper
        import os.path
        chunk_size = 8192
        path = os.path.join(settings.MEDIA_ROOT, path)
        try:
            wrapper = FileWrapper(open(path, 'rb'), chunk_size)
        except FileNotFoundError:
            return HttpResponse(status=404)
        response = StreamingHttpResponse(wrapper, content_type=mime)
        response['Content-Length'] = os.path.getsize(path)
    else:
        response = HttpResponse('', status=206)
        path = '/internal/' + path
        response['X-Accel-Redirect'] = urllib.parse.quote(path.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
        response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        filename.replace('\\', '_').replace('"', '\\"')
    )
    return response


def events_view(request):
    event_list = Event.objects.all()
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    events = paginator.get_page(page)
    return render(
        request,
        'site/event_list.html',
        {'events': events}
    )


def club_view(request, slug):
    club = get_object_or_404(
        Club,
        slug__iexact=slug
    )
    event_list = Event.objects.filter(club=club)
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    events = paginator.get_page(page)
    return render(
        request,
        'site/event_list_for_club.html',
        {
            'club': club,
            'events': events
        }
    )


def event_view(request, club_slug, slug):
    event = get_object_or_404(
        Event,
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )

    return render(
        request,
        'site/event.html',
        {
            'event': event,
        }
    )


def event_export_view(request, club_slug, slug):
    event = get_object_or_404(
        Event,
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        start_date__lt=now()
    )

    return render(
        request,
        'site/event_export.html',
        {
            'event': event,
        }
    )


def competitor_gpx_view(request, club_slug, slug, aid):
    competitor = get_object_or_404(
        Competitor,
        event__club__slug__iexact=club_slug,
        event__slug__iexact=slug,
        aid=aid,
        start_time__lt=now()
    )
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


def event_map_view(request, club_slug, slug):
    event = get_object_or_404(
        Event,
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )
    if not event.map:
        return HttpResponseNotFound()
    if event.hidden:
        return HttpResponseForbidden()
    file_path = event.map.path
    return x_accel_redirect(
        request,
        file_path,
        filename='{}.{}'.format(event.map.name, event.map.mime_type[6:]),
        mime=event.map.mime_type
    )


@api_view(['GET'])
def event_data_view(request, club_slug, slug):
    t0 = time.time()
    event = get_object_or_404(
        Event,
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )
    if event.hidden:
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
        raise ValidationError('Use Traccar App or the official Tracker web app')
    device_id = traccar_id
    device = get_object_or_404(Device, aid=device_id)
    lat = request.query_params.get('lat')
    lon = request.query_params.get('lon')
    tim = request.query_params.get('timestamp')
    if lat and lon and tim:
        device.add_location(float(lat), float(lon), int(float(tim)))
    else:
        raise ValidationError('Missing lat, lon or timestamp argument')
    return Response()


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

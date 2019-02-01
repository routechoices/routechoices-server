import time
import urllib
from itertools import chain

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound, \
    HttpResponseForbidden, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render

from rest_framework import generics, permissions, renderers
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    NotAuthenticated,
    PermissionDenied
)
from rest_framework.response import Response


from routechoices.core.models import Event, Location, Device


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


def home_view(request):
    return HttpResponse('hello world')


def club_view(request, slug):
    return HttpResponse('hello ' + slug)


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
        filename='{}.{}'.format(slug, event.map.mime_type[6:]),
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
    competitor_values = competitors.values_list('id', 'name', 'short_name')
    competitor_data = {}
    for c in competitor_values:
        competitor_data[c[0]] = {
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
            'id': location.competitor,
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

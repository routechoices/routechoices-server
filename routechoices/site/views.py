import re
import time
import urllib.parse
from itertools import chain

import requests
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseNotFound, \
    HttpResponseForbidden, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now

from rest_framework import generics, permissions, renderers, status
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    NotAuthenticated,
    PermissionDenied
)
from rest_framework.response import Response


from routechoices.core.models import Event, Location, Device, Club, Competitor
from routechoices.lib.gps_data_encoder import GeoLocationSeries



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



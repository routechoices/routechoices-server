from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.timezone import now

from routechoices.core.models import (
    Event,
    Club,
    PRIVACY_PUBLIC,
    PRIVACY_PRIVATE,
)


def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home_view')
    return render(
        request,
        'site/home.html',
    )


def tracker_view(request):
    return render(
        request,
        'site/tracker.html',
    )


def events_view(request):
    event_list = Event.objects.filter(privacy=PRIVACY_PUBLIC)
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
    event_list = Event.objects.filter(club=club, privacy=PRIVACY_PUBLIC)
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
        slug__iexact=slug,
        start_date__lt=now(),
    )
    if event.privacy == PRIVACY_PRIVATE:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied


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
    if event.privacy == PRIVACY_PRIVATE:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied

    return render(
        request,
        'site/event_export.html',
        {
            'event': event,
        }
    )

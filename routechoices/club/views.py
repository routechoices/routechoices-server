import gpxpy
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from django_hosts.resolvers import reverse


from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    Event,
    PRIVACY_PUBLIC,
    PRIVACY_PRIVATE,
)
from routechoices.lib.helpers import initial_of_name, short_random_key
from routechoices.site.forms import CompetitorForm, UploadGPXForm
from routechoices.club import feeds


def club_view(request, **kwargs):
    if kwargs.get('club_slug'):
        club_slug = kwargs.get('club_slug')
        if club_slug in ('api', 'admin', 'dashboard', 'oauth'):
            return redirect('/{}/'.format(club_slug))
        return redirect(
            reverse(
                'club_view',
                host='clubs',
                host_kwargs={
                    'club_slug': club_slug
                }
            )
        )
    club_slug = request.club_slug
    club = get_object_or_404(
        Club,
        slug__iexact=club_slug
    )
    if club.domain and not request.use_cname:
        return redirect(club.nice_url)
    event_list = Event.objects.filter(
        club=club,
        privacy=PRIVACY_PUBLIC
    ).select_related('club')
    live_events = event_list.filter(start_date__lte=now(), end_date__gte=now())
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    events = paginator.get_page(page)
    return render(
        request,
        'site/event_list.html',
        {
            'club': club,
            'events': events,
            'live_events': live_events,
        }
    )


def club_live_event_feed(request, **kwargs):
    if kwargs.get('club_slug'):
        club_slug = kwargs.get('club_slug')
        return redirect(
            reverse(
                'club_feed',
                host='clubs',
                host_kwargs={
                    'club_slug': club_slug
                }
            )
        )
    club_slug = request.club_slug
    club = get_object_or_404(
        Club,
        slug__iexact=club_slug
    )
    if club.domain and not request.use_cname:
        return redirect(f'{club.nice_url}feed')
    return feeds.club_live_event_feed(request, **kwargs)


def event_view(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    if not club_slug:
        club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related('club').prefetch_related('competitors'),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    # If event is private, page needs to send ajax with cookies to prove identity, cannot be done from custom domain
    if event.privacy == PRIVACY_PRIVATE:
        if request.use_cname:
            return redirect(
                reverse(
                    'event_view',
                    host='clubs',
                    kwargs={'slug': slug},
                    host_kwargs={
                        'club_slug': club_slug
                    }
                )
            )
    elif event.club.domain and not request.use_cname:
        return redirect(f'{event.club.nice_url}{event.slug}')
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied

    response = render(
        request,
        'club/event.html',
        {
            'event': event,
        }
    )
    if event.privacy == PRIVACY_PRIVATE:
        response['Cache-Control'] = 'private'
    return response


def event_js(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    if not club_slug:
        club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related('club').prefetch_related('competitors'),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    # If event is private, page needs to send ajax with cookies to prove identity, cannot be done from custom domain
    if event.privacy == PRIVACY_PRIVATE:
        if request.use_cname:
            return redirect(
                reverse(
                    'event_view',
                    host='clubs',
                    kwargs={'slug': slug},
                    host_kwargs={
                        'club_slug': club_slug
                    }
                )
            )
    elif event.club.domain and not request.use_cname:
        return redirect(f'{event.club.nice_url}{event.slug}')
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied

    response = render(
        request,
        'club/event.js',
        {
            'event': event,
        }
    )
    if event.privacy == PRIVACY_PRIVATE:
        response['Cache-Control'] = 'private'
    response['Content-Type'] = "application/javascript"
    return response



def event_export_view(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_export_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related('club').prefetch_related('competitors'),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        start_date__lt=now()
    )
    if event.club.domain and not request.use_cname:
        return redirect(f'{event.club.nice_url}{event.slug}/export')
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if not request.user.is_authenticated or \
                not event.club.admins.filter(id=request.user.id).exists():
            raise PermissionDenied

    response = render(
        request,
        'club/event_export.html',
        {
            'event': event,
        }
    )
    if event.privacy == PRIVACY_PRIVATE:
        response['Cache-Control'] = 'private'
    return response


def event_map_view(request, slug, index='0', **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_map_view',
                host='clubs',
                kwargs={'slug': slug, 'index': index},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related('club'),
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )
    if event.club.domain and not request.use_cname:
        return redirect(f'{event.club.nice_url}{event.slug}/map/{index}')
    return redirect(
        reverse(
            'event_map_download',
            host='api',
            kwargs={
                'event_id': event.aid,
                'map_index': index
            }
        )
    )


def event_kmz_view(request, slug, index='0', **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_kmz_view',
                host='clubs',
                kwargs={'slug': slug, 'index': index},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related('club'),
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )
    if event.club.domain and not request.use_cname:
        return redirect(f'{event.club.nice_url}{event.slug}/kmz/{index}')
    return redirect(
        reverse(
            'event_kmz_download',
            host='api',
            kwargs={
                'event_id': event.aid,
                'map_index': index
            }
        )
    )


def event_registration_view(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_registration_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = Event.objects.all().select_related('club').filter(
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        open_registration=True,
    ).first()
    if not event:
        raise Http404()
    club = event.club
    if club.domain and not request.use_cname:
        return redirect(f'{club.nice_url}{event.slug}/registration')
    if event.end_date and event.end_date < now():
        return render(
            request,
            'club/event_registration_closed.html',
            {
                'event': event,
            }
        )
    if request.method == 'POST':
        form = CompetitorForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            competitor = form.save()
            competitor.short_name = initial_of_name(competitor.name)
            competitor.save()
            messages.success(
                request,
                'Successfully registered for this event.'
            )
            target_url = f'{club.nice_url}{event.slug}/registration_complete'
            return redirect(target_url)
        else:
            devices = Device.objects.none()
            if request.user.is_authenticated:
                devices = request.user.devices.all()
            form.fields['device'].queryset = devices
    else:
        form = CompetitorForm(initial={'event': event})
        devices = Device.objects.none()
        if request.user.is_authenticated:
            devices = request.user.devices.all()
        form.fields['device'].queryset = devices
    form.fields['device'].label = "Device ID"
    return render(
        request,
        'club/event_registration.html',
        {
            'event': event,
            'form': form,
        }
    )


def event_registration_done_view(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_registration_done_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = Event.objects.all().select_related('club').filter(
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        open_registration=True,
    ).first()
    if not event:
        raise Http404()
    club = event.club
    if club.domain and not request.use_cname:
        return redirect(f'{club.nice_url}{event.slug}/registration_complete')
    return render(
        request,
        'club/event_registration_done.html',
        {
            'event': event,
        }
    )


def event_route_upload_view(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_route_upload_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = Event.objects.all().select_related('club').filter(
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        allow_route_upload=True,
    ).filter(
        start_date__lte=now()
    ).first()
    if not event:
        raise Http404()
    club = event.club
    if club.domain and not request.use_cname:
        return redirect(f'{club.nice_url}{event.slug}/route_upload')
    if request.method == 'POST':
        form = UploadGPXForm(request.POST, request.FILES, event=event)
        # check whether it's valid:
        if form.is_valid():
            error = None
            try:
                gpx_file = form.cleaned_data['gpx_file'].read().decode('utf8')
            except UnicodeDecodeError:
                error = "Couldn't decode file"
            if not error:
                try:
                    gpx = gpxpy.parse(gpx_file)
                except Exception:
                    error = "Couldn't parse file"
            if not error:
                device = Device.objects.create(aid=f'{short_random_key()}_GPX', is_gpx=True)
                points = {'timestamps': [], 'latitudes': [], 'longitudes': []}
                start_time = None
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            if point.time \
                                    and point.latitude \
                                    and point.longitude:
                                points['timestamps'].append(
                                    int(point.time.timestamp())
                                )
                                points['latitudes'].append(
                                    round(point.latitude, 5)
                                )
                                points['longitudes'].append(
                                    round(point.longitude, 5)
                                )
                                if not start_time:
                                    start_time = point.time
                device.locations = points
                device.save()
                competitor_name = form.cleaned_data['name']
                competitor = Competitor.objects.create(
                    event=event,
                    name=competitor_name,
                    short_name=initial_of_name(competitor_name),
                    device=device,
                )
                if start_time and event.start_date <= start_time \
                        and (
                            not event.end_date
                            or start_time <= event.end_date
                        ):
                    competitor.start_time = start_time
                competitor.save()
            
            target_url = f'{club.nice_url}{event.slug}/route_upload_complete'
            return redirect(target_url)
    else:
        form = UploadGPXForm()
    return render(
        request,
        'club/event_route_upload.html',
        {
            'event': event,
            'form': form,
        }
    )


def event_route_upload_done_view(request, slug, **kwargs):
    if kwargs.get('club_slug'):
        return redirect(
            reverse(
                'event_route_upload_done_view',
                host='clubs',
                kwargs={'slug': slug},
                host_kwargs={
                    'club_slug': kwargs.get('club_slug')
                }
            )
        )
    club_slug = request.club_slug
    event = Event.objects.all().select_related('club').filter(
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        allow_route_upload=True,
    ).filter(
        start_date__lte=now()
    ).first()
    if not event:
        raise Http404()
    club = event.club
    if club.domain and not request.use_cname:
        return redirect(f'{club.nice_url}{event.slug}/route_upload_complete')
    return render(
        request,
        'club/event_route_upload_done.html',
        {
            'event': event,
        }
    )


def acme_challenge(request, challenge):
    club_slug = request.club_slug
    club = get_object_or_404(
        Club,
        slug__iexact=club_slug
    )
    if not club.domain or not request.use_cname:
        return Http404()
    if challenge == club.acme_challenge.split('.')[0]:
        return HttpResponse(club.acme_challenge)
    else:
        raise Http404()

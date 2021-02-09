import gpxpy
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now


from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    Event,
    PRIVACY_PUBLIC,
    PRIVACY_PRIVATE,
)
from routechoices.lib.helper import initial_of_name
from routechoices.site.forms import CompetitorForm, ContactForm, UploadGPXForm


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
    event_list = Event.objects.filter(
        privacy=PRIVACY_PUBLIC
    ).select_related('map', 'club').prefetch_related('map_assignations')
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    events = paginator.get_page(page)
    return render(
        request,
        'site/event_list.html',
        {'events': events}
    )


def club_view(request, slug):
    if slug in ('api', 'admin', 'dashboard',):
        return redirect('/{}/'.format(slug))
    club = get_object_or_404(
        Club,
        slug__iexact=slug
    )
    event_list = Event.objects.filter(
        club=club,
        privacy=PRIVACY_PUBLIC
    ).select_related('map', 'club')
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
        Event.objects.all().prefetch_related('competitors'),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
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
        Event.objects.all().prefetch_related('competitors'),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        start_date__lt=now()
    )
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
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


def event_map_view(request, club_slug, slug):
    event = get_object_or_404(
        Event,
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )
    return redirect('api:event_map_download', aid=event.aid)


def event_extra_map_view(request, club_slug, slug, index):
    event = get_object_or_404(
        Event,
        club__slug__iexact=club_slug,
        slug__iexact=slug
    )
    return redirect('api:event_extra_map_download', aid=event.aid, index=index)


def event_registration_view(request, club_slug, slug):
    event = Event.objects.all().filter(
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        open_registration=True,
    ).exclude(
        end_date__isnull=False,
        end_date__lt=now()
    ).first()
    if not event:
        raise Http404()
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
            return redirect(
                'site:event_registration_view',
                **{
                    'club_slug': event.club.slug,
                    'slug': event.slug,
                }
            )
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
    form.fields['device'].label = "Live Streaming Device ID"
    return render(
        request,
        'site/event_registration.html',
        {
            'event': event,
            'form': form,
        }
    )


def event_route_upload_view(request, club_slug, slug):
    event = Event.objects.all().filter(
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        allow_route_upload=True,
    ).filter(
        start_date__lte=now()
    ).first()
    if not event:
        raise Http404()
    if request.method == 'POST':
        form = UploadGPXForm(request.POST, request.FILES)
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
                device = Device.objects.create()
                device.aid += '_GPX'
                device.is_gpx = True
                device.save()
                points = {'timestamps': [], 'latitudes': [], 'longitudes': []}
                start_time = None
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            if point.time \
                                    and point.latitude \
                                    and point.longitude:
                                points['timestamps'].append(
                                    point.time.timestamp()
                                )
                                points['latitudes'].append(point.latitude)
                                points['longitudes'].append(point.longitude)
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
            messages.success(
                request,
                'Successfully uploaded route for this event.'
            )
            return redirect(
                'site:event_route_upload_view',
                **{
                    'club_slug': event.club.slug,
                    'slug': event.slug,
                }
            )
    else:
        form = UploadGPXForm()
    return render(
        request,
        'site/event_route_upload.html',
        {
            'event': event,
            'form': form,
        }
    )


def contact(request):
    if request.method == 'GET':
        form = ContactForm()
    else:
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = (
                'Routechoices.com contact form - '
                + form.cleaned_data['subject']
            )
            from_email = form.cleaned_data['from_email']
            message = form.cleaned_data['message']
            send_mail(
                subject,
                message,
                from_email,
                [settings.DEFAULT_FROM_EMAIL]
            )
            return redirect('site:contact_email_sent_view')
    return render(request, "site/contact.html", {'form': form})

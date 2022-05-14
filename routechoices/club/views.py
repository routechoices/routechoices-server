import gpxpy
from defusedxml import minidom
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import BadRequest, PermissionDenied
from django.core.paginator import Paginator
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.decorators.clickjacking import xframe_options_exempt
from django_hosts.resolvers import reverse

from routechoices.api.views import serve_from_s3
from routechoices.club import feeds
from routechoices.core.models import (
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    Club,
    Competitor,
    Device,
    Event,
)
from routechoices.lib.helpers import initial_of_name, short_random_key
from routechoices.site.forms import CompetitorForm, UploadGPXForm


def handle_legacy_request(view_name, club_slug=None, **kwargs):
    if club_slug:
        if not Club.objects.filter(slug__iexact=club_slug).exists():
            raise Http404()
        reverse_kwargs = kwargs
        return redirect(
            reverse(
                view_name,
                host="clubs",
                host_kwargs={"club_slug": club_slug},
                kwargs=reverse_kwargs,
            )
        )
    return False


def club_view(request, **kwargs):
    if kwargs.get("club_slug"):
        club_slug = kwargs.get("club_slug")
        if club_slug in ("api", "admin", "dashboard", "oauth"):
            return redirect(f"/{club_slug}/")
    bypass_resp = handle_legacy_request("club_view", kwargs.get("club_slug"))
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and not request.use_cname:
        return redirect(club.nice_url)
    event_list = Event.objects.filter(club=club, privacy=PRIVACY_PUBLIC).select_related(
        "club"
    )
    live_events = event_list.filter(start_date__lte=now(), end_date__gte=now())
    years = list(
        event_list.annotate(year=ExtractYear("start_date"))
        .values_list("year", flat=True)
        .order_by("-year")
        .distinct()
    )
    months = None
    selected_year = request.GET.get("year")
    selected_month = request.GET.get("month")
    if selected_year:
        try:
            selected_year = int(selected_year)
        except Exception:
            raise BadRequest("Invalid year")
        if selected_year not in years:
            raise Http404()
    if selected_year:
        event_list = event_list.filter(start_date__year=selected_year)
        months = list(
            event_list.annotate(month=ExtractMonth("start_date"))
            .values_list("month", flat=True)
            .order_by("-month")
            .distinct()
        )
        if selected_month:
            try:
                selected_month = int(selected_month)
            except Exception:
                raise BadRequest("Invalid month")
            if selected_month not in months:
                raise Http404()
        if selected_month:
            event_list = event_list.filter(start_date__month=selected_month)
    paginator = Paginator(event_list, 25)
    page = request.GET.get("page")
    events = paginator.get_page(page)
    return render(
        request,
        "site/event_list.html",
        {
            "club": club,
            "events": events,
            "live_events": live_events,
            "years": years,
            "months": months,
            "year": selected_year,
            "month": selected_month,
            "month_names": [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
        },
    )


def club_logo(request, **kwargs):
    bypass_resp = handle_legacy_request("club_logo", kwargs.get("club_slug"))
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    if request.use_cname:
        return redirect(
            reverse("club_logo", host="clubs", host_kwargs={"club_slug": club_slug})
        )
    club = get_object_or_404(Club, slug__iexact=club_slug, logo__isnull=False)
    file_path = club.logo.name
    return serve_from_s3(
        "routechoices-maps",
        request,
        "/internal/" + file_path,
        filename=f"{club.name}.png",
        mime="image/png",
    )


def club_live_event_feed(request, **kwargs):
    bypass_resp = handle_legacy_request("club_feed", kwargs.get("club_slug"))
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and not request.use_cname:
        return redirect(f"{club.nice_url}feed")
    return feeds.club_live_event_feed(request, **kwargs)


@xframe_options_exempt
def event_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    if not club_slug:
        club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related("club").prefetch_related("competitors"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    # If event is private, page needs to send ajax with cookies to prove identity, cannot be done from custom domain
    if event.privacy == PRIVACY_PRIVATE:
        if request.use_cname:
            return redirect(
                reverse(
                    "event_view",
                    host="clubs",
                    kwargs={"slug": slug},
                    host_kwargs={"club_slug": club_slug},
                )
            )
    elif event.club.domain and not request.use_cname:
        return redirect(f"{event.club.nice_url}{event.slug}")
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied
    resp_args = {
        "event": event,
    }
    if event.allow_live_chat:
        resp_args["chat_server"] = getattr(settings, "CHAT_SERVER", None)
    response = render(request, "club/event.html", resp_args)
    if event.privacy == PRIVACY_PRIVATE:
        response["Cache-Control"] = "private"
    return response


def event_export_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_export_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related("club").prefetch_related("competitors"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        start_date__lt=now(),
    )
    # If event is private, page needs to be sent with cookies to prove identity, cannot be done from custom domain
    if event.privacy == PRIVACY_PRIVATE:
        if request.use_cname:
            return redirect(
                reverse(
                    "event_export_view",
                    host="clubs",
                    kwargs={"slug": slug},
                    host_kwargs={"club_slug": club_slug},
                )
            )
    elif event.club.domain and not request.use_cname:
        return redirect(f"{event.club.nice_url}{event.slug}/export")
    if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
        if (
            not request.user.is_authenticated
            or not event.club.admins.filter(id=request.user.id).exists()
        ):
            raise PermissionDenied

    response = render(
        request,
        "club/event_export.html",
        {
            "event": event,
        },
    )
    if event.privacy == PRIVACY_PRIVATE:
        response["Cache-Control"] = "private"
    return response


def event_map_view(request, slug, index="0", **kwargs):
    bypass_resp = handle_legacy_request(
        "event_map_view", kwargs.get("club_slug"), slug=slug, index=index
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related("club"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    if event.club.domain and not request.use_cname:
        return redirect(f"{event.club.nice_url}{event.slug}/map/{index}")
    return redirect(
        reverse(
            "event_map_download",
            host="api",
            kwargs={"event_id": event.aid, "map_index": index},
        )
    )


def event_kmz_view(request, slug, index="0", **kwargs):
    bypass_resp = handle_legacy_request(
        "event_kmz_view", kwargs.get("club_slug"), slug=slug, index=index
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related("club"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    if event.club.domain and not request.use_cname:
        return redirect(f"{event.club.nice_url}{event.slug}/kmz/{index}")
    return redirect(
        reverse(
            "event_kmz_download",
            host="api",
            kwargs={"event_id": event.aid, "map_index": index},
        )
    )


def event_registration_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_registration_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related("club"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        open_registration=True,
    )
    if event.end_date < now():
        return render(
            request,
            "club/event_registration_closed.html",
            {
                "event": event,
            },
        )
    if request.method == "POST":
        form = CompetitorForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            competitor = form.save()
            competitor.short_name = initial_of_name(competitor.name)
            competitor.save()
            messages.success(request, "Successfully registered for this event.")
            target_url = f"{event.club.nice_url}{event.slug}/registration"
            return redirect(target_url)
        else:
            devices = Device.objects.none()
            form.fields["device"].queryset = devices
    else:
        if event.club.domain and not request.use_cname:
            return redirect(f"{event.club.nice_url}{event.slug}/registration")
        form = CompetitorForm(initial={"event": event})
        devices = Device.objects.none()
        form.fields["device"].queryset = devices
    form.fields["device"].label = "Device ID"
    return render(
        request,
        "club/event_registration.html",
        {
            "event": event,
            "form": form,
        },
    )


def event_route_upload_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_route_upload_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.all().select_related("club"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
        allow_route_upload=True,
        start_date__lte=now(),
    )
    if request.method == "POST":
        form = UploadGPXForm(request.POST, request.FILES, event=event)
        # check whether it's valid:
        if form.is_valid():
            error = None
            try:
                gpx_file = form.cleaned_data["gpx_file"].read()
                data = minidom.parseString(gpx_file)
                gpx_file = data.toxml(encoding="utf-8")
            except Exception:
                error = "Couldn't decode file"
            if not error:
                try:
                    gpx = gpxpy.parse(gpx_file)
                except Exception:
                    error = "Couldn't parse file"
            if not error:
                device = Device.objects.create(
                    aid=f"{short_random_key()}_GPX", is_gpx=True
                )
                points = []
                start_time = None
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            if point.time and point.latitude and point.longitude:
                                points.append(
                                    (
                                        int(point.time.timestamp()),
                                        round(point.latitude, 5),
                                        round(point.longitude, 5),
                                    )
                                )
                                if not start_time:
                                    start_time = point.time
                device.add_locations(points, push_forward=False)
                competitor_name = form.cleaned_data["name"]
                competitor = Competitor.objects.create(
                    event=event,
                    name=competitor_name,
                    short_name=initial_of_name(competitor_name),
                    device=device,
                )
                if start_time and event.start_date <= start_time <= event.end_date:
                    competitor.start_time = start_time
                competitor.save()
                target_url = f"{event.club.nice_url}{event.slug}/route-upload"
            if not error:
                messages.success(request, "The upload of the GPX file was successful")
                return redirect(target_url)
            else:
                messages.error(request, error)
    else:
        if event.club.domain and not request.use_cname:
            return redirect(f"{event.club.nice_url}{event.slug}/route-upload")
        form = UploadGPXForm()
    return render(
        request,
        "club/event_route_upload.html",
        {
            "event": event,
            "form": form,
        },
    )


def acme_challenge(request, challenge):
    if not request.use_cname:
        return Http404()
    club_slug = request.club_slug
    club = get_object_or_404(
        Club.objects.all().exclude(domain=""), slug__iexact=club_slug
    )
    if challenge == club.acme_challenge.split(".")[0]:
        return HttpResponse(club.acme_challenge)
    else:
        raise Http404()

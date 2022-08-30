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
from routechoices.core.models import PRIVACY_PRIVATE, PRIVACY_PUBLIC, Club, Event
from routechoices.site.forms import CompetitorUploadGPXForm, RegisterForm


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
    event_list = event_list.filter(end_date__lt=now())
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
        settings.AWS_S3_BUCKET,
        request,
        file_path,
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
    event = (
        Event.objects.all()
        .select_related("club")
        .prefetch_related("competitors")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        return render(request, "club/404_event.html", {"club": club}, status=404)
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
    event = (
        Event.objects.all()
        .select_related("club")
        .prefetch_related("competitors")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        return render(request, "club/404_event.html", {"club": club}, status=404)
    if event.start_date > now():
        return render(
            request,
            "club/event_export_closed.html",
            {
                "event": event,
            },
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
    event = (
        Event.objects.all()
        .select_related("club")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        return render(request, "club/404_event.html", {"club": club}, status=404)
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
    event = (
        Event.objects.all()
        .select_related("club")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        return render(request, "club/404_event.html", {"club": club}, status=404)
    if event.club.domain and not request.use_cname:
        return redirect(f"{event.club.nice_url}{event.slug}/kmz/{index}")
    return redirect(
        reverse(
            "event_kmz_download",
            host="api",
            kwargs={"event_id": event.aid, "map_index": index},
        )
    )


def event_contribute_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_registration_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = (
        Event.objects.all()
        .select_related("club")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        return render(request, "club/404_event.html", {"club": club}, status=404)

    if request.GET.get("competitor-added", None):
        messages.success(request, "Competitor Added!")
        return redirect(
            reverse(
                "event_contribute_view",
                host="clubs",
                host_kwargs={"club_slug": club_slug},
                kwargs={"slug": slug},
            )
        )
    if request.GET.get("route-uploaded", None):
        messages.success(request, "Data uploaded!")
        return redirect(
            reverse(
                "event_contribute_view",
                host="clubs",
                host_kwargs={"club_slug": club_slug},
                kwargs={"slug": slug},
            )
        )

    can_upload = event.allow_route_upload and (event.start_date <= now())
    can_register = event.open_registration and (event.end_date >= now() or can_upload)

    register_form = None
    if can_register:
        register_form = RegisterForm(event=event)

    upload_form = None
    if can_upload:
        upload_form = CompetitorUploadGPXForm(event=event)

    return render(
        request,
        "club/event_contribute.html",
        {
            "event": event,
            "register_form": register_form,
            "upload_form": upload_form,
            "event_ended": event.end_date < now(),
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

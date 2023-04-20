from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.sitemaps.views import (
    SitemapIndexItem,
    _get_latest_lastmod,
    x_robots_tag,
)
from django.contrib.sites.shortcuts import get_current_site
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.utils.http import http_date
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.views.decorators.clickjacking import xframe_options_exempt
from django_hosts.resolvers import reverse

from routechoices.club import feeds
from routechoices.core.models import PRIVACY_PRIVATE, Club, Event, EventSet
from routechoices.lib.helpers import set_content_disposition
from routechoices.lib.s3 import get_s3_client
from routechoices.lib.streaming_response import StreamingHttpRangeResponse
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

    return render(
        request, "site/event_list.html", Event.extract_event_lists(request, club)
    )


def club_logo(request, **kwargs):
    bypass_resp = handle_legacy_request("club_logo", kwargs.get("club_slug"))
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    club = get_object_or_404(
        Club.objects.exclude(logo=""), slug__iexact=club_slug, logo__isnull=False
    )
    if club.domain and not request.use_cname:
        return redirect(club.logo_url)
    logo_key = f"club_logo:{club.aid}:{club.modification_date.timestamp()}"
    headers = {}
    if cache.has_key(logo_key):
        logo = cache.get(logo_key)
        headers["X-Cache-Hit"] = 1
    else:
        file_path = club.logo.name
        buf = BytesIO()
        s3_client = get_s3_client()
        s3_client.download_fileobj(settings.AWS_S3_BUCKET, file_path, buf)
        logo = buf.getvalue()
        cache.set(logo_key, logo, 31 * 24 * 3600)

    resp = StreamingHttpRangeResponse(
        request,
        logo,
        content_type="image/png",
        headers=headers,
    )
    resp["Content-Disposition"] = set_content_disposition(f"{club.name}.png", dl=False)
    return resp


def club_favicon(request, icon_name, **kwargs):
    bypass_resp = handle_legacy_request(
        "club_favicon", kwargs.get("club_slug"), icon_name=icon_name
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and not request.use_cname:
        return redirect(f"{club.nice_url}{icon_name}")
    icon_info = {
        "favicon.ico": {"size": 32, "format": "ICO", "mime": "image/x-icon"},
        "apple-touch-icon.png": {"size": 180, "format": "PNG", "mime": "image/png"},
        "icon-192.png": {"size": 192, "format": "PNG", "mime": "image/png"},
        "icon-512.png": {"size": 512, "format": "PNG", "mime": "image/png"},
    }.get(icon_name)
    logo = club.logo
    if not logo:
        with open(f"{settings.BASE_DIR}/static_assets/{icon_name}", "rb") as fp:
            data = fp.read()
    else:
        data = club.logo_scaled(icon_info["size"], icon_info["format"])
    return StreamingHttpRangeResponse(request, data, content_type=icon_info["mime"])


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
@cache_page(5 if not settings.DEBUG else 0)
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
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        if club.domain and not request.use_cname:
            return redirect(f"{club.nice_url}{slug}")
        return render(request, "club/404_event.html", {"club": club}, status=404)
    # If event is private, page needs to send ajax with cookies to prove identity,
    # cannot be done from custom domain
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


@xframe_options_exempt
@cache_page(5 if not settings.DEBUG else 0)
def event_set_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_set_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    if not club_slug:
        club_slug = request.club_slug
    event_set = (
        EventSet.objects.all()
        .select_related("club")
        .prefetch_related("events")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event_set:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        if club.domain and not request.use_cname:
            return redirect(f"{club.nice_url}events/{slug}")
        return render(request, "club/404_event_set.html", {"club": club}, status=404)
    elif event_set.club.domain and not request.use_cname:
        return redirect(f"{event_set.club.nice_url}events/{slug}")
    return render(
        request, "site/event_list.html", event_set.extract_event_lists(request)
    )


def event_export_view(request, slug, **kwargs):
    bypass_resp = handle_legacy_request(
        "event_export_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = (
        Event.objects.all()
        .select_related("club", "event_set")
        .prefetch_related("competitors")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        if club.domain and not request.use_cname:
            return redirect(f"{club.nice_url}{slug}/export")
        return render(request, "club/404_event.html", {"club": club}, status=404)
    # If event is private, page needs to be sent with cookies to prove identity,
    # cannot be done from custom domain
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


def event_map_view(request, slug, index="1", **kwargs):
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
        if club.domain and not request.use_cname:
            return redirect(f"{club.nice_url}{slug}map/{index if index != '1' else ''}")
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


def event_kmz_view(request, slug, index="1", **kwargs):
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
        if club.domain and not request.use_cname:
            return redirect(f"{club.nice_url}{slug}kmz/{index if index != '1' else ''}")
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
        "event_contribute_view", kwargs.get("club_slug"), slug=slug
    )
    if bypass_resp:
        return bypass_resp
    club_slug = request.club_slug
    event = (
        Event.objects.all()
        .select_related("club", "event_set")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        if club.domain and not request.use_cname:
            return redirect(f"{club.nice_url}{slug}/contribute")
        return render(request, "club/404_event.html", {"club": club}, status=404)

    if request.GET.get("competitor-added", None):
        messages.success(request, "Competitor Added!")
    if request.GET.get("route-uploaded", None):
        messages.success(request, "Data uploaded!")

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


@x_robots_tag
def acme_challenge(request, challenge):
    if not request.use_cname:
        return Http404()
    club_slug = request.club_slug
    club = get_object_or_404(
        Club.objects.all().exclude(domain=""), slug__iexact=club_slug
    )
    if challenge == club.acme_challenge.partition(".")[0]:
        return HttpResponse(club.acme_challenge)
    else:
        raise Http404()


def robots_txt(request):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug=club_slug)
    if club.domain and not request.use_cname:
        return redirect(f"{club.nice_url}robots.txt")
    return HttpResponse(
        f"Sitemap: {club.nice_url}sitemap.xml\n", content_type="text/plain"
    )


def manifest(request):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug=club_slug)
    if club.domain and not request.use_cname:
        return redirect(f"{club.nice_url}manifest.json")
    return HttpResponse(
        (
            '{"icons": ['
            f'{{"src":"/icon-192.png{club.logo_last_mod}",'
            '"type":"image/png","sizes":"192x192"},'
            f'{{"src":"/icon-512.png{club.logo_last_mod}",'
            '"type":"image/png","sizes":"512x512"}'
            "]}"
        ),
        content_type="application/json",
    )


@x_robots_tag
def sitemap_index(
    request,
    sitemaps,
    template_name="sitemap_index.xml",
    content_type="application/xml",
    sitemap_url_name="club_sitemap_sections",
):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and not request.use_cname:
        return redirect(f"{club.nice_url}sitemap.xml")
    sites = []  # all sections' sitemap URLs
    all_indexes_lastmod = True
    latest_lastmod = None
    for section, site in sitemaps.items():
        site.club_slug = club_slug
        # For each section label, add links of all pages of its sitemap
        # (usually generated by the `sitemap` view).
        if callable(site):
            site = site()
        sitemap_url = f"{club.nice_url}sitemap-{section}.xml"
        absolute_url = sitemap_url
        site_lastmod = site.get_latest_lastmod()
        if all_indexes_lastmod:
            if site_lastmod is not None:
                latest_lastmod = _get_latest_lastmod(latest_lastmod, site_lastmod)
            else:
                all_indexes_lastmod = False
        sites.append(SitemapIndexItem(absolute_url, site_lastmod))
        # Add links to all pages of the sitemap.
        for page in range(2, site.paginator.num_pages + 1):
            sites.append(SitemapIndexItem(f"{absolute_url}?p={page}", site_lastmod))
    # If lastmod is defined for all sites, set header so as
    # ConditionalGetMiddleware is able to send 304 NOT MODIFIED
    if all_indexes_lastmod and latest_lastmod:
        headers = {"Last-Modified": http_date(latest_lastmod.timestamp())}
    else:
        headers = None
    return TemplateResponse(
        request,
        template_name,
        {"sitemaps": sites},
        content_type=content_type,
        headers=headers,
    )


@x_robots_tag
def sitemap(
    request,
    sitemaps,
    section=None,
    template_name="sitemap.xml",
    content_type="application/xml",
):
    club_slug = request.club_slug
    req_protocol = request.scheme
    req_site = get_current_site(request)

    if section is not None:
        if section not in sitemaps:
            raise Http404(f"No sitemap available for section: {section}")
        maps = [sitemaps[section]]
    else:
        maps = sitemaps.values()
    page = request.GET.get("p", 1)
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and not request.use_cname:
        return redirect(
            f"{club.nice_url}sitemap{f'-{section}' if section else ''}.xml?p={page}"
        )
    lastmod = None
    all_sites_lastmod = True
    urls = []
    for site in maps:
        site.club_slug = club_slug
        try:
            if callable(site):
                site = site()
            urls.extend(site.get_urls(page=page, site=req_site, protocol=req_protocol))
            if all_sites_lastmod:
                site_lastmod = getattr(site, "latest_lastmod", None)
                if site_lastmod is not None:
                    lastmod = _get_latest_lastmod(lastmod, site_lastmod)
                else:
                    all_sites_lastmod = False
        except EmptyPage:
            raise Http404(f"Page {page} empty")
        except PageNotAnInteger:
            raise Http404(f"No page '{page}'")
    # If lastmod is defined for all sites, set header so as
    # ConditionalGetMiddleware is able to send 304 NOT MODIFIED
    if all_sites_lastmod:
        headers = {"Last-Modified": http_date(lastmod.timestamp())} if lastmod else None
    else:
        headers = None
    return TemplateResponse(
        request,
        template_name,
        {"urlset": urls},
        content_type=content_type,
        headers=headers,
    )

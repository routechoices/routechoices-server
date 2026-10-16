import time

from django.conf import settings
from django.contrib.sitemaps.views import _get_latest_lastmod, x_robots_tag
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.utils.http import http_date
from django.views.decorators.cache import cache_page
from django_hosts.resolvers import reverse
from rest_framework import status

from routechoices.club import feeds
from routechoices.core.models import PRIVACY_PRIVATE, Club, Event, EventSet
from routechoices.lib import cache
from routechoices.lib.helpers import (
    get_best_image_mime,
    get_current_site,
    get_image_mime_from_request,
    gpsseuranta_encode_data,
    safe64encodedsha,
)
from routechoices.lib.s3 import serve_image_from_s3
from routechoices.lib.ssl_certificates import is_custom_ssl_cert_active
from routechoices.lib.streaming_response import StreamingHttpRangeResponse


def club_view(request):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug__iexact=club_slug)

    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(club.nice_url)

    event_list = Event.extract_event_lists(request, club)

    return render(request, "site/event_list.html", event_list)


def club_favicon(request, icon_name):
    icon_infos = {
        "favicon.ico": {"size": 32, "format": "ICO", "mime": "image/x-icon"},
        "apple-touch-icon.png": {"size": 180, "format": "PNG", "mime": "image/png"},
        "icon-192.png": {"size": 192, "format": "PNG", "mime": "image/png"},
        "icon-512.png": {"size": 512, "format": "PNG", "mime": "image/png"},
    }
    if icon_name not in icon_infos:
        raise Http404()
    icon_info = icon_infos.get(icon_name)

    club_slug = request.club_slug
    club = get_object_or_404(
        Club.objects.only("logo", "domain", "slug"), slug__iexact=club_slug
    )
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(f"{club.nice_url}{icon_name}")
    if not club.logo:
        with open(f"{settings.BASE_DIR}/static_assets/{icon_name}", "rb") as fp:
            data = fp.read()
    else:
        data = club.logo_scaled(icon_info["size"], icon_info["format"])
    return StreamingHttpRangeResponse(request, data, content_type=icon_info["mime"])


def club_logo(request, extension=None):
    club_slug = request.club_slug
    club = (
        Club.objects.filter(
            slug__iexact=club_slug,
        )
        .only("logo", "name", "domain", "slug")
        .first()
    )
    if not club.logo:
        with open(
            f"{settings.BASE_DIR}/static_assets/img/club-default.png", "rb"
        ) as fp:
            data = fp.read()
            return StreamingHttpRangeResponse(request, data, content_type="image/png")

    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(club.logo_url)

    mime = get_image_mime_from_request(extension)

    return serve_image_from_s3(
        request,
        club.logo,
        f"{club.name} Logo",
        mime=mime,
        default_mime="image/webp",
    )


def club_banner(request, extension=None):
    club_slug = request.club_slug
    club = get_object_or_404(
        Club.objects.exclude(banner="").only("banner", "name", "domain", "slug"),
        slug__iexact=club_slug,
        banner__isnull=False,
    )
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(club.banner_url)

    mime = get_image_mime_from_request(extension)

    return serve_image_from_s3(
        request,
        club.banner,
        f"{club.name} Banner",
        mime=mime,
        default_mime="image/jpeg",
        img_mode="RGB",
    )


def club_thumbnail(request, extension=None):
    club_slug = request.club_slug
    club = get_object_or_404(
        Club.objects.only(
            "slug", "domain", "modification_date", "aid", "banner", "logo"
        ),
        slug__iexact=club_slug,
    )
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(f"{club.nice_url}thumbnail")

    mime = get_image_mime_from_request(
        extension, get_best_image_mime(request, "image/jpeg")
    )

    data_out = club.thumbnail(mime)

    resp = StreamingHttpRangeResponse(request, data_out)
    resp["ETag"] = f'w/"{safe64encodedsha(data_out)}"'
    return resp


def club_live_event_feed(request, *args):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(f"{club.nice_url}feed")
    resp = feeds.club_live_event_feed(request, *args)
    resp["Content-Type"] = "application/rss+xml"
    return resp


@cache_page(5 if not settings.DEBUG else 0)
def event_view(request, slug):
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
            if (
                club.domain
                and is_custom_ssl_cert_active(club.domain)
                and not request.use_cname
            ):
                return redirect(f"{club.nice_url}{slug}")
            return render(
                request,
                "club/404_event.html",
                {"club": club},
                status=status.HTTP_404_NOT_FOUND,
            )
        if (
            event_set.club.domain
            and is_custom_ssl_cert_active(club.domain)
            and not request.use_cname
        ):
            return redirect(f"{event_set.club.nice_url}{slug}")
        return render(
            request, "site/event_list.html", event_set.extract_event_lists(request)
        )

    # If event is private, page needs to send ajax with cookies to prove identity,
    # cannot be done from custom domain.
    if event.privacy == PRIVACY_PRIVATE:
        return redirect(
            reverse(
                "dashboard_club:event:private_view",
                host="dashboard",
                kwargs={"club_slug": club_slug, "event_id": event.aid},
            )
        )
    elif (
        event.club.domain
        and is_custom_ssl_cert_active(event.club.domain)
        and not request.use_cname
    ):
        return redirect(f"{event.club.nice_url}{event.slug}")

    event.check_user_permission(request.user)

    resp_args = {
        "event": event,
    }
    response = render(request, "club/event.html", resp_args)
    if event.privacy == PRIVACY_PRIVATE:
        response["Cache-Control"] = "private"

    # Allow embedding in external site iframe
    response.xframe_options_exempt = True

    return response


def event_startlist_view(request, slug):
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
        if (
            club.domain
            and is_custom_ssl_cert_active(club.domain)
            and not request.use_cname
        ):
            return redirect(f"{club.nice_url}{slug}/export")
        return render(
            request,
            "club/404_event.html",
            {"club": club},
            status=status.HTTP_404_NOT_FOUND,
        )
    if event.privacy == PRIVACY_PRIVATE:
        if request.use_cname:
            return redirect(
                reverse(
                    "event_startlist_view",
                    host="clubs",
                    kwargs={"slug": slug},
                    host_kwargs={"club_slug": club_slug},
                )
            )
    elif (
        event.club.domain
        and is_custom_ssl_cert_active(event.club.domain)
        and not request.use_cname
    ):
        return redirect(f"{event.club.nice_url}{event.slug}/startlist")

    event.check_user_permission(request.user)

    response = render(
        request,
        "club/event_startlist.html",
        {
            "event": event,
        },
    )
    if event.privacy == PRIVACY_PRIVATE:
        response["Cache-Control"] = "private"
    return response


def event_export_view(request, slug):
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
        if (
            club.domain
            and is_custom_ssl_cert_active(club.domain)
            and not request.use_cname
        ):
            return redirect(f"{club.nice_url}{slug}/export")
        return render(
            request,
            "club/404_event.html",
            {"club": club},
            status=status.HTTP_404_NOT_FOUND,
        )
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
    elif (
        event.club.domain
        and is_custom_ssl_cert_active(club.domain)
        and not request.use_cname
    ):
        return redirect(f"{event.club.nice_url}{event.slug}/export")

    event.check_user_permission(request.user)

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


def event_zip_view(request, slug):
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
        if (
            club.domain
            and is_custom_ssl_cert_active(club.domain)
            and not request.use_cname
        ):
            return redirect(f"{club.nice_url}{slug}/zip")
        return render(
            request,
            "club/404_event.html",
            {"club": club},
            status=status.HTTP_404_NOT_FOUND,
        )
    if (
        event.club.domain
        and is_custom_ssl_cert_active(club.domain)
        and not request.use_cname
    ):
        return redirect(f"{event.club.nice_url}{event.slug}/zip")

    event.check_user_permission(request.user)

    return redirect(
        reverse(
            "event_zip",
            host="api",
            kwargs={"event_id": event.aid},
        )
    )


def event_map_view(request, slug, index="1", extension=None):
    club_slug = request.club_slug

    event = (
        Event.objects.all()
        .select_related("club", "map")
        .filter(club__slug__iexact=club_slug, slug__iexact=slug, map_id__isnull=False)
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        if (
            club.domain
            and is_custom_ssl_cert_active(club.domain)
            and not request.use_cname
        ):
            return redirect(
                f"{club.nice_url}{slug}/map{('-' + index) if index != '1' else ''}"
            )
        return render(
            request,
            "club/404_event.html",
            {"club": club},
            status=status.HTTP_404_NOT_FOUND,
        )
    if event.club.domain and not request.use_cname:
        return redirect(
            f"{event.club.nice_url}{event.slug}/map{('-' + index) if index != '1' else ''}"
        )

    if extension is None and request.META.get("HTTP_USER_AGENT", "").startswith(
        "Java/"
    ):
        extension = "jpeg"

    mime = get_image_mime_from_request(extension, event.map.mime_type)
    ext = mime.split("/")[1]
    if ext not in ("jpeg", "png", "avif", "webp"):
        ext = "webp"

    return redirect(
        reverse(
            "event_map_download_with_format",
            host="api",
            kwargs={"event_id": event.aid, "index": index, "extension": ext},
        )
    )


def event_kmz_view(request, slug, index="1"):
    club_slug = request.club_slug
    event = (
        Event.objects.all()
        .select_related("club")
        .filter(
            club__slug__iexact=club_slug,
            slug__iexact=slug,
            map_id__isnull=False,
        )
        .first()
    )
    if not event:
        club = get_object_or_404(Club, slug__iexact=club_slug)
        if (
            club.domain
            and is_custom_ssl_cert_active(club.domain)
            and not request.use_cname
        ):
            return redirect(
                f"{club.nice_url}{slug}/kmz{('-' + index) if index != '1' else ''}"
            )
        return render(
            request,
            "club/404_event.html",
            {"club": club},
            status=status.HTTP_404_NOT_FOUND,
        )
    if (
        event.club.domain
        and is_custom_ssl_cert_active(event.club.domain)
        and not request.use_cname
    ):
        return redirect(
            f"{event.club.nice_url}{event.slug}/kmz{('-' + index) if index != '1' else ''}"
        )
    return redirect(
        reverse(
            "event_map_download_with_format",
            host="api",
            kwargs={"event_id": event.aid, "index": index, "extension": "kmz"},
        )
    )


def event_map_thumbnail(request, slug, extension=None):
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.select_related("club", "map"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )

    event.check_user_permission(request.user)

    display_logo = request.GET.get("no-logo", False) is False

    mime = get_image_mime_from_request(
        extension, get_best_image_mime(request, "image/jpeg")
    )

    data_out = event.thumbnail(display_logo, mime)
    headers = {"ETag": f'W/"{safe64encodedsha(data_out)}"'}
    if event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"
    return StreamingHttpRangeResponse(request, data_out, headers=headers)


@x_robots_tag
def acme_challenge(request, challenge):
    if not request.use_cname:
        raise Http404()
    club_slug = request.club_slug
    club = get_object_or_404(Club.objects.exclude(domain=""), slug__iexact=club_slug)
    if challenge == club.acme_challenge.partition(".")[0]:
        return HttpResponse(club.acme_challenge)
    raise Http404()


def robots_txt(request):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug=club_slug)
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(f"{club.nice_url}robots.txt")
    return HttpResponse(
        f"Sitemap: {club.nice_url}sitemap.xml\n", content_type="text/plain"
    )


def manifest(request):
    club_slug = request.club_slug
    club = get_object_or_404(Club, slug=club_slug)
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
        return redirect(f"{club.nice_url}manifest.json")
    return HttpResponse(
        (
            '{"icons": ['
            f'{{"src":"/icon-192.png?v={club.logo_hash}",'
            '"type":"image/png","sizes":"192x192"},'
            f'{{"src":"/icon-512.png?v={club.logo_hash}",'
            '"type":"image/png","sizes":"512x512"}'
            "]}"
        ),
        content_type="application/json",
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
    req_site = get_current_site()

    if section is not None:
        if section not in sitemaps:
            raise Http404(f"No sitemap available for section: {section}")
        maps = [sitemaps[section]]
    else:
        maps = sitemaps.values()
    page = request.GET.get("p", 1)
    club = get_object_or_404(Club, slug__iexact=club_slug)
    if club.domain and is_custom_ssl_cert_active(club.domain) and not request.use_cname:
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


def gpsseuranta_time(request):
    return HttpResponse(time.time() - 1136073600, headers={"Cache-Control": "no-cache"})


def event_gpsseuranta_init_view(request, slug):
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.select_related("club", "map").prefetch_related("competitors"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )
    event.check_user_permission(request.user)

    out = f"""VERSIO:3
RACENAME:{event.name}
TIMEZONE:0
GRABINTERVAL:15
DASHLIMIT:45
LIVEBUFFER:30
MINBEFORESTART:0
NUMBEROFLOGOS:0
LIVE:{1 if event.is_live else 0}
"""
    if event.can_display_maps():
        width, height = event.map.quick_size
        tl = event.map.map_xy_to_wsg84((0, 0))
        tr = event.map.map_xy_to_wsg84((width, 0))
        br = event.map.map_xy_to_wsg84((width, height))
        out += f"CALIBRATION:{tl['lon']:.5f}|{tl['lat']:.5f}|0|0|{tr['lon']:.5f}|{tr['lat']:.5f}|{width}|0|{br['lon']:.5f}|{br['lat']:.5f}|{width}|{height}\n"

    for comp in event.competitors.all():
        out += f"COMPETITOR:t{comp.aid}|{comp.start_time.strftime("%Y%m%d")}|{comp.start_time.strftime("%H%I%S")}|{comp.name}|{comp.short_name}\n"

    headers = {}
    if event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    content_type = "text/plain; charset=utf-8"
    return HttpResponse(
        out,
        content_type=content_type,
        headers=headers,
    )


def event_gpsseuranta_data_view(request, slug, extension="lst"):
    club_slug = request.club_slug
    event = get_object_or_404(
        Event.objects.select_related("club", "map"),
        club__slug__iexact=club_slug,
        slug__iexact=slug,
    )

    event.check_user_permission(request.user)
    t0 = time.time()
    cache_ts = int(t0 // 5)
    cache_key = f"event:{event.aid}:gpsseuranta-data:{cache_ts}"
    was_cached = False
    if data := cache.get(cache_key):
        result = data
        was_cached = True
    else:
        result = ""
        for competitor, from_date, end_date in event.iterate_competitors():
            if competitor.device_id:
                locations, _ = competitor.device.get_locations_between_dates(
                    from_date, end_date
                )
                result += gpsseuranta_encode_data(f"t{competitor.aid}", locations)

    file_length = len(result)
    headers = {"X-GPS-Server-Filesize": file_length}
    if event.privacy == PRIVACY_PRIVATE:
        headers["Cache-Control"] = "Private"

    if not was_cached:
        cache.set(cache_key, result)

    content_type = "text/plain; charset=utf-8"
    return HttpResponse(
        result,
        content_type=content_type,
        headers=headers,
    )

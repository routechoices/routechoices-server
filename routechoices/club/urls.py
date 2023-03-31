import arrow
from django.models import Q
from django.urls import path, re_path

from routechoices.club import views
from routechoices.club.sitemaps import DynamicViewSitemap
from routechoices.core.models import Club

sitemaps = {
    "dynamic": DynamicViewSitemap,
}


def set_club(request, club_slug):
    club = Club.objects.filter(
        Q(slug=club_slug)
        | Q(
            slug_changed_from=club_slug,
            slug_changed_at__gt=arrow.now().shift(hours=-72).datetime,
        )
    ).first()
    if club:
        request.club_slug = club.slug
    else:
        request.club_slug = club_slug


urlpatterns = [
    re_path(r"^$", views.club_view, name="club_view"),
    re_path(r"^logo/?$", views.club_logo, name="club_logo"),
    re_path(
        r"(?P<icon_name>favicon\.ico|apple-touch-icon\.png|icon-192\.png|icon-512\.png)",
        views.club_favicon,
        name="club_favicon",
    ),
    path("manifest.json", views.manifest, name="manifest"),
    path("robots.txt", views.robots_txt, name="robots.txt"),
    path(
        "sitemap.xml", views.sitemap_index, {"sitemaps": sitemaps}, name="club_sitemap"
    ),
    re_path(
        r"^sitemap-(?P<section>[A-Za-z0-9-_]+).xml$",
        views.sitemap,
        {"sitemaps": sitemaps},
        name="club_sitemap_sections",
    ),
    re_path(r"^feed/?$", views.club_live_event_feed, name="club_feed"),
    re_path(
        r"\.well-known/acme-challenge/(?P<challenge>.+)$",
        views.acme_challenge,
        name="acme_challenge",
    ),
    re_path(
        r"(?P<slug>[0-9a-zA-Z_-]+)/export/?$",
        views.event_export_view,
        name="event_export_view",
    ),
    re_path(
        r"(?P<slug>[0-9a-zA-Z_-]+)/map/(?P<index>\d+)?$",
        views.event_map_view,
        name="event_map_view",
    ),
    re_path(
        r"(?P<slug>[0-9a-zA-Z_-]+)/kmz/(?P<index>\d+)?$",
        views.event_kmz_view,
        name="event_kmz_view",
    ),
    re_path(
        r"(?P<slug>[0-9a-zA-Z_-]+)/contribute/?$",
        views.event_contribute_view,
        name="event_contribute_view",
    ),
    re_path(r"(?P<slug>[0-9a-zA-Z_-]+)/?$", views.event_view, name="event_view"),
]

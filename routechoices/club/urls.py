from django.urls import path, re_path

from routechoices.club import views
from routechoices.club.sitemaps import DynamicViewSitemap

sitemaps = {
    "dynamic": DynamicViewSitemap,
}


def set_club(request, club_slug):
    request.club_slug = club_slug


urlpatterns = [
    re_path(r"^$", views.club_view, name="club_view"),
    re_path(r"^logo/?$", views.club_logo, name="club_logo"),
    re_path("favicon.ico", views.club_favicon, name="club_favicon"),
    re_path(
        "apple-touch-icon.png", views.club_apple_icon, name="club_apple_touch_icon"
    ),
    path("icon-192.png", views.club_icon_192, name="club_logo_192"),
    path("icon-512.png", views.club_icon_512, name="club_logo_512"),
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

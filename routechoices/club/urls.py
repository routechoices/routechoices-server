from django.urls import include, path, re_path

from routechoices.club import views
from routechoices.club.sitemaps import DynamicViewSitemap
from routechoices.core import views as core_views

sitemaps = {
    "dynamic": DynamicViewSitemap,
}


urlpatterns = [
    path("", views.club_view, name="club_view"),
    path("gps/time.php", views.gpsseuranta_time, name="gpsseuranta_time"),
    path("manifest.json", views.manifest, name="manifest"),
    path("robots.txt", views.robots_txt, name="robots.txt"),
    path("sitemap.xml", views.sitemap, {"sitemaps": sitemaps}, name="club_sitemap.xml"),
    re_path(r"^feed(\.rss)?$", views.club_live_event_feed, name="club_feed"),
    path(
        "thumbnail",
        include(
            [
                path(
                    "",
                    views.club_thumbnail,
                    name="club_thumbnail",
                ),
                re_path(
                    r"\.(?P<extension>png|webp|avif|jpeg)$",
                    views.club_thumbnail,
                    name="club_thumbnail_with_format",
                ),
            ]
        ),
    ),
    path(
        "logo",
        include(
            [
                path(
                    "",
                    views.club_logo,
                    name="club_logo",
                ),
                re_path(
                    r"\.(?P<extension>png|webp|avif|jpeg)$",
                    views.club_logo,
                    name="club_logo_with_format",
                ),
            ]
        ),
    ),
    path(
        "banner",
        include(
            [
                path(
                    "",
                    views.club_banner,
                    name="club_banner",
                ),
                re_path(
                    r"\.(?P<extension>png|webp|avif|jpeg)$",
                    views.club_banner,
                    name="club_banner_with_format",
                ),
            ]
        ),
    ),
    re_path(
        r"(?P<icon_name>favicon\.ico|apple-touch-icon\.png|icon-192\.png|icon-512\.png)",
        views.club_favicon,
        name="club_favicon",
    ),
    path(
        '.well-known/acme-challenge/<str:challenge>',
        views.acme_challenge,
        name="acme_challenge",
    ),
    re_path(
        r"(?P<slug>[^/]+)/",
        include(
            [
                path("", views.event_view, name="event_view"),
                path(
                    "export",
                    views.event_export_view,
                    name="event_export_view",
                ),
                path(
                    "startlist",
                    views.event_startlist_view,
                    name="event_startlist_view",
                ),
                path(
                    "thumbnail",
                    include(
                        [
                            path(
                                "",
                                views.event_map_thumbnail,
                                name="event_map_thumbnail",
                            ),
                            re_path(
                                r"\.(?P<extension>png|webp|avif|jpeg)$",
                                views.event_map_thumbnail,
                                name="event_map_thumbnail_with_format",
                            ),
                        ]
                    ),
                ),
                path(
                    "zip",
                    views.event_zip_view,
                    name="event_zip_view",
                ),
                path(
                    "map",
                    include(
                        [
                            path(
                                "",
                                views.event_map_view,
                                name="event_main_map_view",
                            ),
                            re_path(
                                r"^\.(?P<extension>png|webp|avif|jpeg)$",
                                views.event_map_view,
                                name="event_main_map_view_with_format",
                            ),
                            re_path(
                                r"^-(?P<index>[1-9]\d*)$",
                                include(
                                    [
                                        path(
                                            "",
                                            views.event_map_view,
                                            name="event_map_view",
                                        ),
                                        re_path(
                                            r"^\.(?P<extension>png|webp|avif|jpeg)$",
                                            views.event_map_view,
                                            name="event_map_view_with_format",
                                        ),
                                    ]
                                ),
                            ),
                        ]
                    ),
                ),
                path(
                    "kmz",
                    include(
                        [
                            path(
                                "",
                                views.event_kmz_view,
                                name="event_main_kmz_view",
                            ),
                            re_path(
                                r"^-(?P<index>[1-9]\d*)$",
                                views.event_kmz_view,
                                name="event_kmz_view",
                            ),
                        ]
                    ),
                ),
                re_path(
                    r"^data\.(?P<extension>lst|php)$",
                    views.event_gpsseuranta_data_view,
                    name="event_gpsseuranta_data_view",
                ),
                path(
                    "init.txt",
                    views.event_gpsseuranta_init_view,
                    name="event_gpsseuranta_init_view",
                ),
            ]
        ),
    ),
    path(".well-known/security.txt", core_views.security_txt),
]

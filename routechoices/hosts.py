from django_hosts import host, patterns

host_patterns = patterns(
    "",
    host("api", "routechoices.api.urls", name="api"),
    host("wms", "routechoices.api.wms_urls", name="wms"),
    host("www", "routechoices.urls", name="www"),
    host(
        r"(?P<club_slug>[a-zA-Z0-9][a-zA-Z0-9-]+)",
        "routechoices.club.urls",
        callback="routechoices.club.urls.set_club",
        name="clubs",
    ),
)

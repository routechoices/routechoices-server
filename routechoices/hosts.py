from django_hosts import host, patterns

host_patterns = patterns(
    "",
    host("api", "routechoices.api.urls", name="api"),
    host("map", "routechoices.map.urls", name="map"),
    host("tiles", "routechoices.tiles.urls", name="tiles"),
    host("wms", "routechoices.wms.urls", name="wms"),
    host("www", "routechoices.urls", name="www"),
    host(
        r"(?P<club_slug>[a-zA-Z0-9][a-zA-Z0-9-]+)",
        "routechoices.club.urls",
        # callback="routechoices.club.urls.set_club",
        name="clubs",
    ),
)

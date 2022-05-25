from django.urls import include, re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from routechoices.api import views

schema_view = get_schema_view(
    openapi.Info(
        title="Routechoices.com API",
        default_version="v1",
        description="Routechoices.com API",
        terms_of_service="https://www.routechoices.com/tos/",
        contact=openapi.Contact(email="info@routechoices.com"),
        license=openapi.License(
            name="GPLv3", url="https://www.gnu.org/licenses/gpl-3.0.en.html"
        ),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    re_path(r"^oauth2/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    re_path(r"^$", schema_view.with_ui("redoc", cache_timeout=0), name="api_doc"),
    re_path(r"^device_id/?$", views.get_device_id, name="device_id_api"),
    re_path(r"^imei/?$", views.get_device_for_imei, name="device_imei_api"),
    re_path(r"^locations/?$", views.locations_api_gw, name="locations_api_gw"),
    re_path(r"^time/?$", views.get_time, name="time_api"),
    re_path(r"^search/device/?$", views.device_search, name="device_search_api"),
    re_path(r"^search/user/?$", views.user_search, name="user_search_api"),
    re_path(
        r"^device/(?P<device_id>[^/]+)/?$",
        views.device_info,
        name="device_info_api",
    ),
    re_path(
        r"^device/(?P<device_id>[^/]+)/registrations/?$",
        views.device_registrations,
        name="device_registrations_api",
    ),
    re_path(
        r"^clubs/(?P<club_id>[0-9a-zA-Z_-]+)/devices/(?P<device_id>[^/]+)/?$",
        views.device_api_view,
        name="device_api_view",
    ),
    re_path(r"^events/?$", views.event_list, name="event_list"),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/?$",
        views.event_detail,
        name="event_detail",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/chat/?$",
        views.event_chat,
        name="event_chat",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/map-thumb/?$",
        views.event_map_thumb_download,
        name="event_map_thumb_download",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/register/?$",
        views.event_register,
        name="event_register",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/upload-route/?$",
        views.event_upload_route,
        name="event_upload_route",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/competitor/(?P<competitor_id>[0-9a-zA-Z_-]+)/?$",
        views.event_delete_competitor,
        name="event_delete_competitor",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/map/(?P<map_index>\d+)?$",
        views.event_map_download,
        name="event_map_download",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/kmz/(?P<map_index>\d+)?$",
        views.event_kmz_download,
        name="event_kmz_download",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/data/?$",
        views.event_data,
        name="event_data",
    ),
    re_path(
        r"^events/(?P<event_id>[0-9a-zA-Z_-]+)/data-load-test/?$",
        views.event_data_load_test,
        name="event_data_load_test",
    ),
    re_path(
        r"^maps/(?P<map_id>[-0-9a-zA-Z_]+)/kmz/?$",
        views.map_kmz_download,
        name="map_kmz_download",
    ),
    re_path(
        r"^competitor/(?P<competitor_id>[0-9a-zA-Z_-]+)/gpx/?$",
        views.competitor_gpx_download,
        name="competitor_gpx_download",
    ),
    re_path(
        r"^woo/race_status/get_info.json$",
        views.two_d_rerun_race_status,
        name="2d_rerun_race_status",
    ),
    re_path(
        r"^woo/race_status/get_data.json$",
        views.two_d_rerun_race_data,
        name="2d_rerun_race_data",
    ),
    re_path(r"^wms/?$", views.wms_service, name="wms_service"),
    re_path(r"^check-latlon/?$", views.ip_latlon, name="ip_latlon"),
]

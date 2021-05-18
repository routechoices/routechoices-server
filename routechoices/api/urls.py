from django.conf.urls import url

from rest_framework import permissions

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from routechoices.api import views


schema_view = get_schema_view(
   openapi.Info(
      title="Routechoices.com API",
      default_version='v1',
      description="Routechoices.com API",
      terms_of_service="https://www.routechoices.com/tos/",
      contact=openapi.Contact(email="admin@routechoices.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    url(
        r'^$',
        schema_view.with_ui(
            'redoc',
            cache_timeout=0
        ),
        name='api_doc'
    ),
    url(r'^device_id/?$', views.get_device_id, name='device_id_api'),
    url(r'^imei/?$', views.get_device_for_imei, name='device_imei_api'),
    url(
        r'^gps_seuranta_proxy/?$',
        views.gps_seuranta_proxy,
        name='gps_seuranta_proxy'
    ),
    url(r'^pwa/?$', views.pwa_api_gw, name='pwa_api_gw'),
    url(r'^time/?$', views.get_time, name='time_api'),
    url(r'^user/search/?$', views.user_search, name='user_search_api'),
    url(r'^device/search/?$', views.device_search, name='device_search_api'),
    url(r'^traccar/?$', views.traccar_api_gw, name='traccar_api_gw'),
    url(r'^garmin/?$', views.garmin_api_gw, name='garmin_api_gw'),
    url(
        r'^events/?$',
        views.event_list,
        name='event_list'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/?$',
        views.event_detail,
        name='event_detail'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/map/?$',
        views.event_map_download,
        name='event_map_download'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/kmz/?$',
        views.event_kmz_download,
        name='event_kmz_download'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/map_thumb/?$',
        views.event_map_thumb_download,
        name='event_map_thumb_download'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/register/?$',
        views.event_register,
        name='event_register'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/extra_map/(?P<map_index>[1-9]\d*)?$',
        views.event_extra_map_download,
        name='event_extra_map_download'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/extra_kmz/(?P<map_index>[1-9]\d*)?$',
        views.event_extra_kmz_download,
        name='event_extra_kmz_download'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/data/?$',
        views.event_data,
        name='event_data'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/map_details/?$',
        views.event_map_details,
        name='event_map_details'
    ),
    url(
        r'^events/(?P<event_id>[0-9a-zA-Z_-]+)/announcement/?$',
        views.event_announcement,
        name='event_announcement'
    ),
    url(
        r'^maps/'
        r'(?P<map_id>[-0-9a-zA-Z_]+)/kmz/?$',
        views.map_kmz_download,
        name='map_kmz_download',
    ),
    url(
        r'^competitor/(?P<competitor_id>[0-9a-zA-Z_-]+)/gpx$',
        views.competitor_gpx_download,
        name='competitor_gpx_download'
    ),
    url(
        r'^woo/race_status/get_info.json$',
        views.two_d_rerun_race_status,
        name='2d_rerun_race_status'
    ),
    url(
        r'^woo/race_status/get_data.json$',
        views.two_d_rerun_race_data,
        name='2d_rerun_race_data'
    ),
    # url(
    #     r'^wms/?$',
    #     views.wms_service,
    #     name='wms_service'
    # ),
]

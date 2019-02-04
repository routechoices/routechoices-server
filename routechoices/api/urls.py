from django.conf.urls import url
from django.views.generic import TemplateView

from routechoices.api import views

urlpatterns = [
    url(r'^device_id/?$', views.get_device_id, name='device_id_api'),
    url(r'^gps_seuranta_proxy/?$', views.gps_seuranta_proxy, name='gps_seuranta_proxy'),
    url(r'^pwa/?$', views.pwa_api_gw, name='pwa_api_gw'),
    url(r'^time/?$', views.get_time, name='time_api'),
    url(r'^user/search/?$', views.user_search, name='user_search_api'),
    url(r'^device/search/?$', views.device_search, name='device_search_api'),
    url(r'^traccar/?$', views.traccar_api_gw, name='traccar_api_gw'),
    url(r'^events/(?P<aid>[0-9a-zA-Z_-]+)/map/?$', views.event_map_download, name='event_map_download'),
    url(r'^events/(?P<aid>[0-9a-zA-Z_-]+)/rg_data/?$', views.event_rg_data, name='event_rg_data'),
    url(r'^competitor/(?P<aid>[0-9a-zA-Z_-]+)/gpx$', views.competitor_gpx_download, name='competitor_gpx_download'),
]
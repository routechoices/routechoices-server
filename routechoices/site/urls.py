from django.conf.urls import url
from django.views.generic import TemplateView

from routechoices.site import views

urlpatterns = [
    url(r'^$', TemplateView.as_view(template_name='site/home.html'), name='home_view'),
    url(r'^api/device_id/?$', views.get_device_id, name='device_id_api'),
    url(r'^api/gps_seuranta_proxy/?$', views.gps_seuranta_proxy, name='gps_seuranta_proxy'),
    url(r'^api/pwa/?$', views.pwa_api_gw, name='pwa_api_gw'),
    url(r'^api/time/?$', views.get_time, name='time_api'),
    url(r'^api/traccar/?$', views.traccar_api_gw, name='traccar_api_gw'),
    url(r'^contact/?$', TemplateView.as_view(template_name='site/contact.html'), name='contact_view'),
    url(r'^events/?$', views.events_view, name='events_view'),
    url(r'^(?P<slug>[0-9a-zA-Z_-]+)/?$', views.club_view, name='club_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/?$', views.event_view, name='event_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/map/?$', views.event_map_view, name='event_map_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/export/?$', views.event_export_view, name='event_export_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/export/(?P<aid>[0-9a-zA-Z_-]+)\.gpx$', views.competitor_gpx_view, name='competitor_gpx_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/data/?$', views.event_data_view, name='event_data_view'),
]
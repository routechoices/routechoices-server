from django.conf.urls import url

from routechoices.site import views

urlpatterns = [
    url(r'^$', views.home_view, name='home_view'),
    url(r'^api/traccar/?$', views.traccar_api_gw, name='traccar'),
    url(r'^(?P<slug>[0-9a-zA-Z_-]+)/?$', views.club_view, name='club_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/?$', views.event_view, name='event_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/map/?$', views.event_map_view, name='event_map_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/data/?$', views.event_data_view, name='event_data_view'),
]
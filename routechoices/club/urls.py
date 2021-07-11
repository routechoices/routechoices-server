from django.conf.urls import url

from routechoices.club import views


def set_club(request, club_slug):
    request.club_slug = club_slug


urlpatterns = [
    url(r'^$', views.club_view, name='club_view'),
    url(
        r'^feed/?$',
        views.club_live_event_feed,
        name='club_feed'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/export/?$',
        views.event_export_view,
        name='event_export_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/map/?$',
        views.event_map_view,
        name='event_map_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/extra_map/(?P<index>\d+)?$',
        views.event_extra_map_view,
        name='event_extra_map_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/kmz/?$',
        views.event_kmz_view,
        name='event_kmz_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/extra_kmz/(?P<index>\d+)?$',
        views.event_extra_kmz_view,
        name='event_extra_kmz_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/register/?$',
        views.event_registration_view,
        name='event_registration_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/upload_route/?$',
        views.event_route_upload_view,
        name='event_route_upload_view'
    ),
    url(
        r'(?P<slug>[0-9a-zA-Z_-]+)/?$',
        views.event_view,
        name='event_view'
    ),
]

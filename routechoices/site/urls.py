from django.conf.urls import url
from django.views.generic import TemplateView

from routechoices.site import views, feeds


urlpatterns = [
    url(r'^$', views.home_view, name='home_view'),
    url(
        r'^contact/?$',
        views.contact,
        name='contact_view'
    ),
    url(
        r'^contact/success/?$',
        TemplateView.as_view(template_name='site/contact_email_sent.html'),
        name='contact_email_sent_view'
    ),
    url(r'^events/?$', views.events_view, name='events_view'),
    url(r'^events/feed/?$', feeds.live_event_feed, name='events_feed'),
    url(r'^tracker/?$', views.tracker_view, name='tracker_view'),
    url(
        r'^privacy-policy/?$',
        TemplateView.as_view(template_name='site/privacy_policy.html'),
        name='privacy_policy_view'
    ),
    url(
        r'^tos/?$',
        TemplateView.as_view(template_name='site/tos.html'),
        name='tos_view'
    ),
    url(
        r'^r/(?P<event_id>[0-9a-zA-Z_-]+)/?$',
        views.event_shortcut,
        name='event_shortcut'
    ),
    url(r'^(?P<slug>[0-9a-zA-Z_-]+)/?$', views.club_view, name='club_view'),
    url(
        r'^(?P<slug>[0-9a-zA-Z_-]+)/feed/?$',
        feeds.club_live_event_feed,
        name='club_feed'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/?$',
        views.event_view,
        name='event_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/export/?$',
        views.event_export_view,
        name='event_export_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/map/?$',
        views.event_map_view,
        name='event_map_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/extra_map/(?P<index>\d+)?$',
        views.event_extra_map_view,
        name='event_extra_map_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/kmz/?$',
        views.event_kmz_view,
        name='event_kmz_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/extra_kmz/(?P<index>\d+)?$',
        views.event_extra_kmz_view,
        name='event_extra_kmz_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/register/?$',
        views.event_registration_view,
        name='event_registration_view'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z_-]+)/' +
        r'(?P<slug>[0-9a-zA-Z_-]+)/upload_route/?$',
        views.event_route_upload_view,
        name='event_route_upload_view'
    ),
]

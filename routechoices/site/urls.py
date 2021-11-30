from django.urls import re_path, include
from django.views.generic import TemplateView

from routechoices.site import views, feeds


urlpatterns = [
    re_path(r'^$', views.home_view, name='home_view'),
    re_path(
        r'^contact/?$',
        views.contact,
        name='contact_view'
    ),
    re_path(
        r'^contact/success/?$',
        TemplateView.as_view(template_name='site/contact_email_sent.html'),
        name='contact_email_sent_view'
    ),
    re_path(r'^events/?$', views.events_view, name='events_view'),
    re_path(r'^events/feed/?$', feeds.live_event_feed, name='events_feed'),
    re_path(r'^tracker/?$', views.tracker_view, name='tracker_view'),
    re_path(r'^trackers/?$', views.tracker_view, name='trackers_view'),
    re_path(
        r'^privacy-policy/?$',
        TemplateView.as_view(template_name='site/privacy_policy.html'),
        name='privacy_policy_view'
    ),
    re_path(
        r'^tos/?$',
        TemplateView.as_view(template_name='site/tos.html'),
        name='tos_view'
    ),
    re_path(
        r'^features/?$',
        TemplateView.as_view(template_name='site/features.html'),
        name='features_view'
    ),
    re_path(
        r'^pricing/?$',
        TemplateView.as_view(template_name='site/pricing.html'),
        name='pricing_view'
    ),
    re_path(
        r'^r/(?P<event_id>[0-9a-zA-Z_-]+)/?$',
        views.event_shortcut,
        name='event_shortcut'
    ),
    re_path(
        r'^(?P<club_slug>[0-9a-zA-Z][0-9a-zA-Z-]+)/',
        include(
            ('routechoices.club.urls', 'club'),
            namespace='club'
        )
    ),
]

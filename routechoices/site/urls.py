from django.conf.urls import url, include
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
        r'^backers/?$',
        views.backers,
        name='backers_view'
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
        r'^pricing/?$',
        TemplateView.as_view(template_name='site/pricing.html'),
        name='pricing_view'
    ),
    url(
        r'^tos/?$',
        TemplateView.as_view(template_name='site/tos.html'),
        name='tos_view'
    ),
    url(
        r'^features/?$',
        TemplateView.as_view(template_name='site/features.html'),
        name='features_view'
    ),
    url(
        r'^pricing/?$',
        TemplateView.as_view(template_name='site/pricing.html'),
        name='pricing_view'
    ),
    url(
        r'^r/(?P<event_id>[0-9a-zA-Z_-]+)/?$',
        views.event_shortcut,
        name='event_shortcut'
    ),
    url(
        r'^(?P<club_slug>[0-9a-zA-Z][0-9a-zA-Z-]+)/',
        include(
            ('routechoices.club.urls', 'club'),
            namespace='club'
        )
    ),
]

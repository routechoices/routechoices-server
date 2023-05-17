from django.urls import include, re_path
from django.views.generic import TemplateView

from routechoices.site import feeds, views

urlpatterns = [
    re_path(
        r"^$", TemplateView.as_view(template_name="site/home.html"), name="home_view"
    ),
    re_path(r"^contact/?$", views.contact, name="contact_view"),
    re_path(r"^events/?$", views.events_view, name="events_view"),
    re_path(r"^events/feed/?$", feeds.live_event_feed, name="events_feed"),
    re_path(
        r"^tracker/?$",
        TemplateView.as_view(template_name="site/tracker.html"),
        name="tracker_view",
    ),
    re_path(
        r"^trackers/?$",
        TemplateView.as_view(template_name="site/tracker.html"),
        name="trackers_view",
    ),
    re_path(
        r"^privacy-policy/?$",
        TemplateView.as_view(template_name="site/privacy_policy.html"),
        name="privacy_policy_view",
    ),
    re_path(
        r"^tos/?$", TemplateView.as_view(template_name="site/tos.html"), name="tos_view"
    ),
    re_path(
        r"^pricing/?$",
        views.pricing_page,
        name="pricing_view",
    ),
    re_path(r"^lemon-webhook/?$", views.lemon_webhook, name="lemon_webhook"),
    re_path(
        r"^r/(?P<event_id>[0-9a-zA-Z_-]+)/?$",
        views.event_shortcut,
        name="event_shortcut",
    ),
    re_path(
        r"^(?P<club_slug>[0-9a-zA-Z][0-9a-zA-Z-]+)/",
        include(("routechoices.club.urls", "club"), namespace="club"),
    ),
]

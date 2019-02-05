from django.conf.urls import url
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView

from routechoices.site import views
from routechoices.site.sitemaps import (
    EventsSitemap,
    ClubsSitemap,
    EventsExportSitemap,
    StaticViewSitemap,
    DynamicViewSitemap,
)

sitemaps = {
    'events': EventsSitemap,
    'events_export': EventsExportSitemap,
    'clubs': ClubsSitemap,
    'static': StaticViewSitemap,
    'dynamic': DynamicViewSitemap,
}


urlpatterns = [
    url(r'^$', views.home_view, name='home_view'),
    url(r'^sitemap\.xml$', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    url('sitemap-(?P<section>[A-Za-z0-9-_]+).xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    url(r'^contact/?$', TemplateView.as_view(template_name='site/contact.html'), name='contact_view'),
    url(r'^events/?$', views.events_view, name='events_view'),
    url(r'^tracker/?$', views.tracker_view, name='tracker_view'),
    url(r'^privacy-policy/?$', TemplateView.as_view(template_name='site/privacy_policy.html'), name='privacy_policy_view'),
    url(r'^tos/?$', TemplateView.as_view(template_name='site/tos.html'), name='tos_view'),
    url(r'^(?P<slug>[0-9a-zA-Z_-]+)/?$', views.club_view, name='club_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/?$', views.event_view, name='event_view'),
    url(r'^(?P<club_slug>[0-9a-zA-Z_-]+)/(?P<slug>[0-9a-zA-Z_-]+)/export/?$', views.event_export_view, name='event_export_view'),
]
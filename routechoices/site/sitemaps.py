from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.timezone import now
from routechoices.core.models import Event, Club


class EventsSitemap(Sitemap):
    changefreq = "never"
    priority = 0.5
    protocol = "https"

    def items(self):
        return Event.objects.filter(start_date__lt=now())

    def lastmod(self, obj):
        return obj.modification_date


class EventsExportSitemap(Sitemap):
    changefreq = "never"
    priority = 0.4
    protocol = "https"

    def items(self):
        return Event.objects.filter(start_date__lt=now())

    def location(self, item):
        return item.get_absolute_export_url()

    def lastmod(self, obj):
        return obj.modification_date


class ClubsSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.4
    protocol = "https"

    def items(self):
        return Club.objects.all()


class StaticViewSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return [
            'site:contact_view',
            'site:tos_view',
            'site:privacy_policy_view',
            'site:home_view',
            'site:tracker_view',
        ]

    def location(self, item):
        return reverse(item)


class DynamicViewSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = "https"

    def items(self):
        return [
            'site:events_view',
        ]

    def location(self, item):
        return reverse(item)

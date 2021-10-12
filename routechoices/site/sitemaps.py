from django.contrib.sitemaps import Sitemap
from django_hosts.resolvers import reverse


class StaticViewSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return [
            'site:home_view',
            'site:trackers_view',
            'site:contact_view',
            'site:pricing_view',
            'site:tos_view',
            'site:privacy_policy_view',
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

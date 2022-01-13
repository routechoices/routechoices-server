from django.contrib.sitemaps import Sitemap
from django_hosts.resolvers import reverse


class StaticViewSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.7
    protocol = "https"

    def get_domain(self, site=None):
        return ""

    def items(self):
        return [
            "site:home_view",
            "site:trackers_view",
            "site:contact_view",
            "site:pricing_view",
            "site:tos_view",
            "site:privacy_policy_view",
        ]

    def location(self, item):
        path = reverse(item)
        if path.startswith("//"):
            return path[2:]
        return path


class DynamicViewSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = "https"

    def get_domain(self, site=None):
        return ""

    def items(self):
        return [
            "site:events_view",
        ]

    def location(self, item):
        path = reverse(item)
        if path.startswith("//"):
            return path[2:]
        return path

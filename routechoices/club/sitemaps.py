from django.contrib.sitemaps import Sitemap
from django_hosts.resolvers import reverse

from routechoices.core.models import PRIVACY_PUBLIC, Club, Event


class StaticViewSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.7
    protocol = "https"

    def get_domain(self, site=None):
        return ""

    def items(self):
        return [
            "club_view",
        ]

    def location(self, item):
        path = reverse(item, host="clubs", host_kwargs={"club_slug": self.club_slug})
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
        club_root = Club.objects.filter(slug=self.club_slug).first().nice_url
        events = Event.objects.filter(club__slug=self.club_slug, privacy=PRIVACY_PUBLIC)
        items = ()
        for event in events:
            items += (
                f"{club_root}{event.slug}",
                f"{club_root}{event.slug}/export",
                f"{club_root}{event.slug}/contribute"
            )
        return items

    def location(self, item):
        return item

from django.contrib.sitemaps import Sitemap
from django_hosts.resolvers import reverse

from routechoices.core.models import PRIVACY_PUBLIC, Event


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
        events = Event.objects.filter(club__slug=self.club_slug, privacy=PRIVACY_PUBLIC)
        items = ()
        for event in events:
            items += (
                ("event_view", event.slug),
                ("event_export_view", event.slug),
                ("event_contribute_view", event.slug),
            )
        return items

    def location(self, item):
        path = reverse(
            item[0],
            host="clubs",
            host_kwargs={"club_slug": self.club_slug},
            kwargs={"slug": item[1]},
        )
        if path.startswith("//"):
            return path[2:]
        return path

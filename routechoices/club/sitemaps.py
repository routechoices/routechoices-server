import re

from django.contrib.sitemaps import Sitemap

from routechoices.core.models import PRIVACY_PUBLIC, Club, Event


class DynamicViewSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = "https"

    def get_domain(self, site=None):
        return ""

    def items(self):
        club_root = Club.objects.filter(slug=self.club_slug).first().nice_url
        club_root = re.sub("^https?://", "", club_root)
        events = Event.objects.filter(club__slug=self.club_slug, privacy=PRIVACY_PUBLIC)
        items = (club_root,)
        for event in events:
            items += (
                f"{club_root}{event.slug}",
                f"{club_root}{event.slug}/export",
                f"{club_root}{event.slug}/contribute",
            )
        return items

    def location(self, item):
        return item

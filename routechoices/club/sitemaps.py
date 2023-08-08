import re

from django.contrib.sitemaps import Sitemap
from django.utils.timezone import now

from routechoices.core.models import PRIVACY_PUBLIC, Club, Event, EventSet


class DynamicViewSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = "https"

    def get_domain(self, site=None):
        return ""

    def items(self):
        club_root = Club.objects.filter(slug=self.club_slug).first().nice_url
        club_root = re.sub(r"^https?://", "", club_root)

        events = Event.objects.filter(
            club__slug=self.club_slug,
            privacy=PRIVACY_PUBLIC,
        )
        event_sets_with_page = EventSet.objects.filter(
            club__slug=self.club_slug,
            create_page=True,
            list_secret_events=False,
        )

        # below we compute the pages in event list
        event_list = events.filter(end_date__lt=now())
        event_sets_keys = set()
        for event in event_list:
            event_sets_keys.add(event.event_set_id or f"e_{event.aid}")
        page_count = max(0, (len(event_sets_keys) - 1)) // 25 + 1

        items = (club_root,)
        for p in range(1, page_count):
            items += (f"{club_root}?page={p+1}",)
        for event_set in event_sets_with_page:
            items += (f"{club_root}{event_set.slug}",)
        for event in events:
            items += (
                f"{club_root}{event.slug}",
                f"{club_root}{event.slug}/export",
                f"{club_root}{event.slug}/contribute",
            )
        return items

    def location(self, item):
        return item

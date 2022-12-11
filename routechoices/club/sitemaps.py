import re

from django.contrib.sitemaps import Sitemap
from django.utils.timezone import now

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

        events = Event.objects.filter(
            club__slug=self.club_slug, privacy=PRIVACY_PUBLIC
        ).select_related("club")

        # below we compute the pages in event list
        event_list = events.filter(end_date__lt=now())
        event_sets = []
        event_sets_keys = {}
        for event in event_list[::-1]:
            key = event.event_set or f"{event.aid}_E"
            name = event.event_set or event.name
            if key not in event_sets_keys.keys():
                event_sets_keys[key] = len(event_sets)
                event_sets.append(
                    {
                        "name": name,
                        "events": [
                            event,
                        ],
                        "fake": event.event_set is None,
                    }
                )
            else:
                idx = event_sets_keys[key]
                event_sets[idx]["events"].append(event)
        page_count = max(0, (len(event_sets) - 1)) // 25 + 1

        items = (club_root,)
        for p in range(1, page_count):
            items += (f"{club_root}?page={p+1}",)
        for event in events:
            items += (
                f"{club_root}{event.slug}",
                f"{club_root}{event.slug}/export",
                f"{club_root}{event.slug}/contribute",
            )
        return items

    def location(self, item):
        return item

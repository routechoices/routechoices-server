from django.contrib.sitemaps import Sitemap
from django.utils.timezone import now
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
        event_list = Event.objects.filter(privacy=PRIVACY_PUBLIC)
        event_list = event_list.filter(end_date__lt=now())
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

        root = reverse("site:events_view")
        items = (root,)
        for p in range(1, page_count):
            items += (f"{root}?page={p+1}",)
        return items

    def location(self, item):
        path = item
        if path.startswith("//"):
            return path[2:]
        return path

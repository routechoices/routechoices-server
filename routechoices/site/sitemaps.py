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
        event_list = Event.objects.filter(
            privacy=PRIVACY_PUBLIC,
            list_on_routechoices_com=True,
        )
        event_list = event_list.filter(end_date__lt=now())

        events_witout_sets = event_list.filter(event_set__isnull=True)
        first_events_of_each_set = (
            event_list.filter(event_set__isnull=False)
            .order_by("event_set_id", "-start_date")
            .distinct("event_set_id")
        )

        all_events = events_witout_sets.union(first_events_of_each_set).order_by(
            "-start_date", "name"
        )

        page_count = max(0, all_events.count() - 1) // 25 + 1

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

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django.utils.timezone import now
from django_hosts.resolvers import reverse

from routechoices.core.models import PRIVACY_PUBLIC, Event


class LiveEventsFeed(Feed):
    def title(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return f"GPS Tracking Events on {site.name}"

    def description(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return f"Watch live or later the GPS Tracking Events on {site.name}"

    def link(self):
        return reverse("site:events_view")

    def items(self):
        return (
            Event.objects.select_related("club")
            .filter(
                privacy=PRIVACY_PUBLIC,
            )
            .filter(start_date__lte=now())
        )

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return f"GPS Tracking of {item.name} by {item.club}"

    def item_pubdate(self, item):
        return item.start_date


live_event_feed = LiveEventsFeed()

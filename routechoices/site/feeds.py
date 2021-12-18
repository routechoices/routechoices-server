from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django_hosts.resolvers import reverse

from routechoices.core.models import Event, PRIVACY_PUBLIC


class LiveEventsFeed(Feed):
    def title(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return f"Live GPS Events on {site.name}"

    def description(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return f"Events on {site.name}"

    def link(self):
        return reverse('site:events_view')

    def items(self):
        return Event.objects.select_related('club').filter(
            privacy=PRIVACY_PUBLIC,
        )[:25]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return f'Live GPS Tracking of {item.name} by {item.club}'

    def item_pubdate(self, item):
        return item.start_date


live_event_feed = LiveEventsFeed()

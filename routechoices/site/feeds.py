from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.timezone import now

from routechoices.core.models import Event


class LiveEventsFeed(Feed):
    def title(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Live GPS Events from {}".format(site.name)

    def description(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Events from {}".format(site.name)

    def link(self):
        return reverse('site:events_view')

    def items(self):
        return Event.objects.filter(start_date__lt=now())[:25]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return 'Live GPS Tracking of {} by {}'.format(item.name, item.club)

    def item_pubdate(self, item):
        return item.start_date


live_event_feed = LiveEventsFeed()
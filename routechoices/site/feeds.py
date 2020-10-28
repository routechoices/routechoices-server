from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django.urls import reverse

from routechoices.core.models import Event, PRIVACY_PUBLIC, Club


class LiveEventsFeed(Feed):
    def title(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Live GPS Events on {}".format(site.name)

    def description(self):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Events on {}".format(site.name)

    def link(self):
        return reverse('site:events_view')

    def items(self):
        return Event.objects.select_related('club').filter(
            privacy=PRIVACY_PUBLIC,
        )[:25]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return 'Live GPS Tracking of {} by {}'.format(item.name, item.club)

    def item_pubdate(self, item):
        return item.start_date


class ClubLiveEventsFeed(Feed):
    def get_object(self, request, slug):
        return Club.objects.get(slug=slug)

    def title(self, obj):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Live GPS Events by {} on {}".format(obj.name, site.name)

    def description(self, obj):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Events by {} on {}".format(obj, site.name)

    def link(self, obj):
        return reverse('site:club_view', kwargs={'slug': obj.slug})

    def items(self, obj):
        return Event.objects.select_related('club').filter(
            privacy=PRIVACY_PUBLIC,
            club=obj,
        )[:25]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return 'Live GPS Tracking of {} by {}'.format(item.name, item.club)

    def item_pubdate(self, item):
        return item.start_date


live_event_feed = LiveEventsFeed()
club_live_event_feed = ClubLiveEventsFeed()

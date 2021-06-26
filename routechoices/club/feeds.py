from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django_hosts.resolvers import reverse

from routechoices.core.models import Event, PRIVACY_PUBLIC, Club


class ClubLiveEventsFeed(Feed):
    def get_object(self, request, **kwargs):
        return Club.objects.get(slug=request.club_slug)

    def title(self, obj):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Live GPS Events by {} on {}".format(obj.name, site.name)

    def description(self, obj):
        site = Site.objects.get(id=settings.SITE_ID)
        return "Events by {} on {}".format(obj, site.name)

    def link(self, obj):
        return reverse(
            'club_view',
            host='clubs',
            host_kwargs={'club_slug': obj.slug}
        )

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


club_live_event_feed = ClubLiveEventsFeed()

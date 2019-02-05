from django.contrib.syndication.views import Feed
from django.utils.timezone import now

from routechoices.core.models import Event


class LiveEventsFeed(Feed):
    title = "Live Events"
    link = '/events/'
    description = "Updates on changes and additions to the live events list."

    def items(self):
        return Event.objects.filter(start_date__lt=now())[:25]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return 'Live GPS Tracking of {} by {}'.format(item.name, item.club)
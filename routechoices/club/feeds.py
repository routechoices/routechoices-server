from django.contrib.syndication.views import Feed
from django.utils.timezone import now

from routechoices.core.models import PRIVACY_PUBLIC, Club, Event


class ClubLiveEventsFeed(Feed):
    def get_object(self, request, **kwargs):
        return Club.objects.get(slug__iexact=request.club_slug)

    def title(self, obj):
        return f"GPS Tracking Events by {obj.name}"

    def description(self, obj):
        return f"Watch live or later the GPS Tracking Events by {obj.name}"

    def link(self, obj):
        return f"{obj.nice_url}"

    def items(self, obj):
        return (
            Event.objects.select_related("club")
            .filter(
                privacy=PRIVACY_PUBLIC,
                club=obj,
            )
            .filter(start_date__lte=now())
        )

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return f"GPS Tracking of {item.name} by {item.club}"

    def item_pubdate(self, item):
        return item.start_date


club_live_event_feed = ClubLiveEventsFeed()

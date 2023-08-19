from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed
from django.utils.timezone import now
from django.utils.xmlutils import SimplerXMLGenerator

from routechoices.core.models import PRIVACY_PUBLIC, Club, Event


class RssXslFeed(Rss201rev2Feed):
    content_type = "text/xml"
    xsl_path = "/static/xsl/club-feed.xsl"

    def write(self, outfile, encoding):
        handler = SimplerXMLGenerator(outfile, encoding, short_empty_elements=True)
        handler.startDocument()
        handler.processingInstruction(
            "xml-stylesheet", f'type="text/xsl" href="{self.xsl_path}"'
        )
        handler.startElement("rss", self.rss_attributes())
        handler.startElement("channel", self.root_attributes())
        self.add_root_elements(handler)
        self.write_items(handler)
        self.endChannelElement(handler)
        handler.endElement("rss")


class ClubLiveEventsFeed(Feed):
    feed_type = RssXslFeed

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

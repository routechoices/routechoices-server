import time

import arrow
import requests
from defusedxml import minidom
from django.core.management.base import BaseCommand

from routechoices.core.models import Device, SpotFeed


class Command(BaseCommand):
    help = "Run a crawler for SPOT API feeds."

    def parse_response(self, xml):
        doc = minidom.parseString(xml)
        devices = []
        for message in doc.getElementsByTagName("message"):
            type = message.getElementsByTagName("messageType")[0].firstChild.nodeValue
            if type in ("TRACK", "EXTREME-TRACK", "UNLIMITED-TRACK"):
                messenger_id = message.getElementsByTagName("messengerId")[
                    0
                ].firstChild.nodeValue
                if not devices.get(messenger_id):
                    devices[messenger_id] = []
                try:
                    lat = float(
                        message.getElementsByTagName("latitude")[0].firstChild.nodeValue
                    )
                    lon = float(
                        message.getElementsByTagName("longitude")[
                            0
                        ].firstChild.nodeValue
                    )
                    ts = int(
                        message.getElementsByTagName("unixTime")[0].firstChild.nodeValue
                    )
                except Exception:
                    continue
                devices[messenger_id].append((ts, lat, lon))
        n = 0
        for m_id in devices.keys:
            try:
                db_device = Device.objects.get(spot_device__messenger_id=m_id)
                db_device.add_locations(devices[m_id])
                n += len(devices[m_id])
            except Exception:
                continue
        return n

    def handle(self, *args, **options):
        last_fetch_default = (
            arrow.utcnow().shift(weeks=-1).format("YYYY-MM-DD[T]HH:mm:ssZZ")
        )
        last_fetched = {}
        while True:
            try:
                t0 = time.time()
                feeds = SpotFeed.objects.all()
                n = 0
                for feed in feeds:
                    last_fetch = last_fetched.get(feed.id, last_fetch_default)
                    now = arrow.utcnow().format("YYYY-MM-DD[T]HH:mm:ssZZ")
                    url = (
                        "https://api.findmespot.com/spot-main-web/consumer"
                        f"/rest-api/2.0/public/feed/{feed.feed_id}/message.xml?"
                        f"startDate={last_fetch}&endDate={now}"
                    )
                    last_fetched[feed.id] = now
                    res = requests.get(url)
                    if res.status_code == 200:
                        try:
                            n += self.parse_response(res.text)
                        except Exception:
                            pass
                    time.sleep(2)
                print(f"{n} new positions, sleeping now...")
                time.sleep(max(0, 150 - (time.time() - t0)))
            except KeyboardInterrupt:
                break
        print("Goodbye!")

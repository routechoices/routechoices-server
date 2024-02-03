import time

import arrow
from django.core.management.base import BaseCommand

from routechoices.core.models import Club, Competitor, Device, Event


class Command(BaseCommand):
    help = "Simulate N trackers updating data"

    def add_arguments(self, parser):
        parser.add_argument("--nb-trackers", dest="nb_trackers", type=int, default=1)

    def handle(self, *args, **options):
        nb_trackers = options["nb_trackers"]
        club = Club.objects.create(name="Test trackers", slug="test")
        event = Event.objects.create(
            club=club,
            name="Test",
            slug="test",
            privacy="secret",
            start_date=arrow.utcnow().datetime,
            end_date=arrow.utcnow().shift(hours=1).datetime,
        )
        devs = []
        for i in range(nb_trackers):
            d = Device.objects.create(aid=f"TEST_{i}")
            devs.append(d)
            Competitor.objects.create(
                event=event, name=f"Test {i}", short_name=f"T {i}", device=d
            )
        lat = 0
        lng = 0
        k = 0
        while True:
            try:
                time.sleep(0.1)
                for i, d in enumerate(devs):
                    if (i + k) % 50 == 0:
                        t0 = int(time.time()) - 5
                        locations = ()
                        for j in range(5):
                            locations += (
                                ((t0 + j), lat + i / 100, lng + (k * 5 + j) / 5000),
                            )
                        d.add_locations(locations, save=True)
                k += 1
            except KeyboardInterrupt:
                break
        club.delete()
        for d in devs:
            d.delete()

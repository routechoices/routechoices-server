from django.core.management.base import BaseCommand

from routechoices.core.models import Event
from routechoices.lib.helpers import distance_latlon


class Command(BaseCommand):
    help = "Import race from livelox.com"

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=str)
        parser.add_argument("min_dist", type=float)
        parser.add_argument("max_dist", type=float)

    def handle(self, *args, **options):
        event_id = options["event_id"]
        e = Event.objects.get(aid=event_id)
        nb_del = 0
        for c, start, end in e.iterate_competitors():
            pp = None
            dist = 0
            d_locs = c.device.locations_series if c.device else []
            crop_start = None
            for i, p in enumerate(d_locs):
                if start.timestamp() > p[0]:
                    continue
                if p[0] > end.timestamp():
                    break
                if pp:
                    dist += distance_latlon(
                        {"lat": p[1], "lon": p[2]}, {"lat": pp[1], "lon": pp[2]}
                    )
                if dist > options["max_dist"] * 1000:
                    print(dist)
                    crop_start = p[0]
                    break
                pp = p
            if dist < options["min_dist"] * 1000:
                print(f"Removing {c}")
                nb_del += 1
                c.delete()
            if crop_start:
                d_locs_nb = len(d_locs)
                new_locs = [
                    p for p in d_locs if p[0] < crop_start or p[0] > end.timestamp()
                ]
                locs_rem = d_locs_nb - len(new_locs)
                c.device.locations_series = new_locs
                c.device.save()
                print(f"Cropping {locs_rem} locations for {c}")

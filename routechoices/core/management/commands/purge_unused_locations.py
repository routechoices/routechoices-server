from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from routechoices.core.models import Device


class Command(BaseCommand):
    help = "Delete unused locations after 14 days"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", default=False)
        parser.add_argument("--incremental", action="store_true", default=False)

    def handle(self, *args, **options):
        force = options["force"]
        incremental = options["incremental"]
        deleted_count = 0
        two_weeks_ago = now() - timedelta(days=14)
        devices = Device.objects.all()
        if incremental:
            two_weeks_two_days_ago = now() - timedelta(days=16)
            devices = devices.filter(modification_date__gte=two_weeks_two_days_ago)
        for device in devices:
            orig_pts_count = device.location_count
            device.remove_duplicates(force)
            pts_count_after_deduplication = device.location_count
            locs = device.locations
            periods_used = []
            competitors = device.competitor_set.all()
            for competitor in competitors:
                event = competitor.event
                start = event.start_date
                if competitor.start_time:
                    start = competitor.start_time
                end = None
                end = min(event.end_date, two_weeks_ago)
                if start < end:
                    periods_used.append((start, end))
            valid_indexes = []
            for idx, timestamp in enumerate(locs["timestamps"]):
                is_valid = False
                if timestamp >= two_weeks_ago.timestamp():
                    is_valid = True
                if not is_valid:
                    for p in periods_used:
                        if p[0].timestamp() <= timestamp <= p[1].timestamp():
                            is_valid = True
                            break
                if is_valid:
                    valid_indexes.append(idx)
            dev_del_loc_count_total = orig_pts_count - len(valid_indexes)
            dev_del_loc_count_invalids = pts_count_after_deduplication - len(
                valid_indexes
            )
            if dev_del_loc_count_total:
                if orig_pts_count - pts_count_after_deduplication > 0:
                    self.stdout.write(
                        f"Device {device.aid}, extra {dev_del_loc_count_total} locations, including {orig_pts_count - pts_count_after_deduplication} duplicates"
                    )
                else:
                    self.stdout.write(
                        f"Device {device.aid}, extra {dev_del_loc_count_total} locations"
                    )
            deleted_count += dev_del_loc_count_total
            if force and dev_del_loc_count_invalids:
                new_locs = {
                    "timestamps": [locs["timestamps"][i] for i in valid_indexes],
                    "latitudes": [locs["latitudes"][i] for i in valid_indexes],
                    "longitudes": [locs["longitudes"][i] for i in valid_indexes],
                }
                device.locations = new_locs
                device.save()
        if force:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully removed {deleted_count} Locations")
            )
        else:
            self.stdout.write(f"Would remove {deleted_count} Locations")

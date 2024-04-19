from django.core.management.base import BaseCommand
from django.db.models import Count

from routechoices.core.models import Device


class Command(BaseCommand):
    help = "Remove old images files from storage"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", default=False)

    def handle(self, *args, **options):
        force = options["force"]
        nb_devices = 0
        devices = Device.objects.annotate(
            competitor_count=Count("competitor_set")
        ).filter(
            is_gpx=True,
            competitor_count=0,
            _location_count=0,
        )
        nb_devices = len(devices)
        if nb_devices == 0:
            self.stdout.write(self.style.SUCCESS("No devices to remove!"))
        elif force:
            devices.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully removed {nb_devices} devices")
            )
        else:
            self.stdout.write(f"Would remove {nb_devices} devices")

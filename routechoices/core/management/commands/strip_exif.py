from django.core.management.base import BaseCommand
from routechoices.core.models import Map


class Command(BaseCommand):
    help = 'Strip map images from exif data'

    def handle(self, *args, **options):
        qs = Map.objects.all()
        for raster_map in qs:
            raster_map.strip_exif()
            raster_map.save()
        self.stdout.write(self.style.SUCCESS('Done'))
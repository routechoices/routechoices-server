from django.conf import settings
from django.core.management.base import BaseCommand

from routechoices.core.models import Map
from routechoices.lib.s3 import get_s3_client, s3_delete_key


class Command(BaseCommand):
    help = "Remove old images files from db"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=False)

    def scan_map_directory(self):

        # Should use v2 but wasabi fails to list all files with it
        # paginator = s3.get_paginator('list_objects_v2')
        paginator = self.s3.get_paginator("list_objects")
        kwargs = {
            "Bucket": settings.AWS_S3_BUCKET,
            "Prefix": "maps",
        }
        for page in paginator.paginate(**kwargs):
            try:
                contents = page["Contents"]
            except KeyError:
                break
            for obj in contents:
                key = obj["Key"]
                yield key

    def process_image_file(self, image_name, dry_run):
        if image_name not in self.maps_image_paths:
            self.n_image_removed += 1
            self.stdout.write(f"File {image_name} is unused")
            if not dry_run:
                s3_delete_key(image_name, settings.AWS_S3_BUCKET)
        else:
            self.n_image_keeped += 1
            self.keeped.add(image_name)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.maps_image_paths = set(Map.objects.all().values_list("image", flat=True))
        self.n_image_removed = 0
        self.keeped = set()
        self.n_image_keeped = 0
        self.s3 = get_s3_client()
        for filename in self.scan_map_directory():
            self.process_image_file(filename, dry_run)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully removed {self.n_image_removed} files, keeping {self.n_image_keeped}"
                )
            )
        else:
            self.stdout.write(
                f"Would remove {self.n_image_removed} files, keeping {self.n_image_keeped}"
            )

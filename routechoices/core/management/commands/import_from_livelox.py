from io import BytesIO
from urllib.parse import parse_qs, urlparse

import requests
from django.core.management.base import BaseCommand
from PIL import Image

from routechoices.core.tasks import EventImportError, import_single_event_from_livelox


class Command(BaseCommand):
    help = "Import race from livelox.com"

    def add_arguments(self, parser):
        parser.add_argument("event_ids", nargs="+", type=str)
        parser.add_argument("--task", action="store_true", default=False)

    def handle(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                if event_id.startswith("https://www.livelox.com/"):
                    try:
                        parsed_url = urlparse(event_id)
                        event_id = parse_qs(parsed_url.query).get("classId")[0]
                    except Exception:
                        self.stderr.write("Could not parse url")
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_livelox(event_id)
                else:
                    import_single_event_from_livelox.now(event_id)
            except EventImportError:
                self.stderr.write(f"Could not import event {event_id}")
                continue

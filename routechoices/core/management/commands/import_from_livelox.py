from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand

from routechoices.core.bg_tasks import (
    EventImportError,
    import_single_event_from_livelox,
)


class Command(BaseCommand):
    help = "Import race from livelox.com"

    def add_arguments(self, parser):
        parser.add_argument("event_ids", nargs="+", type=str)
        parser.add_argument("--task", action="store_true", default=False)

    def handle(self, *args, **options):
        for event_id in options["event_ids"]:
            leg = None
            try:
                if event_id.startswith("https://www.livelox.com/"):
                    try:
                        parsed_url = urlparse(event_id)
                        event_id = parse_qs(parsed_url.query).get("classId")[0]
                    except Exception:
                        self.stderr.write("Could not parse url")
                    else:
                        try:
                            leg = parse_qs(parsed_url.query).get("relayLeg")[0]
                        except Exception:
                            pass
                elif "," in event_id:
                    event_id, leg = event_id.split(",", 1)
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_livelox(event_id, leg)
                else:
                    import_single_event_from_livelox.now(event_id, leg)
            except EventImportError as e:
                self.stderr.write(f"Could not import event {event_id}: {e}")
                continue

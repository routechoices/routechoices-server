from django.core.management.base import BaseCommand

from routechoices.core.bg_tasks import (
    import_single_event_from_gps_seuranta,
    import_single_event_from_livelox,
    import_single_event_from_loggator,
    import_single_event_from_otracker,
    import_single_event_from_sportrec,
    import_single_event_from_tractrac,
)
from routechoices.lib.third_party_downloader import EventImportError


class Command(BaseCommand):
    help = "Import event from 3rd party"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            title="sub-commands",
            required=True,
        )
        gpsseuranta_parser = subparsers.add_parser(
            "gpsseuranta",
            help="Import from gpsseuranta",
        )
        gpsseuranta_parser.set_defaults(method=self.gpsseuranta)

        livelox_parser = subparsers.add_parser(
            "livelox",
            help="Import from livelox",
        )
        livelox_parser.set_defaults(method=self.livelox)

        loggator_parser = subparsers.add_parser(
            "loggator",
            help="Import from loggator",
        )
        loggator_parser.set_defaults(method=self.loggator)

        otracker_parser = subparsers.add_parser(
            "otracker",
            help="Import from otracker",
        )
        otracker_parser.set_defaults(method=self.otracker)

        sportrec_parser = subparsers.add_parser(
            "sportrec",
            help="Import from sportrec",
        )
        sportrec_parser.set_defaults(method=self.sportrec)

        tractrac_parser = subparsers.add_parser(
            "tractrac",
            help="Import from tractrac",
        )
        tractrac_parser.set_defaults(method=self.tractrac)

        parser.add_argument("event_ids", nargs="+", type=str)
        parser.add_argument("--task", action="store_true", default=False)

    def handle(self, *args, method, **options):
        method(*args, **options)

    def gpsseuranta(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_gps_seuranta(event_id)
                else:
                    import_single_event_from_gps_seuranta.now(event_id)
            except EventImportError:
                self.stderr.write(f"Could not import event {event_id}")
                continue

    def livelox(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_livelox(event_id)
                else:
                    import_single_event_from_livelox.now(event_id)
            except EventImportError:
                self.stderr.write(f"Could not import event {event_id}")
                continue

    def loggator(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_loggator(event_id)
                else:
                    import_single_event_from_loggator.now(event_id)
            except EventImportError:
                self.stderr.write(f"Could not import event {event_id}")
                continue

    def otracker(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_otracker(event_id)
                else:
                    import_single_event_from_otracker.now(event_id)
            except EventImportError:
                self.stderr.write(f"Could not import event {event_id}")
                continue

    def sportrec(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_sportrec(event_id)
                else:
                    import_single_event_from_sportrec.now(event_id)
            except EventImportError as e:
                self.stderr.write(f"Could not import event {event_id}: {str(e)}")
                continue

    def tractrac(self, *args, **options):
        for event_id in options["event_ids"]:
            try:
                self.stdout.write(f"Importing event {event_id}")
                if options["task"]:
                    import_single_event_from_tractrac(event_id)
                else:
                    import_single_event_from_tractrac.now(event_id)
            except EventImportError:
                self.stderr.write(f"Could not import event {event_id}")
                continue

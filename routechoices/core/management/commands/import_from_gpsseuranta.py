from django.core.management.base import BaseCommand

from routechoices.core.tasks import (
    import_single_event_from_gps_seuranta,
    EventImportError,
)


class Command(BaseCommand):
    help = 'Import race from GPS Seuranta'

    def add_arguments(self, parser):
        parser.add_argument('event_ids', nargs='+', type=str)
        parser.add_argument('--task', action='store_true', default=False)

    def handle(self, *args, **options):
        for event_id in options['event_ids']:
            try:
                self.stdout.write('Importing event %s' % event_id)
                if options['task']:
                    import_single_event_from_gps_seuranta(event_id)
                else:
                    import_single_event_from_gps_seuranta.now(event_id)
            except EventImportError:
                self.stderr.write('Could not import event %s' % event_id)
                continue

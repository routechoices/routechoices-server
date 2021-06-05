import orjson as json

from django.core.management.base import BaseCommand

from routechoices.core.models import Club


class Command(BaseCommand):
    help = 'Set all existing events inside the free plans so that they can be modified by their club admins'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', default=False)

    def handle(self, *args, **options):
        force = options['force']
        clubs = Club.objects.all()
        for club in clubs:
            print('Club %s' % (club.name))
            events = club.events.all()
            free_events = [
                {
                    'id': event.aid,
                    'created_at': event.creation_date.timestamp()
                } for event in events
            ]
            n_event_archived = events.count()
            if force and free_events:
                club.free_plan_events_raw = str(json.dumps(free_events), 'utf-8')
                club.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        'Successfully set %d events in free plans' % n_event_archived
                    )
                )
            elif free_events:
                self.stdout.write('Would set %d events in free plans' % n_event_archived)
            else:
                self.stdout.write('No events')


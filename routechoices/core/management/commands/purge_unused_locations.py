from django.core.management.base import BaseCommand
from routechoices.core.models import Location, Event

from datetime import timedelta
from django.db.backends.signals import connection_created
from django.utils.timezone import now


def set_timeout_on_new_conn(sender, connection, **kwargs):
    """
        Rig django to set statement timeout for each new connection based on the config
    """
    timeout_to_set = 120000     # Set timeout to 2 minutes

    with connection.cursor() as cursor:
        cursor.execute("set statement_timeout={0}".format(timeout_to_set))


connection_created.connect(set_timeout_on_new_conn)


class Command(BaseCommand):
    help = 'Delete unused locations after 14 days'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', default=False)

    def handle(self, *args, **options):
        force = options['force']
        qs = Location.objects.filter(datetime__lt=now() - timedelta(days=14))
        events = Event.objects.all()
        for event in events:
            for competitor in event.competitors.all():
                if competitor.device:
                    filter_args = {
                        'device': competitor.device,
                        'datetime__gte': max(
                            competitor.start_time,
                            event.start_date
                        )
                    }
                    if event.end_date:
                        filter_args['datetime__lte'] = event.end_date
                    qs = qs.exclude(**filter_args)
        if force:
            deleted_count, _ = qs.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    'Successfully removed %d Locations' % deleted_count
                )
            )
        else:
            self.stdout.write('Would remove %d Locations' % qs.count())

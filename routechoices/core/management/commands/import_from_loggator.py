import requests
import arrow
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from routechoices.core.models import Map, Club, Event, Device, Competitor, \
    Location
from routechoices.lib.helper import short_random_key


def get_loggator_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='loggator',
        defaults={
            'name':'Loggator'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


LOGGATOR_EVENT_URL = 'https://loggator.com/api/events/'


class EventImportError(Exception):
    pass


class MapImportError(Exception):
    pass


class Command(BaseCommand):
    help = 'Import race from loggator.com'

    def add_arguments(self, parser):
        parser.add_argument('event_ids', nargs='+', type=str)

    def import_map(self, club, map_data, name):
        map_url = map_data['url']
        r = requests.get(map_url)
        map_model, created = Map.objects.get_or_create(
            name=name,
            club=club,
        )
        if not created:
            return map_model
        if r.status_code != 200:
            raise MapImportError('API returned error code')
        map_file = ContentFile(r.content)
        coordinates = ','.join([
            str(map_data['coordinates']['topLeft']['lat']),
            str(map_data['coordinates']['topLeft']['lng']),
            str(map_data['coordinates']['topRight']['lat']),
            str(map_data['coordinates']['topRight']['lng']),
            str(map_data['coordinates']['bottomRight']['lat']),
            str(map_data['coordinates']['bottomRight']['lng']),
            str(map_data['coordinates']['bottomLeft']['lat']),
            str(map_data['coordinates']['bottomLeft']['lng'])
        ])
        map_model.image.save('imported_image', map_file, save=False)
        map_model.corners_coordinates = coordinates
        map_model.save()
        return map_model

    def import_single_event(self, club, event_id):
        event_url = LOGGATOR_EVENT_URL + event_id + '.json'
        r = requests.get(event_url)
        if r.status_code != 200:
            raise EventImportError('API returned error code')
        event_data = r.json()
        event_map = None
        event_map_data = event_data.get('map')
        event, created = Event.objects.get_or_create(
            club=club,
            slug=event_data['event']['slug'],
            defaults={
                'name': event_data['event']['name'],
                'start_date': arrow.get(event_data['event']['start_date']).datetime,
                'end_date': arrow.get(event_data['event']['end_date']).datetime,
            }
        )
        if not created:
            return
        if event_map_data:
            try:
                event_map = self.import_map(
                    club,
                    event_map_data,
                    event_data['event']['name']
                )
            except MapImportError:
                pass
            if event_map:
                event.map = event_map
                event.save()

        locs = []
        device_map = {}
        r = requests.get(event_data['tracks'])
        if r.status_code == 200:
            tracks_raw = r.json()['data']
            tracks_pts = tracks_raw.split(';')
            for pt in tracks_pts:
                d = pt.split(',')
                if not device_map.get(int(d[0])):
                    device_map[int(d[0])] = Device.objects.create(
                        aid=short_random_key() + '_LOG',
                        is_gpx=True,
                    )
                locs.append(
                    Location(
                        device=device_map[int(d[0])],
                        latitude=float(d[1]),
                        longitude=float(d[2]),
                        datetime=arrow.get(int(d[4])).datetime
                    )
                )
            Location.objects.bulk_create(locs)

        for c_data in event_data['competitors']:
            Competitor.objects.create(
                name=c_data['name'],
                short_name=c_data['shortname'],
                start_time=arrow.get(c_data['start_time']).datetime,
                device=device_map.get(c_data['device_id']),
                event=event,
            )
        return event



    def handle(self, *args, **options):
        club = get_loggator_club()
        for event_id in options['event_ids']:
            try:
                self.import_single_event(club, event_id)
            except EventImportError:
                print('Could not import event %s' % event_id)
                continue

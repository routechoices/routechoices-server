import requests
import arrow
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from routechoices.core.models import Map, Club, Event, Device, Competitor, \
    Location
from routechoices.lib.helper import short_random_key, \
    three_point_calibration_to_corners


def get_gpsseuranta_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='gpsseuranta',
        defaults={
            'name': 'GPS Seuranta'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


GPSSEURANTA_EVENT_URL = 'http://www.tulospalvelu.fi/gps/'


class EventImportError(Exception):
    pass


class MapImportError(Exception):
    pass


class Command(BaseCommand):
    help = 'Import race from GPS Seuranta'

    def add_arguments(self, parser):
        parser.add_argument('event_ids', nargs='+', type=str)

    def import_map(self, club, map_data, name, event_id):
        map_url = GPSSEURANTA_EVENT_URL + event_id + '/map'
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
        with Image.open(map_file) as img:
            width, height = img.size
        corners = three_point_calibration_to_corners(
            map_data,
            width,
            height
        )
        coordinates = ','.join([
            str(x) for x in corners
        ])
        map_model.image.save('imported_image', map_file, save=False)
        map_model.corners_coordinates = coordinates
        map_model.save()
        return map_model

    def decode_track_line(self, device, data, timezone_offset, min_date=None, max_date=None):
        ls = []
        if not data:
            return [], min_date, max_date
        o_pt = data[0].split('_')
        prev_loc = Location(
            device=device,
            datetime=arrow.get(int(o_pt[0]) + 1136073600 + int(timezone_offset) * 60).datetime,
            longitude=int(o_pt[1]) * 2.0 / 1e5,
            latitude=int(o_pt[2]) * 1.0 / 1e5,
        )
        ls.append(prev_loc)
        if min_date is None or prev_loc.datetime < min_date:
            min_date = prev_loc.datetime
        if max_date is None or prev_loc.datetime > min_date:
            max_date = prev_loc.datetime
        for p in data[1:]:
            if len(p) < 3:
                continue
            if '_' in p:
                pt = p.split('_')
                dt = int(pt[0])
                dlng = int(pt[1])
                dlat = int(pt[2])
            else:
                chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                dt = chars.index(p[0]) - 31
                dlng = chars.index(p[1]) - 31
                dlat = chars.index(p[2]) - 31
            new_loc = Location(
                device=device,
                datetime=arrow.get(prev_loc.timestamp + dt).datetime,
                longitude=((prev_loc.longitude * 50000) + dlng) / 50000,
                latitude=((prev_loc.latitude * 100000) + dlat) / 100000,
            )
            ls.append(new_loc)
            prev_loc = new_loc
            if prev_loc.datetime < min_date:
                min_date = prev_loc.datetime
            if prev_loc.datetime > min_date:
                max_date = prev_loc.datetime
        return ls, min_date, max_date

    def import_single_event(self, club, event_id):
        event_url = GPSSEURANTA_EVENT_URL + event_id + '/init.txt'
        r = requests.get(event_url)
        if r.status_code != 200:
            raise EventImportError('API returned error code')
        event_raw_data = r.text
        event_data = {'COMPETITOR':[]}
        for line in event_raw_data.split('\n'):
            try:
                key, val = line.strip().split(':')
                if key != 'COMPETITOR':
                    event_data[key] = val
                else:
                    event_data[key].append(val)
            except ValueError:
                continue

        locs = []
        event_start_date = None
        event_end_date = None
        device_map = {}
        event_tracks_url = GPSSEURANTA_EVENT_URL + event_id + '/data.lst'
        r = requests.get(event_tracks_url)
        if r.status_code == 200:
            tracks_raw = r.text
            for line in tracks_raw.split('\n'):
                d = line.strip().split('.')
                if len(d) == 0:
                    continue
                dev_id = d[0]
                if '_' in dev_id:
                    dev_id, _ = dev_id.split('_', 1)
                if not device_map.get(dev_id):
                    device_map[dev_id] = Device.objects.create(
                        aid=short_random_key() + '_SEU',
                        is_gpx=True,
                    )
                dev = device_map[dev_id]
                pts, event_start_date, event_end_date = self.decode_track_line(
                    dev,
                    d[1:],
                    event_data.get('TIMEZONE', 0),
                    event_start_date,
                    event_end_date,
                )
                locs += pts

        event, created = Event.objects.get_or_create(
            club=club,
            slug=event_id,
            defaults={
                'name': event_data['RACENAME'],
                'start_date': event_start_date,
                'end_date': event_end_date,
            }
        )
        if not created:
            for dev in device_map:
                device_map[dev].delete()
            return

        event_map_data = event_data.get('CALIBRATION')
        event_map = None
        try:
            event_map = self.import_map(club, event_map_data, event_data['RACENAME'], event_id)
        except MapImportError:
            pass

        if event_map:
            event.map = event_map
            event.save()

        if locs:
            Location.objects.bulk_create(locs)

        for c_raw in event_data['COMPETITOR']:
            c_data = c_raw.strip().split('|')
            start_time = arrow.get(
                c_data[1] + c_data[2],
                'YYYYMMDDHHmmss'
            ).shift(
                minutes=-int(event_data.get('TIMEZONE', 0))
            ).datetime
            Competitor.objects.create(
                name=c_data[3],
                short_name=c_data[4],
                start_time=start_time,
                device=device_map[c_data[0]],
                event=event,
            )
        return event

    def handle(self, *args, **options):
        club = get_gpsseuranta_club()
        for event_id in options['event_ids']:
            try:
                self.import_single_event(club, event_id)
            except EventImportError:
                print('Could not import event %s' % event_id)
                continue
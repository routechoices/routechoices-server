from os import EX_CANTCREAT
import requests
import arrow
import tempfile
import json
from bs4 import BeautifulSoup

from uuid import UUID
from PIL import Image, ImageDraw
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from io import BytesIO
import math
from background_task import background

from routechoices.core.models import Map, Event, Device, Competitor, Club
from routechoices.lib.helpers import initial_of_name, short_random_key, safe32encode, \
    three_point_calibration_to_corners, compute_corners_from_kml_latlonbox, project
from routechoices.lib.mtb_decoder import MtbDecoder
from routechoices.lib.tractrac_ws_decoder import TracTracWSReader

GPSSEURANTA_EVENT_URL = 'http://www.tulospalvelu.fi/gps/'
LOGGATOR_EVENT_URL = 'https://loggator.com/api/events/'


class EventImportError(Exception):
    pass


class MapImportError(Exception):
    pass


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


def get_livelox_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='livelox',
        defaults={
            'name': 'Livelox'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


def get_sportrec_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='sportrec',
        defaults={
            'name': 'SportRec'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club

def get_otracker_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='otracker',
        defaults={
            'name': 'OTracker'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


def get_loggator_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='loggator',
        defaults={
            'name': 'Loggator'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


def get_tractrac_club():
    admins = User.objects.filter(is_superuser=True)
    club, created = Club.objects.get_or_create(
        slug='tractrac',
        defaults={
            'name': 'TracTrac'
        }
    )
    if created:
        club.admins.set(admins)
        club.save()
    return club


def import_map_from_gps_seuranta(club, map_data, name, event_id):
    map_url = GPSSEURANTA_EVENT_URL + event_id + '/map'
    r = requests.get(map_url)
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    if r.status_code != 200:
        if created:
            map_model.delete()
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


def import_map_from_sportrec(club, event_id, map_data, name):
    map_url = f'https://sportrec.eu/ui/nsport_admin/index.php?r=api/map&id={event_id}'
    r = requests.get(map_url)
    map_file = ContentFile(r.content)
    if r.status_code != 200:
        raise MapImportError('API returned error code')
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    coords = map_data['map_box']
    n, e, s, w = [float(x) for x in coords.replace('(', '').replace(')', '').split(',')]

    nw, ne, se, sw = compute_corners_from_kml_latlonbox(n, e, s, w, -float(map_data['map_angle']))
    corners_coords = f'{nw[0]},{nw[1]},{ne[0]},{ne[1]},{se[0]},{se[1]},{sw[0]},{sw[1]}'
    map_model.image.save('imported_image', map_file, save=False)
    map_model.corners_coordinates = corners_coords
    map_model.save()
    return map_model


def import_map_from_tractrac(club, map_info, name):
    map_url = map_info.get('location')
    r = requests.get(map_url)
    
    if r.status_code != 200:
        raise MapImportError('API returned error code')
    map_file = ContentFile(r.content)
    with Image.open(map_file) as img:
        width, height = img.size
    corners = three_point_calibration_to_corners(
        f"{map_info['long1']}|{map_info['lat1']}|{map_info['x1']}|{map_info['y1']}|{map_info['long2']}|{map_info['lat2']}|{map_info['x2']}|{map_info['y2']}|{map_info['long3']}|{map_info['lat3']}|{map_info['x3']}|{map_info['y3']}",
        width,
        height
    )
    coordinates = ','.join([
        str(x) for x in corners
    ])
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    map_model.image.save('imported_image', map_file, save=False)
    map_model.corners_coordinates = coordinates
    map_model.save()
    return map_model


def import_map_from_otracker(club, map_data, name):
    map_url = map_data['url']
    r = requests.get(map_url)
    if r.status_code != 200:
        raise MapImportError('API returned error code')
    map_file = ContentFile(r.content)
    coordinates = f"{map_data['options']['tl']['lat']},{map_data['options']['tl']['lon']},{map_data['options']['tr']['lat']},{map_data['options']['tr']['lon']},{map_data['options']['br']['lat']},{map_data['options']['br']['lon']},{map_data['options']['bl']['lat']},{map_data['options']['bl']['lon']}"
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    map_model.image.save('imported_image', map_file, save=False)
    map_model.corners_coordinates = coordinates
    map_model.save()
    return map_model


def decode_track_line(device, data, min_date=None, max_date=None):
    if not data:
        return min_date, max_date
    o_pt = data[0].split('_')
    if o_pt[0] == '*' or o_pt[1] == '*' or o_pt[2] == '*':
        return min_date, max_date
    t = arrow.get(int(o_pt[0]) + 1136073600).datetime
    prev_loc = {
        'lat': int(o_pt[2]) * 1.0 / 1e5,
        'lon': int(o_pt[1]) * 2.0 / 1e5,
        'datetime': t,
    }
    device.add_location(
        prev_loc['lat'],
        prev_loc['lon'],
        t.timestamp(),
        False
    )
    if min_date is None or t < min_date:
        min_date = t
    if max_date is None or t > max_date:
        max_date = t
    loc_array = []
    for p in data[1:]:
        if len(p) < 3:
            continue
        if '_' in p:
            pt = p.split('_')
            if pt[0] == '*':
                pt[0] = 0
            if pt[1] == '*':
                pt[1] = 0
            if pt[2] == '*':
                pt[2] = 0
            dt = int(pt[0])
            dlon = int(pt[1])
            dlat = int(pt[2])
        else:
            chars = \
                '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' + \
                'abcdefghijklmnopqrstuvwxyz'
            dt = chars.index(p[0]) - 31
            dlon = chars.index(p[1]) - 31
            dlat = chars.index(p[2]) - 31
        t = arrow.get(prev_loc['datetime'].timestamp() + dt).datetime

        prev_loc = {
            'lat': ((prev_loc['lat'] * 100000) + dlat) / 100000,
            'lon': ((prev_loc['lon'] * 50000) + dlon) / 50000,
            'datetime': t,
        }
        loc_array.append({
            'timestamp': t.timestamp(),
            'latitude': prev_loc['lat'],
            'longitude': prev_loc['lon'],
        })
        if t < min_date:
            min_date = t
        if t > max_date:
            max_date = t
    device.add_locations(loc_array, False)
    return min_date, max_date


@background(schedule=0)
def import_single_event_from_gps_seuranta(event_id):
    club = get_gpsseuranta_club()
    event_url = GPSSEURANTA_EVENT_URL + event_id + '/init.txt'
    r = requests.get(event_url)
    if r.status_code != 200:
        raise EventImportError('API returned error code')
    event_raw_data = r.text
    event_data = {'COMPETITOR': []}
    for line in event_raw_data.split('\n'):
        try:
            key, val = line.strip().split(':')
            if key != 'COMPETITOR':
                event_data[key] = val
            else:
                event_data[key].append(val)
        except ValueError:
            continue

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
            event_start_date, event_end_date = decode_track_line(
                dev,
                d[1:],
                event_start_date,
                event_end_date,
            )

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
        event_map = import_map_from_gps_seuranta(
            club,
            event_map_data,
            event_data['RACENAME'],
            event_id
        )
    except MapImportError:
        pass

    if event_map:
        event.map = event_map
        event.save()

    for c_raw in event_data['COMPETITOR']:
        c_data = c_raw.strip().split('|')
        start_time_raw = c_data[1] + c_data[2]
        if len(start_time_raw) == 12:
            start_time = arrow.get(
                c_data[1] + c_data[2],
                'YYYYMMDDHHmm'
            )
        else:
            start_time = arrow.get(
                c_data[1] + c_data[2],
                'YYYYMMDDHHmmss'
            )
        start_time = start_time.shift(
            minutes=-int(event_data.get('TIMEZONE', 0))
        ).datetime
        Competitor.objects.create(
            name=c_data[3],
            short_name=c_data[4],
            start_time=start_time,
            device=device_map.get(c_data[0]),
            event=event,
        )
        dev = device_map.get(c_data[0])
        if dev:
            dev.save()
    return event


def import_map_from_loggator(club, map_data, name):
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
    try:
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
    except Exception:
        map_model.delete()
        raise MapImportError('Could not import map')
    return map_model


@background(schedule=0)
def import_single_event_from_loggator(event_id):
    club = get_loggator_club()
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
            'start_date':
                arrow.get(event_data['event']['start_date']).datetime,
            'end_date':
                arrow.get(event_data['event']['end_date']).datetime,
        }
    )
    if not created:
        return
    if event_map_data:
        try:
            event_map = import_map_from_loggator(
                club,
                event_map_data,
                event_data['event']['name']
            )
        except MapImportError:
            pass
        if event_map:
            event.map = event_map
            event.save()

    device_map = {}
    loc_array_map = {}
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
                loc_array_map[int(d[0])] = []
            loc_array_map[int(d[0])].append({
                'timestamp': arrow.get(int(d[4])).timestamp(),
                'latitude': float(d[1]),
                'longitude': float(d[2]),
            })

    for c_data in event_data['competitors']:
        Competitor.objects.create(
            name=c_data['name'],
            short_name=c_data['shortname'],
            start_time=arrow.get(c_data['start_time']).datetime,
            device=device_map.get(c_data['device_id']),
            event=event,
        )
        dev = device_map.get(c_data['device_id'])
        if dev:
            dev.add_locations(loc_array_map.get(c_data['device_id']))
    return event


@background(schedule=0)
def import_single_event_from_tractrac(event_id):
    club = get_tractrac_club()
    r = requests.get(event_id)
    if r.status_code != 200:
        raise EventImportError('API returned error code')
    event_data = r.json()
    event_name = event_data['eventName'] + ' - ' + event_data['raceName']
    slug = safe32encode(UUID(hex=event_data['raceId']).bytes)
    event, created = Event.objects.get_or_create(
        club=club,
        slug=slug,
        defaults={
            'name': event_name,
            'start_date':
                arrow.get(event_data['raceTrackingStartTime']).datetime,
            'end_date':
                arrow.get(event_data['raceTrackingEndTime']).datetime,
        }
    )
    if not created:
        return
    maps = [m for m in event_data['maps'] if m.get('is_default_loaded')]
    map_model = None
    if maps:  
        map_info = maps[0]
        map_model = import_map_from_tractrac(club, map_info, event_name)
    if map_model:
        event.map = map_model
        event.save()
    
    device_map = None
    mtb_url = event_data['parameters'].get('stored-uri')
    if mtb_url and not mtb_url.startswith('tcp:') and '.mtb' in mtb_url:
        data_url = event_data['parameters'].get('stored-uri')
        if not data_url.startswith('http'):
            data_url = f'http:{data_url}'
        response = requests.get(data_url, stream=True)
        if response.status_code == 200:
            lf = tempfile.NamedTemporaryFile()
            for block in response.iter_content(1024 * 8):
                if not block:
                    break
                lf.write(block)
            lf.flush()
            try:
                device_map = MtbDecoder(lf.name).decode()
            except:
                if not event_data['parameters'].get('ws-uri'):
                    event.delete()
                    raise EventImportError('Could not decode mtb')
            finally:
                lf.close()
    
    if event_data['parameters'].get('ws-uri') and not device_map:
        try:
            url = event_data['parameters'].get('ws-uri')+'/'+event_data['eventType']+'?snapping=false'
            device_map = TracTracWSReader().read_data(url)
        except:
            event.delete()
            raise EventImportError('Could not decode ws data')
    
    if not device_map:
        event.delete()
        raise EventImportError('Did not figure out how to get data')

    for c_data in event_data['competitors'].values():
        st = c_data.get('startTime')
        if not st:
            st = event_data['raceTrackingStartTime']
        dev = device_map.get(c_data['uuid'])
        dev_model = None
        if dev:
            dev_model = Device.objects.create(
                aid=short_random_key() + '_TRC',
                is_gpx=True,
            )
            dev_model.add_locations(dev)
        Competitor.objects.create(
            name=c_data['name'],
            short_name=c_data['nameShort'],
            start_time=arrow.get(st).datetime,
            device=dev_model,
            event=event,
        )


@background(schedule=0)
def import_single_event_from_sportrec(event_id):
    club = get_sportrec_club()
    r = requests.get(f'https://sportrec.eu/ui/nsport_admin/index.php?r=api/competition&id={event_id}')
    if r.status_code != 200:
        raise EventImportError('API returned error code')
    event_data = r.json()
    event_name = event_data['competition']['title']
    slug = event_id
    event, created = Event.objects.get_or_create(
        club=club,
        slug=slug,
        defaults={
            'name': event_name,
            'start_date':
                arrow.get(event_data['competition']['time_start']).datetime,
            'end_date':
                arrow.get(event_data['competition']['time_finish']).datetime,
        }
    )
    if not created:
        return
    map_model = None
    if event_data['hasMap']:
        map_model = import_map_from_sportrec(club, event_id, event_data['track'], event_name)
    if map_model:
        event.map = map_model
        event.save()
    data_url = f'https://sportrec.eu/ui/nsport_admin/index.php?r=api/history&id={event_id}'
    response = requests.get(data_url, stream=True)
    if response.status_code != 200:
        event.delete()
        raise EventImportError('API returned error code')
    lf = tempfile.NamedTemporaryFile()
    for block in response.iter_content(1024 * 8):
        if not block:
            break
        lf.write(block)
    lf.flush()
    try:
        with open(lf.name, 'r') as f:
            device_map = {}
            device_data = json.load(f)
            for d in device_data['locations']:
                device_map[d['device_id']] = [{'timestamp': float(x['aq'])/1e3, 'latitude': float(x['lat']), 'longitude': float(x['lon'])} for x in d['locations']]
    except Exception:
        event.delete()
        raise EventImportError('Could not decode data')
    lf.close()

    for c_data in event_data['participants']:
        st = c_data.get('time_start')
        if not st:
            st = event_data['competition']['time_start']
        dev = device_map.get(c_data['device_id'])
        dev_model = None
        if dev:
            dev_model = Device.objects.create(
                aid=short_random_key() + '_SPR',
                is_gpx=True,
            )
            dev_model.add_locations(dev)
        Competitor.objects.create(
            name=c_data['fullname'],
            short_name=c_data['shortname'],
            start_time=arrow.get(st).datetime,
            device=dev_model,
            event=event,
        )


@background(schedule=0)
def import_single_event_from_otracker(event_id):
    club = get_otracker_club()
    rp = requests.get(f'https://otracker.lt/events/{event_id}')
    if rp.status_code != 200:
        raise EventImportError('API returned error code')
    soup = BeautifulSoup(rp.text, 'html.parser')
    event_name = soup.find('title').string[:-13]
    r = requests.get(f'https://otracker.lt/data/events/{event_id}')
    if r.status_code != 200:
        raise EventImportError('API returned error code')
    event_data = r.json()
    ft = event_data['event']['replay_time']['from_ts']
    slug = safe32encode(UUID(hex=event_id).bytes)
    event, created = Event.objects.get_or_create(
        club=club,
        slug=slug,
        defaults={
            'name': event_name,
            'start_date':
                arrow.get(event_data['event']['replay_time']['from_ts']).datetime,
            'end_date':
                arrow.get(event_data['event']['replay_time']['to_ts']).datetime,
        }
    )
    if not created:
        return
    map_model = None
    map_model = import_map_from_otracker(club, event_data['event']['map_image'], event_name)
    if map_model:
        event.map = map_model
        event.save()

    data_url = f'https://otracker.lt/data/locations/history/{event_id}?map_type=tileimage'
    response = requests.get(data_url, stream=True)
    if response.status_code != 200:
        event.delete()
        raise EventImportError('API returned error code')
    lf = tempfile.NamedTemporaryFile()
    for block in response.iter_content(1024 * 8):
        if not block:
            break
        lf.write(block)
    lf.flush()
    try:
        with open(lf.name, 'r') as f:
            orig_device_map = json.load(f)
            device_map = {}
            for d in orig_device_map.keys():
                device_map[d] = [{'timestamp': x['fix_time']+ft, 'latitude': x['lat'], 'longitude': x['lon']} for x in orig_device_map[d]]
    except Exception:
        event.delete()
        raise EventImportError('Could not decode data')
    lf.close()

    for c_data in event_data['competitors'].values():
        st = c_data.get('sync_offset') + ft
        dev = device_map.get(str(c_data['id']))
        dev_model = None
        if dev:
            dev_model = Device.objects.create(
                aid=short_random_key() + '_OTR',
                is_gpx=True,
            )
            dev_model.add_locations(dev)
        Competitor.objects.create(
            name=c_data['name'],
            short_name=c_data['short_name'],
            start_time=arrow.get(st).datetime,
            device=dev_model,
            event=event,
        )


def draw_livelox_route(name, club, url, bound, routes, res):
    map_model, created = Map.objects.get_or_create(
        name=name,
        club=club,
    )
    if not created:
        return map_model
    r = requests.get(url)
    if r.status_code != 200:
        if created:
            map_model.delete()
        raise MapImportError('API returned error code')
    img_blob = ContentFile(r.content)
    with Image.open(img_blob).convert("RGBA") as img:
        course = Image.new("RGBA", img.size, (255, 255, 255, 0))
        coordinates = [f"{b['latitude']},{b['longitude']}" for b in bound[::-1]]
        map_model.corners_coordinates = ','.join(coordinates)
        map_model.image.save('imported_image', img_blob, save=False)
        draw = ImageDraw.Draw(course)
        circle_size = int(40 * res)
        line_width = int(8 * res)
        line_color = (128, 0, 128, 180)
        for route in routes:
            ctrls = [map_model.wsg84_to_map_xy(c['control']['position']['latitude'], c['control']['position']['longitude']) for c in route]
            for i in range(len(ctrls) - 1):
                if ctrls[i][0] == ctrls[i+1][0]:
                    ctrls[i][0] -= 0.0001
                start_from_a = ctrls[i][0] < ctrls[i+1][0]
                pt_a = ctrls[i] if start_from_a else ctrls[i+1]
                pt_b = ctrls[i] if not start_from_a else ctrls[i+1]
                angle = math.atan((pt_b[1] - pt_a[1]) / (pt_b[0] - pt_a[0]))
                if i == 0:
                    pt_s = pt_a if start_from_a else pt_b
                    draw.line(
                        [
                            int(pt_s[0] - (-1 if start_from_a else 1) * circle_size * math.cos(angle)), int(pt_s[1] - (-1 if start_from_a else 1) * circle_size * math.sin(angle)),
                            int(pt_s[0] - (-1 if start_from_a else 1) * circle_size * math.cos(angle + 2 * math.pi / 3)), int(pt_s[1] - (-1 if start_from_a else 1) * circle_size * math.sin(angle + 2 * math.pi / 3)),
                            int(pt_s[0] - (-1 if start_from_a else 1) * circle_size * math.cos(angle - 2 * math.pi / 3)), int(pt_s[1] - (-1 if start_from_a else 1) * circle_size * math.sin(angle - 2 * math.pi / 3)),
                            int(pt_s[0] - (-1 if start_from_a else 1) * circle_size * math.cos(angle)), int(pt_s[1] - (-1 if start_from_a else 1) * circle_size * math.sin(angle))
                        ],
                        fill=line_color,
                        width=line_width,
                        joint='curve'
                    )
                draw.line(
                    [
                        int(pt_a[0] + circle_size * math.cos(angle)), int(pt_a[1] + circle_size * math.sin(angle)),
                        int(pt_b[0] - circle_size * math.cos(angle)), int(pt_b[1] - circle_size * math.sin(angle))
                    ],
                    fill=line_color,
                    width=line_width
                )
                pt_o = pt_b if start_from_a else pt_a
                draw.ellipse(
                    [
                        int(pt_o[0] - circle_size), int(pt_o[1] - circle_size),
                        int(pt_o[0] + circle_size), int(pt_o[1] + circle_size)
                    ],
                    outline=line_color,
                    width=line_width
                )
                if i == (len(ctrls) - 2):
                    inner_circle_size = int(30 * res)
                    draw.ellipse(
                        [
                            int(pt_o[0] - inner_circle_size), int(pt_o[1] - inner_circle_size),
                            int(pt_o[0] + inner_circle_size), int(pt_o[1] + inner_circle_size)
                        ],
                        outline=line_color,
                        width=line_width
                    )
        out_buffer = BytesIO()
        params = {
            'dpi': (72, 72),
        }
        out = Image.alpha_composite(img, course)
        out.save(out_buffer, 'PNG', **params)
        out_buffer.seek(0)
        f_new = ContentFile(out_buffer.read())
        map_model.image.save('imported_image', f_new)
    return map_model


@background(schedule=0)
def import_single_event_from_livelox(class_id):
    club = get_livelox_club()
    r = requests.post('https://www.livelox.com/Data/ClassBlob',
        data={
            "classIds":[class_id],
            "courseIds": None,
            "relayLegs": [],
            "relayLegGroupIds": [],
            "routeReductionProperties": {"distanceTolerance": 1,"speedTolerance": 0.1},
            "includeMap": True,
            "includeCourses": True,
            "skipStoreInCache": False
        }
    )
    if r.status_code != 200:
        raise EventImportError('Can not fetch data')
    data = r.json()
    map_model = None
    map_projection = None
    try:
        map_data = data['map']
        map_url = map_data['url'];
        map_bound = map_data['boundingQuadrilateral']['vertices']
        map_resolution = map_data['resolution']
        map_name = f"{map_data['name']} - {data['courses'][0]['name']}"
        route_ctrls = [c['controls'] for c in data['courses']]
        map_projection = data['map'].get('projection')
        map_model = draw_livelox_route(map_name, club, map_url, map_bound, route_ctrls, map_resolution)
    except Exception:
        raise MapImportError('Could not import map')

    participant_data = [d for d in data['participants'] if d.get('routeData')]
    time_offset = 22089888e5

    r = requests.post(
        'https://www.livelox.com/Data/ClassInfo',
        data={'classIds': [class_id], 'courseIds': [], 'relayLegs': [], 'relayLegGroupIds': []}

    )
    if r.status_code != 200:
        raise EventImportError('Can not fetch event data')
    event_data = r.json()
    event_name = f"{event_data['general']['class']['event']['name']} - {event_data['general']['class']['name']}"
    event_start = arrow.get(event_data['general']['class']['event']['timeInterval']['start']).datetime
    event_end = arrow.get(event_data['general']['class']['event']['timeInterval']['end']).datetime
    event, created = Event.objects.get_or_create(
        club=club,
        slug=f'{class_id}',
        defaults={
            'name': event_name,
            'start_date': event_start,
            'end_date': event_end,
            'map': map_model,
        },
    )

    #event.competitors.all().delete()
    if not created:
        return
    
    if map_projection:
        matrix = map_projection['matrix'][0] + map_projection['matrix'][1] + map_projection['matrix'][2]

    for p in participant_data:
        lat = 0
        lon = 0
        t = -time_offset
        pts = []
        p_data = p['routeData'][1:]
        min_t = None
        for i in range((len(p_data) - 1) // 3):
            t += p_data[3 * i]
            lon += p_data[3 * i+1]
            lat += p_data[3 * i+2]
            min_t = t if not min_t else min(min_t, t)
            if map_projection:
                px, py = project(matrix, lon / 10, lat /10)
                latlon = map_model.map_xy_to_wsg84(px, py)
                pts.append({
                    'timestamp': int(t/1e3),
                    'latitude': latlon['lat'],
                    'longitude': latlon['lon'],
                })
            else:
                pts.append({
                    'timestamp': int(t/1e3),
                    'latitude': lat / 1e6,
                    'longitude': lon / 1e6,
                })
        dev = Device.objects.create(aid=short_random_key() + '_LLX', is_gpx=True)
        if pts:
            dev.add_locations(pts)
        c_name = f"{p.get('firstName')} {p.get('lastName')}"
        c_sname = initial_of_name(c_name)
        Competitor.objects.create(
            name=c_name,
            short_name=c_sname,
            start_time=arrow.get(min_t).datetime,
            event=event,
            device=dev
        )

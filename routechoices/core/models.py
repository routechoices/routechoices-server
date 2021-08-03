import arrow
import base64
import bisect
import datetime
from decimal import Decimal
from io import BytesIO
import logging
import hashlib
from operator import itemgetter
import orjson as json
import re
import time
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Polygon, LinearRing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.core.validators import validate_slug
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.timezone import now

from django_hosts.resolvers import reverse

import gpxpy
import gpxpy.gpx

import polyline_encoding

import pytz

from PIL import Image

from routechoices.lib.gps_data_encoder import GeoLocationSeries, GeoLocation
from routechoices.lib.validators import (
     validate_gpx,
     validate_domain_slug,
     validate_nice_slug,
     validate_latitude,
     validate_longitude,
     validate_corners_coordinates,
     validate_imei,
)
from routechoices.lib.helper import (
    random_key,
    short_random_key,
    short_random_slug,
    general_2d_projection,
    adjugate_matrix, project
)
from routechoices.lib.storages import OverwriteImageStorage
from routechoices.lib.globalmaptiles import GlobalMercator


logger = logging.getLogger(__name__)

GLOBAL_MERCATOR = GlobalMercator()


class Point(object):
    def __init__(self, x, y=None):
        if isinstance(x, tuple):
            self.x = x[0]
            self.y = x[1]
        elif isinstance(x, dict):
            self.x = x.get('x')
            self.y = x.get('y')
        else:
            self.x = x
            self.y = y

    def __repr__(self):
        return f'x: {self.x}, y:{self.y}'


class Club(models.Model):
    aid = models.CharField(
         default=random_key,
         max_length=12,
         editable=False,
         unique=True,
    )
    creator = models.ForeignKey(
         User,
         related_name='+',
         blank=True,
         null=True,
         on_delete=models.SET_NULL,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255, unique=True)
    slug = models.CharField(
        max_length=50,
        validators=[validate_domain_slug, ],
        unique=True,
        help_text='This is used in the urls of your events'
    )
    admins = models.ManyToManyField(User)

    class Meta:
        ordering = ['name']
        verbose_name = 'club'
        verbose_name_plural = 'clubs'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            'club_view',
            host='clubs',
            host_kwargs={'club_slug': self.slug}
        )

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = Club.objects.filter(slug__iexact=self.slug)
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            raise ValidationError('Club with this slug already exists.')


def map_upload_path(instance=None, file_name=None):
    import os.path
    tmp_path = [
        'maps'
    ]
    if file_name:
        pass
    basename = instance.aid + '_' + str(int(time.time()))
    tmp_path.append(basename[0])
    tmp_path.append(basename[1])
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


def route_upload_path(instance=None, file_name=None):
    import os.path
    tmp_path = [
        'routes'
    ]
    if file_name:
        pass
    basename = instance.aid + '_' + str(int(time.time())) + '.gpx'
    tmp_path.append(basename[0])
    tmp_path.append(basename[1])
    tmp_path.append(basename)
    return os.path.join(*tmp_path)


class Map(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
        Club,
        related_name='maps',
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    image = models.ImageField(
        upload_to=map_upload_path,
        height_field='height',
        width_field='width',
        storage=OverwriteImageStorage(aws_s3_bucket_name='routechoices-maps'),
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False
    )
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    corners_coordinates = models.CharField(
        max_length=255,
        help_text='Latitude and longitude of map corners separated by commas '
        'in following order Top Left, Top right, Bottom Right, Bottom left. '
        'eg: 60.519,22.078,60.518,22.115,60.491,22.112,60.492,22.073',
        validators=[validate_corners_coordinates]
    )

    class Meta:
        ordering = ['-creation_date']
        verbose_name = 'map'
        verbose_name_plural = 'maps'

    def __str__(self):
        return '{} ({})'.format(self.name, self.club)

    @property
    def path(self):
        return self.image.name

    @property
    def data(self):
        with self.image.open('rb') as fp:
            data = fp.read()
        return data

    @property
    def corners_coordinates_short(self):
        coords = ','.join(
            [str(round(Decimal(x), 5)) for x in self.corners_coordinates.split(',')]
        )
        return coords

    @property
    def kmz(self):
        doc_kml = '''<?xml version="1.0" encoding="utf-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"
     xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <Folder>
      <name>{}</name>
      <GroundOverlay>
        <name>{}</name>
        <drawOrder>50</drawOrder>
        <Icon>
          <href>files/doc.jpg</href>
        </Icon>
        <altitudeMode>clampToGround</altitudeMode>
        <gx:LatLonQuad>
          <coordinates>
            {},{} {},{} {},{} {},{}
          </coordinates>
        </gx:LatLonQuad>
      </GroundOverlay>
    </Folder>
  </Document>
</kml>'''.format(
            self.name,
            self.name,
            self.bound['bottomLeft']['lon'],
            self.bound['bottomLeft']['lat'],
            self.bound['bottomRight']['lon'],
            self.bound['bottomRight']['lat'],
            self.bound['topRight']['lon'],
            self.bound['topRight']['lat'],
            self.bound['topLeft']['lon'],
            self.bound['topLeft']['lat'],
        )
        doc_jpg = self.data
        kmz = BytesIO()
        with ZipFile(kmz, 'w') as fp:
            with fp.open('doc.kml', 'w') as file1:
                file1.write(doc_kml.encode('utf-8'))
            with fp.open('files/doc.jpg', 'w') as file2:
                file2.write(doc_jpg)
        return kmz.getbuffer()

    @property
    def mime_type(self):
        return 'image/jpeg'

    @property
    def data_uri(self):
        return 'data:{};base64,{}'.format(
            self.mime_type,
            base64.b64encode(self.data).decode('utf-8')
        )

    @data_uri.setter
    def data_uri(self, value):
        if not value:
            raise ValueError('Value can not be null')
        data_matched = re.match(
            r'^data:image/(?P<format>jpeg|png|gif);base64,'
            r'(?P<data_b64>(?:[A-Za-z0-9+/]{4})*'
            r'(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)$',
            value
        )
        if data_matched:
            self.image.save(
                'filename',
                ContentFile(
                    base64.b64decode(data_matched.group('data_b64'))
                ),
                save=False
            )
            self.image.close()
        else:
            raise ValueError('Not a base 64 encoded data URI of an image')

    @property
    def thumbnail(self):
        orig = self.image.open('rb').read()
        img = Image.open(BytesIO(orig))
        if img.mode != 'RGBA':
            img = img.convert('RGB')
        img = img.transform(
            (1200, 630),
            Image.QUAD,
            (
                int(self.width) / 2 - 300,
                int(self.height) / 2 - 158,
                int(self.width) / 2 - 300,
                int(self.height) / 2 + 157,
                int(self.width) / 2 + 300,
                int(self.height) / 2 + 157,
                int(self.width) / 2 + 300,
                int(self.height) / 2 - 158
            )
        )
        img_out = Image.new(
            'RGB',
            img.size,
            (255, 255, 255, 0)
        )
        img_out.paste(img, (0, 0))
        img.close()
        return img_out

    @property
    def size(self):
        return {'width': self.width, 'height': self.height}

    @property
    def alignment_points(self):
        r1_a = Point(0, 0)
        r1_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound['topLeft']))
        r2_a = Point(0, self.height)
        r2_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound['bottomLeft']))
        r3_a = Point(self.width, 0)
        r3_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound['topRight']))
        r4_a = Point(self.width, self.height)
        r4_b = Point(GLOBAL_MERCATOR.latlon_to_meters(self.bound['bottomRight']))
        return r1_a, r1_b, r2_a, r2_b, r3_a, r3_b, r4_a, r4_b

    @property
    def matrix_3d(self):
        r1_a, r1_b, r2_a, r2_b, r3_a, r3_b, r4_a, r4_b = self.alignment_points
        m = general_2d_projection(
            r1_a.x, r1_a.y, r1_b.x, r1_b.y,
            r2_a.x, r2_a.y, r2_b.x, r2_b.y,
            r3_a.x, r3_a.y, r3_b.x, r3_b.y,
            r4_a.x, r4_a.y, r4_b.x, r4_b.y
        )
        if not m[8]:
            return
        for i in range(9):
            m[i] = m[i] / m[8]
        return m

    @property
    def matrix_3d_inverse(self):
        return adjugate_matrix(self.matrix_3d)

    @property
    def map_xy_to_spherical_mercator(self):
        if not self.matrix_3d:
            return lambda x, y: (0, 0)
        return lambda x, y: project(self.matrix_3d, x, y)

    @property
    def spherical_mercator_to_map_xy(self):
        return lambda x, y: project(self.matrix_3d_inverse, x, y)

    def wsg84_to_map_xy(self, lat, lon):
        xy = GLOBAL_MERCATOR.latlon_to_meters({'lat': lat, 'lon': lon})
        return self.spherical_mercator_to_map_xy(xy['x'], xy['y'])

    def map_xy_to_wsg84(self, x, y):
        mx, my = self.map_xy_to_spherical_mercator(x, y)
        return GLOBAL_MERCATOR.meters_to_latlon({'x': mx, 'y': my})

    def create_tile(self, output_width, output_height,
                    min_lon, max_lon, max_lat, min_lat):
        tile_img = None
        if self.intersects_with_tile(min_lon, max_lon, max_lat, min_lat):
            orig = self.image.open('rb').read()
            self.image.close()
            img = Image.open(BytesIO(orig))
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            nw = self.spherical_mercator_to_map_xy(max_lat, min_lon)
            ne = self.spherical_mercator_to_map_xy(max_lat, max_lon)
            se = self.spherical_mercator_to_map_xy(min_lat, max_lon)
            sw = self.spherical_mercator_to_map_xy(min_lat, min_lon)
            tile_img = img.transform(
                (output_width, output_height),
                Image.QUAD,
                (
                    ne[0], ne[1],
                    nw[0], nw[1],
                    sw[0], sw[1],
                    se[0], se[1],
                )
            )
        img_out = Image.new('RGBA', (output_width, output_height), (255, 255, 255, 0))
        if tile_img:
            img_out.paste(tile_img, (0, 0), tile_img)
        # output = BytesIO()
        # img_out.save(output, format='png')
        # data_out = output.getvalue()
        # return data_out
        return img_out

    def intersects_with_tile(self, min_lon, max_lon, max_lat, min_lat):
        tile_bounds_polygon = Polygon(
            LinearRing(
                (min_lat, min_lon),
                (max_lat, min_lon),
                (max_lat, max_lon),
                (min_lat, max_lon),
                (min_lat, min_lon),
            )
        )
        map_bounds_polygon = Polygon(
            LinearRing(
                self.map_xy_to_spherical_mercator(0, 0),
                self.map_xy_to_spherical_mercator(0, self.height),
                self.map_xy_to_spherical_mercator(self.width,
                                                  self.height),
                self.map_xy_to_spherical_mercator(self.width, 0),
                self.map_xy_to_spherical_mercator(0, 0),
            )
        )
        tile_bounds_polygon_prep = tile_bounds_polygon.prepared

        if not tile_bounds_polygon_prep.intersects(map_bounds_polygon):
            return False
        return True

    def strip_exif(self):
        if self.image.closed:
            self.image.open()
        with Image.open(self.image.file) as image:
            rgb_img = image.convert('RGB')
            if image.size[0] > 3000 and image.size[1] > 3000:
                if image.size[0] >= image.size[1]:
                    new_h = 3000
                    new_w = new_h / image.size[1] * image.size[0]
                else:
                    new_w = 3000
                    new_h = new_w / image.size[0] * image.size[1]
                rgb_img.thumbnail((new_w, new_h), Image.ANTIALIAS)
            out_buffer = BytesIO()
            rgb_img.save(out_buffer, 'JPEG', quality=60, dpi=(300, 300))
            f_new = File(out_buffer, name=self.image.name)
            self.image.save(
                'filename',
                f_new,
                save=False,
            )
        self.image.close()

    @property
    def hash(self):
        h = hashlib.sha256()
        h.update(self.path.encode('utf-8'))
        h.update(self.corners_coordinates.encode('utf-8'))
        return base64.b64encode(h.digest()).decode('utf-8')

    @property
    def bound(self):
        coords = [float(x) for x in self.corners_coordinates.split(',')]
        return {
            'topLeft': {'lat': coords[0], 'lon': coords[1]},
            'topRight': {'lat': coords[2], 'lon': coords[3]},
            'bottomRight': {'lat': coords[4], 'lon': coords[5]},
            'bottomLeft': {'lat': coords[6], 'lon': coords[7]},
        }


PRIVACY_PUBLIC = 'public'
PRIVACY_SECRET = 'secret'
PRIVACY_PRIVATE = 'private'
PRIVACY_CHOICES = (
    (PRIVACY_PUBLIC, 'Public'),
    (PRIVACY_SECRET, 'Secret'),
    (PRIVACY_PRIVATE, 'Private'),
)

MAP_OSM = 'osm'
MAP_GOOGLE_STREET = 'gmap-street'
MAP_GOOGLE_SAT = 'gmap-hybrid'
MAP_MAPANT_FI = 'mapant-fi'
MAP_MAPANT_NO = 'mapant-no'
MAP_MAPANT_ES = 'mapant-es'
MAP_TOPO_FI = 'topo-fi'
MAP_TOPO_NO = 'topo-no'

MAP_CHOICES = (
    (MAP_OSM, 'Open Street Map'),
    (MAP_GOOGLE_STREET, 'Google Map Street'),
    (MAP_GOOGLE_SAT, 'Google Map Satellite'),
    (MAP_MAPANT_FI, 'Mapant Finland'),
    (MAP_MAPANT_NO, 'Mapant Norway'),
    (MAP_MAPANT_ES, 'Mapant Spain'),
    (MAP_TOPO_FI, 'Topo Finland'),
    (MAP_TOPO_NO, 'Topo Norway'),
)


class Event(models.Model):
    aid = models.CharField(
         default=random_key,
         max_length=12,
         editable=False,
         unique=True,
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    club = models.ForeignKey(
         Club,
         verbose_name='Club',
         related_name='events',
         on_delete=models.CASCADE
    )
    name = models.CharField(
        verbose_name='Name',
        max_length=255
    )
    slug = models.CharField(
        verbose_name='Slug',
        max_length=50,
        validators=[validate_nice_slug, ],
        db_index=True,
        help_text='This is used to build the url of this event',
        default=short_random_slug,
    )
    start_date = models.DateTimeField(verbose_name='Start Date (UTC)')
    end_date = models.DateTimeField(
        verbose_name='End Date (UTC)',
    )
    privacy = models.CharField(
        max_length=8,
        choices=PRIVACY_CHOICES,
        default=PRIVACY_PUBLIC,
    )
    backdrop_map = models.CharField(
        max_length=16,
        choices=MAP_CHOICES,
        default=MAP_OSM,
    )
    map = models.ForeignKey(
        Map,
        related_name='+',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    map_title = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Leave blank if you are not using extra maps',
    )
    extra_maps = models.ManyToManyField(
        Map,
        through='MapAssignation',
        related_name='+',
        through_fields=('event', 'map'),
    )
    open_registration = models.BooleanField(
        default=False,
        help_text="Participants can register themselves to the event.",
    )
    allow_route_upload = models.BooleanField(
        default=False,
        help_text="Participants can upload their routes after the event.",
    )

    class Meta:
        ordering = ['-start_date']
        unique_together = (('club', 'slug'), ('club', 'name'))
        verbose_name = 'event'
        verbose_name_plural = 'events'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            'event_view',
            host='clubs',
            kwargs={'slug': self.slug},
            host_kwargs={'club_slug': self.club.slug}
        )

    def get_absolute_map_url(self):
        return reverse(
            'event_map_view',
            host='clubs',
            kwargs={
                'slug': self.slug
            },
            host_kwargs={'club_slug': self.club.slug}
        )

    def get_absolute_export_url(self):
        return reverse(
            'event_export_view',
            host='clubs',
            kwargs={'slug': self.slug},
            host_kwargs={'club_slug': self.club.slug}
        )

    @property
    def shortcut(self):
        if hasattr(settings, 'SHORTCUT_BASE_URL'):
            return settings.SHORTCUT_BASE_URL + self.aid
        return None

    @property
    def hidden(self):
        return self.start_date > now()

    @property
    def started(self):
        return self.start_date <= now()

    @property
    def is_live(self):
        if self.end_date:
            return self.start_date <= now() <= self.end_date
        else:
            return self.start_date <= now()

    @property
    def ended(self):
        return self.end_date and self.end_date < now()

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        qs = Event.objects.filter(
            club__slug__iexact=self.club.slug,
            slug__iexact=self.slug
        )
        if self.id:
            qs = qs.exclude(id=self.id)
        if qs.exists():
            raise ValidationError(
                'Event with this Club and Slug already exists.'
            )

    def invalidate_cache(self):
        t0 = time.time()
        cache_ts = int(t0 // (10 if self.is_live else 7*24*3600))
        cache_prefix = 'live' if self.is_live else 'archived'
        cache_key = f'{cache_prefix}_event_data:{self.aid}:{cache_ts}'
        cache.delete(cache_key)

    @property
    def has_notice(self):
        return hasattr(self, 'notice')


class Notice(models.Model):
    modification_date = models.DateTimeField(auto_now=True)
    event = models.OneToOneField(
        Event,
        related_name='notice',
        on_delete=models.CASCADE
    )
    text = models.CharField(
        max_length=280,
        blank=True,
        help_text='Optional text that will be displayed on the event page',
    )

    def __str__(self):
        return self.text


class MapAssignation(models.Model):
    event = models.ForeignKey(
        Event,
        related_name='map_assignations',
        on_delete=models.CASCADE
    )
    map = models.ForeignKey(
        Map,
        related_name='map_assignations',
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)

    class Meta:
        unique_together = (('map', 'event'), ('event', 'title'))
        ordering = ['id']


class Device(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    aid = models.CharField(
        default=short_random_key,
        max_length=12,
        unique=True,
        validators=[validate_slug, ]
    )
    user_agent = models.CharField(max_length=200, blank=True)
    is_gpx = models.BooleanField(default=False)
    owners = models.ManyToManyField(
        User,
        through='DeviceOwnership',
        related_name='devices',
        through_fields=('device', 'user'),
    )
    locations_raw = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['aid']
        verbose_name = 'device'
        verbose_name_plural = 'devices'

    def __str__(self):
        return self.aid

    @property
    def locations(self):
        if not self.locations_raw:
            return {'timestamps': [], 'latitudes': [], 'longitudes': []}
        return json.loads(self.locations_raw)

    @locations.setter
    def locations(self, locs):
        self.locations_raw = str(json.dumps(locs), 'utf-8')

    def get_locations_between_dates_alt(self, from_date, end_date, encoded=False):
        qs = self.locations
        from_ts = from_date.timestamp()
        end_ts = end_date.timestamp()
        timestamps_w_order = sorted(
            enumerate(qs['timestamps']),
            key=itemgetter(1)
        )
        timestamps = list(zip(*timestamps_w_order))[1]
        ts_from_index = bisect.bisect_right(timestamps, from_ts)
        ts_end_index = bisect.bisect_left(timestamps, end_ts)
        locs = [
            {
                'timestamp': timestamps_w_order[i][1],
                'latitude': qs['latitudes'][timestamps_w_order[i][0]],
                'longitude': qs['longitudes'][timestamps_w_order[i][0]],
            } for i in range(ts_from_index, ts_end_index)]
        if not encoded:
            return len(locs), locs
        result = polyline_encoding.encode_data(locs)
        return len(locs), result

    def get_locations_between_dates(self, from_date, end_date, encoded=False):
        qs = self.locations
        from_ts = from_date.timestamp()
        end_ts = end_date.timestamp()
        d = zip(qs['timestamps'], qs['latitudes'], qs['longitudes'])
        
        locs = [
            {
                'timestamp': i[0],
                'latitude': i[1],
                'longitude': i[2],
            } for i in sorted(
                d,
                key=itemgetter(0)
            ) if from_ts < i[0] < end_ts
        ]
        if not encoded:
            return len(locs), locs
        result = polyline_encoding.encode_data(locs)
        return len(locs), result

    def add_location(self, lat, lon, timestamp=None, save=True):
        try:
            validate_latitude(lat)
            validate_longitude(lon)
        except Exception:
            return
        if timestamp is not None:
            ts_datetime = datetime.datetime \
                .utcfromtimestamp(timestamp) \
                .replace(tzinfo=pytz.utc)
        else:
            ts_datetime = now()
        locs = self.locations
        ts = int(ts_datetime.timestamp())
        if isinstance(lat, Decimal):
            lat = float(lat)
        if isinstance(lon, Decimal):
            lon = float(lon)
        all_ts = set(locs['timestamps'])
        if ts not in all_ts:
            locs['timestamps'].append(ts)
            locs['latitudes'].append(round(lat, 5))
            locs['longitudes'].append(round(lon, 5))
            self.locations = locs
            if save:
                self.save()

    def add_locations(self, loc_array, save=True):
        new_ts = []
        new_lat = []
        new_lon = []
        locs = self.locations
        all_ts = set(locs['timestamps'])
        for loc in loc_array:
            ts = int(loc['timestamp'])
            lat = loc['latitude']
            lon = loc['longitude']
            if ts in all_ts:
                continue
            try:
                validate_latitude(lat)
                validate_longitude(lon)
            except Exception:
                continue
            if isinstance(lat, Decimal):
                lat = float(lat)
            if isinstance(lon, Decimal):
                lon = float(lon)
            new_ts.append(ts)
            new_lat.append(round(lat, 5))
            new_lon.append(round(lon, 5))
        locs['timestamps'] += new_ts
        locs['latitudes'] += new_lat
        locs['longitudes'] += new_lon
        self.locations = locs
        if save:
            self.save()

    @property
    def location_count(self):
        try:
            return len(self.locations['timestamps'])
        except Exception:
            return 0

    def remove_duplicates(self, save=True):
        qs = self.locations
        d = zip(qs['timestamps'], qs['latitudes'], qs['longitudes'])
        sorted_locs = sorted(
            d,
            key=itemgetter(0)
        )
        loc_list = []
        prev_t = None
        for loc in sorted_locs:
            t = int(loc[0])
            if t != prev_t:
                prev_t = t
                loc_list.append([t, round(loc[1], 5), round(loc[2], 5)])
        tims, lats, lons = zip(*locs)
        new_locs = {'timestamps': tims, 'latitudes': lats, 'longitudes': lons}
        if save and qs != new_locs:
            self.save()

    @cached_property
    def last_location(self):
        if self.location_count == 0:
            return None
        qs = self.locations
        d = zip(qs['timestamps'], qs['latitudes'], qs['longitudes'])
        locs = [
            {
                'timestamp': i[0],
                'latitude': i[1],
                'longitude': i[2],
            } for i in sorted(
                d,
                key=itemgetter(0)
            )
        ]
        return locs[-1]

    @property
    def last_date_viewed(self):
        ll = self.last_location
        if not ll:
            return None
        t = ll['timestamp']
        return datetime.datetime \
            .utcfromtimestamp(t) \
            .replace(tzinfo=pytz.utc)

    @cached_property
    def last_position(self):
        ll = self.last_location
        if not ll:
            return None
        return ll['latitude'], ll['longitude']


class ImeiDevice(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    imei = models.CharField(
        max_length=32,
        unique=True,
        validators=[validate_imei, ]
    )
    device = models.OneToOneField(
        Device,
        related_name='physical_device',
        on_delete=models.CASCADE
    )

    class Meta:
        ordering = ['imei']
        verbose_name = 'imei device'
        verbose_name_plural = 'imei devices'

    def __str__(self):
        return self.imei


class DeviceOwnership(models.Model):
    device = models.ForeignKey(
        Device,
        related_name='ownerships',
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User,
        related_name='ownerships',
        on_delete=models.CASCADE
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('device', 'user'), )


class Competitor(models.Model):
    aid = models.CharField(
        default=random_key,
        max_length=12,
        editable=False,
        unique=True,
    )
    event = models.ForeignKey(
        Event,
        related_name='competitors',
        on_delete=models.CASCADE,
    )
    device = models.ForeignKey(
        Device,
        related_name='competitor_set',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    name = models.CharField(max_length=64)
    short_name = models.CharField(max_length=32)
    start_time = models.DateTimeField(
        verbose_name='Start time (UTC)',
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['start_time', 'name']
        verbose_name = 'competitor'
        verbose_name_plural = 'competitors'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.start_time:
            self.start_time = self.event.start_date
        super().save(*args, **kwargs)

    @property
    def started(self):
        return self.start_time > now()

    @cached_property
    def locations(self):
        if self.device:
            qs = self.device.locations
        else:
            return []

        from_date = self.event.start_date
        if self.start_time:
            from_date = self.start_time
        next_competitor_start_time = self.device.competitor_set.filter(
            start_time__gt=from_date
        ).order_by('start_time').values_list('start_time', flat=True).first()

        end_date = now()
        if next_competitor_start_time:
            end_date = min(
                next_competitor_start_time,
                end_date
            )
        if self.event.end_date:
            end_date = min(
                self.event.end_date,
                end_date
            )

        locs = [
            {
                'timestamp': i[1],
                'latitude': qs['latitudes'][i[0]],
                'longitude': qs['longitudes'][i[0]],
                'competitor': self.id,
            } for i in sorted(
                enumerate(qs['timestamps']),
                key=lambda x:x[1]
            ) if i[1] > from_date.timestamp() and i[1] < end_date.timestamp()
        ]
        return locs

    @property
    def encoded_data(self):
        result = polyline_encoding.encode_data(self.locations)
        return result

    @property
    def gpx(self):
        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)

        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        locs = self.locations
        for location in locs:
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(
                    location['latitude'],
                    location['longitude'],
                    time=arrow.get(location['timestamp']).datetime
                )
            )
        gpx_track.segments.append(gpx_segment)
        return gpx.to_xml()

    def get_absolute_gpx_url(self):
        return reverse(
            'competitor_gpx_download',
            host='api',
            kwargs={
                'competitor_id': self.aid,
            }
        )


@receiver([post_save, post_delete], sender=Competitor)
def save_profile(sender, instance, **kwargs):
    instance.event.invalidate_cache()

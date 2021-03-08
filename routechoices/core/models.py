import arrow
import base64
import datetime
import orjson as json
import hashlib
import re
import time
from io import BytesIO
from decimal import Decimal

import gpxpy
import gpxpy.gpx
import pytz
from PIL import Image
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.core.validators import validate_slug
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now

from routechoices.lib.gps_data_encoder import GeoLocationSeries, GeoLocation
from routechoices.lib.validators import (
     validate_nice_slug,
     validate_latitude,
     validate_longitude,
     validate_corners_coordinates,
     validate_imei,
)
from routechoices.lib.helper import (
    random_key,
    short_random_key,
    short_random_slug
)
from routechoices.lib.storages import OverwriteImageStorage
import logging
logger = logging.getLogger(__name__)


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
        validators=[validate_nice_slug, ],
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
            'site:club_view',
            kwargs={
                'slug': self.slug
            }
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
        coords = self.corners_coordinates.split(',')
        return {
            'topLeft': {'lat': coords[0], 'lon': coords[1]},
            'topRight': {'lat': coords[2], 'lon': coords[3]},
            'bottomRight': {'lat': coords[4], 'lon': coords[5]},
            'botttomLeft': {'lat': coords[6], 'lon': coords[7]},
        }


PRIVACY_PUBLIC = 'public'
PRIVACY_SECRET = 'secret'
PRIVACY_PRIVATE = 'private'
PRIVACY_CHOICES = (
    (PRIVACY_PUBLIC, 'Public'),
    (PRIVACY_SECRET, 'Secret'),
    (PRIVACY_PRIVATE, 'Private'),
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
         related_name='events',
         on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=50,
        validators=[validate_nice_slug, ],
        db_index=True,
        help_text='This is used to build the url of this event',
        default=short_random_slug,
    )
    start_date = models.DateTimeField(verbose_name='Start Date (UTC)')
    end_date = models.DateTimeField(
        verbose_name='End Date (UTC)',
        null=True,
        blank=True,
    )
    privacy = models.CharField(
        max_length=8,
        choices=PRIVACY_CHOICES,
        default=PRIVACY_PUBLIC,
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
            'site:event_view',
            kwargs={
                'club_slug': self.club.slug,
                'slug': self.slug
            }
        )

    def get_absolute_map_url(self):
        return

    def get_absolute_export_url(self):
        return reverse(
            'site:event_export_view',
            kwargs={
                'club_slug': self.club.slug,
                'slug': self.slug
            }
        )

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
    aid = models.CharField(
        default=short_random_key,
        max_length=12,
        unique=True,
        validators=[validate_slug, ]
    )
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
            locs['latitudes'].append(lat)
            locs['longitudes'].append(lon)
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
            new_lat.append(lat)
            new_lon.append(lon)
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
        locations = self.locations
        timestamps = set()
        locs = {'timestamps': [], 'latitudes': [], 'longitudes': []}
        for idx, timestamp in sorted(
                    enumerate(locations['timestamps']),
                    key=lambda x: x[1]
                ):
            timestamp_int = int(timestamp)
            if timestamp_int not in timestamps:
                timestamps.add(timestamp_int)
                locs['timestamps'].append(timestamp_int)
                locs['latitudes'].append(locations['latitudes'][idx])
                locs['longitudes'].append(locations['longitudes'][idx])
        self.locations = locs
        if save:
            self.save()

    @property
    def last_location(self):
        if self.location_count == 0:
            return None
        locations = self.locations
        locs = [
            {
                'timestamp': timestamp,
                'latitude': locations['latitudes'][idx],
                'longitude': locations['longitudes'][idx],
            } for idx, timestamp in sorted(
                enumerate(locations['timestamps']),
                key=lambda x:x[1]
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

    @property
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
        next_competitor = self.device.competitor_set.filter(
            start_time__gt=from_date
        ).order_by('start_time').first()

        end_date = now()
        if next_competitor:
            end_date = min(
                next_competitor.start_time,
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
        data = []
        for loc in self.locations:
            data.append(
                GeoLocation(
                    loc['timestamp'],
                    (loc['latitude'], loc['longitude'])
                )
            )
        return str(GeoLocationSeries(data))

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
            'api:competitor_gpx_download',
            kwargs={
                'competitor_id': self.aid,
            }
        )

import requests
import arrow
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from routechoices.core.models import Map, Club, Event, Device, Competitor, \
    Location
from routechoices.lib.helper import short_random_key



class Command(BaseCommand):
    help = 'Transfer location table to json field'

    def handle(self, *args, **options):
        for dev in Device.objects.all():
            locs = {'timestamps': [], 'latitudes': [], 'longitudes': []}
            for l in Location.objects.filter(device_id=dev.id):
                locs['timestamps'].append(l.timestamp)
                locs['latitudes'].append(l.latitude)
                locs['longitudes'].append(l.longitude)
            dev.locations = locs
            dev.save()

import time

from django.conf import settings

from django_hosts.resolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient, override_settings

from routechoices.core.models import Device
from routechoices.lib.gps_data_encoder import GeoLocationSeries, GeoLocation


@override_settings(PARENT_HOST='localhost:8000')
class ApiTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def reverse_and_check(self, path, expected):
        url = reverse(path, host='api')
        self.assertEquals(url, '//api.localhost:8000' + expected)
        return url

    def get_device_id(self):
        url = reverse('device_id_api', host='api')
        res = self.client.post(url, SERVER_NAME='api.localhost:8000')
        return res.data.get('device_id')

    def test_api_root(self):
        url = self.reverse_and_check('api_doc', '/')
        res = self.client.get(url, SERVER_NAME='api.localhost:8000')
        self.assertEquals(res.status_code, status.HTTP_200_OK)

    def test_get_time(self):
        url = self.reverse_and_check('time_api', '/time')
        t1 = time.time()
        res = self.client.get(url, SERVER_NAME='api.localhost:8000')
        t2 = time.time()
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertTrue(t1 < res.data.get('time') < t2)

    def test_get_device_id(self):
        url = self.reverse_and_check('device_id_api', '/device_id')
        res = self.client.post(url, SERVER_NAME='api.localhost:8000')
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data.get('device_id')) == 8)
        self.assertTrue(res.data.get('device_id') != self.get_device_id())


    def test_locations_api_gw(self):
        url = self.reverse_and_check('locations_api_gw', '/locations')
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                'device_id': dev_id,
                'latitudes': '1.1,1.2',
                'longitudes': '3.1,3.2',
                'timestamps': '{},{}'.format(t, t+1),
                'secret': settings.POST_LOCATION_SECRETS[0]
            },
            SERVER_NAME='api.localhost:8000'
        )
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        nb_points = len(Device.objects.get(aid=dev_id).locations['timestamps'])
        self.assertEquals(nb_points, 2)

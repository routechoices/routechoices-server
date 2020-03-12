import time
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from routechoices.core.models import Device
from routechoices.lib.gps_data_encoder import GeoLocationSeries, GeoLocation


class ApiTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def reverse_and_check(self, path, expected):
        url = reverse(path)
        self.assertEquals(url, expected)
        return url

    def get_device_id(self):
        url = reverse('api:device_id_api')
        res = self.client.post(url)
        return res.data.get('device_id')

    def test_api_root(self):
        url = self.reverse_and_check('api:api_root', '/api/')
        res = self.client.get(url)
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertEquals(res.data, None)

    def test_get_time(self):
        url = self.reverse_and_check('api:time_api', '/api/time')
        t1 = time.time()
        res = self.client.get(url)
        t2 = time.time()
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertTrue(t1 < res.data.get('time') < t2)

    def test_get_device_id(self):
        url = self.reverse_and_check('api:device_id_api', '/api/device_id')
        res = self.client.post(url)
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data.get('device_id')) == 6)
        self.assertTrue(res.data.get('device_id') != self.get_device_id())

    def test_traccar_api_gw(self):
        url = self.reverse_and_check('api:traccar_api_gw', '/api/traccar')
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            '{}?id={}&lat={}&lon={}&timestamp={}'.format(
                url,
                dev_id,
                30.21,
                40.32,
                t
            ))
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        nb_points = len(Device.objects.get(aid=dev_id).locations['timestamps'])
        self.assertEquals(nb_points, 1)

    def test_garmin_api_gw(self):
        url = self.reverse_and_check('api:garmin_api_gw', '/api/garmin')
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                'device_id': dev_id,
                'latitudes': '1.1,1.2',
                'longitudes': '3.1,3.2',
                'timestamps': '{},{}'.format(t, t+1),
            }
        )
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        nb_points = len(Device.objects.get(aid=dev_id).locations['timestamps'])
        self.assertEquals(nb_points, 2)

    def test_pwa_api_gw(self):
        url = self.reverse_and_check('api:pwa_api_gw', '/api/pwa')
        dev_id = self.get_device_id()
        t = time.time()
        gps_encoded = GeoLocationSeries([])
        gps_encoded.insert(GeoLocation(t, [1.1, 2.2]))
        gps_encoded.insert(GeoLocation(t + 1, [1.2, 2.1]))
        gps_encoded.insert(GeoLocation(t + 2, [1.3, 2.0]))
        res = self.client.post(url, {
            'id': dev_id,
            'raw_data': str(gps_encoded)
        })
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        nb_points = len(Device.objects.get(aid=dev_id).locations['timestamps'])
        self.assertEquals(nb_points, 3)

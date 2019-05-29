import time
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient


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

    def test_traccar_gw_api(self):
        pass


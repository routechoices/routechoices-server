import json
import tempfile
import time
from pathlib import Path

import arrow
from django.conf import settings
from django.contrib.auth.models import User
from django_hosts.resolvers import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, override_settings

from routechoices.core.models import (
    PRIVACY_PRIVATE,
    Club,
    Competitor,
    Device,
    Event,
    Map,
    MapAssignation,
)


class EssentialApiBase(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def reverse_and_check(self, path, expected, host="api"):
        url = reverse(path, host=host)
        self.assertEqual(url, f"//{host}.localhost:8000{expected}")
        return url

    def get_device_id(self):
        d = Device.objects.create()
        return d.aid


@override_settings(PARENT_HOST="localhost:8000")
class EssentialApiTestCase1(EssentialApiBase):
    def test_api_root(self):
        url = self.reverse_and_check("api_doc", "/")
        res = self.client.get(url, SERVER_NAME="api.localhost:8000")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_get_time(self):
        url = self.reverse_and_check("time_api", "/time")
        t1 = time.time()
        res = self.client.get(url, SERVER_NAME="api.localhost:8000")
        t2 = time.time()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(t1 < res.data.get("time") < t2)

    def test_get_device_id(self):
        url = self.reverse_and_check("device_id_api", "/device_id")
        res = self.client.post(url, SERVER_NAME="api.localhost:8000")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data.get("device_id")) == 8)
        self.assertTrue(res.data.get("device_id") != self.get_device_id())


@override_settings(PARENT_HOST="localhost:8000")
class ImeiApiTestCase(EssentialApiBase):
    def test_get_imei_no_data(self):
        url = self.reverse_and_check("device_imei_api", "/imei")
        res = self.client.post(url, SERVER_NAME="api.localhost:8000")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_imei_invalid(self):
        url = self.reverse_and_check("device_imei_api", "/imei")
        res = self.client.post(url, {"imei": "abcd"}, SERVER_NAME="api.localhost:8000")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_imei_valid(self):
        url = self.reverse_and_check("device_imei_api", "/imei")
        res = self.client.post(
            url, {"imei": "123456789123458"}, SERVER_NAME="api.localhost:8000"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dev_id = res.data.get("device_id")
        self.assertTrue(dev_id.isdigit())
        self.assertEqual(len(dev_id), 8)
        self.assertNotEqual(dev_id, self.get_device_id())

        # test device with alpha character get new id with only digits
        device = Device.objects.get(aid=dev_id)
        device.aid = "1234abcd"
        device.save()
        res = self.client.post(
            url, {"imei": "123456789123458"}, SERVER_NAME="api.localhost:8000"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_dev_id = res.data.get("device_id")
        self.assertNotEqual(new_dev_id, "1234abcd")
        self.assertTrue(dev_id.isdigit())
        self.assertEqual(len(new_dev_id), 8)
        self.assertNotEqual(new_dev_id, self.get_device_id())

        # test device with alpha character dont get new id if assigned a competitor in future
        club = Club.objects.create(name="Test club", slug="club")
        event = Event.objects.create(
            club=club,
            name="Test event",
            open_registration=True,
            start_date=arrow.get().shift(minutes=-1).datetime,
            end_date=arrow.get().shift(hours=1).datetime,
        )
        Competitor.objects.create(
            name="Alice", short_name="A", event=event, device=device
        )
        device.aid = "1234abcd"
        device.save()
        res = self.client.post(
            url, {"imei": "123456789123458"}, SERVER_NAME="api.localhost:8000"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_dev_id = res.data.get("device_id")
        self.assertEqual(new_dev_id, "1234abcd")

        # test device with alpha character get new id if assigned a competitor in past
        event.end_date = arrow.get().shift(seconds=-1).datetime
        event.save()
        res = self.client.post(
            url, {"imei": "123456789123458"}, SERVER_NAME="api.localhost:8000"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_dev_id = res.data.get("device_id")
        self.assertNotEqual(new_dev_id, "1234abcd")
        self.assertTrue(dev_id.isdigit())
        self.assertEqual(len(new_dev_id), 8)


@override_settings(MEDIA_ROOT=Path(tempfile.gettempdir()), PARENT_HOST="localhost:8000")
class MapApiTestCase(EssentialApiBase):
    def test_get_tile(self):
        url = self.reverse_and_check("wms_service", "/", "wms")
        club = Club.objects.create(name="Test club", slug="club")
        raster_map = Map.objects.create(
            club=club,
            name="Test map",
            corners_coordinates="61.45075,24.18994,61.44656,24.24721,61.42094,24.23851,61.42533,24.18156",
            width=1,
            height=1,
        )
        raster_map.data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAA1JREFUGFdjED765z8ABZcC1M3x7TQAAAAASUVORK5CYII="
        raster_map.save()
        event = Event.objects.create(
            club=club,
            name="Test event",
            open_registration=True,
            start_date=arrow.get().shift(minutes=-1).datetime,
            end_date=arrow.get().shift(hours=1).datetime,
            map=raster_map,
        )
        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        raster_map2 = Map.objects.create(
            club=club,
            name="Test map",
            corners_coordinates="61.45075,24.18994,61.44656,24.24721,61.42094,24.23851,61.42533,24.18156",
            width=1,
            height=1,
        )
        raster_map2.data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAA1JREFUGFdjED765z8ABZcC1M3x7TQAAAAASUVORK5CYII="
        raster_map2.save()
        MapAssignation.objects.create(event=event, map=raster_map2, title="Other route")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/jpeg")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
            HTTP_ACCEPT="image/avif",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/avif")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fpng&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/png")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fwebp&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/webp")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Favif&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/avif")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fgif&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(PARENT_HOST="localhost:8000")
class LocationApiTestCase(EssentialApiBase):
    def test_locations_api_gw_valid(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        nb_points = len(Device.objects.get(aid=dev_id).locations["timestamps"])
        self.assertEqual(nb_points, 2)

    def test_locations_api_gw_invalid_cast(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},NaN",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid data format", errors[0])

    def test_locations_api_gw_invalid_lon(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,182",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid longitude value", errors[0])

    def test_locations_api_gw_invalid_lat(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,100",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid latitude value", errors[0])

    def test_locations_api_gw_invalid_length(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Latitudes, longitudes, and timestamps, should have same amount of points",
            errors[0],
        )

    def test_locations_api_gw_bad_secret(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": "bad secret",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_locations_api_gw_old_dev_id_valid(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        d = Device.objects.create(aid="abcd1234")
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": d.aid,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": "bad secret",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_locations_api_gw_no_device(self):
        url = self.reverse_and_check("locations_api_gw", "/locations")
        t = time.time()
        res = self.client.post(
            url,
            {
                "device_id": "doesnotexist",
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": "bad secret",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("No such device ID", errors[0])


@override_settings(PARENT_HOST="localhost:8000")
class RegistrationApiTestCase(EssentialApiBase):
    def test_registration(self):
        device_id = self.get_device_id()
        user = User.objects.create_user("alice", "alice@example.com", "pa$$word123")
        club = Club.objects.create(name="Test club", slug="club")
        club.admins.set([user])
        event = Event.objects.create(
            club=club,
            name="Test event",
            open_registration=True,
            start_date=arrow.get().datetime,
            end_date=arrow.get().shift(hours=1).datetime,
        )
        url = reverse("event_register", host="api", kwargs={"event_id": event.aid})
        self.assertEqual(url, f"//api.localhost:8000/events/{event.aid}/register")
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Alice",
                "short_name": "🇺🇸 A",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # name exists
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Alice",
                "short_name": "🇺🇸 Al",
            },
            SERVER_NAME="api.localhost:8000",
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Competitor with same name already registered", errors[0])
        # short_name exists
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Albert",
                "short_name": "🇺🇸 A",
            },
            SERVER_NAME="api.localhost:8000",
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Competitor with same short name already registered", errors[0])
        # bad start_time
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Albert",
                "short_name": "🇺🇸 Al",
                "start_time": arrow.get().shift(hours=-1).datetime,
            },
            SERVER_NAME="api.localhost:8000",
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Competitor start time should be during the event time", errors[0]
        )
        # invalid start_time
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Bob",
                "short_name": "🇺🇸 B",
                "start_time": "unreadable",
            },
            SERVER_NAME="api.localhost:8000",
            format="json",
        )
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Start time could not be parsed", errors[0])
        # no name
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "",
                "short_name": "🇺🇸 B",
            },
            SERVER_NAME="api.localhost:8000",
            format="json",
        )
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Name is missing", errors[0])
        # no device
        res = self.client.post(
            url,
            {
                "device_id": "does not exists",
                "name": "Bob",
                "short_name": "🇺🇸 B",
            },
            SERVER_NAME="api.localhost:8000",
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Device ID not found", errors[0])
        # ok
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Bob",
                "short_name": "🇺🇸 B",
                "start_time": arrow.get().shift(minutes=+1).datetime,
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # ended event
        event.start_date = arrow.get().shift(hours=-1).datetime
        event.end_date = arrow.get().shift(minutes=-1).datetime
        event.save()
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Charles",
                "short_name": "🇺🇸 C",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        # ok event
        event.end_date = arrow.get().shift(minutes=1).datetime
        event.save()
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Charles",
                "short_name": "🇺🇸 C",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # private event not logged in
        event.end_date = arrow.get().shift(minutes=1).datetime
        event.privacy = PRIVACY_PRIVATE
        event.save()
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Dylan",
                "short_name": "🇺🇸 D",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        # private event logged in as not admin
        user_not_admin = User.objects.create_user(
            "bob", "bob@example.com", "pa$$word123"
        )
        self.client.force_login(user_not_admin)
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Dylan",
                "short_name": "🇺🇸 D",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        # private event logged in as admin ok
        self.client.force_login(user)
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Dylan",
                "short_name": "🇺🇸 D",
            },
            SERVER_NAME="api.localhost:8000",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

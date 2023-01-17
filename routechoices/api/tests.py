import json
import random
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
        self.user = User.objects.create_user(
            "alice", f"alice{random.randrange(1000)}@example.com", "pa$$word123"
        )

    def reverse_and_check(self, path, expected, host="api"):
        url = reverse(path, host=host)
        self.assertEqual(url, f"//{host}.routechoices.dev{expected}")
        return url

    def get_device_id(self):
        d = Device.objects.create()
        return d.aid


class EssentialApiTestCase1(EssentialApiBase):
    def test_api_root(self):
        url = self.reverse_and_check("api_doc", "/")
        res = self.client.get(url, SERVER_NAME="api.routechoices.dev")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_get_time(self):
        url = self.reverse_and_check("time_api", "/time")
        t1 = time.time()
        res = self.client.get(url, SERVER_NAME="api.routechoices.dev")
        t2 = time.time()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(t1 < res.data.get("time") < t2)

    def test_get_device_id_legacy(self):
        url = self.reverse_and_check("device_id_api", "/device_id")
        res = self.client.post(url, SERVER_NAME="api.routechoices.dev")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data.get("device_id")) == 8)
        self.assertTrue(res.data.get("device_id") != self.get_device_id())

    def test_create_device_id(self):
        url = self.reverse_and_check("device_api", "/device")
        res = self.client.post(url, SERVER_NAME="api.routechoices.dev")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.user)
        res = self.client.post(url, SERVER_NAME="api.routechoices.dev")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        dev_id = res.data.get("device_id")
        self.assertTrue(dev_id.isdigit())
        self.assertEqual(len(dev_id), 8)
        self.assertTrue(dev_id != self.get_device_id())


class ImeiApiTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.url = self.reverse_and_check("device_api", "/device")

    def test_get_imei_invalid(self):
        res = self.client.post(
            self.url, {"imei": "abcd"}, SERVER_NAME="api.routechoices.dev"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_imei_valid(self):
        res = self.client.post(
            self.url, {"imei": "123456789123458"}, SERVER_NAME="api.routechoices.dev"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        dev_id = res.data.get("device_id")
        self.assertTrue(dev_id.isdigit())
        self.assertEqual(len(dev_id), 8)
        self.assertNotEqual(dev_id, self.get_device_id())

        # request with same imei
        res = self.client.post(
            self.url, {"imei": "123456789123458"}, SERVER_NAME="api.routechoices.dev"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(dev_id, res.data.get("device_id"))

        # test device with alpha character get new id with only digits
        device = Device.objects.get(aid=dev_id)
        device.aid = "1234abcd"
        device.save()
        res = self.client.post(
            self.url, {"imei": "123456789123458"}, SERVER_NAME="api.routechoices.dev"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
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
            self.url, {"imei": "123456789123458"}, SERVER_NAME="api.routechoices.dev"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_dev_id = res.data.get("device_id")
        self.assertEqual(new_dev_id, "1234abcd")

        # test device with alpha character get new id if assigned a competitor in past
        event.end_date = arrow.get().shift(seconds=-1).datetime
        event.save()
        res = self.client.post(
            self.url, {"imei": "123456789123458"}, SERVER_NAME="api.routechoices.dev"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        new_dev_id = res.data.get("device_id")
        self.assertNotEqual(new_dev_id, "1234abcd")
        self.assertTrue(dev_id.isdigit())
        self.assertEqual(len(new_dev_id), 8)


class EventCreationApiTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.url = self.reverse_and_check("event_list", "/events")
        self.club = Club.objects.create(name="Test club", slug="club")
        self.club.admins.set([self.user])
        self.client.force_login(self.user)

    def test_ok(self):
        res = self.client.post(
            self.url,
            {
                "club_slug": "club",
                "end_date": arrow.now().shift(minutes=60),
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)


@override_settings(MEDIA_ROOT=Path(tempfile.gettempdir()))
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
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
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
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/jpeg")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
            HTTP_ACCEPT="image/avif",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/avif")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fpng&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/png")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fwebp&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/webp")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Favif&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/avif")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F1&styles=&format=image%2Fgif&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LocationApiTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.url = self.reverse_and_check("locations_api_gw", "/locations")

    def test_locations_api_gw_valid(self):
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        nb_points = len(Device.objects.get(aid=dev_id).locations["timestamps"])
        self.assertEqual(nb_points, 2)
        # Add more location
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.3,1.4",
                "longitudes": "3.3,3.4",
                "timestamps": f"{t+2},{t+3}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        nb_points = len(Device.objects.get(aid=dev_id).locations["timestamps"])
        self.assertEqual(nb_points, 4)
        # post same location again
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.3,1.4",
                "longitudes": "3.3,3.4",
                "timestamps": f"{t+2},{t+3}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        nb_points = len(Device.objects.get(aid=dev_id).locations["timestamps"])
        self.assertEqual(nb_points, 4)
        dev = Device.objects.get(aid=dev_id)
        dev.remove_duplicates()
        dev.save()
        nb_points = len(Device.objects.get(aid=dev_id).locations["timestamps"])
        self.assertEqual(nb_points, 4)

    def test_locations_api_gw_invalid_cast(self):
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},NaN",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid data format", errors[0])

    def test_locations_api_gw_invalid_lon(self):
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,182",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid longitude value", errors[0])

    def test_locations_api_gw_invalid_lat(self):
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,100",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid latitude value", errors[0])

    def test_locations_api_gw_invalid_length(self):
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1",
                "timestamps": f"{t},{t+1}",
                "secret": settings.POST_LOCATION_SECRETS[0],
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Latitudes, longitudes, and timestamps, should have same amount of points",
            errors[0],
        )

    def test_locations_api_gw_bad_secret(self):
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": "bad secret",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_locations_api_gw_no_secret_but_logged_in(self):
        self.client.force_login(self.user)
        dev_id = self.get_device_id()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": dev_id,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data.get("device_id"), dev_id)
        self.assertEqual(res.data.get("location_count"), 2)

    def test_locations_api_gw_old_dev_id_valid(self):
        # Original app didnt require any authentication to post location
        # The device id included alphabetical characters
        d = Device.objects.create(aid="abcd1234")
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": d.aid,
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": "bad secret",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_locations_api_gw_no_device(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "device_id": "doesnotexist",
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
                "secret": "bad secret",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("No such device ID", errors[0])


class RouteUploadApiTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.club = Club.objects.create(name="Test club", slug="club")
        self.event = Event.objects.create(
            club=self.club,
            name="Test event",
            open_registration=True,
            allow_route_upload=True,
            start_date=arrow.get().shift(seconds=-1).datetime,
            end_date=arrow.get().shift(hours=1).datetime,
        )
        self.club.admins.set([self.user])
        self.competitor = Competitor.objects.create(
            name="Alice", short_name="A", event=self.event
        )
        self.url = reverse(
            "competitor_route_upload",
            host="api",
            kwargs={"competitor_id": self.competitor.aid},
        )
        self.assertEqual(
            self.url, f"//api.routechoices.dev/competitors/{self.competitor.aid}/route"
        )

    def test_route_upload_api_valid(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{ t },{t + 1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Competitor.objects.get(aid=self.competitor.aid).device.location_count, 2
        )
        # Upload again on same competitor without being an admin
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.3,1.4",
                "longitudes": "3.3,3.4",
                "timestamps": f"{t+2},{t+3}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Competitor already assigned a route", errors[0])
        # Upload again on same competitor while being an admin
        self.client.force_login(self.user)
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.3,1.4,1.5",
                "longitudes": "3.3,3.4,3.5",
                "timestamps": f"{t+2},{t+3},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Competitor.objects.get(aid=self.competitor.aid).device.location_count, 3
        )

    def test_route_upload_api_invalid_cast(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},NaN",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid time value", errors[0])

        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},Nope",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid data format", errors[0])

        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,NaN",
                "timestamps": f"{t},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid longitude value", errors[0])

    def test_route_upload_api_invalid_lon(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,182",
                "timestamps": f"{t},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid longitude value", errors[0])

    def test_route_upload_api_invalid_lat(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,100",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid latitude value", errors[0])

    def test_route_upload_api_invalid_length(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Latitudes, longitudes, and timestamps, should have same amount of points",
            errors[0],
        )

    def test_route_upload_api_not_enough_points(self):
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1",
                "longitudes": "3.1",
                "timestamps": f"{t}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Minimum amount of locations is 2",
            errors[0],
        )

    def test_route_upload_api_not_allowed(self):
        self.event.allow_route_upload = False
        self.event.save()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_route_upload_api_not_started(self):
        self.event.start_date = arrow.get().shift(minutes=1).datetime
        self.event.save()
        t = time.time()
        res = self.client.post(
            self.url,
            {
                "latitudes": "1.1,1.2",
                "longitudes": "3.1,3.2",
                "timestamps": f"{t},{t+1}",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "Event not yet started",
            errors[0],
        )


class RegistrationApiTestCase(EssentialApiBase):
    def test_registration(self):
        device_id = self.get_device_id()
        club = Club.objects.create(name="Test club", slug="club")
        club.admins.set([self.user])
        event = Event.objects.create(
            club=club,
            name="Test event",
            open_registration=True,
            start_date=arrow.get().datetime,
            end_date=arrow.get().shift(hours=1).datetime,
        )
        url = reverse("event_register", host="api", kwargs={"event_id": event.aid})
        self.assertEqual(url, f"//api.routechoices.dev/events/{event.aid}/register")
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Alice",
                "short_name": "🇺🇸 A",
            },
            SERVER_NAME="api.routechoices.dev",
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
            SERVER_NAME="api.routechoices.dev",
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Name already in use in this event", errors[0])
        # short_name exists
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Albert",
                "short_name": "🇺🇸 A",
            },
            SERVER_NAME="api.routechoices.dev",
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Short name already in use in this event", errors[0])
        # bad start_time
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Albert",
                "short_name": "🇺🇸 Al",
                "start_time": arrow.get().shift(hours=-1).datetime,
            },
            SERVER_NAME="api.routechoices.dev",
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
            SERVER_NAME="api.routechoices.dev",
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
            SERVER_NAME="api.routechoices.dev",
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
            SERVER_NAME="api.routechoices.dev",
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
            SERVER_NAME="api.routechoices.dev",
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
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = json.loads(res.content)
        self.assertEqual(len(errors), 1)
        self.assertIn("Registration is closed", errors[0])
        # ended event but allow route upload
        event.start_date = arrow.get().shift(hours=-1).datetime
        event.end_date = arrow.get().shift(minutes=-1).datetime
        event.allow_route_upload = True
        event.save()
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Dick",
                "short_name": "🇺🇸 D",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # ok event
        event.end_date = arrow.get().shift(minutes=1).datetime
        event.allow_route_upload = False
        event.save()
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Elsa",
                "short_name": "🇺🇸 E",
            },
            SERVER_NAME="api.routechoices.dev",
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
                "name": "Frank",
                "short_name": "🇺🇸 F",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # private event logged in as not admin
        user_not_admin = User.objects.create_user(
            "bob", "bob@example.com", "pa$$word123"
        )
        self.client.force_login(user_not_admin)
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "George",
                "short_name": "🇺🇸 G",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # private event logged in as admin ok
        self.client.force_login(self.user)
        res = self.client.post(
            url,
            {
                "device_id": device_id,
                "name": "Hugh",
                "short_name": "🇺🇸 H",
            },
            SERVER_NAME="api.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

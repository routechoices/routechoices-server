import tempfile
from pathlib import Path

import arrow
from rest_framework import status
from rest_framework.test import override_settings

from routechoices.api.tests import EssentialApiBase
from routechoices.core.models import Club, Event, Map, MapAssignation


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
        raster_map.data_uri = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXN"
            "SR0IArs4c6QAAAA1JREFUGFdjED765z8ABZcC1M3x7TQAAAAASUVORK5CYII="
        )
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
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
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
        raster_map2.data_uri = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXN"
            "SR0IArs4c6QAAAA1JREFUGFdjED765z8ABZcC1M3x7TQAAAAASUVORK5CYII="
        )
        raster_map2.save()
        MapAssignation.objects.create(event=event, map=raster_map2, title="Other route")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/jpeg")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
            HTTP_ACCEPT="image/avif",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/avif")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F3&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fpng&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/png")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fwebp&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/webp")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Favif&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["content-type"], "image/avif")

        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={event.aid}%2F2&styles=&format=image%2Fgif&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        future_event = Event.objects.create(
            club=club,
            name="Test future event",
            open_registration=True,
            start_date=arrow.get().shift(minutes=1).datetime,
            end_date=arrow.get().shift(hours=10).datetime,
            map=raster_map,
        )
        res = self.client.get(
            f"{url}?service=WMS&request=GetMap&layers={future_event.aid}&styles=&format=image%2Fjpeg&transparent=false&version=1.1.1&width=512&height=512&srs=EPSG%3A3857&bbox=2690583.395638204,8727274.141488286,2693029.3805433298,8729720.12639341",
            SERVER_NAME="wms.routechoices.dev",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

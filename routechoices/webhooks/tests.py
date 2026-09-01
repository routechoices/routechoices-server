import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import arrow
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import User
from django.test.client import MULTIPART_CONTENT
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from routechoices.api.tests import EssentialApiBase
from routechoices.core.bg_tasks import rastilippu_update_event_url
from routechoices.core.models import Club, Event, EventSet, Map


class WebhookConsumer(APIClient):
    signature = None

    @classmethod
    def sign(cls, data):
        return hmac.new(
            cls.signature.encode("utf-8"),
            msg=data,
            digestmod=hashlib.sha256,
        ).hexdigest()

    def post(
        self,
        path,
        data=None,
        content_type=MULTIPART_CONTENT,
        **kwargs,
    ):
        data = self._encode_json({} if data is None else data, content_type)
        post_data = self._encode_data(data, content_type)
        return super().post(
            path,
            data,
            content_type,
            HTTP_X_SIGNATURE=self.sign(post_data[0]),
            **kwargs,
        )


class LemonSqueezyWebhookConsumer(WebhookConsumer):
    signature = settings.LEMONSQUEEZY_SIGNATURE


class RastiLippuWebhookConsumer(WebhookConsumer):
    signature = settings.RASTILIPPU_SIGNATURE


class LSWebHookTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.club = Club.objects.create(name="Kemiön Kiilat", slug="kiilat")
        self.club.creation_date = now() - timedelta(days=14)
        self.club.admins.set([self.user])
        self.webhook_client = LemonSqueezyWebhookConsumer(
            HTTP_HOST="api.routechoices.dev"
        )

    def test_invalid_signature(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        client = APIClient(HTTP_HOST="api.routechoices.dev")
        res = client.post(url, {"random": 123})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_signature(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        res = self.webhook_client.post(url, {"random": 123}, content_type="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_upgrade_club(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        res = self.webhook_client.post(
            url,
            {
                "data": {
                    "id": "123456",
                    "attributes": {
                        "first_order_item": {"variant_id": 1102505, "order_id": 123456}
                    },
                },
                "meta": {"custom_data": {"club": "kiilat"}},
            },
            HTTP_X_EVENT_NAME="order_created",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.upgraded)
        self.assertEqual(self.club.order_id, "LS-123456")
        self.assertTrue(self.club.can_modify_events)

    def test_downgrade_club(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        self.club.upgraded = True
        self.club.order_id = "LS-123456"
        self.club.save()
        res = self.webhook_client.post(
            url,
            {"data": {"attributes": {"order_id": 123456, "variant_id": 1102505}}},
            HTTP_X_EVENT_NAME="subscription_expired",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertFalse(self.club.upgraded)
        self.assertEqual(self.club.order_id, "")
        self.assertFalse(self.club.can_modify_events)

    def test_pause_club_subscription(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        self.club.upgraded = True
        self.club.order_id = "LS-123456"
        self.club.save()
        self.assertFalse(self.club.subscription_paused)
        self.assertTrue(self.club.can_modify_events)
        res = self.webhook_client.post(
            url,
            {
                "data": {
                    "attributes": {
                        "order_id": 123456,
                        "variant_id": 1102505,
                        "pause": {"mode": "void"},
                    }
                }
            },
            HTTP_X_EVENT_NAME="subscription_paused",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.subscription_paused)
        self.assertFalse(self.club.can_modify_events)

    def test_unpause_club_subscription(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy"
        )
        self.club.upgraded = True
        self.club.order_id = "LS-123456"
        self.club.subscription_paused_at = now() - timedelta(days=2)
        self.club.save()
        self.assertTrue(self.club.subscription_paused)
        self.assertFalse(self.club.can_modify_events)
        res = self.webhook_client.post(
            url,
            {
                "data": {
                    "attributes": {
                        "order_id": 123456,
                        "variant_id": 1102505,
                    }
                }
            },
            HTTP_X_EVENT_NAME="subscription_unpaused",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertFalse(self.club.subscription_paused)
        self.assertTrue(self.club.can_modify_events)


class RLWebHookTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.club = Club.objects.create(name="Kemiön Kiilat", slug="kiilat")
        self.club.creation_date = now() - timedelta(days=14)
        self.club.admins.set([self.user])
        self.webhook_client = RastiLippuWebhookConsumer(
            HTTP_HOST="api.routechoices.dev"
        )

    def test_invalid_signature(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        client = APIClient(HTTP_HOST="api.routechoices.dev")
        res = client.post(url, {"random": 123})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_signature(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        res = self.webhook_client.post(url, {"random": 123}, content_type="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_enable_club(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        res = self.webhook_client.post(
            url,
            {
                "action": "enable",
                "data": {
                    "order_id": "1234",
                    "club_slug": "kiilat",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.upgraded)
        self.assertEqual(self.club.order_id, "RL-1234")
        self.assertTrue(self.club.can_modify_events)

    def test_enable_club_fail(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        res = self.webhook_client.post(
            url,
            {
                "action": "enable",
                "data": {
                    "club_slug": "kiilat",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.webhook_client.post(
            url,
            {
                "action": "enable",
                "data": {
                    "order_id": "1234",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.webhook_client.post(
            url,
            {
                "action": "enable",
                "data": {
                    "order_id": "1234",
                    "club_slug": "kemki",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disable_club(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        self.club.upgraded = True
        self.club.order_id = "RL-1234"
        self.club.save()

        res = self.webhook_client.post(
            url,
            {
                "action": "disable",
                "data": {
                    "order_id": "1234",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.club.refresh_from_db()
        self.assertFalse(self.club.upgraded)
        self.assertEqual(self.club.order_id, "")
        self.assertFalse(self.club.can_modify_events)

    def test_disable_club_fail(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        self.club.upgraded = True
        self.club.order_id = "RL-1234"
        self.club.save()
        res = self.webhook_client.post(
            url,
            {
                "action": "disable",
                "data": {},
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.webhook_client.post(
            url,
            {
                "action": "disable",
                "data": {
                    "order_id": "12345",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.club.refresh_from_db()
        self.assertTrue(self.club.upgraded)
        self.assertEqual(self.club.order_id, "RL-1234")
        self.assertTrue(self.club.can_modify_events)

    @patch("routechoices.lib.rastilippu.requests")
    def test_create_event(self, mock_requests):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        self.club.upgraded = True
        self.club.order_id = "RL-1234"
        self.club.save()

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-12T13:00:00Z",
                    "end_datetime": "2026-08-12T19:00:00Z",
                    "courses": [],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        event_set = EventSet.objects.get(external_id="RL-1234")
        self.assertTrue(event_set.create_page)
        self.assertTrue(event_set.slug.startswith("turku-rastit-12-08-2026-"))
        self.assertEqual(
            event_set.external_metadata["start_date"], "2026-08-12T13:00:00+00:00"
        )
        self.assertEqual(
            event_set.external_metadata["end_date"], "2026-08-12T19:00:00+00:00"
        )
        self.assertEqual(
            event_set.external_metadata["uuid"], "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23"
        )
        self.assertEqual(
            event_set.url,
            res.json()["url"],
        )
        self.assertEqual(
            event_set.name,
            res.json()["name"],
            "Turku Rastit 12.08.2026",
        )

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit - 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-12T14:00:00Z",
                    "end_datetime": "2026-08-12T19:00:00Z",
                    "courses": [],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        event_set.refresh_from_db()
        self.assertEqual(
            event_set.external_metadata["start_date"], "2026-08-12T14:00:00+00:00"
        )
        self.assertEqual(
            event_set.external_metadata["end_date"], "2026-08-12T19:00:00+00:00"
        )
        self.assertEqual(
            event_set.external_metadata["uuid"], "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23"
        )
        self.assertEqual(
            event_set.name,
            res.json()["name"],
            "Turku Rastit - 12.08.2026",
        )

        # Create courses
        # We need to mock Rastilippu API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "1514276621",
                "name": "A-rata",
                "length": 3100,
                "controls": [
                    "75",
                    "69",
                    "52",
                    "50",
                    "40",
                    "61",
                    "51",
                    "42",
                    "43",
                    "44",
                    "53",
                    "45",
                    "60",
                    "54",
                    "64",
                    "63",
                    "46",
                    "47",
                    "49",
                    "70",
                    "77",
                ],
                "order": 1,
            },
            {
                "id": "1514276622",
                "name": "B-rata",
                "length": 3100,
                "controls": [
                    "67",
                    "55",
                    "52",
                    "71",
                    "40",
                    "61",
                    "41",
                    "51",
                    "43",
                    "44",
                    "56",
                    "45",
                    "60",
                    "54",
                    "59",
                    "46",
                    "48",
                    "47",
                    "49",
                    "70",
                    "77",
                ],
                "order": 2,
            },
            {
                "id": "1514276623",
                "name": "C-rata",
                "length": 2700,
                "controls": [
                    "75",
                    "52",
                    "71",
                    "61",
                    "41",
                    "53",
                    "45",
                    "60",
                    "43",
                    "64",
                    "63",
                    "65",
                    "57",
                    "48",
                    "47",
                    "70",
                    "77",
                ],
                "order": 3,
            },
            {
                "id": "1514276624",
                "name": "D-rata",
                "length": 2700,
                "controls": [
                    "67",
                    "52",
                    "50",
                    "61",
                    "41",
                    "56",
                    "45",
                    "44",
                    "43",
                    "42",
                    "54",
                    "59",
                    "57",
                    "48",
                    "47",
                    "70",
                    "77",
                ],
                "order": 4,
            },
        ]
        mock_requests.get.return_value = mock_response

        # Add courses to the event set
        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit - 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-12T14:00:00Z",
                    "end_datetime": "2026-08-12T19:00:00Z",
                    "courses": [
                        "1514276621",
                        "1514276622",
                        "1514276623",
                        "1514276624",
                    ],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()
        self.assertIn("courses", res_data)
        self.assertEqual(len(res_data["courses"]), 4)
        self.assertEqual(res_data["courses"][0]["irma_id"], "1514276621")
        self.assertIn("map_upload_url", res_data["courses"][0])

        first_course = event_set.events.get(external_id="RL-1514276621")
        self.assertEqual(res_data["courses"][0]["id"], first_course.aid)
        self.assertEqual(
            res_data["courses"][0]["map_upload_url"],
            f"https://dashboard.routechoices.dev/clubs/kiilat/events/{first_course.aid}/map",
        )
        self.assertEqual(first_course.name, "Turku Rastit - 12.08.2026 - A-rata")
        self.assertTrue(first_course.slug.startswith("turku-rastit-12-08-2026-a-rata-"))

        event_set.refresh_from_db()
        self.assertEqual(event_set.events.count(), 4)
        for event in event_set.events.all():
            self.assertEqual(
                event.start_date, arrow.get("2026-08-12T14:00:00Z").datetime
            )
            self.assertEqual(event.end_date, arrow.get("2026-08-12T19:00:00Z").datetime)

        # Change bundle date changes all events schedules
        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit - 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-11T14:00:00Z",
                    "end_datetime": "2026-08-11T19:00:00Z",
                    "courses": [
                        "1514276621",
                        "1514276622",
                        "1514276623",
                        "1514276624",
                    ],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        event_set.refresh_from_db()
        self.assertEqual(event_set.events.count(), 4)
        for event in event_set.events.all():
            self.assertEqual(
                event.start_date, arrow.get("2026-08-11T14:00:00Z").datetime
            )
            self.assertEqual(event.end_date, arrow.get("2026-08-11T19:00:00Z").datetime)

        # Adding a course
        mock_response.json.return_value.append({"id": "abc", "name": "RR"})
        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit - 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-11T14:00:00Z",
                    "end_datetime": "2026-08-11T19:00:00Z",
                    "courses": [
                        "1514276621",
                        "1514276622",
                        "1514276623",
                        "1514276624",
                        "abc",
                    ],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        event_set.refresh_from_db()
        self.assertEqual(event_set.events.count(), 5)
        self.assertTrue(event_set.events.filter(external_id="RL-abc").exists())

        # Removing a course
        mock_response.json.return_value.pop()
        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit - 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-11T14:00:00Z",
                    "end_datetime": "2026-08-11T19:00:00Z",
                    "courses": [
                        "1514276621",
                        "1514276622",
                        "1514276623",
                        "1514276624",
                    ],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        event_set.refresh_from_db()
        self.assertEqual(event_set.events.count(), 4)
        self.assertFalse(event_set.events.filter(external_id="RL-abc").exists())
        # Removing all courses
        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": {
                    "club_slug": "kiilat",
                    "name": "Turku Rastit - 12.08.2026",
                    "irma_id": "1234",
                    "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
                    "start_datetime": "2026-08-11T14:00:00Z",
                    "end_datetime": "2026-08-11T19:00:00Z",
                    "courses": [],
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        event_set.refresh_from_db()
        self.assertEqual(event_set.events.count(), 0)

    @patch("routechoices.lib.rastilippu.requests")
    def test_update_event_url_hook(self, mock_requests):
        self.club.upgraded = True
        self.club.order_id = "RL-1234"
        self.club.save()

        bundle = EventSet.objects.create(
            name="Test Bundle", slug="abc123", club=self.club, external_id="RL-6353"
        )
        event = Event.objects.create(
            name="RR",
            slug="rr",
            club=self.club,
            event_set=bundle,
            external_id="RL-1514276621",
            start_date=arrow.get("2026-08-11T14:00:00Z").datetime,
            end_date=arrow.get("2026-08-11T19:00:00Z").datetime,
        )
        event.save()

        raster_map = Map.objects.create(
            club=self.club,
            name="Test map",
            calibration_string_raw=(
                "61.45075,24.18994,61.44656,24.24721,"
                "61.42094,24.23851,61.42533,24.18156"
            ),
            width=1,
            height=1,
        )
        raster_map.data_uri = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6Q"
            "AAAA1JREFUGFdjED765z8ABZcC1M3x7TQAAAAASUVORK5CYII="
        )
        raster_map.save()

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_requests.post.return_value = mock_response

        with patch(
            "routechoices.core.bg_tasks.rastilippu_update_event_url"
        ) as mock_rl_update:
            event.map = raster_map
            event.save()
            mock_rl_update.assert_called_once_with(event.id)
            event.save()
            self.assertEqual(mock_rl_update.call_count, 1)

        mock_requests.post.assert_not_called()
        rastilippu_update_event_url.now(event.id)
        mock_requests.post.assert_called_once()

        data_sent = json.loads(mock_requests.post.call_args.kwargs["data"])
        self.assertEqual(data_sent["action"], "update_courses_gps_replay_pages")
        self.assertEqual(data_sent["data"]["irma_id"], "6353")
        self.assertEqual(data_sent["data"]["courses"][0]["course_id"], "1514276621")
        self.assertEqual(
            data_sent["data"]["courses"][0]["gps_replay_url"],
            "https://kiilat.routechoices.dev/rr",
        )

        with patch(
            "routechoices.core.bg_tasks.rastilippu_update_event_url"
        ) as mock_rl_update:
            event.map = None
            event.save()
            mock_rl_update.assert_called_once_with(event.id)
            event.save()
            self.assertEqual(mock_rl_update.call_count, 1)

        self.assertEqual(mock_requests.post.call_count, 1)
        rastilippu_update_event_url.now(event.id)
        self.assertEqual(mock_requests.post.call_count, 2)

        data_sent = json.loads(mock_requests.post.call_args.kwargs["data"])
        self.assertEqual(data_sent["action"], "update_courses_gps_replay_pages")
        self.assertEqual(data_sent["data"]["irma_id"], "6353")
        self.assertEqual(data_sent["data"]["courses"][0]["course_id"], "1514276621")
        self.assertEqual(data_sent["data"]["courses"][0]["gps_replay_url"], "")

    def test_create_event_fails(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        self.club.upgraded = True
        self.club.order_id = "RL-1234"
        self.club.save()

        correct_data = {
            "name": "Turku Rastit 12.08.2026",
            "irma_id": "1234",
            "uuid": "9fd89ce9-14cf-4a4d-93b3-1c3201c75e23",
            "start_datetime": "2026-08-12T13:00:00Z",
            "end_datetime": "2026-08-12T19:00:00Z",
        }

        # Missing name
        wrong_data = correct_data
        del wrong_data["name"]

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing irma_id
        wrong_data = correct_data
        del wrong_data["irma_id"]

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing uuid
        wrong_data = correct_data
        del wrong_data["uuid"]

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing start_datetime
        wrong_data = correct_data
        del wrong_data["start_datetime"]

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing end_datetime
        wrong_data = correct_data
        del wrong_data["end_datetime"]

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid end datetime
        wrong_data = correct_data
        wrong_data["end_datetime"] = "hello"

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid start datetime
        wrong_data = correct_data
        wrong_data["start_datetime"] = "hello"

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid datetimes
        wrong_data = correct_data
        wrong_data["end_datetime"] = correct_data["start_datetime"]
        wrong_data["start_datetime"] = correct_data["end_datetime"]

        res = self.webhook_client.post(
            url,
            {
                "action": "update_event",
                "data": wrong_data,
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # No event sets should have been created
        self.assertEqual(EventSet.objects.count(), 0)

    def test_retrieve_clubs(self):
        url = self.reverse_and_check(
            "webhooks:rastilippu_webhook", "/webhooks/rastilippu"
        )
        other_user = User.objects.create_user("bob", "bob@example.com", "pa$$word123")
        other_club = Club.objects.create(name="Kalevan Rasti", slug="kr", upgraded=True)
        other_club.creation_date = now() - timedelta(days=14)
        other_club.admins.set([other_user])

        EmailAddress.objects.create(
            email="kiila@kiilat.com", user=self.user, verified=True, primary=True
        )
        EmailAddress.objects.create(
            email=self.user.email, user=self.user, verified=True
        )
        EmailAddress.objects.create(
            email=other_user.email, user=other_user, verified=True, primary=True
        )

        res = self.webhook_client.post(
            url,
            {
                "action": "retrieve_clubs",
                "data": {},
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.webhook_client.post(
            url,
            {
                "action": "retrieve_clubs",
                "data": {"email": self.user.email},
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data["clubs"]), data["count"], 1)
        self.assertEqual(
            data["clubs"],
            [
                {
                    "slug": "kiilat",
                    "name": "Kemiön Kiilat",
                    "is_upgraded": False,
                }
            ],
        )

        res = self.webhook_client.post(
            url,
            {
                "action": "retrieve_clubs",
                "data": {"email": other_user.email},
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data["clubs"]), data["count"], 1)
        self.assertEqual(
            data["clubs"],
            [
                {
                    "slug": "kr",
                    "name": "Kalevan Rasti",
                    "is_upgraded": True,
                }
            ],
        )

        res = self.webhook_client.post(
            url,
            {
                "action": "retrieve_clubs",
                "data": {"email": "unknown or invalid email"},
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data["clubs"]), data["count"], 0)
        self.assertEqual(data["clubs"], [])

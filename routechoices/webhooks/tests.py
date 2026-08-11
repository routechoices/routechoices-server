import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.test.client import MULTIPART_CONTENT
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from routechoices.api.tests import EssentialApiBase
from routechoices.core.models import Club, EventSet


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

    def test_create_event(self):
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
                    "start_datetime": "2026-08-12T13:00:00Z",
                    "end_datetime": "2026-08-12T19:00:00Z",
                },
            },
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        event_set = EventSet.objects.get(external_id="RL-1234")
        self.assertTrue(event_set.create_page)
        self.assertEqual(
            event_set.external_metadata["start_date"], "2026-08-12T13:00:00+00:00"
        )
        self.assertEqual(
            event_set.external_metadata["end_date"], "2026-08-12T19:00:00+00:00"
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
                    "start_datetime": "2026-08-12T14:00:00Z",
                    "end_datetime": "2026-08-12T19:00:00Z",
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
            event_set.name,
            res.json()["name"],
            "Turku Rastit - 12.08.2026",
        )
        # TODO: test sub events are updated too

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

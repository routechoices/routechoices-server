import hashlib
import hmac

from django.conf import settings
from django.test.client import MULTIPART_CONTENT
from rest_framework import status
from rest_framework.test import APIClient

from routechoices.api.tests import EssentialApiBase
from routechoices.core.models import Club, IndividualDonator


class LemonSqueezyAPIClient(APIClient):
    @staticmethod
    def get_signature(data):
        digest = hmac.new(
            settings.LEMONSQUEEZY_SIGNATURE.encode("utf-8"),
            msg=data,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return digest

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
            HTTP_X_SIGNATURE=self.get_signature(post_data[0]),
            **kwargs,
        )


class WebHookTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.club = Club.objects.create(name="Kemiön Kiilat", slug="kiilat")
        self.club.admins.set([self.user])
        self.ls_client = LemonSqueezyAPIClient(HTTP_HOST="www.routechoices.dev")

    def test_invalid_signature(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy", host="www"
        )
        client = APIClient(HTTP_HOST="www.routechoices.dev")
        res = client.post(url, {"random": 123})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_signature(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy", host="www"
        )
        res = self.ls_client.post(url, {"random": 123}, content_type="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_upgrade_club(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy", host="www"
        )
        res = self.ls_client.post(
            url,
            {"data": {"id": "abc123"}, "meta": {"custom_data": {"club": "kiilat"}}},
            HTTP_X_EVENT_NAME="order_created",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.upgraded)
        self.assertEqual(self.club.order_id, "abc123")

    def test_downgrade_club(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy", host="www"
        )
        self.club.upgraded = True
        self.club.order_id = "abc123"
        self.club.save()
        res = self.ls_client.post(
            url,
            {"data": {"attributes": {"order_id": "abc123"}}},
            HTTP_X_EVENT_NAME="subscription_expired",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertFalse(self.club.upgraded)
        self.assertEqual(self.club.order_id, "")

    def test_upgrade_person(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy", host="www"
        )
        res = self.ls_client.post(
            url,
            {
                "data": {
                    "id": "abc123",
                    "attributes": {
                        "user_name": "Bill Gates",
                        "user_email": "bill@microsoft.com",
                    },
                }
            },
            HTTP_X_EVENT_NAME="order_created",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(
            IndividualDonator.objects.filter(order_id="abc123", upgraded=True).exists()
        )

    def test_downgrade_person(self):
        url = self.reverse_and_check(
            "webhooks:lemonsqueezy_webhook", "/webhooks/lemonsqueezy", host="www"
        )
        p = IndividualDonator.objects.create(
            name="Bill Gates",
            email="bill@microsoft.com",
            upgraded=True,
            order_id="abc123",
        )
        res = self.ls_client.post(
            url,
            {"data": {"attributes": {"order_id": "abc123"}}},
            HTTP_X_EVENT_NAME="subscription_expired",
            content_type="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(IndividualDonator.objects.filter(id=p.id).exists())

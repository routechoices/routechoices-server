import arrow
from allauth.account.models import EmailAddress
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient

from routechoices.api.tests import EssentialApiBase
from routechoices.core.models import Club, Event, EventSet


class SiteViewsTestCase(EssentialApiBase):
    def setUp(self):
        super().setUp()
        self.club = Club.objects.create(name="Kemiön Kiilat", slug="kiilat")
        self.club.admins.set([self.user])

    def test_events_page_loads(self):
        s = EventSet.objects.create(
            club=self.club,
            name="Killa Cup",
        )
        Event.objects.create(
            name="Kiila Cup 1",
            slug="kiila-cup-1",
            club=self.club,
            start_date=arrow.now().shift(days=-112).datetime,
            end_date=arrow.now().shift(days=-111).datetime,
            event_set=s,
        )
        Event.objects.create(
            name="Kiila Cup 2",
            slug="kiila-cup-2",
            club=self.club,
            start_date=arrow.now().shift(hours=-12).datetime,
            end_date=arrow.now().shift(hours=-11).datetime,
            event_set=s,
        )
        Event.objects.create(
            name="Training",
            slug="training-1",
            club=self.club,
            start_date=arrow.now().shift(hours=-2).datetime,
            end_date=arrow.now().shift(hours=-1).datetime,
        )

        client = APIClient(HTTP_HOST="www.routechoices.dev")

        url = self.reverse_and_check("site:events_view", "/events", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = client.get(f"{url}?q=Kiila+Cup+2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, "Kiila Cup 1")
        self.assertContains(response, "Kiila Cup 2")
        response = client.get(f'{url}?q="Cup+2"')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, "Kiila Cup 1")
        self.assertContains(response, "Kiila Cup 2")
        response = client.get(
            f"{url}?year={arrow.get().year}&month={arrow.get().month}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, "Kiila Cup 1")
        self.assertContains(response, "Kiila Cup 2")

    def test_semi_static_pages_loads(self):
        client = APIClient(HTTP_HOST="www.routechoices.dev")

        url = self.reverse_and_check("site:home_view", "/", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = client.get("/favicon.ico")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = client.get("/robots.txt")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = self.reverse_and_check("site:trackers_view", "/trackers", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = self.reverse_and_check("site:contact_view", "/contact", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = self.reverse_and_check("site:pricing_view", "/pricing", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_send_message(self):
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )
        client = APIClient(HTTP_HOST="www.routechoices.dev")
        client.force_login(self.user)
        url = self.reverse_and_check("site:contact_view", "/contact", host="www")
        response = client.post(
            url, {"subject": "Hello, can I ask a question?", "message": "Does it work?"}
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue("Hello, can I ask a question?" in mail.outbox[0].subject)
        self.assertTrue(self.user.email in mail.outbox[0].subject)
        self.assertTrue(mail.outbox[0].body.startswith("Does it work?"))

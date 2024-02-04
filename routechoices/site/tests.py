import arrow
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
            start_date=arrow.now().shift(days=-12).datetime,
            end_date=arrow.now().shift(days=-11).datetime,
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
        self.assertEqual(response.status_code, 200)
        response = client.get(f"{url}?q=Kiila+Cup+2")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Kiila Cup 1")
        self.assertContains(response, "Kiila Cup 2")

    def test_semi_static_pages_loads(self):
        client = APIClient(HTTP_HOST="www.routechoices.dev")

        url = self.reverse_and_check("site:home_view", "/", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

        url = self.reverse_and_check("site:trackers_view", "/trackers", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

        url = self.reverse_and_check("site:contact_view", "/contact", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

        url = self.reverse_and_check("site:pricing_view", "/pricing", host="www")
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

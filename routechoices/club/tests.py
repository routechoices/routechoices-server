import arrow
from django.contrib.auth.models import User
from django.test import Client, LiveServerTestCase

from routechoices.core.models import Club, Event


class ClubViewsTestCase(LiveServerTestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="kiilat.routechoices.dev:8081")
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "pa$$word123"
        )
        self.club = Club.objects.create(name="Kemiön Kiilat", slug="kiilat")
        self.club.admins.set([self.user])

    def test_event_pages_loads(self):
        e = Event.objects.create(
            name="Kiila Cup 1",
            slug="kiila-cup-1",
            club=self.club,
            start_date=arrow.now().shift(hours=-1).datetime,
            end_date=arrow.now().shift(hours=1).datetime,
        )

        response = self.client.get(f"{self.live_server_url}/kiila-cup-1")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-1/export")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-1/registration")
        self.assertEqual(response.status_code, 404)
        e.open_registration = True
        e.save()
        response = self.client.get(f"{self.live_server_url}/kiila-cup-1/registration")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-1/route-upload")
        self.assertEqual(response.status_code, 404)
        e.allow_route_upload = True
        e.save()
        response = self.client.get(f"{self.live_server_url}/kiila-cup-1/route-upload")
        self.assertEqual(response.status_code, 200)

    def test_future_event_pages_loads(self):
        Event.objects.create(
            name="Kiila Cup 2",
            slug="kiila-cup-2",
            club=self.club,
            start_date=arrow.now().shift(hours=1).datetime,
            end_date=arrow.now().shift(hours=2).datetime,
            open_registration=True,
            allow_route_upload=True,
        )

        response = self.client.get(f"{self.live_server_url}/kiila-cup-2")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-2/export")
        self.assertEqual(response.status_code, 404)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-2/registration")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-2/route-upload")
        self.assertEqual(response.status_code, 404)

    def test_past_event_pages_loads(self):
        Event.objects.create(
            name="Kiila Cup 3",
            slug="kiila-cup-3",
            club=self.club,
            start_date=arrow.now().shift(hours=-2).datetime,
            end_date=arrow.now().shift(hours=-1).datetime,
            open_registration=True,
            allow_route_upload=True,
        )

        response = self.client.get(f"{self.live_server_url}/kiila-cup-3")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-3/export")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-3/registration")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sorry, Registration is closed")

        response = self.client.get(f"{self.live_server_url}/kiila-cup-3/route-upload")
        self.assertEqual(response.status_code, 200)

    def test_private_event_page_load(self):
        Event.objects.create(
            name="Kiila Cup 4",
            slug="kiila-cup-4",
            club=self.club,
            start_date=arrow.now().shift(hours=-1).datetime,
            end_date=arrow.now().shift(hours=1).datetime,
            privacy="private",
            open_registration=True,
            allow_route_upload=True,
        )

        response = self.client.get(f"{self.live_server_url}/kiila-cup-4")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-4/export")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-4/registration")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-4/route-upload")
        self.assertEqual(response.status_code, 200)

        self.client.login(username="alice", password="pa$$word123")
        response = self.client.get(f"{self.live_server_url}/kiila-cup-4")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"{self.live_server_url}/kiila-cup-4/export")
        self.assertEqual(response.status_code, 200)

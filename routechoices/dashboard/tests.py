import random
from io import BytesIO

import arrow
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django_hosts.resolvers import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    Event,
    EventSet,
    ImeiDevice,
    Map,
)


class EssentialDashboardBase(APITestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST="www.routechoices.dev")
        self.club = Club.objects.create(name="My Club", slug="myclub")
        self.user = User.objects.create_user(
            "alice", f"alice{random.randrange(1000)}@example.com", "pa$$word123"
        )
        self.club.admins.set([self.user])
        self.client.force_login(self.user)
        self.client.get(f"/dashboard/club/{self.club.aid}")

    def reverse_and_check(
        self,
        path,
        expected,
        extra_kwargs=None,
        host_kwargs=None,
    ):
        url = reverse(path, host="www", kwargs=extra_kwargs, host_kwargs=host_kwargs)
        self.assertEqual(url, f"//www.routechoices.dev{expected}")
        return url


class TestDashboard(EssentialDashboardBase):
    def test_change_club_slug(self):
        url = self.reverse_and_check("dashboard:club_view", "/dashboard/club")

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(
            url,
            {"name": self.club.name, "admins": self.user.pk, "slug": "mynewclubslug"},
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "invalid-feedback")

        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": "mynewestclubslug",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, "invalid-feedback")
        self.assertContains(
            res, "Domain prefix can be changed only once every 72 hours."
        )

        res = self.client.post(
            url,
            {"name": self.club.name, "admins": self.user.pk, "slug": "myclub"},
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "invalid-feedback")

        Club.objects.create(name="Other Club", slug="mynewclubslug")

        res = self.client.post(
            url,
            {"name": self.club.name, "admins": self.user.pk, "slug": "mynewclubslug"},
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, "invalid-feedback")
        self.assertContains(res, "Domain prefix already registered.")

    def test_change_club_logo(self):
        url = self.reverse_and_check("dashboard:club_view", "/dashboard/club")

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        image = Image.new("RGB", (200, 300), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "PNG")
        logo = SimpleUploadedFile(
            "logo.png", buffer.getvalue(), content_type="image/png"
        )
        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": self.club.slug,
                "logo": logo,
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "invalid-feedback")

        image = Image.new("RGB", (300, 200), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "PNG")
        logo = SimpleUploadedFile(
            "logo.png", buffer.getvalue(), content_type="image/png"
        )
        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": self.club.slug,
                "logo": logo,
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "invalid-feedback")

        image = Image.new("RGB", (100, 100), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "PNG")
        logo = SimpleUploadedFile(
            "logo.png", buffer.getvalue(), content_type="image/png"
        )
        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": self.club.slug,
                "logo": logo,
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, "invalid-feedback")
        self.assertContains(res, "The image is too small, minimum 128x128 pixels")

    def test_change_club_banner(self):
        url = self.reverse_and_check("dashboard:club_view", "/dashboard/club")

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        image = Image.new("RGB", (700, 400), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "JPEG")
        banner = SimpleUploadedFile(
            "banner.jpg", buffer.getvalue(), content_type="image/jpeg"
        )
        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": self.club.slug,
                "banner": banner,
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "invalid-feedback")

        image = Image.new("RGB", (800, 400), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "JPEG")
        banner = SimpleUploadedFile(
            "banner.jpg", buffer.getvalue(), content_type="image/jpeg"
        )
        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": self.club.slug,
                "banner": banner,
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "invalid-feedback")

        image = Image.new("RGB", (100, 100), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "JPEG")
        banner = SimpleUploadedFile(
            "banner.jpg", buffer.getvalue(), content_type="image/jpeg"
        )
        res = self.client.post(
            url,
            {
                "name": self.club.name,
                "admins": self.user.pk,
                "slug": self.club.slug,
                "banner": banner,
            },
            follow=True,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, "invalid-feedback")
        self.assertContains(res, "The image is too small, minimum 600x315 pixels")

    def test_device_lists(self):
        device = Device.objects.create()

        url = self.reverse_and_check(
            "dashboard:device_add_view", "/dashboard/devices/new"
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(url, {"device": device.id, "nickname": "MyTrckr"})
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)

        url = self.reverse_and_check("dashboard:device_list_view", "/dashboard/devices")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, device.id)
        self.assertContains(res, "MyTrckr")

        url = self.reverse_and_check(
            "dashboard:device_list_download", "/dashboard/devices.csv"
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, f"MyTrckr;{device.aid};\n")

        ImeiDevice.objects.create(imei="012345678901237", device=device)

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, f"MyTrckr;{device.aid};012345678901237\n")

    def test_delete_club(self):
        url = self.reverse_and_check(
            "dashboard:club_delete_view", "/dashboard/club/delete"
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(url, {"password": "not the password"})
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertTrue(Club.objects.filter(id=self.club.id).exists())
        res = self.client.post(url, {"password": "pa$$word123"})
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertFalse(Club.objects.filter(id=self.club.id).exists())

    def test_edit_map(self):
        raster_map = Map.objects.create(
            club=self.club,
            name="Test map",
            corners_coordinates=(
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

        url = self.reverse_and_check(
            "dashboard:map_edit_view",
            f"/dashboard/maps/{raster_map.aid}",
            extra_kwargs={"map_id": raster_map.aid},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        image = Image.new("RGB", (100, 100), (255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, "JPEG")
        banner = SimpleUploadedFile(
            "map.jpg", buffer.getvalue(), content_type="image/jpeg"
        )

        res = self.client.post(
            url,
            {
                "name": "My Test Map",
                "image": banner,
                "corners_coordinates": "61.45075,24.18994,61.44656,24.24721,61.42094,24.23851,61.42533,24.18157",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)

        url = self.reverse_and_check(
            "dashboard:map_delete_view",
            f"/dashboard/maps/{raster_map.aid}/delete",
            extra_kwargs={"map_id": raster_map.aid},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertFalse(Map.objects.filter(id=raster_map.id).exists())

    def test_edit_event_sets(self):
        # Create event set
        url = self.reverse_and_check(
            "dashboard:event_set_create_view",
            "/dashboard/event-sets/new",
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(url, {"name": "Tough Competition"})
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)

        # List event set
        url = self.reverse_and_check(
            "dashboard:event_set_list_view",
            "/dashboard/event-sets",
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertContains(res, "Tough Competition")

        # Edit event set
        es = EventSet.objects.all().first()
        url = self.reverse_and_check(
            "dashboard:event_set_edit_view",
            f"/dashboard/event-sets/{es.aid}",
            extra_kwargs={"event_set_id": es.aid},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(url, {"name": "Easy Competition"})
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        res = self.client.get("/dashboard/event-sets")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "Tough Competition")
        self.assertContains(res, "Easy Competition")

        # Delete event set
        url = self.reverse_and_check(
            "dashboard:event_set_delete_view",
            f"/dashboard/event-sets/{es.aid}/delete",
            extra_kwargs={"event_set_id": es.aid},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        res = self.client.get("/dashboard/event-sets")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotContains(res, "Tough Competition")
        self.assertNotContains(res, "Easy Competition")
        self.assertFalse(EventSet.objects.filter(id=es.id).exists())

    def test_delete_event(self):
        event = Event.objects.create(
            club=self.club,
            slug="abc",
            name="WOC Long Distance",
            start_date=arrow.get("2023-08-01T00:00:00Z").datetime,
            end_date=arrow.get("2023-08-01T23:59:59Z").datetime,
        )
        url = self.reverse_and_check(
            "dashboard:event_delete_view",
            f"/dashboard/events/{event.aid}/delete",
            extra_kwargs={"event_id": event.aid},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertFalse(Event.objects.filter(id=event.id).exists())

    def test_competitors_page(self):
        event = Event.objects.create(
            club=self.club,
            slug="abc",
            name="WOC Long Distance",
            start_date=arrow.get("2023-08-01T00:00:00Z").datetime,
            end_date=arrow.get("2023-08-01T23:59:59Z").datetime,
        )
        comps = []
        for i in range(120):
            c = Competitor(
                event=event,
                name="c {i}",
                short_name=f"c{i}",
            )
            comps.append(c)
        Competitor.objects.bulk_create(comps)
        url = self.reverse_and_check(
            "dashboard:event_competitors_view",
            f"/dashboard/events/{event.aid}/competitors",
            extra_kwargs={"event_id": event.aid},
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class TestInviteFlow(APITestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST="www.routechoices.dev")
        self.club = Club.objects.create(name="My Club", slug="myclub")
        self.user = User.objects.create_user(
            "alice", f"alice{random.randrange(1000)}@example.com", "pa$$word123"
        )
        self.user2 = User.objects.create_user(
            "bob", f"bob{random.randrange(1000)}@example.com", "pa$$word123"
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )
        EmailAddress.objects.create(
            user=self.user2, email=self.user2.email, primary=True, verified=True
        )

        self.club.admins.set([self.user])

    def test_request_invite(self):
        self.client.force_login(self.user2)
        self.client.get("/dashboard/request-invite/")
        res = self.client.post("/dashboard/request-invite/", {"club": self.club.id})
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            f"Request for an invitation to manage club { self.club }"
            in mail.outbox[0].subject
        )
        self.assertTrue(
            mail.outbox[0].body.startswith(
                f"Hello,\n\nA user ({ self.user2.email }) has requested an invite to manage the club"
            )
        )

    def test_send_invite(self):
        self.client.force_login(self.user)
        self.client.get(f"/dashboard/club/{self.club.aid}")
        self.client.get("/dashboard/club/send-invite/")
        res = self.client.post(
            "/dashboard/club/send-invite/", {"email": self.user2.email}
        )
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            f"Invitation to manage club { self.club } on " in mail.outbox[0].subject
        )

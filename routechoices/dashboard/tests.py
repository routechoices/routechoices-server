import random
from io import BytesIO

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django_hosts.resolvers import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from routechoices.core.models import Club


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


class TestEditClub(EssentialDashboardBase):
    def test_change_slug(self):
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

    def test_change_logo(self):
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

    def test_change_banner(self):
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
        res = self.client.post("/dashboard/request-invite/", {"club": 1})
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

import random

from django.contrib.auth.models import User
from django_hosts.resolvers import reverse
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

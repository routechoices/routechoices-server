import arrow
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand

from routechoices.core.models import Club, Device, Event


class Command(BaseCommand):
    help = "Reset the DB before e2e tests"

    def handle(self, *args, **options):
        call_command("flush", "--noinput")
        call_command("migrate", "--noinput")
        s = Site.objects.first()
        s.domain = "routechoices.dev"
        s.name = "Routechoices.com"
        s.save()
        Device.objects.create(aid=12345678)
        admin_user = User.objects.create_user(
            "admin", "admin@routechoices.com", "pa$$word123"
        )

        club = Club.objects.create(name="Halden SK", slug="halden-sk")
        club.admins.set([admin_user])

        Event.objects.create(
            club=club,
            name="My future event",
            slug="future-default",
            start_date=arrow.now().shift(days=2).datetime,
            end_date=arrow.now().shift(days=3).datetime,
        )
        Event.objects.create(
            club=club,
            name="My future event with open registration",
            slug="future-open-registration",
            start_date=arrow.now().shift(days=2).datetime,
            end_date=arrow.now().shift(days=3).datetime,
            open_registration=True,
        )
        Event.objects.create(
            club=club,
            name="My future event with upload allowed",
            slug="future-upload-allowed",
            start_date=arrow.now().shift(days=2).datetime,
            end_date=arrow.now().shift(days=3).datetime,
            allow_route_upload=True,
        )
        Event.objects.create(
            club=club,
            name="My future event with open registration and upload allowed",
            slug="future-open-registration-upload-allowed",
            start_date=arrow.now().shift(days=2).datetime,
            end_date=arrow.now().shift(days=3).datetime,
            open_registration=True,
            allow_route_upload=True,
        )

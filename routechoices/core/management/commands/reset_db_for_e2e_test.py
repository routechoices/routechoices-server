import arrow
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand

from routechoices.core.models import Club, Device, Event


class Command(BaseCommand):
    help = "Reset the DB before tests"

    def add_arguments(self, parser):
        parser.add_argument("--spec", type=str, required=True)

    def handle(self, *args, **options):
        call_command("flush", "--noinput")
        call_command("migrate", "--noinput")
        s = Site.objects.all().first()
        s.domain = "routechoices.dev"
        s.name = "Routechoices.com"
        s.save()
        Device.objects.create(aid=12345678)
        User.objects.create_user("admin", "admin@routechoices.com", "pa$$word123")
        spec_file = options["spec"]
        if spec_file == "cypress/e2e/registration-flow.cy.js":
            club = Club.objects.create(name="Halden SK", slug="halden-sk")
            Event.objects.create(
                club=club,
                name="Jukola 2040 - 1st Leg",
                slug="Jukola-2040-1st-leg",
                start_date=arrow.get("2040-06-15 20:00:00").datetime,
                end_date=arrow.get("2040-06-16 20:00:00").datetime,
                open_registration=True,
            )

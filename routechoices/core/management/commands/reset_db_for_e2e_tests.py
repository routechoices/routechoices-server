import arrow
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand

from routechoices.core.models import Club, Competitor, Device, Event, FrontPageFeedback


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
        Device.objects.create(aid=10000000, gpsseuranta_known=True)
        admin_user = User.objects.create_user(
            "admin", "admin@routechoices.com", "pa$$word123"
        )
        other_user = User.objects.create_user(
            "test-user", "test@routechoices.com", "pa$$word123"
        )

        club = Club.objects.create(name="Kimito SK", slug="kimito-sk")
        club.admins.set([admin_user, other_user])

        Event.objects.create(
            club=club,
            name="My future event",
            slug="future-default",
            start_date=arrow.now().shift(days=2).datetime,
            end_date=arrow.now().shift(days=3).datetime,
        )
        Event.objects.create(
            club=club,
            name="My future open event with open registration",
            slug="future-open-registration",
            start_date=arrow.now().shift(days=2).datetime,
            end_date=arrow.now().shift(days=3).datetime,
            open_registration=True,
        )
        ev = Event.objects.create(
            club=club,
            name="My event with open registration and upload allowed",
            slug="open-registration-upload-allowed",
            start_date=arrow.get("2019-06-15T20:00:00Z").datetime,
            end_date=arrow.now().shift(days=3).datetime,
            open_registration=True,
            allow_route_upload=True,
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

        Competitor.objects.create(
            user=admin_user,
            event=ev,
            name="Aatos",
            short_name="A",
        )

        FrontPageFeedback.objects.create(
            name="Anonymous", club_name="AA", content="Great Software", stars=5
        )

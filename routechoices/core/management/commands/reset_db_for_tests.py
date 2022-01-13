from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset the DB before tests"

    def handle(self, *args, **options):
        call_command("flush", "--noinput")
        call_command("migrate", "--noinput")
        s = Site.objects.all().first()
        s.domain = "routechoices.dev"
        s.name = "Routechoices.com"
        s.save()
        User.objects.create_user("admin", "admin@routechoices.com", "pa$$word123")

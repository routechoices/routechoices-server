from allauth.account.models import EmailAddress
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export users email list"

    def handle(self, *args, **options):
        email_list = EmailAddress.objects.filter(
            primary=True, verified=True
        ).values_list("email", flat=True)
        self.stdout.write("\n".join(email_list))

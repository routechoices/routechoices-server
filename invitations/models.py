import datetime

from routechoices.lib.helpers import get_current_site

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse

from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from . import signals
from .adapters import get_invitations_adapter
from .app_settings import app_settings
from .base_invitation import AbstractBaseInvitation


class Invitation(AbstractBaseInvitation):
    email = models.EmailField(
        verbose_name=_("e-mail address"),
        max_length=app_settings.EMAIL_MAX_LENGTH,
    )
    club = models.ForeignKey(
        "core.Club", related_name="invitations", on_delete=models.CASCADE
    )
    created = models.DateTimeField(verbose_name=_("created"), default=timezone.now)

    def __str__(self):
        return f"Invite to club {self.club}: {self.email}"

    @classmethod
    def create(cls, email, club, inviter=None, **kwargs):
        key = get_random_string(64).lower()
        instance = cls._default_manager.create(
            email=email, club=club, key=key, inviter=inviter, **kwargs
        )
        return instance

    def key_expired(self):
        expiration_date = self.sent + datetime.timedelta(
            days=app_settings.INVITATION_EXPIRY,
        )
        return expiration_date <= timezone.now()

    def send_invitation(self, request, **kwargs):
        current_site = get_current_site()
        invite_url = reverse(app_settings.CONFIRMATION_URL_NAME, args=[self.key])
        invite_url = request.build_absolute_uri(invite_url)
        ctx = kwargs
        ctx.update(
            {
                "invite_url": invite_url,
                "site_name": current_site.name,
                "email": self.email,
                "club": self.club,
                "key": self.key,
                "inviter": self.inviter,
            },
        )

        email_template = "invitations/email/email_invite"

        get_invitations_adapter().send_mail(email_template, self.email, ctx)
        self.sent = timezone.now()
        self.save()

        signals.invite_url_sent.send(
            sender=self.__class__,
            instance=self,
            invite_url_sent=invite_url,
            inviter=self.inviter,
        )

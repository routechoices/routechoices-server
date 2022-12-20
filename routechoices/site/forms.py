from allauth.account.adapter import get_adapter
from allauth.account.forms import ResetPasswordForm as OrigResetPasswordForm
from allauth.account.utils import filter_users_by_email
from django.contrib.sites.shortcuts import get_current_site
from django.core.validators import FileExtensionValidator
from django.db.models import Q
from django.forms import (
    CharField,
    ChoiceField,
    FileField,
    Form,
    ModelChoiceField,
    Textarea,
)

from routechoices.core.models import Competitor, Device


class ResetPasswordForm(OrigResetPasswordForm):
    def clean_email(self):
        email = self.cleaned_data["email"]
        email = get_adapter().clean_email(email)
        self.users = filter_users_by_email(email, is_active=True)
        return self.cleaned_data["email"]

    def save(self, request, **kwargs):
        email = super().save(request, **kwargs)
        if len(self.users) == 0:
            current_site = get_current_site(request)
            context = {
                "current_site": current_site,
                "request": request,
            }
            get_adapter(request).send_mail(
                "account/email/password_reset_nomatch", email, context
            )
        return self.cleaned_data["email"]


class RegisterForm(Form):
    name = CharField(max_length=64, required=True)
    short_name = CharField(max_length=64, required=False)
    device_id = ModelChoiceField(
        required=False, queryset=Device.objects.none(), label="Device ID"
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)


class CompetitorUploadGPXForm(Form):
    competitor_aid = ChoiceField(required=True, choices=[], label="Competitor")
    gpx_file = FileField(
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=["gpx"])],
        label="GPX File",
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        competitors = list(
            Competitor.objects.select_related("device")
            .filter(event=event)
            .filter(
                Q(device__locations_encoded_compressed=b"") | Q(device__isnull=True)
            )
        )
        self.fields["competitor_aid"].choices = [(c.aid, c.name) for c in competitors]


class ContactForm(Form):
    subject = CharField(required=True, max_length=128)
    message = CharField(widget=Textarea, required=True)

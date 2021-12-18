from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms import (
    CharField,
    FileField,
    Form,
    HiddenInput,
    ModelChoiceField,
    ModelForm,
    EmailField,
    Textarea,
)
from django_hosts.resolvers import reverse
from django.utils.timezone import now
from django.contrib.sites.shortcuts import get_current_site

from allauth.account.forms import ResetPasswordForm as OrigResetPasswordForm
from allauth.account.adapter import get_adapter
from allauth.account.utils import filter_users_by_email

from captcha.fields import CaptchaField

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
            context ={
                "current_site": current_site,
                "request": request,
            }
            get_adapter(request).send_mail(
                "account/email/password_reset_nomatch", email, context
            )
        return self.cleaned_data["email"]


class UploadGPXForm(Form):
    name = CharField(max_length=64, required=True)
    gpx_file = FileField(
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=['gpx'])]
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.event and self.event.competitors.filter(name=name).exists():
            raise ValidationError('Name already taken')
        return name
        

class CompetitorForm(ModelForm):
    device = ModelChoiceField(required=True, queryset=Device.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device'].help_text = f"<find out how to get a device ID from the <a href=\"{reverse('site:trackers_view')}\">trackers page</a>"

    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name')
        widgets = {
            'event': HiddenInput(),
        }

    def clean_name(self):
        event = self.cleaned_data.get('event')
        name = self.cleaned_data['name']
        if event and event.competitors.filter(name=name).exists():
            raise ValidationError('Name already taken')
        return name

    def clean(self):
        super().clean()
        event = self.cleaned_data.get('event')
        event_end = event.end_date
        if event_end and now() > event_end:
            raise ValidationError(
                'Competition ended, registration is not possible anymore'
            )


class ContactForm(Form):
    from_email = EmailField(label='Your email address', required=True)
    subject = CharField(required=True, max_length=128)
    message = CharField(widget=Textarea, required=True)
    captcha = CaptchaField(help_text="To verify that you are not a robot, please enter the letters in the picture.")

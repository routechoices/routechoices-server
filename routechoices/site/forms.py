from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms import (
    CharField,
    DateTimeInput,
    FileField,
    Form,
    HiddenInput,
    ModelChoiceField,
    ModelForm,
    EmailField,
    Textarea,
    BooleanField
)
from django_hosts.resolvers import reverse
from django.utils.timezone import now

from routechoices.core.models import Competitor, Event, Device


class UploadGPXForm(Form):
    name = CharField(max_length=64, required=True)
    gpx_file = FileField(
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
        self.fields['device'].help_text = 'Get a device ID from the <a href= \
            "%s">trackers page</a>' % reverse('site:tracker_view')

    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name')
        widgets = {
            'event': HiddenInput(),
        }

    def clean(self):
        super().clean()
        event = Event.objects.get(id=self.data.get('event'))
        event_end = event.end_date
        if event_end and now() > event_end:
            raise ValidationError(
                'Competition ended, registration is not possible anymore'
            )
        name = self.cleaned_data.get('name')
        device = self.cleaned_data.get('device')
        start_time = self.cleaned_data.get('start_time')
        event_start = event.start_date
        if not start_time and event_start < now():
            start_time = now()
        elif not start_time and event_start > now():
            start_time = event_start
        prev_dev_comp = Competitor.objects.filter(
            device_id=device.id,
            start_time__lte=start_time
        ).order_by('-start_time').first()
        if prev_dev_comp and prev_dev_comp.name == name and prev_dev_comp.event == event:
            raise ValidationError('Competitor already registered')


class ContactForm(Form):
    from_email = EmailField(label='Your email address', required=True)
    subject = CharField(required=True, max_length=128)
    message = CharField(widget=Textarea, required=True)
    spam_filter = BooleanField(
        label='Leave this box unchecked to prove you are human',
        required=False
    )

    def clean_spam_filter(self):
        if self.cleaned_data['spam_filter']:
            raise ValidationError('You must prove you are human')
        return self.cleaned_data['spam_filter']

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
from django.urls import reverse
from django.utils.timezone import now

from routechoices.core.models import Competitor, Event, Device


class UploadGPXForm(Form):
    name = CharField(max_length=64, required=True)
    gpx_file = FileField(
        validators=[FileExtensionValidator(allowed_extensions=['gpx'])]
    )


class CompetitorForm(ModelForm):
    device = ModelChoiceField(required=True, queryset=Device.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].label = "Start time (Optional)"
        self.fields['device'].help_text = 'Get a device ID from the <a href= \
            "%s">trackers page</a>' % reverse('site:tracker_view')

    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name', 'start_time')
        widgets = {
            'event': HiddenInput(),
            'start_time': DateTimeInput(attrs={
                'title': 'Start time',
                'placeholder': 'Start time',
                'class': 'datetimepicker'
            }),
        }

    def clean(self):
        event = Event.objects.get(id=self.data.get('event'))
        event_end = event.end_date
        if event_end and now() > event_end:
            raise ValidationError(
                'Competition ended, registration is not posible anymore'
            )

    def clean_start_time(self):
        start = self.cleaned_data.get('start_time')
        event = Event.objects.get(id=self.data.get('event'))
        event_start = event.start_date
        event_end = event.end_date
        if start and ((not event_end and event_start > start)
                      or (event_end
                          and (event_start > start
                               or start > event_end))):
            raise ValidationError(
                'Competitor start time should be during the event time'
            )
        elif not start and event_start < now():
            start = now()
        return start


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

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms import ModelForm, DateTimeInput, HiddenInput, \
    ModelChoiceField, Form, CharField, FileField

from routechoices.core.models import Competitor, Event, Device
from routechoices.lib.helper import get_aware_datetime


class UploadGPXForm(Form):
    name = CharField(max_length=64, required=True)
    gpx_file = FileField(validators=[FileExtensionValidator(allowed_extensions=['gpx'])])


class CompetitorForm(ModelForm):
    device = ModelChoiceField(required=True, queryset=Device.objects.all())

    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name', 'start_time')
        widgets = {
            'event': HiddenInput(),
            'start_time': DateTimeInput(attrs={'class': 'datetimepicker'}),
        }

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
        return start

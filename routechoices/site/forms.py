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
)

from routechoices.core.models import Competitor, Event, Device


class UploadGPXForm(Form):
    name = CharField(max_length=64, required=True)
    gpx_file = FileField(validators=[FileExtensionValidator(allowed_extensions=['gpx'])])


class CompetitorForm(ModelForm):
    device = ModelChoiceField(required=True, queryset=Device.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].label = "Start time"

    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name', 'start_time')
        widgets = {
            'event': HiddenInput(),
            'start_time': DateTimeInput(attrs={'title': 'Start time', 'placeholder': 'Start time', 'class': 'datetimepicker'}),
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

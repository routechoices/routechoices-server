from django.core.exceptions import ValidationError
from django.forms import ModelForm, DateTimeInput, HiddenInput, ModelChoiceField

from routechoices.core.models import Competitor, Event, Device
from routechoices.lib.helper import get_aware_datetime


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
        if event_end:
            event_end = get_aware_datetime(event_end)
        if start and ((not event_end and event_start > start)
                      or (event_end
                          and (event_start > start
                               or start > event_end))):
            raise ValidationError(
                'Competitor start time should be during the event time'
            )
        return start

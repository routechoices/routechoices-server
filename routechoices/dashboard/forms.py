from django.core.exceptions import ValidationError
from django.forms import ModelForm, DateTimeInput, inlineformset_factory

from routechoices.core.models import Club, Map, Event, Competitor


class ClubForm(ModelForm):
    class Meta:
        model = Club
        fields = ['name', 'slug', 'admins']


class MapForm(ModelForm):
    class Meta:
        model = Map
        fields = ['club', 'name', 'image', 'corners_coordinates']


class EventForm(ModelForm):
    class Meta:
        model = Event
        fields = ['club', 'name', 'slug', 'start_date', 'end_date', 'map']
        widgets = {
            'start_date': DateTimeInput(attrs={'class': 'datetimepicker'}),
            'end_date': DateTimeInput(attrs={'class': 'datetimepicker'})
        }

    def clean(self):
        super().clean()
        start_date = self.cleaned_data['start_date']
        end_date = self.cleaned_data.get('end_date')
        if end_date and end_date < start_date:
            raise ValidationError('Start Date must be before End Date')
        club = self.cleaned_data['club']
        map = self.cleaned_data['map']
        if map and club != map.club:
            raise ValidationError('Pick a map from the organizer club')


class CompetitorForm(ModelForm):
    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name', 'short_name', 'start_time')
        widgets = {
            'start_time': DateTimeInput(attrs={'class': 'datetimepicker'}),
        }


CompetitorFormSet = inlineformset_factory(
    Event,
    Competitor,
    form=CompetitorForm,
    extra=1,
    min_num=1,
    validate_min=True
)

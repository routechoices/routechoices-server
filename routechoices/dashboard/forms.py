from django.core.exceptions import ValidationError
from django.forms import ModelForm, DateTimeInput

from routechoices.core.models import Club, Map, Event


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
        if self.cleaned_data.get('end_date') and self.cleaned_data['end_date'] < self.cleaned_data['start_date']:
            raise ValidationError('Start Date must be before End Date')

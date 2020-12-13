from io import BytesIO

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import FileExtensionValidator
from django.forms import (
    Form,
    ModelForm,
    DateTimeInput,
    inlineformset_factory,
    ModelChoiceField,
    FileField,
)

from routechoices.core.models import Club, Map, Event, Competitor, Device
from routechoices.lib.helper import get_aware_datetime


class ClubForm(ModelForm):
    class Meta:
        model = Club
        fields = ['name', 'slug', 'admins']


class DeviceForm(Form):
    device = ModelChoiceField(
        label="Device ID",
        help_text="Enter the device ID used by your tracker",
        queryset=Device.objects.all(),
    )


class MapForm(ModelForm):
    class Meta:
        model = Map
        fields = ['club', 'name', 'image', 'corners_coordinates']

    def clean_image(self):
        f_orig = self.cleaned_data['image']
        fn = f_orig.name
        with Image.open(f_orig.file) as image:
            rgb_img = image.convert('RGB')
            if image.size[0] > 3000 and image.size[1] > 3000:
                if image.size[0] >= image.size[1]:
                    new_h = 3000
                    new_w = new_h / image.size[1] * image.size[0]
                else:
                    new_w = 3000
                    new_h = new_w / image.size[0] * image.size[1]
                rgb_img.thumbnail((new_w, new_h), Image.ANTIALIAS)
            out_buffer = BytesIO()
            rgb_img.save(out_buffer, 'JPEG', quality=60)
            f_new = File(out_buffer, name=fn)
            return f_new
        return None


class EventForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].help_text = \
            '<span class="local_time"></span>'
        self.fields['end_date'].help_text = '<span class="local_time"></span>'

    class Meta:
        model = Event
        fields = ['club', 'name', 'slug', 'privacy', 'open_registration',
                  'allow_route_upload', 'start_date', 'end_date', 'map']
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].help_text = \
            '<span class="local_time"></span>'

    class Meta:
        model = Competitor
        fields = ('event', 'device', 'name', 'short_name', 'start_time')
        widgets = {
            'start_time': DateTimeInput(attrs={'class': 'datetimepicker'}),
        }

    def clean_start_time(self):
        start = self.cleaned_data.get('start_time')
        event_start = get_aware_datetime(self.data.get('start_date'))
        event_end = self.data.get('end_date')
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


class UploadGPXForm(Form):
    competitor = ModelChoiceField(queryset=Competitor.objects.all())
    gpx_file = FileField(
        validators=[FileExtensionValidator(allowed_extensions=['gpx'])]
    )


class UploadKmzForm(Form):
    club = ModelChoiceField(queryset=Club.objects.all())
    file = FileField(
        label='KML/KMZ file',
        validators=[FileExtensionValidator(allowed_extensions=['kmz', 'kml'])]
    )


CompetitorFormSet = inlineformset_factory(
    Event,
    Competitor,
    form=CompetitorForm,
    extra=1,
    min_num=0,
    validate_min=True
)

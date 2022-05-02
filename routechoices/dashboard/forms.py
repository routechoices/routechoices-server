from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.images import get_image_dimensions
from django.core.validators import FileExtensionValidator
from django.forms import (
    CharField,
    DateTimeInput,
    FileField,
    Form,
    ModelChoiceField,
    ModelForm,
    inlineformset_factory,
)
from PIL import Image

from routechoices.core.models import (
    WEBP_MAX_SIZE,
    Club,
    Competitor,
    Device,
    Event,
    Map,
    MapAssignation,
    Notice,
)
from routechoices.lib.helpers import check_records, get_aware_datetime
from routechoices.lib.validators import domain_validator


class ClubForm(ModelForm):
    class Meta:
        model = Club
        fields = ["name", "slug", "admins", "website", "logo", "description"]

    def clean_admins(self):
        admins = self.cleaned_data["admins"]
        if admins.count() > 10:
            raise ValidationError("Clubs can only have a maximum of 10 admins")
        return admins

    def clean_logo(self):
        logo = self.cleaned_data["logo"]
        if not logo:
            return logo
        w, h = get_image_dimensions(logo)
        if w != h:
            raise ValidationError("The image should be square")
        if w < 128:
            raise ValidationError("The image is too small, < 128px width")
        fn = logo.name
        with Image.open(logo.file) as image:
            rgba_img = image.convert("RGBA")
            target = 256
            if image.size[0] > target:
                scale = target / min(image.size[0], image.size[1])
                new_w = image.size[0] * scale
                rgba_img.thumbnail((new_w, new_w), Image.ANTIALIAS)
            out_buffer = BytesIO()
            params = {
                "dpi": (72, 72),
            }
            rgba_img.save(out_buffer, "PNG", **params)
            f_new = File(out_buffer, name=fn)
            return f_new


class ClubDomainForm(ModelForm):
    domain = CharField(
        max_length=128,
        label="Custom domain",
        help_text="eg: 'example.com'",
        validators=[domain_validator],
        required=False,
    )

    class Meta:
        model = Club
        fields = ("domain",)

    def clean_domain(self):
        domain = self.cleaned_data["domain"]
        if domain == "":
            return domain
        if not check_records(domain):
            raise ValidationError(f"TXT record for '{domain}' has not been set.")
        matching_clubs = Club.objects.filter(domain__iexact=domain)
        if self.instance:
            matching_clubs = matching_clubs.exclude(pk=self.instance.pk)
        if matching_clubs.exists():
            raise ValidationError(f"Domain '{domain}'  already exists.")
        else:
            return domain.lower()


class DeviceForm(Form):
    device = ModelChoiceField(
        label="Device ID",
        help_text="Enter the device ID of the tracker",
        queryset=Device.objects.all(),
    )


class MapForm(ModelForm):
    class Meta:
        model = Map
        fields = ["club", "name", "image", "corners_coordinates"]

    def clean_image(self):
        f_orig = self.cleaned_data["image"]
        fn = f_orig.name
        with Image.open(f_orig.file) as image:
            rgba_img = image.convert("RGBA")
            MAX = 4000
            if image.size[0] > MAX and image.size[1] > MAX:
                scale = MAX / min(image.size[0], image.size[1])
                new_w = image.size[0] * scale
                new_h = image.size[1] * scale
                rgba_img.thumbnail((new_w, new_h), Image.ANTIALIAS)
            format = "WEBP"
            if rgba_img.size[0] > WEBP_MAX_SIZE or rgba_img.size[1] > WEBP_MAX_SIZE:
                format = "PNG"
            out_buffer = BytesIO()
            params = {
                "dpi": (72, 72),
            }
            if format == "WEBP":
                params["quality"] = 60
            rgba_img.save(out_buffer, format, **params)
            f_new = File(out_buffer, name=fn)
            return f_new


class EventForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].help_text = '<span class="local_time"></span>'
        self.fields["end_date"].help_text = '<span class="local_time"></span>'
        self.fields["send_interval"].widget.attrs["min"] = 1

    class Meta:
        model = Event
        fields = [
            "club",
            "name",
            "slug",
            "privacy",
            "open_registration",
            "allow_route_upload",
            "allow_live_chat",
            "start_date",
            "end_date",
            "send_interval",
            "tail_length",
            "backdrop_map",
            "map",
            "map_title",
        ]
        widgets = {
            "start_date": DateTimeInput(
                attrs={"class": "datetimepicker", "autocomplete": "off"}
            ),
            "end_date": DateTimeInput(
                attrs={"class": "datetimepicker", "autocomplete": "off"}
            ),
        }

    def clean(self):
        super().clean()
        start_date = self.cleaned_data["start_date"]
        end_date = self.cleaned_data["end_date"]
        if end_date < start_date:
            raise ValidationError("Start Date must be before End Date")

    def clean_map(self):
        rmap = self.cleaned_data.get("map")
        club = self.data.get("club")
        if rmap and club and int(club) != rmap.club_id:
            raise ValidationError("Map must be from the organizing club")
        return rmap


class NoticeForm(ModelForm):
    class Meta:
        model = Notice
        fields = ("text",)


class ExtraMapForm(ModelForm):
    class Meta:
        model = MapAssignation
        fields = ("event", "map", "title")

    def clean_map(self):
        rmap = self.cleaned_data.get("map")
        club = self.data.get("club")
        if club and int(club) != rmap.club_id:
            raise ValidationError("Map must be from the organizing club")
        if not self.data.get("map"):
            raise ValidationError(
                "Extra maps can be set only if the main map field is set first"
            )
        return rmap

    def clean_title(self):
        map_title = self.cleaned_data.get("title")
        main_map_title = self.data.get("map_title")
        if main_map_title and main_map_title == map_title:
            raise ValidationError("Extra maps title can not be same as main map title")
        return map_title


class CompetitorForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_time"].help_text = '<span class="local_time"></span>'

    class Meta:
        model = Competitor
        fields = ("event", "device", "name", "short_name", "start_time")
        widgets = {
            "start_time": DateTimeInput(
                attrs={"class": "datetimepicker", "autocomplete": "off"}
            ),
        }

    def clean_start_time(self):
        start = self.cleaned_data.get("start_time")
        event_start = get_aware_datetime(self.data.get("start_date"))
        event_end = get_aware_datetime(self.data.get("end_date"))
        if start and (event_start > start or start > event_end):
            raise ValidationError(
                "Competitor start time should be during the event time"
            )
        return start


class UploadGPXForm(Form):
    competitor = ModelChoiceField(queryset=Competitor.objects.all())
    gpx_file = FileField(
        max_length=255, validators=[FileExtensionValidator(allowed_extensions=["gpx"])]
    )


class UploadMapGPXForm(Form):
    club = ModelChoiceField(queryset=Club.objects.all())
    gpx_file = FileField(
        max_length=255, validators=[FileExtensionValidator(allowed_extensions=["gpx"])]
    )


class UploadKmzForm(Form):
    club = ModelChoiceField(queryset=Club.objects.all())
    file = FileField(
        label="KML/KMZ file",
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=["kmz", "kml"])],
    )


CompetitorFormSet = inlineformset_factory(
    Event, Competitor, form=CompetitorForm, extra=1, min_num=0, validate_min=True
)

ExtraMapFormSet = inlineformset_factory(
    Event, MapAssignation, form=ExtraMapForm, extra=1, min_num=0, validate_min=True
)

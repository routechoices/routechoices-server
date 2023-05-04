from io import BytesIO

import arrow
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.images import get_image_dimensions
from django.core.validators import FileExtensionValidator
from django.db.models import Q
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
    EventSet,
    Map,
    MapAssignation,
    Notice,
)
from routechoices.lib.helpers import (
    check_cname_record,
    check_txt_record,
    get_aware_datetime,
)
from routechoices.lib.validators import domain_validator, validate_nice_slug


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = ""

    def clean_username(self):
        username = self.cleaned_data["username"]
        validate_nice_slug(username)
        return username


class ClubForm(ModelForm):
    class Meta:
        model = Club
        fields = ["name", "slug", "admins", "website", "logo", "description"]

    def clean_slug(self):
        slug = self.cleaned_data["slug"].lower()

        club_with_slug_qs = Club.objects.filter(
            Q(slug=slug)
            | Q(
                slug_changed_from=slug,
                slug_changed_at__gt=arrow.now().shift(hours=-72).datetime,
            ),
        )
        if self.instance:
            club_with_slug_qs = club_with_slug_qs.exclude(pk=self.instance.pk)
            if (
                self.instance.slug_changed_at
                and self.instance.slug_changed_at
                > arrow.now().shift(hours=-72).datetime
                and not (
                    (
                        self.instance.slug_changed_from
                        and slug == self.instance.slug_changed_from
                    )
                    or slug == self.instance.slug
                )
            ):
                raise ValidationError(
                    "Domain prefix can be changed only once every 72 hours."
                )

        if club_with_slug_qs.exists():
            raise ValidationError("Domain prefix already registered.")
        return slug

    def clean_logo(self):
        logo = self.cleaned_data["logo"]
        if not logo:
            return logo
        w, h = get_image_dimensions(logo)
        minimum = 128
        if w < minimum or h < minimum:
            raise ValidationError(
                f"The image is too small, minimum {minimum}x{minimum} pixels"
            )
        fn = logo.name
        with Image.open(logo.file) as image:
            rgba_img = image.convert("RGBA")
            target = min([256, w, h])
            if w < h:
                resized_image = rgba_img.resize(
                    (target, int(image.size[1] * (target / image.size[0])))
                )
                required_loss = resized_image.size[1] - target
                sqare_image = resized_image.crop(
                    box=(
                        0,
                        required_loss / 2,
                        target,
                        resized_image.size[1] - required_loss / 2,
                    )
                )
            else:
                resized_image = rgba_img.resize(
                    (int(image.size[0] * (target / image.size[1])), target)
                )
                required_loss = resized_image.size[0] - target
                sqare_image = resized_image.crop(
                    box=(
                        required_loss / 2,
                        0,
                        resized_image.size[0] - required_loss / 2,
                        target,
                    )
                )
            out_buffer = BytesIO()
            params = {
                "dpi": (72, 72),
            }
            sqare_image.save(out_buffer, "PNG", **params)
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
        if not check_txt_record(domain):
            raise ValidationError(
                f"TXT record for '{domain}' has not been set properly."
            )
        if not check_cname_record(domain):
            raise ValidationError(
                f"CNAME record for '{domain}' has not been set properly."
            )
        matching_clubs = Club.objects.filter(domain__iexact=domain)
        if self.instance:
            matching_clubs = matching_clubs.exclude(pk=self.instance.pk)
        if matching_clubs.exists():
            raise ValidationError(f"Domain '{domain}' already exists.")
        return domain.lower()


class DeviceForm(Form):
    device = ModelChoiceField(
        label="Device ID",
        help_text="Enter the device ID of the tracker",
        queryset=Device.objects.all(),
    )
    nickname = CharField(max_length=12)


class MapForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "image"
        ].help_text = "Image of map as a PNG, JPEG, GIF, WEBP, or PDF file"

    class Meta:
        model = Map
        fields = ["name", "image", "corners_coordinates"]

    def clean_image(self):
        f_orig = self.cleaned_data["image"]
        fn = f_orig.name
        with Image.open(f_orig.file) as image:
            rgba_img = image.convert("RGBA")
            format = "WEBP"
            if rgba_img.size[0] > WEBP_MAX_SIZE or rgba_img.size[1] > WEBP_MAX_SIZE:
                format = "PNG"
            out_buffer = BytesIO()
            params = {
                "dpi": (72, 72),
            }
            if format == "WEBP":
                params["quality"] = 80
            rgba_img.save(out_buffer, format, **params)
            f_new = File(out_buffer, name=fn)
            return f_new


class EventSetForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop("club")
        super().__init__(*args, **kwargs)
        self.instance.club = self.club

    class Meta:
        model = EventSet
        fields = ["name", "create_page", "slug", "list_secret_events"]

    def validate_unique(self):
        exclude = self._get_validation_exclusions()
        exclude.remove("club")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)


class EventForm(ModelForm):
    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop("club")
        super().__init__(*args, **kwargs)
        self.fields["start_date"].help_text = '<span class="local_time"></span>'
        self.fields["end_date"].help_text = '<span class="local_time"></span>'
        self.fields["send_interval"].widget.attrs["min"] = 1
        self.instance.club = self.club

    class Meta:
        model = Event
        fields = [
            "name",
            "slug",
            "event_set",
            "start_date",
            "end_date",
            "open_registration",
            "allow_route_upload",
            "privacy",
            "send_interval",
            "tail_length",
            "emergency_contact",
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

    def validate_unique(self):
        exclude = self._get_validation_exclusions()
        exclude.remove("club")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)

    def clean(self):
        super().clean()
        start_date = self.cleaned_data.get("start_date")
        end_date = self.cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise ValidationError("Start Date must be before End Date")

    def clean_map(self):
        raster_map = self.cleaned_data.get("map")
        club = self.club
        if raster_map and club.id != raster_map.club_id:
            raise ValidationError("Map must be from the organizing club")

        if raster_map:
            num_maps = int(self.data.get("map_assignations-TOTAL_FORMS"))
            start_count_maps = int(self.data.get("map_assignations-MIN_NUM_FORMS"))
            for i in range(start_count_maps, start_count_maps + num_maps):
                if (
                    self.data.get(f"map_assignations-{i}-map")
                    and int(self.data.get(f"map_assignations-{i}-map")) == raster_map.id
                ):
                    raise ValidationError("Map assigned more than once in this event")

        return raster_map

    def clean_map_title(self):
        map_title = self.cleaned_data.get("map_title")
        num_maps = int(self.data.get("map_assignations-TOTAL_FORMS"))
        start_count_maps = int(self.data.get("map_assignations-MIN_NUM_FORMS"))
        for i in range(start_count_maps, start_count_maps + num_maps):
            if (
                self.data.get(f"map_assignations-{i}-title")
                and self.data.get(f"map_assignations-{i}-title") == map_title
            ):
                raise ValidationError("Map title given more than once in this event")
        return map_title


class NoticeForm(ModelForm):
    class Meta:
        model = Notice
        fields = ("text",)


class ExtraMapForm(ModelForm):
    class Meta:
        model = MapAssignation
        fields = ("event", "map", "title")

    def clean_map(self):
        raster_map = self.cleaned_data.get("map")
        club = self.data.get("club")
        if club and int(club) != raster_map.club_id:
            raise ValidationError("Map must be from the organizing club")
        if not self.data.get("map"):
            raise ValidationError(
                "Extra maps can be set only if the main map field is set first"
            )
        if int(self.data.get("map")) == self.cleaned_data.get("map").id:
            raise ValidationError("Map assigned more than once in this event")

        num_maps = int(self.data.get("map_assignations-TOTAL_FORMS"))
        start_count_maps = int(self.data.get("map_assignations-MIN_NUM_FORMS"))
        map_with_same_id = 0
        for i in range(start_count_maps, start_count_maps + num_maps):
            if (
                self.data.get(f"map_assignations-{i}-map")
                and int(self.data.get(f"map_assignations-{i}-map"))
                == self.cleaned_data.get("map").id
            ):
                map_with_same_id += 1
                if map_with_same_id > 1:
                    raise ValidationError("Map assigned more than once in this event")
        return raster_map

    def clean_title(self):
        map_title = self.cleaned_data.get("title")
        main_map_title = self.data.get("map_title")
        if main_map_title and main_map_title == map_title:
            raise ValidationError("Map title given more than once in this event")

        num_maps = int(self.data.get("map_assignations-TOTAL_FORMS"))
        start_count_maps = int(self.data.get("map_assignations-MIN_NUM_FORMS"))
        map_with_same_title = 0
        for i in range(start_count_maps, start_count_maps + num_maps):
            if (
                self.data.get(f"map_assignations-{i}-title")
                and self.data.get(f"map_assignations-{i}-title") == map_title
            ):
                map_with_same_title += 1
                if map_with_same_title > 1:
                    raise ValidationError(
                        "Map title given more than once in this event"
                    )
        return map_title


class CompetitorForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_time"].help_text = '<span class="local_time"></span>'

    class Meta:
        model = Competitor
        fields = ("event", "name", "short_name", "device", "start_time")
        widgets = {
            "start_time": DateTimeInput(
                attrs={"class": "datetimepicker", "autocomplete": "off"}
            ),
        }

    def clean_start_time(self):
        start = self.cleaned_data.get("start_time")
        orig_event = self.cleaned_data.get("event")
        if self.data.get("start_date"):
            try:
                event_start = get_aware_datetime(self.data.get("start_date"))
            except Exception:
                event_start = orig_event.start_date
        else:
            event_start = orig_event.start_date
        if self.data.get("end_date"):
            try:
                event_end = get_aware_datetime(self.data.get("end_date"))
            except Exception:
                event_end = orig_event.end_date
        else:
            event_end = orig_event.end_date
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
    gpx_file = FileField(
        max_length=255, validators=[FileExtensionValidator(allowed_extensions=["gpx"])]
    )


class UploadKmzForm(Form):
    file = FileField(
        label="KML/KMZ file",
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=["kmz", "kml"])],
    )


CompetitorFormSet = inlineformset_factory(
    Event,
    Competitor,
    form=CompetitorForm,
    extra=1,
    min_num=0,
    max_num=None,
    validate_min=True,
)

ExtraMapFormSet = inlineformset_factory(
    Event,
    MapAssignation,
    form=ExtraMapForm,
    extra=1,
    min_num=0,
    max_num=None,
    validate_min=True,
)

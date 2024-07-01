from django.core.validators import FileExtensionValidator
from django.forms import (
    CharField,
    ChoiceField,
    FileField,
    Form,
    ModelChoiceField,
    Textarea,
)

from routechoices.core.models import Device


class RegisterForm(Form):
    name = CharField(max_length=64, required=True)
    short_name = CharField(max_length=64, required=False)
    device_id = ModelChoiceField(
        required=False, queryset=Device.objects.none(), label="Device ID"
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)


class CompetitorUploadGPXForm(Form):
    competitor_aid = ChoiceField(required=True, choices=[], label="Competitor")
    gpx_file = FileField(
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=["gpx"])],
        label="GPX File",
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        competitors_who_can_upload = []
        for competitor, from_date, end_date in event.iterate_competitors():
            if competitor.device_id:
                _, nb_pts = competitor.device.get_locations_between_dates(
                    from_date, end_date
                )
                if nb_pts == 0:
                    competitors_who_can_upload.append(competitor)
            else:
                competitors_who_can_upload.append(competitor)
        self.fields["competitor_aid"].choices = [
            (c.aid, c.name) for c in competitors_who_can_upload
        ]


class ContactForm(Form):
    subject = CharField(required=True, max_length=128)
    message = CharField(widget=Textarea, required=True)

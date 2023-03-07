from allauth.account.models import EmailAddress
from django import forms
from django.utils.translation import gettext_lazy as _

from routechoices.core.models import Club

from .adapters import get_invitations_adapter
from .exceptions import AlreadyInvited, UserAlreadyAdmin
from .utils import get_invitation_model

Invitation = get_invitation_model()


class CleanEmailMixin:
    def validate_invitation(self, email, club):
        user = EmailAddress.objects.filter(email__iexact=email).first()
        if user and club.admins.filter(id=user.user_id).exists():
            raise UserAlreadyAdmin

        if Invitation.objects.all_valid().filter(
            email__iexact=email, club=club, accepted=False
        ):
            raise AlreadyInvited
        return True

    def clean_email(self):
        email = self.cleaned_data["email"]
        email = get_invitations_adapter().clean_email(email)

        club = self.club
        if not club and self.data.get("club"):
            club = Club.objects.filter(id=self.data.get("club")).first()

        errors = {
            "already_invited": (
                "An invite to manage this club with this email address "
                "has already been sent to this email address."
            ),
            "already_admin": (
                "The email address is already associated with an account "
                "that is managing this club"
            ),
        }
        try:
            self.validate_invitation(email, club)
        except AlreadyInvited:
            raise forms.ValidationError(errors["already_invited"])
        except UserAlreadyAdmin:
            raise forms.ValidationError(errors["already_admin"])
        return email


class InviteForm(forms.Form, CleanEmailMixin):
    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop("club", None)
        super().__init__(*args, **kwargs)

    email = forms.EmailField(
        label=_("Email"),
        required=True,
        widget=forms.TextInput(attrs={"type": "email", "size": "60"}),
        initial="",
    )

    def save(self, email, club):
        self.clean()
        return Invitation.create(email=email, club=club)


class InvitationAdminAddForm(forms.ModelForm, CleanEmailMixin):
    email = forms.EmailField(
        label=_("E-mail"),
        required=True,
        widget=forms.TextInput(attrs={"type": "email", "size": "30"}),
    )

    def __init__(self, *args, **kwargs):
        self.club = None
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        club = cleaned_data.get("club")
        params = {"email": email, "club": club}
        if cleaned_data.get("inviter"):
            params["inviter"] = cleaned_data.get("inviter")
        instance = Invitation.create(**params)
        instance.send_invitation(self.request)
        super().save(*args, **kwargs)
        return instance

    class Meta:
        model = Invitation
        fields = ("email", "club", "inviter")


class InvitationAdminChangeForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = "__all__"

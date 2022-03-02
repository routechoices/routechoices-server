from allauth_2fa.utils import user_has_valid_totp_device
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django_otp.forms import OTPAuthenticationFormMixin


class AdminSiteAuthForm(OTPAuthenticationFormMixin, AuthenticationForm):
    otp_token = forms.IntegerField(
        label="Token", min_value=1, max_value=int("9" * 6), required=False
    )
    otp_token.widget.attrs.update(
        {
            "autofocus": "autofocus",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
        }
    )

    def clean(self):
        super().clean()
        if user_has_valid_totp_device(self.get_user()):
            self.clean_otp(self.get_user())
        return self.cleaned_data

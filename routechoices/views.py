from base64 import b32encode

from allauth_2fa.views import TwoFactorSetup as OrigTwoFactorSetup


class TwoFactorSetup(OrigTwoFactorSetup):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["code_secret"] = b32encode(self.device.bin_key).decode("utf-8")
        return context

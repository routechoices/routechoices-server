from allauth_2fa.adapter import OTPAdapter
from django.conf import settings


class SiteAccountAdapter(OTPAdapter):
    def is_safe_url(self, url):
        try:
            from django.utils.http import url_has_allowed_host_and_scheme
        except ImportError:
            from django.utils.http import is_safe_url as url_has_allowed_host_and_scheme

        return url_has_allowed_host_and_scheme(
            url, allowed_hosts=settings.REDIRECT_ALLOWED_DOMAINS
        )

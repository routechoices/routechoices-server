from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.signals import user_logged_in, user_signed_up
from django.conf import settings


class SiteAccountAdapter(DefaultAccountAdapter):
    def is_safe_url(self, url):
        try:
            from django.utils.http import url_has_allowed_host_and_scheme
        except ImportError:
            from django.utils.http import is_safe_url as url_has_allowed_host_and_scheme

        return url_has_allowed_host_and_scheme(
            url, allowed_hosts=settings.REDIRECT_ALLOWED_DOMAINS
        )

    def get_user_signed_up_signal(self):
        return user_signed_up

    def get_user_logged_in_signal(self):
        return user_logged_in

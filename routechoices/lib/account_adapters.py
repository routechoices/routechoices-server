from django.conf import settings
from allauth.account.adapter import DefaultAccountAdapter


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Checks whether or not the site is open for signups.

        Next to simply returning True/False you can also intervene the
        regular flow by raising an ImmediateHttpResponse
        """
        return False

class SiteAccountAdapter(DefaultAccountAdapter):
    def is_safe_url(self, url):
        try:
            from django.utils.http import url_has_allowed_host_and_scheme
        except ImportError:
            from django.utils.http import (
                is_safe_url as url_has_allowed_host_and_scheme,
            )

        return url_has_allowed_host_and_scheme(url, allowed_hosts=settings.REDIRECT_ALLOWED_DOMAINS)

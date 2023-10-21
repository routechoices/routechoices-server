from functools import cache

from django.conf import settings

from routechoices.lib.helpers import get_current_site, git_master_hash


def site(request):
    @cache
    def current_site():
        return get_current_site()

    @cache
    def version():
        return git_master_hash()

    return {
        "site": current_site,
        "analytics_enabled": bool(getattr(settings, "ANALYTICS_API_KEY")),
        "DEBUG": settings.DEBUG,
        "version": version,
    }

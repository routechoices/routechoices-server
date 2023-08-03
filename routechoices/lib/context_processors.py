from functools import cache

from django.conf import settings
from django.contrib.sites.models import Site

from routechoices.lib.helpers import git_master_hash


def site(request):
    @cache
    def current_site():
        return Site.objects.get_current()

    @cache
    def version():
        return git_master_hash()

    return {
        "site": current_site,
        "enable_analytics": getattr(settings, "ENABLE_ANALYTICS", None),
        "DEBUG": settings.DEBUG,
        "version": version,
    }

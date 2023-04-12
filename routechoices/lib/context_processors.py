from functools import cache

from django.conf import settings
from django.contrib.sites.models import Site


def site(request):
    @cache
    def current_site():
        return Site.objects.get_current()

    return {
        "site": current_site,
        "enable_analytics": getattr(settings, "ENABLE_ANALYTICS", None),
    }

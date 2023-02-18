from django.conf import settings
from django.contrib.sites.models import Site


def site(request):
    return {
        "site": Site.objects.get_current(),
        "enable_analytics": getattr(settings, "ENABLE_ANALYTICS", None),
    }

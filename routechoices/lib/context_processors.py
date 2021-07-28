from django.contrib.sites.models import Site
from django.conf import settings

def site(request):
    return {
        'site': Site.objects.get_current(),
        'panelbear_id': getattr(settings, 'PANELBEAR_ID', None)
    }

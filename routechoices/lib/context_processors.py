from django.contrib.sites.models import Site
from django.conf import settings
import subprocess

def get_git_revision_hash():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('utf8').strip()

def get_git_revision_short_hash():
    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf8').strip()


def site(request):
    return {
        'site': Site.objects.get_current(),
        'panelbear_id': getattr(settings, 'PANELBEAR_ID', None),
        'version': get_git_revision_hash(),
    }

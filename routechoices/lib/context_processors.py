from django.contrib.sites.models import Site
from django.conf import settings
import subprocess

def get_git_revision_hash():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=settings.BASE_DIR).decode('utf8').strip()

def get_git_revision_short_hash():
    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=settings.BASE_DIR).decode('utf8').strip()


def site(request):
    return {
        'site': Site.objects.get_current(),
        'enable_analytics': getattr(settings, 'ENABLE_ANALYTICS', None),
        'version': get_git_revision_hash(),
    }

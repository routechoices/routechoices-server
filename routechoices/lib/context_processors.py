from django.contrib.sites.models import Site
from django.conf import settings
from git import Repo


def get_git_revision_hash():
    repo = Repo(settings.BASE_DIR)
    hc = repo.head.commit
    return hc.hexsha


def get_git_revision_short_hash():
    return get_git_revision_hash()[:7]


def site(request):
    return {
        'site': Site.objects.get_current(),
        'enable_analytics': getattr(settings, 'ENABLE_ANALYTICS', None),
        'version': get_git_revision_hash(),
    }

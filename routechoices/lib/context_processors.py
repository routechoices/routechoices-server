from django.contrib.sites.models import Site
from django.conf import settings

try:
    from git import Repo
except ImportError:

    class Repo:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError()


def get_git_revision_hash():
    try:
        repo = Repo(settings.BASE_DIR)
    except NotImplementedError:
        return "dev"
    hc = repo.head.commit
    return hc.hexsha


def get_git_revision_short_hash():
    return get_git_revision_hash()[:7]


def site(request):
    return {
        "site": Site.objects.get_current(),
        "enable_analytics": getattr(settings, "ENABLE_ANALYTICS", None),
        "version": get_git_revision_hash(),
    }

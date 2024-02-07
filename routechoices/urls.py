"""routechoices URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.contrib.sitemaps import views as sitemaps_views
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

from routechoices.dashboard.views import (
    backup_codes,
    dashboard_banner_download,
    dashboard_logo_download,
    dashboard_map_download,
)
from routechoices.site.sitemaps import DynamicViewSitemap, StaticViewSitemap

admin.site.site_header = "Admin"
admin.site.site_title = "Admin Site"
admin.site.index_title = "Welcome to the administration site"

sitemaps = {
    "static": StaticViewSitemap,
    "dynamic": DynamicViewSitemap,
}

urlpatterns = [
    path("account/login/", RedirectView.as_view(url="/login")),
    path("account/logout/", RedirectView.as_view(url="/logout")),
    path("account/signup/", RedirectView.as_view(url="/signup")),
    path("account/email/", RedirectView.as_view(url="/dashboard/account/emails")),
    path(
        "account/password/change/",
        RedirectView.as_view(url="/dashboard/account/change-password"),
    ),
    path("account/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("api/", include(("routechoices.api.urls", "api"), namespace="api")),
    path("dashboard/account/mfa/login/", RedirectView.as_view(url="/login")),
    path("dashboard/account/mfa/backup-codes/", backup_codes, name="backup-codes"),
    path("dashboard/account/mfa/", include("kagi.urls", namespace="kagi")),
    path(
        "dashboard/",
        include(("routechoices.dashboard.urls", "dashboard"), namespace="dashboard"),
    ),
    path("invitations/", include("invitations.urls", namespace="invitations")),
    path(
        "webhooks/",
        include(("routechoices.webhooks.urls", "webhooks"), namespace="webhooks"),
    ),
    path("hijack/", include("hijack.urls")),
    re_path(
        r"^media/maps/(?P<hash>[-0-9a-zA-Z_])/(?P<hash2>[-0-9a-zA-Z_])/"
        r"(?P<map_id>(?P=hash)(?P=hash2)[-0-9a-zA-Z_]{9})(\_\d+)?",
        dashboard_map_download,
        name="dashboard_map_download",
    ),
    re_path(
        r"^media/logos/(?P<hash>[-0-9a-zA-Z_])/(?P<hash2>[-0-9a-zA-Z_])/"
        r"(?P<club_id>(?P=hash)(?P=hash2)[-0-9a-zA-Z_]{9})(\_\d+)?",
        dashboard_logo_download,
        name="dashboard_logo_download",
    ),
    re_path(
        r"^media/banners/(?P<hash>[-0-9a-zA-Z_])/(?P<hash2>[-0-9a-zA-Z_])/"
        r"(?P<club_id>(?P=hash)(?P=hash2)[-0-9a-zA-Z_]{9})(\_\d+)?",
        dashboard_banner_download,
        name="dashboard_banner_download",
    ),
    path(
        "sitemap.xml",
        sitemaps_views.index,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.index",
    ),
    re_path(
        "^sitemap-(?P<section>[A-Za-z0-9-_]+).xml$",
        sitemaps_views.sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("", include(("routechoices.site.urls", "site"), namespace="site")),
]

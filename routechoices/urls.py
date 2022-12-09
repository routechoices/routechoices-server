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
import kagi
from allauth.account import views as account_views
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

from routechoices.dashboard.views import dashboard_logo_download, dashboard_map_download
from routechoices.site.sitemaps import DynamicViewSitemap, StaticViewSitemap

admin.site.site_header = "Routechoices.com Admin"
admin.site.site_title = "Routechoices.com Admin Site"
admin.site.index_title = "Welcome to Routechoices.com Administration Site"

sitemaps = {
    "static": StaticViewSitemap,
    "dynamic": DynamicViewSitemap,
}

urlpatterns = [
    path("accounts/login/", RedirectView.as_view(url="/login")),
    path("mfa/login/", RedirectView.as_view(url="/login")),
    path("mfa/", include("kagi.urls", namespace="kagi")),
    path("accounts/", include("allauth.urls")),
    path("login/", kagi.views.login, name="root_account_login"),
    path("logout/", account_views.logout, name="root_account_logout"),
    path("signup/", account_views.signup, name="root_account_signup"),
    path("admin/", admin.site.urls),
    path("invitations/", include("invitations.urls", namespace="invitations")),
    path("api/", include(("routechoices.api.urls", "api"), namespace="api")),
    path(
        "dashboard/",
        include(("routechoices.dashboard.urls", "dashboard"), namespace="dashboard"),
    ),
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
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    re_path(
        "^sitemap-(?P<section>[A-Za-z0-9-_]+).xml$",
        sitemap,
        {"sitemaps": sitemaps},
        name="sitemap",
    ),
    path("", include("user_sessions.urls", "user_sessions")),
    path("", include(("routechoices.site.urls", "site"), namespace="site")),
]

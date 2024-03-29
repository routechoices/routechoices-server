from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django_hosts.resolvers import reverse

admin.site.site_header = "Admin"
admin.site.site_title = "Admin Site"
admin.site.index_title = "Welcome to the administration site"
admin.site.site_url = f"//www.{settings.PARENT_HOST}"


def admin_login(request):
    return redirect(
        reverse("account_login", host="www") + f"?next=//admin.{settings.PARENT_HOST}"
    )


urlpatterns = [
    path("hijack/", include("hijack.urls")),
    path("login/", admin_login),
    path("", admin.site.urls),
]

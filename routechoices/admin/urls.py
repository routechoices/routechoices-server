from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from routechoices.site import views

admin.site.site_header = "Admin"
admin.site.site_title = "Admin Site"
admin.site.index_title = "Welcome to the administration site"
admin.site.site_url = f"//www.{settings.PARENT_HOST}"
admin.site.login = views.CustomAdminLoginView.as_view()

urlpatterns = [
    path("hijack/", include("hijack.urls")),
    path("", admin.site.urls),
]

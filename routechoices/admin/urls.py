from django.contrib import admin
from django.urls import path

admin.site.site_header = "Admin"
admin.site.site_title = "Admin Site"
admin.site.index_title = "Welcome to the administration site"

urlpatterns = [
    path("", admin.site.urls),
]

from django.urls import re_path

from routechoices.api import views

urlpatterns = [
    re_path(r"^$", views.wms_service, name="wms_service"),
]

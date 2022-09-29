from django.urls import re_path

from routechoices.wms import views

urlpatterns = [
    re_path(r"^$", views.wms_service, name="wms_service"),
]

from django.urls import re_path
from django.views.generic import TemplateView

urlpatterns = [
    re_path(
        r"^$",
        TemplateView.as_view(template_name="site/registration.html"),
        name="registration",
    ),
]

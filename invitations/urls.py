from django.urls import re_path

from . import views

app_name = "invitations"

urlpatterns = [
    re_path(
        r"^accept/(?P<key>\w+)/?$",
        views.AcceptInvite.as_view(),
        name="accept-invite",
    ),
]

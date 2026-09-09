from django.urls import path

from routechoices.webhooks import views

urlpatterns = [
    path(
        "lemonsqueezy",
        views.lemonsqueezy_webhook,
        name="lemonsqueezy_webhook",
    ),
    path(
        "rastilippu",
        views.rastilippu_webhook,
        name="rastilippu_webhook",
    ),
]

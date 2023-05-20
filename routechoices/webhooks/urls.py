from django.urls import re_path

from routechoices.webhooks import views

urlpatterns = [
    re_path(
        r"^lemonsqueezy/?$", views.lemonsqueezy_webhook, name="lemonsqueezy_webhook"
    ),
]

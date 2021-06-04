from django.conf.urls import url

from routechoices.stripe import views

urlpatterns = [
    url(
        r'^webhook/?$',
        views.webhook_handler,
        name='webhook_handler'
    ),
    url(
        r'^create_subscription/?$',
        views.create_subscription_view,
        name='create_subscription_view'
    ),
    url(
        r'^cancel_subscription/?$',
        views.cancel_subscription_view,
        name='cancel_subscription_view'
    ),
]

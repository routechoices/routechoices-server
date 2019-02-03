from django.conf.urls import url
from django.views.generic import TemplateView

from routechoices.dashboard import views

urlpatterns = [
    url(r'^/?$', views.home_view, name='home_view'),
]
from django.urls import path, re_path

from routechoices.core import views as core_views
from routechoices.tiles import views

urlpatterns = [
    re_path(r"^$", views.serve_tile, name="tile_service"),
    re_path(
        r"^proxy/(?P<country>ch|ee|uk|fr)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.webp$",
        views.serve_tile_proxy,
        name="proxy_tile_service",
    ),
    path(".well-known/security.txt", core_views.security_txt),
]

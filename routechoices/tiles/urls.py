from django.urls import re_path

from routechoices.tiles import views

urlpatterns = [
    re_path(r"^$", views.serve_tile, name="tile_service"),
]

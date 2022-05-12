from django.urls import re_path

from routechoices.dashboard import views

urlpatterns = [
    re_path(r"^$", views.home_view, name="home_view"),
    re_path(r"^account/?$", views.account_edit_view, name="account_edit_view"),
    re_path(
        r"^account/delete/?$", views.account_delete_view, name="account_delete_view"
    ),
    re_path(r"^calibrate_map/?$", views.calibration_view, name="calibration_view"),
    re_path(r"^pdf-to-jpg/?$", views.pdf_to_jpg, name="pdf_to_jpg"),
    re_path(
        r"^check_calibration/?$",
        views.check_calibration_view,
        name="check_calibration_view",
    ),
    re_path(r"^devices/?$", views.device_list_view, name="device_list_view"),
    re_path(r"^devices/add/?$", views.device_add_view, name="device_add_view"),
    re_path(r"^select-club/?$", views.club_select_view, name="club_select_view"),
    re_path(r"^new-club/?$", views.club_create_view, name="club_create_view"),
    re_path(
        r"^club/set/(?P<club_id>[A-Za-z0-9_-]+)/$",
        views.club_set_view,
        name="club_set_view",
    ),
    re_path(r"^club/$", views.club_view, name="club_view"),
    re_path(
        r"^club/custom-domain/?$",
        views.club_custom_domain_view,
        name="club_custom_domain_view",
    ),
    re_path(
        r"^club/delete/?$",
        views.club_delete_view,
        name="club_delete_view",
    ),
    re_path(r"^maps/?$", views.map_list_view, name="map_list_view"),
    re_path(r"^maps/new/?$", views.map_create_view, name="map_create_view"),
    re_path(
        r"^maps/upload-kmz/?$", views.map_kmz_upload_view, name="map_upload_kmz_view"
    ),
    re_path(
        r"^maps/upload-gpx/?$", views.map_gpx_upload_view, name="map_upload_gpx_view"
    ),
    re_path(
        r"^maps/(?P<map_id>[A-Za-z0-9_-]+)/?$",
        views.map_edit_view,
        name="map_edit_view",
    ),
    re_path(
        r"^maps/(?P<map_id>[A-Za-z0-9_-]+)/delete/?$",
        views.map_delete_view,
        name="map_delete_view",
    ),
    re_path(r"^events/?$", views.event_list_view, name="event_list_view"),
    re_path(r"^events/new/?$", views.event_create_view, name="event_create_view"),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/?$",
        views.event_edit_view,
        name="event_edit_view",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/competitors/?$",
        views.event_competitors_view,
        name="event_competitors_view",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/delete/?$",
        views.event_delete_view,
        name="event_delete_view",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/chat-moderation/?$",
        views.event_chat_moderation_view,
        name="event_chat_moderation_view",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/live/?$",
        views.event_view_live,
        name="event_view_live",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/route-upload/?$",
        views.event_route_upload_view,
        name="event_route_upload_view",
    ),
]

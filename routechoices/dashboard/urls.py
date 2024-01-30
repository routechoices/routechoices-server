from allauth.account import views as allauth_views
from django.urls import re_path
from user_sessions import views as user_sessions_views

from routechoices.dashboard import views

urlpatterns = [
    re_path(r"^$", views.home_view, name="home_view"),
    re_path(r"^account/?$", views.account_edit_view, name="account_edit_view"),
    re_path(r"^account/emails/?$", views.email_view, name="account_emails"),
    re_path(
        r"^account/change-password/?$",
        allauth_views.password_change,
        name="account_password_change",
    ),
    re_path(
        r"^account/delete/?$", views.account_delete_view, name="account_delete_view"
    ),
    re_path(
        r"^account/sessions/?$",
        view=user_sessions_views.SessionListView.as_view(),
        name="account_session_list",
    ),
    re_path(
        r"^account/sessions/delete-others/?$",
        view=views.CustomSessionDeleteOtherView.as_view(),
        name="account_session_delete_other",
    ),
    re_path(r"^club/?$", views.club_view, name="club_view"),
    re_path(
        r"^club/send-invite/?$", views.club_invite_add_view, name="club_invite_add_view"
    ),
    re_path(
        r"^request-invite/?$",
        views.club_request_invite_view,
        name="club_request_invite_view",
    ),
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
    re_path(
        r"^club/(?P<club_id>[A-Za-z0-9_-]+)/?$",
        views.club_set_view,
        name="club_set_view",
    ),
    re_path(r"^clubs/?$", views.club_select_view, name="club_select_view"),
    re_path(r"^clubs/new/?$", views.club_create_view, name="club_create_view"),
    re_path(r"^devices/?$", views.device_list_view, name="device_list_view"),
    re_path(r"^devices/new/?$", views.device_add_view, name="device_add_view"),
    re_path(r"^devices.csv$", views.device_list_download, name="device_list_download"),
    re_path(r"^maps/?$", views.map_list_view, name="map_list_view"),
    re_path(r"^maps/new/?$", views.map_create_view, name="map_create_view"),
    re_path(r"^maps/draw/?$", views.map_draw_view, name="map_draw_view"),
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
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/competitors-printer-friendly/?$",
        views.event_competitors_printer_view,
        name="event_competitors_printer_view",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/delete/?$",
        views.event_delete_view,
        name="event_delete_view",
    ),
    re_path(
        r"^events/(?P<event_id>[A-Za-z0-9_-]+)/route-upload/?$",
        views.event_route_upload_view,
        name="event_route_upload_view",
    ),
    re_path(r"^event-sets/?$", views.event_set_list_view, name="event_set_list_view"),
    re_path(
        r"^event-sets/new/?$", views.event_set_create_view, name="event_set_create_view"
    ),
    re_path(
        r"^event-sets/(?P<event_set_id>[A-Za-z0-9_-]+)/?$",
        views.event_set_edit_view,
        name="event_set_edit_view",
    ),
    re_path(
        r"^event-sets/(?P<event_set_id>[A-Za-z0-9_-]+)/delete/?$",
        views.event_set_delete_view,
        name="event_set_delete_view",
    ),
    re_path(
        r"^quick-event/?$",
        views.quick_event,
        name="quick_event_view",
    ),
    re_path(r"^upgrade/?$", views.upgrade, name="upgrade"),
]

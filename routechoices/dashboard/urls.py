from django.conf.urls import url

from routechoices.dashboard import views

urlpatterns = [
    url(r'^$', views.home_view, name='home_view'),
    url(r'^account/?$', views.account_edit_view, name='account_edit_view'),
    url(r'^calibrate_map/?$', views.calibration_view, name='calibration_view'),
    url(r'^pdf_to_jpg/?$', views.pdf_to_jpg, name='pdf_to_jpg'),
    url(
        r'^check_calibration/?$',
        views.check_calibration_view,
        name='check_calibration_view'
    ),

    url(r'^device/?$', views.device_list_view, name='device_list_view'),
    url(r'^device/add/?$', views.device_add_view, name='device_add_view'),
    url(
        r'^device/(?P<id>[A-Za-z0-9_-]+)/remove/?$',
        views.device_remove_view,
        name='device_remove_view'
    ),

    url(r'^club/?$', views.club_list_view, name='club_list_view'),
    url(r'^club/new/?$', views.club_create_view, name='club_create_view'),
    url(
        r'^club/(?P<id>[A-Za-z0-9_-]+)/$',
        views.club_edit_view,
        name='club_edit_view'
    ),
    url(
        r'^club/(?P<id>[A-Za-z0-9_-]+)/custom_domain/?$',
        views.club_custom_domain_view,
        name='club_custom_domain_view'
    ),
    url(
        r'^club/(?P<id>[A-Za-z0-9_-]+)/delete/?$',
        views.club_delete_view,
        name='club_delete_view'
    ),

    url(r'^map/?$', views.map_list_view, name='map_list_view'),
    url(r'^map/new/?$', views.map_create_view, name='map_create_view'),
    url(
        r'^map/upload_kmz/?$',
        views.map_kmz_upload_view,
        name='map_upload_kmz_view'
    ),
    url(
        r'^map/upload_gpx/?$',
        views.map_gpx_upload_view,
        name='map_upload_gpx_view'
    ),
    url(
        r'^map/(?P<id>[A-Za-z0-9_-]+)/?$',
        views.map_edit_view,
        name='map_edit_view'
    ),
    url(
        r'^map/(?P<id>[A-Za-z0-9_-]+)/delete/?$',
        views.map_delete_view,
        name='map_delete_view'
    ),

    url(r'^event/?$', views.event_list_view, name='event_list_view'),
    url(r'^event/new/?$', views.event_create_view, name='event_create_view'),
    url(
        r'^event/(?P<id>[A-Za-z0-9_-]+)/?$',
        views.event_edit_view,
        name='event_edit_view'
    ),
    url(
        r'^event/(?P<id>[A-Za-z0-9_-]+)/delete/?$',
        views.event_delete_view,
        name='event_delete_view'
    ),
    url(
        r'^event/(?P<id>[A-Za-z0-9_-]+)/route_upload/?$',
        views.event_route_upload_view,
        name='event_gpx_upload_view'
    ),
]

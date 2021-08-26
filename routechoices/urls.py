"""routechoices URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf.urls import url
from django.urls import include
from django.contrib.sitemaps.views import sitemap
from routechoices.dashboard.views import dashboard_map_download
from routechoices.site.sitemaps import (
    StaticViewSitemap,
    DynamicViewSitemap,
)


admin.site.site_header = "Routechoices.com Admin"
admin.site.site_title = "Routechoices.com Admin Site"
admin.site.index_title = "Welcome to Routechoices.com Administration Site"

sitemaps = {
    'static': StaticViewSitemap,
    'dynamic': DynamicViewSitemap,
}

urlpatterns = [
    url(r'^accounts/', include('allauth.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include(('routechoices.api.urls', 'api'), namespace='api')),
    url(
        r'^dashboard/',
        include(
            ('routechoices.dashboard.urls', 'dashboard'),
            namespace='dashboard'
        )
    ),
    url(
        r'^media/maps/(?P<hash>[-0-9a-zA-Z_])/(?P<hash2>[-0-9a-zA-Z_])/'
        r'(?P<id>(?P=hash)(?P=hash2)[-0-9a-zA-Z_]{9})(\_\d+)?',
        dashboard_map_download,
        name='dashboard_map_download',
    ),
    url(r'^sitemap\.xml$', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    url('^sitemap-(?P<section>[A-Za-z0-9-_]+).xml$', sitemap,
        {'sitemaps': sitemaps}, name='sitemap'),
    url(r'', include('user_sessions.urls', 'user_sessions')),
    url(r'', include(('routechoices.site.urls', 'site'), namespace='site')),
]

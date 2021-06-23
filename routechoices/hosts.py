from django_hosts import patterns, host


host_patterns = patterns(
    '',
    host(r'www', 'routechoices.urls', name='www'),
    host(
        r'(?P<club_slug>[a-zA-Z0-9_-]{2,})', 
        'routechoices.site.clubs_urls', 
        callback='routechoices.site.clubs_urls.set_club',
        name='clubs'),
)

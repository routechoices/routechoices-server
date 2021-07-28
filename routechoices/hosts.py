from django_hosts import patterns, host


host_patterns = patterns(
    '',
    host(r'www', 'routechoices.urls', name='www'),
    host(r'api', 'routechoices.api.urls', name='api'),
    host(
        r'(?P<club_slug>[a-zA-Z0-9][a-zA-Z0-9_-]+)', 
        'routechoices.club.urls', 
        callback='routechoices.club.urls.set_club',
        name='clubs'),
)

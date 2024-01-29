"""
WSGI config for routechoices project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import atexit
import os

import coverage
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "routechoices.settings")
os.environ["HTTPS"] = "on"
cov = coverage.coverage()
cov.start()
application = get_wsgi_application()


def save_coverage():
    print("Saving coverage")
    cov.stop()
    cov.save()


atexit.register(save_coverage)

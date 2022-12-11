import time
from urllib.parse import urlencode
from urllib.request import urlopen

from django.contrib.sitemaps import PING_URL
from django.core.management.base import BaseCommand

from routechoices.core.models import Club


class Command(BaseCommand):
    help = "Ping Google with an updated sitemap for all subdomains"

    def handle(self, *args, **options):
        clubs = Club.objects.all()
        for club in clubs:
            sitemap_full_url = f"{club.nice_url}sitemap.xml"
            print(sitemap_full_url)
            params = urlencode({"sitemap": sitemap_full_url})
            urlopen(f"{PING_URL}?{params}")
            time.sleep(0.1)

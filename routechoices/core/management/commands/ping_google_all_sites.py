import time
from urllib.parse import urlencode

import requests
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
            requests.get(
                f"{PING_URL}?{params}",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/102.0.0.0 Safari/537.36"
                    )
                },
                timeout=5,
            )
            time.sleep(0.1)

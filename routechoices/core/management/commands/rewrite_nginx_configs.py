import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from routechoices.core.management.commands.create_certificate import write_nginx_conf
from routechoices.core.models import Club


class Command(BaseCommand):
    help = "Rewrite the nginx configuration file for club with custom domain"

    def add_arguments(self, parser):
        parser.add_argument("domains", nargs="*", type=str)
        parser.add_argument("--post-hook", dest="post-hook", type=str, default=None)

    def handle(self, *args, **options):
        nginx_need_restart = False
        domains = options["domains"]
        if not domains:
            clubs_w_domain = Club.objects.exclude(domain="").exclude(
                domain__isnull=True
            )
            for club in clubs_w_domain:
                domain = club.domain
                if Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.key").exists():
                    domains.append(domain)
            if not domains:
                self.stderr.write("No clubs have certificates")
        for domain in domains:
            club = Club.objects.filter(domain=domain).first()
            if not club:
                self.stderr.write("No club with this domain")
                continue
            write_nginx_conf(domain)
            nginx_need_restart = True
        if nginx_need_restart:
            print("Reload nginx for changes to take effect...")
            if options["post-hook"]:
                subprocess.run(
                    options["post-hook"],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=False,
                )

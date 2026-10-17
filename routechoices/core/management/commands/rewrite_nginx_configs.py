import subprocess

from django.core.management.base import BaseCommand

from routechoices.core.models import Club, write_nginx_conf


class Command(BaseCommand):
    help = "Rewrite the nginx configuration file for club with custom domain"

    def add_arguments(self, parser):
        parser.add_argument("domains", nargs="*", type=str)
        parser.add_argument("--post-hook", dest="post-hook", type=str, default=None)

    def handle(self, *args, **options):
        nginx_need_restart = False
        domains = options["domains"]
        if not domains:
            domains = Club.objects.exclude(domain="")
            if not domains:
                self.stderr.write("No clubs have setup custom domain")
        for domain in domains:
            club = Club.objects.filter(domain=domain).first()
            if not club:
                self.stderr.write(f"No club with this domain ({domain})")
                continue
            write_nginx_conf(domain)
            nginx_need_restart = True
        # TODO: erase extra leftover configs
        if nginx_need_restart:
            self.stdout.write("Reload nginx for changes to take effect...")
            if options["post-hook"]:
                subprocess.run(
                    options["post-hook"],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )

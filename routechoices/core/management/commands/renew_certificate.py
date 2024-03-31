import os
import os.path
import subprocess
import sys

import sewer.client
from django.conf import settings
from django.core.management.base import BaseCommand
from sewer.crypto import AcmeAccount, AcmeKey

from routechoices.core.models import Club
from routechoices.lib.helpers import check_cname_record
from routechoices.lib.ssl_certificates import (
    ClubAcmeProvider,
    is_account_ssl_expirying,
    read_account_ssl_key,
    write_account_ssl_key,
)


class Command(BaseCommand):
    help = "Renew letsencrypt certificate for club custom domain"

    def add_arguments(self, parser):
        parser.add_argument("domains", nargs="*", type=str)
        parser.add_argument("--post-hook", dest="post-hook", type=str, default=None)

    def handle(self, *args, **options):
        nginx_need_restart = False

        domains = options["domains"]

        if not domains:
            domains = Club.objects.exclude(domain="").values_list("domain", flat=True)

        for domain in domains:
            self.stdout.write(f"Processing {domain} ...")
            club = Club.objects.filter(domain=domain).first()
            if not club:
                self.stderr.write("No club with this domain")
                continue

            if not os.path.exists(
                os.path.join(settings.BASE_DIR, "nginx", "certs", f"{domain}.key")
            ):
                self.stderr.write(
                    "SSL not setup for this domain, no key/certificate found"
                )
                continue

            if not is_account_ssl_expirying(domain):
                self.stderr.write("Certificate for domain is not yet expiring")
                continue

            if not check_cname_record(domain):
                self.stderr.write("Domain is not pointing to routechoices.com anymore")
                club.domain = ""
                club.save()
                continue

            account_exists = os.path.exists(
                os.path.join(
                    settings.BASE_DIR, "nginx", "certs", "accounts", f"{domain}.key"
                )
            )
            if account_exists:
                acct_key = read_account_ssl_key(domain, AcmeAccount)
            else:
                acct_key = AcmeAccount.create("secp256r1")
                write_account_ssl_key(domain, acct_key)

            cert_key = AcmeKey.read_pem(
                os.path.join(settings.BASE_DIR, "nginx", "certs", f"{domain}.key")
            )

            client = sewer.client.Client(
                domain_name=domain,
                provider=ClubAcmeProvider(club),
                account=acct_key,
                cert_key=cert_key,
                is_new_acct=(not account_exists),
                contact_email="raphael@routechoices.com",
            )
            try:
                certificate = client.get_certificate()
            except Exception:
                self.stderr.write("Failed to create certificate...")
                continue
            cert_key = client.cert_key

            cert_filename = os.path.join(
                settings.BASE_DIR, "nginx", "certs", f"{domain}.crt"
            )
            cert_key_filename = os.path.join(
                settings.BASE_DIR, "nginx", "certs", f"{domain}.key"
            )

            with open(cert_filename, "w", encoding="utf_8") as fp:
                fp.write(certificate)
            cert_key.write_pem(cert_key_filename)

            os.chmod(cert_filename, 0o600)
            os.chmod(cert_key_filename, 0o600)

            nginx_need_restart = True
            self.stdout.write("Certificate renewed.")
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
            sys.exit(0)
        else:
            sys.exit(1)

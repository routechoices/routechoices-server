import os
import os.path
import subprocess
import sys
from pathlib import Path

import sewer.client
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from sewer.crypto import AcmeAccount, AcmeKey

from routechoices.core.models import Club
from routechoices.lib.helpers import check_cname_record
from routechoices.lib.ssl_certificates import (
    ClubAcmeProvider,
    is_account_ssl_expirying,
    read_account_ssl_key,
    write_account_ssl_key,
)


def write_nginx_conf(domain):
    conf_file = render_to_string(
        "nginx_domain.conf", {"base_dir": settings.BASE_DIR, "domain": domain}
    )
    Path(f"{settings.BASE_DIR}/nginx/custom_domains/{domain}").write_text(conf_file)


class Command(BaseCommand):
    help = "Manage SSL certificates for club custom domains"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            title="sub-commands",
            required=True,
        )
        create_parser = subparsers.add_parser(
            "create",
            help="Create SSL certificates",
        )
        create_parser.set_defaults(method=self.create)

        renew_parser = subparsers.add_parser(
            "renew",
            help="Renew SSL certificates",
        )
        renew_parser.set_defaults(method=self.renew)

        parser.add_argument("domains", nargs="*", type=str)
        parser.add_argument("--post-hook", dest="post-hook", type=str, default=None)

    def handle(self, *args, method, **options):
        method(*args, **options)

    def create(self, *args, **options):
        nginx_need_restart = False
        domains = options["domains"]
        if not domains:
            clubs_w_domain = Club.objects.exclude(domain="").exclude(
                domain__isnull=True
            )
            for club in clubs_w_domain:
                domain = club.domain
                if (
                    not Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.key").exists()
                    and not Path(
                        f"{settings.BASE_DIR}/nginx/certs/{domain}.lock"
                    ).exists()
                ):
                    domains.append(domain)
            if not domains:
                self.stderr.write("No clubs require certificates")
        for domain in domains:
            club = Club.objects.filter(domain=domain).first()
            if not club:
                self.stderr.write("No club with this domain")
                continue

            if Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.lock").exists():
                self.stderr.write("Certificate creation for this domain in progress")
                continue

            if Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.key").exists():
                self.stderr.write("Certificate for this domain already exists")
                continue

            if not check_cname_record(domain):
                self.stderr.write("Domain is not pointing to routechoices.com anymore")
                club.domain = ""
                club.save()
                continue

            acct_key = AcmeAccount.create("secp256r1")
            write_account_ssl_key(domain, acct_key)

            client = sewer.client.Client(
                domain_name=domain,
                provider=ClubAcmeProvider(club),
                account=acct_key,
                cert_key=AcmeKey.create("secp256r1"),
                is_new_acct=True,
                contact_email="raphael@routechoices.com",
            )

            Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.lock").touch()
            try:
                certificate = client.get_certificate()
            except Exception:
                self.stderr.write("Failed to create certificate...")
                continue
            finally:
                Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.lock").unlink()

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
            sys.exit(0)
        else:
            sys.exit(1)

    def renew(self, *args, **options):
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

import os.path

import sewer.client
from django.conf import settings
from django.core.management.base import BaseCommand
from sewer.auth import ProviderBase
from sewer.crypto import AcmeAccount, AcmeKey

from routechoices.core.models import Club


def write_nginf_conf(domain):
    with open(
        os.path.join(settings.BASE_DIR, "nginx", "custom_domains", f"{domain}"),
        "w",
        encoding="utf_8",
    ) as fp:
        fp.write(
            f"""server {{
    server_name {domain};
    if ($host = {domain}) {{
        return 302 https://$host$request_uri;
    }}
    listen 80;
    listen [::]:80;
    return 404;
}}

server {{
    server_name {domain};

    ssl_certificate {os.path.join(settings.BASE_DIR, 'nginx', 'certs', f'{domain}.crt')};
    ssl_certificate_key {os.path.join(settings.BASE_DIR, 'nginx', 'certs', f'{domain}.key')};
    listen 443 ssl http2;
    listen [::]:443 ssl http2;

    location / {{
       set $no_cache "";
       if ($request_method !~ ^(GET|HEAD)$) {{
           set $no_cache "1";
       }}
       if ($uri ~ ^(\\/dashboard|\\/admin)) {{
           set $no_cache "1";
       }}
       if ($no_cache = "1") {{
           add_header Set-Cookie "_mcnc=1; Max-Age=2; Path=/";
           add_header X-Microcachable "0";
       }}
       if ($http_cookie ~* "_mcnc") {{
           set $no_cache "1";
       }}
       uwsgi_cache microcache;
       uwsgi_cache_key $scheme$host$request_method$request_uri;
       uwsgi_cache_valid 200 1s;
       uwsgi_cache_use_stale updating;
       uwsgi_max_temp_file_size 10M;
       uwsgi_no_cache $no_cache;
       uwsgi_cache_bypass $no_cache;

       client_max_body_size    10M;
       proxy_set_header        Host $host;
       proxy_set_header        X-Real-IP $remote_addr;
       proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
       uwsgi_pass              unix://{os.path.join(settings.BASE_DIR, 'var', 'django.sock')};
       uwsgi_pass_header       Authorization;
       uwsgi_hide_header       X-Accel-Redirect;
       uwsgi_hide_header       X-Sendfile;
       uwsgi_pass_header       Set-Cookie;
       uwsgi_intercept_errors  off;
       include                 uwsgi_params;
    }}
}}
"""
        )


def write_account_key(self, filename):
    with open(filename, "wb") as f:
        if hasattr(self, "__kid") and self.__kid:
            f.write(f"KID: {self.__kid}\n".encode())
            if self._timestamp:
                f.write(f"Timestamp: {self._timestamp}\n".encode())
        f.write(self.to_pem())


class ClubProvider(ProviderBase):
    def __init__(self, club, **kwargs):
        kwargs["chal_types"] = ["http-01"]
        self.club = club
        super().__init__(**kwargs)
        self.chal_type = "http-01"

    def setup(self, challenges):
        self.club.acme_challenge = challenges[0]["key_auth"]
        self.club.save()
        return []

    def unpropagated(self, challenges):
        # could add confirmation here, but it's just a demo
        return []

    def clear(self, challenges):
        self.club.acme_challenge = ""
        self.club.save()
        return []


class Command(BaseCommand):
    help = "Create letsencrypt certificate for club custom domain"

    def add_arguments(self, parser):
        parser.add_argument("domains", nargs="+", type=str)

    def handle(self, *args, **options):
        nginx_need_restart = False
        for domain in options["domains"]:
            club = Club.objects.filter(domain=domain).first()
            if not club:
                self.stderr.write("No club with this domain")
                continue

            if os.path.exists(
                os.path.join(settings.BASE_DIR, "nginx", "certs", f"{domain}.key")
            ):
                self.stderr.write("Certificates for this domain already exists")
                continue

            acct_key = AcmeAccount.create("secp256r1")

            client = sewer.client.Client(
                domain_name=domain,
                provider=ClubProvider(club),
                account=acct_key,
                cert_key=AcmeKey.create("secp256r1"),
                is_new_acct=True,
                contact_email="raphael@routechoices.com",
            )
            try:
                certificate = client.get_certificate()
            except Exception:
                self.stderr.write("Failed to create certificate...")
                continue
            cert_key = client.cert_key

            with open(
                os.path.join(settings.BASE_DIR, "nginx", "certs", f"{domain}.crt"),
                "w",
                encoding="utf_8",
            ) as fp:
                fp.write(certificate)
            cert_key.write_pem(
                os.path.join(settings.BASE_DIR, "nginx", "certs", f"{domain}.key")
            )
            write_account_key(
                acct_key,
                os.path.join(
                    settings.BASE_DIR, "nginx", "certs", "accounts", f"{domain}.key"
                ),
            )
            write_nginf_conf(domain)
            nginx_need_restart = True
        if nginx_need_restart:
            print("Reload nginx for changes to take effect...")

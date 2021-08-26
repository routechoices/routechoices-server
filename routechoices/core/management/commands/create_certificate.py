import os.path
import sys
from django.core.management.base import BaseCommand
from django.conf import settings

import sewer.client
from sewer.crypto import AcmeKey, AcmeAccount
from sewer.auth import ProviderBase

from routechoices.core.models import Club
from typing import cast


def write_nginf_conf(domain):
    with open(os.path.join(settings.BASE_DIR, 'nginx', 'custom_domains', f'{domain}'), 'w') as f:
        f.write(f'''server {{
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
    listen 443;
    listen [::]:443;

    location / {{
       client_max_body_size    10M;
       proxy_set_header Host   $host;
       proxy_set_header        X-Real-IP $remote_addr;
       proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
       uwsgi_pass              unix://{os.path.join(settings.BASE_DIR, 'var', 'django.sock')};
       uwsgi_pass_header       Authorization;
       uwsgi_hide_header       X-Accel-Redirect;
       uwsgi_hide_header       X-Sendfile;
       uwsgi_intercept_errors  off;
       include                 uwsgi_params;
    }}
}}''')


def write_account_key(self, filename):
    with open(filename, "wb") as f:
        if self.__kid:
            f.write(("KID: %s\n" % self.__kid).encode())
            if self._timestamp:
                f.write(("Timestamp: %s\n" % self._timestamp).encode())
        f.write(self.to_pem())


class ClubProvider(ProviderBase):
    def __init__(self, club, **kwargs):
        kwargs["chal_types"] = ["http-01"]
        self.club = club
        super().__init__(**kwargs)
        self.chal_type = "http-01"

    def setup(self, challenges):
        self.club.acme_challenge = challenges[0]['key_auth']
        self.club.save()
        return []
    
    def unpropagated(self, challenges):
        # could add confirmation here, but it's just a demo
        return []

    def clear(self, challenges):
        self.club.acme_challenge = ''
        self.club.save()
        return []



class Command(BaseCommand):
    help = 'Create letsencrypt certificate for club custom domain'

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='+', type=str)

    def handle(self, *args, **options):
        nginx_need_restart = False
        for domain in options['domains']:
            club = Club.objects.filter(domain=domain).first()
            if not club:
                self.stderr.write('No club with this domain')
                continue
        
            if os.path.exists(os.path.join(settings.BASE_DIR, 'nginx', 'certs', f'{domain}.key')):
                self.stderr.write('Certificates for this domain already exists')
                continue
            
            acct_key = AcmeAccount.create("secp256r1")

            client = sewer.client.Client(
                domain_name=domain,
                provider=ClubProvider(club),
                account=acct_key,
                cert_key=AcmeKey.create("secp256r1"),
                is_new_acct=True,
                contact_email='raphael@routechoices.com'
            )
            try:
                certificate = client.get_certificate()
            except Exception:
                self.stderr.write('Failed to create certificate...')
                continue
            cert_key = client.cert_key

            with open(os.path.join(settings.BASE_DIR, 'nginx', 'certs', f'{domain}.crt'), 'w') as f:
                f.write(certificate)
            cert_key.write_pem(os.path.join(settings.BASE_DIR, 'nginx', 'certs', f'{domain}.key'))
            write_account_key(acct_key, os.path.join(settings.BASE_DIR, 'nginx', 'certs', 'accounts', f'{domain}.key'))
            write_nginf_conf(domain)
        if nginx_need_restart:
            print('Reload nginx for changes to take effect...')
        


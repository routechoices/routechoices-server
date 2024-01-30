import os
import os.path

import arrow
from cryptography import x509
from django.conf import settings
from sewer.auth import ProviderBase


def is_account_ssl_expirying(domain):
    cert_path = os.path.join(settings.BASE_DIR, "nginx", "certs", f"{domain}.crt")
    if not os.path.exists(cert_path):
        return True
    with open(cert_path, "rb") as fp:
        data = fp.read()
    cert = x509.load_pem_x509_certificate(data)
    return arrow.utcnow().shift(days=30) > arrow.get(cert.not_valid_after)


def read_account_ssl_key(domain, key_cls):
    filename = os.path.join(
        settings.BASE_DIR, "nginx", "certs", "accounts", f"{domain}.key"
    )
    with open(filename, "rb") as f:
        data = f.read()
    prefix = b""
    n = data.find(b"-----BEGIN")
    if n > 0:
        prefix = data[:n]
        data = data[n:]
    acct = key_cls.from_pem(data)
    if prefix:
        parts = prefix.split(b"\n")
        for p in parts:
            if p.startswith(b"KID: "):
                acct.__kid = p[5:].decode()
            elif p.startswith(b"Timestamp: "):
                acct._timestamp = float(p[11:])
    return acct


def write_account_ssl_key(domain, key):
    filename = os.path.join(
        settings.BASE_DIR, "nginx", "certs", "accounts", f"{domain}.key"
    )
    with open(filename, "wb") as f:
        if hasattr(key, "__kid") and key.__kid:
            f.write(f"KID: {key.__kid}\n".encode())
            if key._timestamp:
                f.write(f"Timestamp: {key._timestamp}\n".encode())
        f.write(key.to_pem())


class ClubAcmeProvider(ProviderBase):
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
        return []

    def clear(self, challenges):
        self.club.acme_challenge = ""
        self.club.save()
        return []

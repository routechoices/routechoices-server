import os
import re
import urllib.parse
from pathlib import Path

import sewer.client
from background_task import background
from django.conf import settings
from django.template.loader import render_to_string
from sewer.crypto import AcmeAccount, AcmeKey

from routechoices.core.models import Club, Event
from routechoices.lib.helpers import check_dns_records
from routechoices.lib.other_gps_services.gpsseuranta import GpsSeurantaNet
from routechoices.lib.other_gps_services.livelox import Livelox
from routechoices.lib.other_gps_services.loggator import Loggator
from routechoices.lib.other_gps_services.otracker import OTracker
from routechoices.lib.other_gps_services.sportrec import SportRec
from routechoices.lib.other_gps_services.tractrac import Tractrac
from routechoices.lib.other_gps_services.virekunnas import GpsVirekunnasFi
from routechoices.lib.rastilippu import update_event_url as rl_update_event_url
from routechoices.lib.ssl_certificates import (
    ClubAcmeProvider,
    write_account_ssl_key,
)


def write_nginx_conf(domain):
    conf_file = render_to_string(
        "nginx_domain.conf", {"base_dir": settings.BASE_DIR, "domain": domain}
    )
    Path(f"{settings.BASE_DIR}/nginx/custom_domains/{domain}.conf").write_text(
        conf_file
    )


class EventImportError(Exception):
    pass


class MapImportError(Exception):
    pass


@background(schedule=0)
def import_single_event_from_gps_seuranta(event_id, club=None):
    event_id = event_id.strip()
    if match := re.match(
        r"^https?://((gps|www)\.)?tulospalvelu\.fi/gps/(?P<uid>[^/]+)/?", event_id
    ):
        event_id = match.group("uid")
    solution = GpsSeurantaNet()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_virekunnas(event_id, club=None):
    event_id = event_id.strip()
    if match := re.match(r"^https?://gps\.virekunnas\.fi/(?P<uid>[^/]+)/?", event_id):
        event_id = match.group("uid")
    solution = GpsVirekunnasFi()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_loggator(event_id, club=None):
    event_id = event_id.strip()
    if match := re.match(
        r"^https?://(events\.)?loggator\.com/(?P<uid>[^/]+)/?", event_id
    ):
        event_id = match.group("uid")
    solution = Loggator()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_tractrac(event_id, club=None):
    prefix = "https://live.tractrac.com/viewer/index.html?target="
    event_id = event_id.removeprefix(prefix)
    solution = Tractrac()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_otracker(event_id, club=None):
    prefix = "https://otracker.lt/events/"
    event_id = event_id.removeprefix(prefix)
    solution = OTracker()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_sportrec(event_id, club=None):
    prefix = "https://sportrec.eu/gps/"
    event_id = event_id.removeprefix(prefix)
    solution = SportRec()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_livelox(event_id, club=None):
    prefix = "https://www.livelox.com/Viewer/"
    if event_id.startswith(prefix):
        event_id = urllib.parse.urlparse(event_id).query
    solution = Livelox()
    if club:
        solution.club = Club.objects.get(slug=club)
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def rastilippu_update_event_url(event_id):
    event = Event.objects.select_related("club", "event_set").get(id=event_id)
    if not rl_update_event_url(event):
        raise Exception("Couldn't reach rastilippu service")


@background(schedule=0)
def provision_ssl_certificate(domain):
    club = Club.objects.get(domain=domain)
    if Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.lock").exists():
        print(f'Certificate creation for the domain "{domain}" already in progress')
        return
    if Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.key").exists():
        print(f'Certificate for the domain "{domain}" already exists')
        return
    if not check_dns_records(domain):
        print(
            f'DNS Record for domain "{domain}" is not pointing to cname.routechoices.com anymore'
        )
        club.domain = ""
        club.save()
        return

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
    certificate = client.get_certificate()
    Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.lock").unlink()

    cert_key = client.cert_key

    cert_filename = Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.crt")
    cert_key_filename = Path(f"{settings.BASE_DIR}/nginx/certs/{domain}.key")

    with open(cert_filename, "w", encoding="ascii") as fp:
        fp.write(certificate)
    os.chmod(cert_filename, 0o600)

    cert_key.write_pem(cert_key_filename)
    os.chmod(cert_key_filename, 0o600)
    write_nginx_conf(domain)

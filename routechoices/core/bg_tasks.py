import re
import urllib.parse

from background_task import background

from routechoices.core.models import Club, Event
from routechoices.lib.other_gps_services.gpsseuranta import GpsSeurantaNet
from routechoices.lib.other_gps_services.livelox import Livelox
from routechoices.lib.other_gps_services.loggator import Loggator
from routechoices.lib.other_gps_services.otracker import OTracker
from routechoices.lib.other_gps_services.sportrec import SportRec
from routechoices.lib.other_gps_services.tractrac import Tractrac
from routechoices.lib.other_gps_services.virekunnas import GpsVirekunnasFi
from routechoices.lib.rastilippu import update_event_url as rl_update_event_url


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
        print("sdsds")
        raise Exception("Couldn't reach rastilippu service")

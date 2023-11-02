import re
import urllib.parse

from background_task import background

from routechoices.lib.third_party_downloader import (
    GpsSeurantaNet,
    Livelox,
    Loggator,
    OTracker,
    SportRec,
    Tractrac,
)


class EventImportError(Exception):
    pass


class MapImportError(Exception):
    pass


@background(schedule=0)
def import_single_event_from_gps_seuranta(event_id):
    event_id = event_id.strip()
    if match := re.match(
        r"https?://((gps|www)\.)?tulospalvelu\.fi/gps/(?P<uid>[^/]+)/?", event_id
    ):
        event_id = match.group("uid")
    solution = GpsSeurantaNet()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_loggator(event_id):
    event_id = event_id.strip()
    if match := re.match(
        r"https?://(events\.)?loggator\.com/(?P<uid>[^/]+)/?", event_id
    ):
        event_id = match.group("uid")
    solution = Loggator()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_tractrac(event_id):
    prefix = "https://live.tractrac.com/viewer/index.html?target="
    if event_id.startswith(prefix):
        event_id = event_id[len(prefix) :]
    solution = Tractrac()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_otracker(event_id):
    prefix = "https://otracker.lt/events/"
    if event_id.startswith(prefix):
        event_id = event_id[len(prefix) :]
    solution = OTracker()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_sportrec(event_id):
    prefix = "https://sportrec.eu/gps/"
    if event_id.startswith(prefix):
        event_id = event_id[len(prefix) :]
    solution = SportRec()
    event = solution.import_event(event_id)
    return event


@background(schedule=0)
def import_single_event_from_livelox(event_id):
    prefix = "https://www.livelox.com/Viewer/"
    if event_id.startswith(prefix):
        event_id = urllib.parse.urlparse(event_id).query
    solution = Livelox()
    event = solution.import_event(event_id)
    return event

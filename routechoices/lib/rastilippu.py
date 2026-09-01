import hashlib
import hmac

import arrow
import orjson as json
from curl_cffi import requests
from django.conf import settings

from routechoices.core.models import Event, EventSet
from routechoices.lib.helpers import short_random_slug

RASTILIPPU_PREFIX = "RL-"
RASTILIPPU_WEBHOOK_URL = (
    f"{settings.RASTILIPPU_API_ROOT}/integration/webhooks/routechoices"
)


def webhook_sign(data):
    return hmac.new(
        settings.RASTILIPPU_SECRET.encode("utf-8"),
        msg=data,
        digestmod=hashlib.sha256,
    ).hexdigest()


def update_event_url(event):
    data = json.dumps(
        {
            "action": "update_courses_gps_replay_pages",
            "data": {
                "irma_id": event.event_set.external_id[len(RASTILIPPU_PREFIX) :],
                "courses": [
                    {
                        "course_id": event.external_id[len(RASTILIPPU_PREFIX) :],
                        "gps_replay_url": (
                            event.get_absolute_url() if event.map_id else ""
                        ),
                    }
                ],
            },
        }
    )
    r = requests.post(
        RASTILIPPU_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json", "X-Signature": webhook_sign(data)},
        timeout=10,
    )
    try:
        r.raise_for_status()
    except Exception:
        return False

    return r.status_code == 204
    # TODO: check why not 204, log it


def sync_courses_data(uuid):
    bundle = EventSet.objects.prefetch_related("events").get(
        external_metadata__uuid=uuid
    )

    r = requests.get(
        f"{settings.RASTILIPPU_API_ROOT}integration/event/{uuid}/courses",
        headers={"X-Authorization-rs": settings.RASTILIPPU_API_KEY},
        timeout=10,
    )
    try:
        r.raise_for_status()
    except Exception:
        return
    courses = r.json()

    course_data_by_id = {c.get("id"): c for c in courses}
    # Remove courses that do not exists anymore
    existing_events = bundle.events.all()
    for event in existing_events:
        event_rl_id = event.external_id[len(RASTILIPPU_PREFIX) :]
        if event_rl_id in course_data_by_id:
            course_data_by_id.pop(event_rl_id)
        else:
            # event not listed in courses anymore > remove
            event.delete()

    # here course_id_set should contain only ids that are not yet created
    for course in course_data_by_id.values():
        event, _ = Event.objects.get_or_create(
            external_id=f"{RASTILIPPU_PREFIX}{course["id"]}",
            event_set_id=bundle.id,
            club_id=bundle.club_id,
            defaults={
                "name": f"{bundle.name} - {course["name"]}",
                "slug": short_random_slug(),  # TODO: generate nice slugs
                "start_date": arrow.get(
                    bundle.external_metadata["start_date"]
                ).datetime,
                "end_date": arrow.get(bundle.external_metadata["end_date"]).datetime,
                "open_registration": True,
                "allow_route_upload": True,
            },
        )

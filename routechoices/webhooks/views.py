import hashlib
import hmac
import json

import arrow
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.exceptions import BadRequest
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from routechoices.core.models import Club, EventSet
from routechoices.lib.helpers import short_random_slug
from routechoices.lib.lemonsqueezy import LEMONSQUEEZY_PREFIX

RASTILIPPU_PREFIX = "RL-"


@csrf_exempt
def rastilippu_webhook(request):
    digest = hmac.new(
        settings.RASTILIPPU_SIGNATURE.encode("utf-8"),
        msg=request.body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if request.META.get("HTTP_X_SIGNATURE") != digest:
        return HttpResponseBadRequest("Invalid signature")

    data = json.loads(request.body, strict=False)

    action = data.get("action")
    data = data.get("data")

    if action == "retrieve_clubs":
        clubs = []
        try:
            email_raw = data["email"]
        except KeyError:
            raise BadRequest("Missing order_id")
        email = (
            EmailAddress.objects.prefetch_related("user")
            .filter(email__iexact=email_raw, verified=True)
            .first()
        )
        if email:
            user = email.user
            clubs = Club.objects.filter(admins=user)
        result = [
            {"slug": club.slug, "name": club.name, "is_upgraded": club.upgraded}
            for club in clubs
        ]
        return JsonResponse({"clubs": result, "count": len(result)})
    if action == "enable":
        try:
            order_id = data["order_id"]
        except KeyError:
            raise BadRequest("Missing order_id")

        try:
            slug = str(data["club_slug"])
        except KeyError:
            raise BadRequest("Missing clug_slug")

        club = Club.objects.filter(slug__iexact=slug, upgraded=False).first()
        if not club:
            raise BadRequest("No club without subscriptions found")

        club.upgraded = True
        club.upgraded_date = now()
        club.order_id = f"{RASTILIPPU_PREFIX}{order_id}"
        club.save()
        return JsonResponse(
            {
                "order_id": order_id,
                "club_slug": club.slug,
            }
        )

    if action == "disable":
        try:
            order_id = data["order_id"]
        except KeyError:
            raise BadRequest("Missing order_id")

        club = Club.objects.filter(order_id=f"{RASTILIPPU_PREFIX}{order_id}").first()
        if not club:
            raise BadRequest("No matching club with this order_id")

        club.upgraded = False
        club.upgraded_date = None
        club.order_id = ""
        club.save()
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)

    if action == "update_event":
        try:
            club_slug = data["club_slug"]
            name = data["name"][:255]
            irma_id = data["irma_id"]
            event_uuid = data["uuid"]
            start_date_raw = data["start_datetime"]
            end_date_raw = data["end_datetime"]
        except KeyError:
            raise BadRequest("Missing data")

        try:
            start_date = arrow.get(start_date_raw).datetime
            end_date = arrow.get(end_date_raw).datetime
            if end_date <= start_date:
                raise Exception("Start should be before end")
        except Exception:
            raise BadRequest("Invalid dates")

        club = Club.objects.filter(
            slug=club_slug,
            upgraded=True,
            order_id__startswith=RASTILIPPU_PREFIX,
        ).first()
        if not club:
            raise BadRequest("No matching club")

        bundle, created = EventSet.objects.get_or_create(
            external_id=f"{RASTILIPPU_PREFIX}{irma_id}",
            defaults={
                "club": club,
                "name": name,
                "slug": short_random_slug(),
                "create_page": True,
            },
        )

        bundle.name = name
        bundle.external_metadata = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "uuid": event_uuid,
        }
        bundle.save()

        if not created:
            for event in bundle.events.all():
                event.start_date = start_date
                event.end_date = end_date
                event.save()

        return JsonResponse(
            {
                "name": bundle.name,
                "slug": bundle.slug,
                "url": bundle.url,
            },
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
        )
    return HttpResponse("Valid webhook call with no action taken")


@csrf_exempt
def lemonsqueezy_webhook(request):
    digest = hmac.new(
        settings.LEMONSQUEEZY_SIGNATURE.encode("utf-8"),
        msg=request.body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if request.META.get("HTTP_X_SIGNATURE") != digest:
        return HttpResponseBadRequest("Invalid signature")

    data = json.loads(request.body, strict=False)

    variant_id = None
    try:
        variant_id = str(
            data["data"]["attributes"].get("variant_id")
            or data["data"]["attributes"].get("first_order_item", {}).get("variant_id")
        )
    except Exception:
        pass

    # Club Upgrade
    if (
        "order_created" in request.META.get("HTTP_X_EVENT_NAME", "")
        and variant_id in settings.LEMONSQUEEZY_PRODUCTS_VARIANTS
    ):
        club = None
        try:
            order_id = str(data["data"]["attributes"]["first_order_item"]["order_id"])
        except KeyError:
            # Could not find order_id info
            raise BadRequest("Missing order id")
        try:
            slug = str(data["meta"]["custom_data"]["club"])
        except KeyError:
            pass
        else:
            club = Club.objects.filter(slug__iexact=slug).first()
        if not club:
            raise BadRequest("Missing attribute")

        club.upgraded = True
        club.upgraded_date = now()
        club.order_id = f"{LEMONSQUEEZY_PREFIX}{order_id}"
        club.save()
        return HttpResponse(f"Upgraded {club}")

    # Club Downgrade
    if (
        "subscription_expired" in request.META.get("HTTP_X_EVENT_NAME", "")
        and variant_id in settings.LEMONSQUEEZY_PRODUCTS_VARIANTS
    ):
        club = None
        try:
            order_id = str(data["data"]["attributes"]["order_id"])
        except KeyError:
            # Could not find order_id info
            raise BadRequest("Missing order id")
        club = Club.objects.filter(order_id=f"{LEMONSQUEEZY_PREFIX}{order_id}").first()
        if club:
            club.upgraded = False
            club.upgraded_date = None
            club.order_id = ""
            club.save()
            return HttpResponse(f"Downgraded {club}")

    # Club Pause
    if (
        "subscription_paused" in request.META.get("HTTP_X_EVENT_NAME", "")
        and variant_id in settings.LEMONSQUEEZY_PRODUCTS_VARIANTS
    ):
        club = None
        try:
            order_id = str(data["data"]["attributes"]["order_id"])
        except KeyError:
            # Could not find order_id info
            raise BadRequest("Missing order id")
        club = Club.objects.filter(order_id=f"{LEMONSQUEEZY_PREFIX}{order_id}").first()
        if club and data["data"]["attributes"]["pause"]["mode"] == "void":
            club.subscription_paused_at = now()
            club.save()
        return HttpResponse(f"Paused {club}")

    # Club UnPause
    if (
        "subscription_unpaused" in request.META.get("HTTP_X_EVENT_NAME", "")
        and variant_id in settings.LEMONSQUEEZY_PRODUCTS_VARIANTS
    ):
        club = None
        try:
            order_id = str(data["data"]["attributes"]["order_id"])
        except KeyError:
            # Could not find order_id info
            raise BadRequest("Missing order id")
        club = Club.objects.filter(order_id=f"{LEMONSQUEEZY_PREFIX}{order_id}").first()
        if club:
            club.subscription_paused_at = None
            club.save()
            return HttpResponse(f"Unpaused {club}")

    return HttpResponse("Valid webhook call with no action taken")

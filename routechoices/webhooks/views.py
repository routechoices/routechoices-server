import hashlib
import hmac
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from routechoices.core.models import Club


@csrf_exempt
def lemonsqueezy_webhook(request):
    digest = hmac.new(
        settings.LEMONSQUEEZY_SIGNATURE.encode("utf-8"),
        msg=request.body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if request.META.get("HTTP_X_SIGNATURE") != digest:
        raise ValidationError("Invalid signature")

    data = json.loads(request.body, strict=False)

    # Club Upgrade
    if "order_created" in request.META.get("HTTP_X_EVENT_NAME", ""):
        club = None
        try:
            slug = str(data["meta"]["custom_data"]["club"])
            club = get_object_or_404(Club, slug=slug)
        except KeyError:
            # Could not find club info
            str(data["data"]["attributes"]["user_email"])

        if club:
            club.upgraded = True
            club.upgraded_date = now()
            club.order_id = data["data"]["id"]
            club.save()
            return HttpResponse(f"Upgraded {club}")

    # Club Downgrade
    elif "subscription_expired" in request.META.get("HTTP_X_EVENT_NAME", ""):
        club = None
        try:
            club = get_object_or_404(
                Club, order_id=data["data"]["attributes"]["order_id"]
            )
            if club:
                club.upgraded = False
                club.upgraded_date = None
                club.order_id = None
                club.save()
                return HttpResponse(f"Downgraded {club}")
        except KeyError:
            # Could not find order_id info
            pass

    return HttpResponse("Valid webhook call with no action taken")

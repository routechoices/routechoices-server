import hashlib
import hmac
import json

from django.conf import settings
from django.core.exceptions import BadRequest
from django.http import HttpResponse, HttpResponseBadRequest
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
        return HttpResponseBadRequest("Invalid signature")

    data = json.loads(request.body, strict=False)

    # Club Upgrade
    if "order_created" in request.META.get("HTTP_X_EVENT_NAME", ""):
        club = None
        try:
            slug = str(data["meta"]["custom_data"]["club"])
        except KeyError:
            pass
        else:
            club = Club.objects.filter(slug=slug).first()
        if not club:
            raise BadRequest("Missing attribute")

        club.upgraded = True
        club.upgraded_date = now()
        club.order_id = data["data"]["id"]
        club.save()
        return HttpResponse(f"Upgraded {club}")

    # Club Downgrade
    if "subscription_expired" in request.META.get("HTTP_X_EVENT_NAME", ""):
        club = None
        try:
            order_id = data["data"]["attributes"]["order_id"]
        except KeyError:
            # Could not find order_id info
            raise BadRequest("Missing order id")
        club = Club.objects.filter(order_id=order_id).first()
        club.upgraded = False
        club.upgraded_date = None
        club.order_id = ""
        club.save()
        return HttpResponse(f"Downgraded {club}")
    return HttpResponse("Valid webhook call with no action taken")

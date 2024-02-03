import hashlib
import hmac
import json

from django.conf import settings
from django.core.exceptions import BadRequest
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from routechoices.core.models import Club, IndividualDonator


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
        individual = None
        try:
            slug = str(data["meta"]["custom_data"]["club"])
        except KeyError:
            pass
        else:
            club = Club.objects.filter(slug=slug).first()
        if not club:
            try:
                name = data["data"]["attributes"]["user_name"]
                email = data["data"]["attributes"]["user_email"]
            except KeyError:
                # Could not find club info
                raise BadRequest("Missing attribute")
            else:
                individual, created = IndividualDonator.objects.get_or_create(
                    email=email
                )
                individual.name = name

        obj = club or individual
        if obj:
            obj.upgraded = True
            obj.upgraded_date = now()
            obj.order_id = data["data"]["id"]
            obj.save()
            return HttpResponse(f"Upgraded {obj}")
        raise Http404()

    # Club Downgrade
    elif "subscription_expired" in request.META.get("HTTP_X_EVENT_NAME", ""):
        club = None
        individual = None
        try:
            order_id = data["data"]["attributes"]["order_id"]
        except KeyError:
            # Could not find order_id info
            raise BadRequest("Missing order id")

        club = Club.objects.filter(order_id=order_id).first()
        individual = IndividualDonator.objects.filter(order_id=order_id).first()
        if club:
            club.upgraded = False
            club.upgraded_date = None
            club.order_id = ""
            club.save()
            return HttpResponse(f"Downgraded {club}")
        if individual:
            individual.delete()
            return HttpResponse("Downgraded user")
        raise Http404()
    return HttpResponse("Valid webhook call with no action taken")

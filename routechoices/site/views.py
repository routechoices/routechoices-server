from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import BadRequest
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from routechoices.core.models import PRIVACY_PUBLIC, Event
from routechoices.lib.patreon_api import PatreonAPI
from routechoices.site.forms import ContactForm


def home_view(request):
    return render(
        request,
        "site/home.html",
    )


def event_shortcut(request, event_id):
    event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)
    return redirect(event.get_absolute_url())


def tracker_view(request):
    return render(
        request,
        "site/tracker.html",
    )


def events_view(request):
    event_list = (
        Event.objects.filter(privacy=PRIVACY_PUBLIC)
        .select_related("club")
        .prefetch_related("map_assignations")
    )
    live_events = event_list.filter(start_date__lte=now(), end_date__gte=now())
    years = list(
        event_list.annotate(year=ExtractYear("start_date"))
        .values_list("year", flat=True)
        .order_by("-year")
        .distinct()
    )
    months = None
    selected_year = request.GET.get("year")
    selected_month = request.GET.get("month")
    if selected_year:
        try:
            selected_year = int(selected_year)
        except Exception:
            raise BadRequest("Invalid year")
        if selected_year not in years:
            raise Http404()
    if selected_year:
        event_list = event_list.filter(start_date__year=selected_year)
        months = list(
            event_list.annotate(month=ExtractMonth("start_date"))
            .values_list("month", flat=True)
            .order_by("-month")
            .distinct()
        )
        if selected_month:
            try:
                selected_month = int(selected_month)
            except Exception:
                raise BadRequest("Invalid month")
            if selected_month not in months:
                raise Http404()
        if selected_month:
            event_list = event_list.filter(start_date__month=selected_month)
    paginator = Paginator(event_list, 25)
    page = request.GET.get("page")
    events = paginator.get_page(page)
    return render(
        request,
        "site/event_list.html",
        {
            "events": events,
            "live_events": live_events,
            "years": years,
            "months": months,
            "year": selected_year,
            "month": selected_month,
            "month_names": [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
        },
    )


def backers(request):
    access_token = settings.PATREON_CREATOR_ID
    api_client = PatreonAPI(access_token)

    # Get the campaign ID
    response = api_client.fetch_campaign_and_patrons()
    main_campaign = response["data"][0]
    creator_id = main_campaign["relationships"]["creator"]["data"]["id"]
    included = response.get("included")
    pledges = [
        obj
        for obj in included
        if obj["type"] == "pledge"
        and obj["relationships"]["creator"]["data"]["id"] == creator_id
    ]
    patron_ids = [pledge["relationships"]["patron"]["data"]["id"] for pledge in pledges]
    patrons = [
        obj for obj in included if obj["type"] == "user" and obj["id"] in patron_ids
    ]
    patron_attributes_map = {
        patron["id"]: patron["attributes"]
        for patron in patrons
        if "full_name" in patron["attributes"]
    }
    patronage_map = {}
    for pledge in pledges:
        if pledge["relationships"]["patron"]["data"]["id"] in patron_attributes_map:
            patron_attributes = patron_attributes_map[
                pledge["relationships"]["patron"]["data"]["id"]
            ]
            if (
                "full_name" in patron_attributes
                and "amount_cents" in pledge["attributes"]
            ):
                relevant_info = {"amount_cents": pledge["attributes"]["amount_cents"]}
                relevant_info["full_name"] = patron_attributes["full_name"]
                patronage_map[patron_attributes["full_name"]] = relevant_info
    return render(
        request,
        "site/backers.html",
        {
            "backers": [
                b.get("full_name") for b in patronage_map.values() if b.get("full_name")
            ]
        },
    )


def contact(request):
    if request.method == "POST" and request.user.is_authenticated:
        form = ContactForm(request.POST)
        if form.is_valid():
            from_email = EmailAddress.objects.get_primary(request.user)
            subject = f'Routechoices.com contact form - {form.cleaned_data["subject"]} [{from_email}]'
            message = form.cleaned_data["message"]
            msg = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.EMAIL_CUSTOMER_SERVICE],
            )
            msg.content_subtype = "html"
            msg.send()
            messages.success(request, "Message sent succesfully")
            return redirect("site:contact_view")
    else:
        form = ContactForm()
    return render(request, "site/contact.html", {"form": form})

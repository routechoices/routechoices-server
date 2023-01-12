from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import BadRequest
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django_hosts.resolvers import reverse

from routechoices.core.models import PRIVACY_PUBLIC, Event
from routechoices.site.forms import ContactForm


def event_shortcut(request, event_id):
    event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)
    return redirect(event.get_absolute_url())


def events_view(request):
    event_list = Event.objects.filter(privacy=PRIVACY_PUBLIC).select_related(
        "club", "event_set"
    )
    live_events = event_list.filter(start_date__lte=now(), end_date__gte=now())
    event_list = event_list.filter(end_date__lt=now())
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
                if selected_month < 1 or selected_month > 12:
                    raise ValueError()
            except Exception:
                raise BadRequest("Invalid month")
        if selected_month:
            event_list = event_list.filter(start_date__month=selected_month)

    events_wo_set = event_list.filter(event_set__isnull=True)
    events_w_set = (
        event_list.filter(event_set__isnull=False)
        .order_by("event_set_id")
        .distinct("event_set_id")
    )

    all_events = events_wo_set.union(events_w_set).order_by("-start_date", "name")

    paginator = Paginator(all_events, 25)
    page = request.GET.get("page")
    events_page = paginator.get_page(page)

    events_set_ids = [e.event_set_id for e in events_page if e.event_set_id]
    events_by_set = {}
    if events_set_ids:
        all_events_w_set = list(
            Event.objects.select_related("club")
            .filter(event_set_id__in=events_set_ids)
            .order_by("start_date", "name")
        )
        for e in all_events_w_set:
            if e.event_set_id in events_by_set.keys():
                events_by_set[e.event_set_id].append(e)
            else:
                events_by_set[e.event_set_id] = [e]

    events = []
    for event in events_page:
        event_set = event.event_set
        if event_set is None:
            events.append(
                {
                    "name": event.name,
                    "events": [
                        event,
                    ],
                    "fake": True,
                }
            )
        else:
            events.append(
                {
                    "name": event_set.name,
                    "events": events_by_set[event_set.id],
                    "fake": False,
                }
            )

    live_events_wo_set = live_events.filter(event_set__isnull=True)
    live_events_w_set = (
        live_events.select_related("event_set")
        .filter(event_set__isnull=False)
        .order_by("event_set_id")
        .distinct("event_set_id")
    )

    all_live_events = live_events_wo_set.union(live_events_w_set).order_by(
        "-start_date", "name"
    )

    live_events_set_ids = [e.event_set_id for e in all_live_events if e.event_set_id]
    live_events_by_set = {}
    if live_events_set_ids:
        all_live_events_w_set = list(
            Event.objects.select_related("club")
            .filter(event_set_id__in=live_events_set_ids)
            .order_by("start_date", "name")
        )
        for e in all_live_events_w_set:
            if e.event_set_id in live_events_by_set.keys():
                live_events_by_set[e.event_set_id].append(e)
            else:
                live_events_by_set[e.event_set_id] = [e]

    live_events = []
    for event in all_live_events:
        event_set = event.event_set
        if event.event_set_id is None:
            live_events.append(
                {
                    "name": event.name,
                    "events": [
                        event,
                    ],
                    "fake": True,
                }
            )
        else:
            live_events.append(
                {
                    "name": event_set.name,
                    "events": live_events_by_set[event_set.id],
                    "fake": False,
                }
            )

    return render(
        request,
        "site/event_list.html",
        {
            "events": events,
            "events_page": events_page,
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


def robots_txt(request):
    sitemap_url = reverse("django.contrib.sitemaps.views.index")
    return HttpResponse(
        f"Sitemap: {request.scheme}:{sitemap_url}\n", content_type="text/plain"
    )

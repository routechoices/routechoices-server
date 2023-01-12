from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django_hosts.resolvers import reverse

from routechoices.core.models import Event
from routechoices.site.forms import ContactForm


def event_shortcut(request, event_id):
    event = get_object_or_404(Event.objects.select_related("club"), aid=event_id)
    return redirect(event.get_absolute_url())


def events_view(request):
    return render(request, "site/event_list.html", Event.extract_event_lists(request))


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

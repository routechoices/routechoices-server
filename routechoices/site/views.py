from decimal import Decimal

import arrow
import requests
from allauth.account.forms import LoginForm
from allauth.account.models import EmailAddress
from allauth.account.views import LoginView
from django.conf import settings
from django.contrib import auth, messages
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django_hosts.resolvers import reverse

from routechoices.core.models import Club, Event, IndividualDonator
from routechoices.lib.streaming_response import StreamingHttpRangeResponse
from routechoices.site.forms import ContactForm


def home_page(request):
    club_partners = Club.objects.filter(upgraded=True).order_by("name")
    indi_partners = IndividualDonator.objects.filter(upgraded=True).order_by("name")
    return render(
        request,
        "site/home.html",
        {"partner_clubs": club_partners, "individual_partners": indi_partners},
    )


def site_favicon(request, icon_name, **kwargs):
    icon_info = {
        "favicon.ico": {"size": 32, "format": "ICO", "mime": "image/x-icon"},
        "apple-touch-icon.png": {"size": 180, "format": "PNG", "mime": "image/png"},
        "icon-192.png": {"size": 192, "format": "PNG", "mime": "image/png"},
        "icon-512.png": {"size": 512, "format": "PNG", "mime": "image/png"},
    }.get(icon_name)
    with open(f"{settings.BASE_DIR}/static_assets/{icon_name}", "rb") as fp:
        data = fp.read()
    return StreamingHttpRangeResponse(request, data, content_type=icon_info["mime"])


def pricing_page(request):
    if request.method == "POST":
        price = request.POST.get("price-per-month", "4.99")
        price = max(Decimal(4.99), Decimal(price))
        yearly_payment = request.POST.get("per-year", False) == "on"
        final_price = price * Decimal(100)
        if yearly_payment:
            final_price *= 12
        body = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "custom_price": int(final_price),
                    "product_options": {
                        "enabled_variants": [78515 if yearly_payment else 78535],
                    },
                    "checkout_options": {
                        "embed": True,
                        "desc": False,
                    },
                    "preview": False,
                    "expires_at": arrow.utcnow().shift(hours=1).isoformat(),
                },
                "relationships": {
                    "store": {"data": {"type": "stores", "id": "19955"}},
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": "78515" if yearly_payment else "78535",
                        }
                    },
                },
            }
        }
        if club_slug := request.POST.get("club"):
            body["data"]["attributes"]["checkout_data"] = {
                "custom": {"club": club_slug}
            }
        r = requests.post(
            "https://api.lemonsqueezy.com/v1/checkouts",
            headers={
                "Accept": "application/vnd.api+json",
                "Authorization": f"Bearer {settings.LEMONSQUEEZY_API_KEY}",
                "Content-Type": "application/vnd.api+json",
            },
            json=body,
        )
        if r.status_code // 100 == 2:
            data = r.json()
            return redirect(data["data"]["attributes"]["url"])
        messages.error(request, "Something went wrong!")
    partners = Club.objects.filter(upgraded=True).order_by("name")
    indi_partners = IndividualDonator.objects.filter(upgraded=True).order_by("name")
    return render(
        request,
        "site/pricing.html",
        {"partner_clubs": partners, "individual_partners": indi_partners},
    )


def events_view(request):
    return render(request, "site/event_list.html", Event.extract_event_lists(request))


def contact(request):
    if request.method == "POST" and request.user.is_authenticated:
        form = ContactForm(request.POST)
        if form.is_valid():
            from_email = EmailAddress.objects.get_primary(request.user)
            subject = (
                "Routechoices.com contact form - "
                f'{form.cleaned_data["subject"]} [{from_email}]'
            )
            message = form.cleaned_data["message"]
            msg = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.EMAIL_CUSTOMER_SERVICE],
                reply_to=[from_email],
            )
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


class CustomLoginForm(LoginForm):
    def get_user(self):
        return self.user


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = "kagi/login.html"

    @property
    def is_admin(self):
        return self.template_name == "admin/login.html"

    def requires_two_factor(self, user):
        return user.webauthn_keys.exists() or user.totp_devices.exists()

    def form_valid(self, form):
        user = form.get_user()
        if not self.requires_two_factor(user):
            # no keys registered, use single-factor auth
            return super().form_valid(form)

        self.request.session["kagi_pre_verify_user_pk"] = user.pk
        self.request.session["kagi_pre_verify_user_backend"] = user.backend

        verify_url = reverse("kagi:verify-second-factor")
        redirect_to = self.request.POST.get(
            auth.REDIRECT_FIELD_NAME,
            self.request.GET.get(auth.REDIRECT_FIELD_NAME, ""),
        )
        params = {}
        if url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts=[self.request.get_host()],
            require_https=True,
        ):
            params[auth.REDIRECT_FIELD_NAME] = redirect_to
        if self.is_admin:
            params["admin"] = 1
        if params:
            verify_url += "?" + urlencode(params)

        return HttpResponseRedirect(verify_url)

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        kwargs[auth.REDIRECT_FIELD_NAME] = self.request.GET.get(
            auth.REDIRECT_FIELD_NAME, ""
        )
        kwargs.update(self.kwargs.get("extra_context", {}))
        return kwargs

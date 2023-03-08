from allauth.account.forms import LoginForm
from allauth.account.models import EmailAddress
from allauth.account.views import LoginView
from django.conf import settings
from django.contrib import auth, messages
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
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
        else:
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

import logging
import time
from importlib import import_module
from re import compile

import arrow
from corsheaders.middleware import CorsMiddleware as OrigCorsMiddleware
from django.conf import settings
from django.contrib.gis.geoip2 import GeoIP2, GeoIP2Exception
from django.core.exceptions import DisallowedHost
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.middleware.csrf import CsrfViewMiddleware as OrigCsrfViewMiddleware
from django.shortcuts import redirect, render
from django.urls import get_urlconf, set_urlconf
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import cached_property
from django.utils.http import http_date
from django_hosts.middleware import HostsBaseMiddleware
from geoip2.errors import GeoIP2Error

from routechoices.core.models import Club

XFF_EXEMPT_URLS = []
if hasattr(settings, "XFF_EXEMPT_URLS"):
    XFF_EXEMPT_URLS = [compile(expr) for expr in settings.XFF_EXEMPT_URLS]

logger = logging.getLogger(__name__)


class XForwardedForMiddleware:
    """
    Fix HTTP_REMOTE_ADDR header to show client IP in a proxied environment.
    WARNING: If you are going to trust the address, you need to know how
    many proxies you have in chain. Nothing stops a malicious client from
    sending one and your reverse proxies adding one.
    You can set the exact number of reverse proxies by adding the
    XFF_TRUSTED_PROXY_DEPTH setting. Without it, the header will remain
    insecure even with this middleware. Setting XFF_STRICT = True will
    cause a bad request to be sent on spoofed or wrongly routed requests.
    XFF_ALWAYS_PROXY will drop all requests with too little depth.
    XFF_NO_SPOOFING will drop connections with too many headers.
    This middleware will automatically clean the X-Forwarded-For header
    unless XFF_CLEAN = False is set.
    XFF_LOOSE_UNSAFE = True will simply shut up and set the last in the
    stack.
    XFF_EXEMPT_URLS can be an iterable (eg. list) that defines URLs as
    regexps that will not be checked. XFF_EXEMPT_STEALTH = True will
    return a 404 when all proxies are present. This is nice for a
    healtcheck URL that is not for the public eye.
    XFF_HEADER_REQUIRED = True will return a bad request when the header
    is not set. By default it takes the same value as XFF_ALWAYS_PROXY.
    """

    def __init__(self, get_response=None):
        self.get_response = get_response

        self.depth = getattr(settings, "XFF_TRUSTED_PROXY_DEPTH", 0)
        self.stealth = getattr(settings, "XFF_EXEMPT_STEALTH", False)
        self.loose = getattr(settings, "XFF_LOOSE_UNSAFE", False)
        self.strict = getattr(settings, "XFF_STRICT", False)
        self.always_proxy = getattr(settings, "XFF_ALWAYS_PROXY", False)
        self.no_spoofing = getattr(settings, "XFF_NO_SPOOFING", False)
        self.header_required = getattr(
            settings, "XFF_HEADER_REQUIRED", (self.always_proxy or self.strict)
        )
        self.clean = getattr(settings, "XFF_CLEAN", True)

    def __call__(self, request):
        response = self.process_request(request)
        if not response:
            response = self.get_response(request)
        return response

    def process_request(self, request):
        """
        The beef.
        """
        path = request.path_info.lstrip("/")
        depth = self.depth
        exempt = any(m.match(path) for m in XFF_EXEMPT_URLS)
        if "HTTP_X_FORWARDED_FOR" in request.META:
            header = request.META["HTTP_X_FORWARDED_FOR"]
            levels = [x.strip() for x in header.split(",")]

            if len(levels) >= depth and exempt and self.stealth:
                return HttpResponseNotFound()

            if self.loose or exempt:
                request.META["REMOTE_ADDR"] = levels[0]
                return None

            if len(levels) != depth and self.strict:
                logger.warning(
                    (
                        "Incorrect proxy depth in incoming request.\n"
                        + "Expected {} and got {} remote addresses in "
                        + "X-Forwarded-For header."
                    ).format(depth, len(levels))
                )
                return HttpResponseBadRequest()

            if len(levels) < depth or depth == 0:
                logger.warning(
                    "Not running behind as many reverse proxies as expected."
                    + "\nThe right value for XFF_TRUSTED_PROXY_DEPTH for this "
                    + f"request is {len(levels)} and {depth} is configured."
                )
                if self.always_proxy:
                    return HttpResponseBadRequest()

                depth = len(levels)
            elif len(levels) > depth:
                logger.info(
                    (
                        "X-Forwarded-For spoof attempt with {} addresses when "
                        + "{} expected. Full header: {}"
                    ).format(len(levels), depth, header)
                )
                if self.no_spoofing:
                    return HttpResponseBadRequest()

            request.META["REMOTE_ADDR"] = levels[-1 * depth]

            if self.clean:
                cleaned = ",".join(levels[-1 * depth :])
                request.META["HTTP_X_FORWARDED_FOR"] = cleaned

        elif self.header_required and not (exempt or self.loose):
            logger.error("No X-Forwarded-For header set, not behind a reverse proxy.")
            return HttpResponseBadRequest()

        return None


class HostsRequestMiddleware(HostsBaseMiddleware):
    def process_request(self, request):
        # Find best match, falling back to settings.DEFAULT_HOST
        try:
            host, kwargs = self.get_host(request.get_host())
        except DisallowedHost:
            return HttpResponse(status=444)
        # Hack for custom domains
        default_domain = settings.PARENT_HOST
        default_subdomain_suffix = f".{default_domain}"
        raw_host = request.get_host()
        if raw_host[-1] == ".":
            raw_host = raw_host[:-1]
        if raw_host == default_domain:
            return redirect(f"//www.{settings.PARENT_HOST}{request.get_full_path()}")
        request.use_cname = False
        club = None
        if raw_host.endswith(default_subdomain_suffix):
            slug = raw_host[: -(len(default_subdomain_suffix))].lower()
            if slug not in ("api", "map", "tiles", "wms", "www"):
                club = Club.objects.filter(
                    Q(slug__iexact=slug)
                    | Q(
                        slug_changed_from__iexact=slug,
                        slug_changed_at__gt=arrow.now().shift(hours=-72).datetime,
                    )
                ).first()
                if not club:
                    request.club_slug = True
                    if request.path != "/":
                        return render(request, "404.html", status=404)
                    return render(request, "club/404.html", status=404)
        else:
            club = Club.objects.filter(domain__iexact=raw_host).first()
            if not club:
                return render(request, "404.html", status=404)
            original_host = f"{club.slug.lower()}{default_subdomain_suffix}"
            host, kwargs = self.get_host(original_host)
            request.use_cname = True
        if club:
            request.club_slug = club.slug
        # This is the main part of this middleware
        request.urlconf = host.urlconf
        request.host = host
        # But we have to temporarily override the URLconf
        # already to allow correctly reversing host URLs in
        # the host callback, if needed.
        current_urlconf = get_urlconf()
        try:
            set_urlconf(host.urlconf)
            return host.callback(request, **kwargs)
        finally:
            # Reset URLconf for this thread on the way out for complete
            # isolation of request.urlconf
            set_urlconf(current_urlconf)


class HostsResponseMiddleware(HostsBaseMiddleware):
    def process_response(self, request, response):
        # Django resets the base urlconf when it starts to process
        # the response, so we need to set this again, in case
        # any of our middleware makes use of host, etc URLs.

        # Find best match, falling back to settings.DEFAULT_HOST
        host, kwargs = self.get_host(request.get_host())
        # Hack for custom domains
        default_domain = settings.PARENT_HOST
        default_subdomain_suffix = f".{default_domain}"
        raw_host = request.get_host()
        if raw_host[-1] == ".":
            raw_host = raw_host[:-1]
        request.use_cname = False
        if not raw_host.endswith(default_subdomain_suffix):
            club = Club.objects.filter(domain__iexact=raw_host).first()
            if not club:
                return HttpResponse(status=444)
            original_host = f"{club.slug.lower()}{default_subdomain_suffix}"
            host, kwargs = self.get_host(original_host)
            request.use_cname = True
        # This is the main part of this middleware
        request.urlconf = host.urlconf
        request.host = host

        set_urlconf(host.urlconf)
        return response


class CorsMiddleware(OrigCorsMiddleware):
    def is_enabled(self, request):
        return request.host.name == "api" and super().is_enabled(request)


class CsrfViewMiddleware(OrigCsrfViewMiddleware):
    @cached_property
    def allowed_origins_exact(self):
        allowed = super().allowed_origins_exact
        domains = (
            Club.objects.exclude(domain__isnull=True)
            .exclude(domain="")
            .values_list("domain", flat=True)
        )
        for domain in domains:
            allowed.add(f"http://{domain}")
            allowed.add(f"https://{domain}")
        return allowed


class FilterCountriesIPsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if not response:
            response = self.get_response(request)
        return response

    def process_request(self, request):
        try:
            g = GeoIP2()
            country = g.country_code(request.META["REMOTE_ADDR"])
        except (GeoIP2Exception, GeoIP2Error):
            country = None
        if country in getattr(settings, "BANNED_COUNTRIES", []):
            return HttpResponse("Sorry, we block IP addresses from your country.")
        return None


class SessionMiddleware(MiddlewareMixin):
    """
    Middleware that provides ip and user_agent to the session store.
    """

    def process_request(self, request):
        engine = import_module(settings.SESSION_ENGINE)
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME, None)
        request.session = engine.SessionStore(
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            session_key=session_key,
        )

    def process_response(self, request, response):
        """
        If request.session was modified, or if the configuration is to save the
        session every time, save the changes and set a session cookie.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
        except AttributeError:
            pass
        else:
            if accessed:
                patch_vary_headers(response, ("Cookie",))
            if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)
                # Save the session data and refresh the client cookie.
                # Skip session save for 500 responses, refs #3881.
                if response.status_code != 500:
                    request.session.save()
                    host = request.get_host().partition(":")[0]
                    domain = settings.SESSION_COOKIE_DOMAIN
                    if Club.objects.filter(domain=host).exists():
                        domain = host
                    response.set_cookie(
                        settings.SESSION_COOKIE_NAME,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=domain,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
        return response

import math
import os
import tempfile
import zipfile

import gpxpy
import requests
from allauth.account import app_settings as allauth_settings
from allauth.account.adapter import get_adapter
from allauth.account.forms import default_token_generator
from allauth.account.signals import password_changed, password_reset
from allauth.account.utils import user_username
from allauth.utils import build_absolute_uri
from defusedxml import minidom
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.core.files import File
from django.core.paginator import Paginator
from django.db.models import Case, Q, Value, When
from django.dispatch import receiver
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import now
from PIL import Image

from invitations.forms import InviteForm
from routechoices.api.views import serve_from_s3
from routechoices.core.models import (
    IS_DB_SQLITE,
    Club,
    Competitor,
    Device,
    DeviceClubOwnership,
    Event,
    Map,
    Notice,
)
from routechoices.dashboard.forms import (
    ClubDomainForm,
    ClubForm,
    CompetitorFormSet,
    DeviceForm,
    EventForm,
    ExtraMapFormSet,
    MapForm,
    NoticeForm,
    UploadGPXForm,
    UploadKmzForm,
    UploadMapGPXForm,
)
from routechoices.lib.helpers import short_random_key
from routechoices.lib.kmz import extract_ground_overlay_info

DEFAULT_PAGE_SIZE = 25


def requires_club_in_session(function):
    def wrap(request, *args, **kwargs):
        if "dashboard_club" not in request.session:
            return redirect("dashboard:club_select_view")
        session_club = request.session["dashboard_club"]
        if not request.user.is_superuser:
            club = Club.objects.filter(admins=request.user, aid=session_club).first()
        else:
            club = Club.objects.filter(aid=session_club).first()
        if not club:
            return redirect("dashboard:club_select_view")
        request.club = club
        return function(request, *args, **kwargs)

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


@login_required
@requires_club_in_session
def home_view(request):
    return redirect("dashboard:club_view")


@login_required
@requires_club_in_session
def club_invite_add_view(request):
    club = request.club
    if request.method == "POST":
        form = InviteForm(request.POST, club=club)
        if form.is_valid():
            email = form.cleaned_data["email"]
            invite = form.save(email, club)
            invite.inviter = request.user
            invite.save()
            invite.send_invitation(request)
            messages.success(request, "Invite sent successfully")
            return redirect("dashboard:club_view")
    else:
        form = InviteForm()
    return render(request, "dashboard/invite_add.html", {"club": club, "form": form})


@login_required
def club_select_view(request):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)

    paginator = Paginator(club_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get("page")
    clubs = paginator.get_page(page)

    return render(request, "dashboard/club_list.html", {"clubs": clubs})


@login_required
def calibration_view(request):
    return render(
        request,
        "dashboard/calibration.html",
    )


@login_required
def pdf_to_jpg(request):
    return render(
        request,
        "dashboard/pdf_to_jpg.html",
    )


@login_required
def check_calibration_view(request):
    return render(
        request,
        "dashboard/check_calibration.html",
    )


@login_required
def account_edit_view(request):
    return render(
        request,
        "dashboard/account_edit.html",
    )


@login_required
def account_delete_view(request):
    token_generator = default_token_generator
    token_generator.key_salt = "AccountDeletionTokenGenerator"
    user = request.user
    if request.method == "POST":
        conf_key = request.POST.get("confirmation_key")
        if conf_key:
            if token_generator.check_token(user, conf_key):
                request.user.delete()
                request.session.user_id = None
                messages.success(request, "Account deleted.")
                return redirect("site:home_view")
            return render(
                request,
                "dashboard/account_delete_confirm.html",
                {"confirmation": True, "confirmation_valid": False},
            )
        else:
            temp_key = token_generator.make_token(user)
            current_site = get_current_site(request)
            url = build_absolute_uri(request, reverse("dashboard:account_delete_view"))
            context = {
                "current_site": current_site,
                "user": user,
                "account_deletion_url": f"{url}?confirmation_key={temp_key}",
                "request": request,
            }
            if (
                allauth_settings.AUTHENTICATION_METHOD
                != allauth_settings.AuthenticationMethod.EMAIL
            ):
                context["username"] = user_username(user)
            get_adapter(request).send_mail(
                "account/email/account_delete", request.user.email, context
            )
            return render(
                request,
                "dashboard/account_delete_confirm.html",
                {"confirmation": False, "sent": True},
            )
    conf_key = request.GET.get("confirmation_key")
    if conf_key:
        if token_generator.check_token(user, conf_key):
            return render(
                request,
                "dashboard/account_delete_confirm.html",
                {
                    "confirmation": True,
                    "confirmation_valid": True,
                    "confirmation_key": conf_key,
                },
            )
        return render(
            request,
            "dashboard/account_delete_confirm.html",
            {"confirmation": True, "confirmation_valid": False},
        )
    return render(
        request,
        "dashboard/account_delete_confirm.html",
        {"confirmation": False, "sent": False},
    )


@login_required
@requires_club_in_session
def device_list_view(request):
    club = request.club

    ordering_blank_last = Case(When(nickname="", then=Value(1)), default=Value(0))

    device_owned_list = (
        DeviceClubOwnership.objects.filter(club=club)
        .select_related("club", "device")
        .order_by(ordering_blank_last, "nickname", "device__aid")
    )
    paginator = Paginator(device_owned_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get("page")
    devices = paginator.get_page(page)
    devices_listed = devices.object_list.values_list("device__id")
    competitors = (
        Competitor.objects.select_related("event")
        .filter(device_id__in=devices_listed, start_time__lt=now())
        .order_by("device_id", "-start_time")
    )

    if not IS_DB_SQLITE:
        competitors = competitors.distinct("device_id")
    else:
        unique_devid = set()
        unique_competitors = []
        for c in competitors:
            if c.device_id not in unique_devid:
                unique_devid.add(c.device_id)
                unique_competitors.append(c)
        competitors = unique_competitors

    last_usage = {}
    for competitor in competitors:
        last_usage[competitor.device_id] = f"{competitor.event} ({competitor})"
    return render(
        request,
        "dashboard/device_list.html",
        {"club": club, "devices": devices, "last_usage": last_usage},
    )


@login_required
@requires_club_in_session
def device_add_view(request):
    club = request.club

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = DeviceForm(request.POST)
        # check whether it's valid:
        form.fields["device"].queryset = Device.objects.exclude(owners=club)
        if form.is_valid():
            device = form.cleaned_data["device"]
            ownership = DeviceClubOwnership()
            ownership.club = club
            ownership.device = device
            ownership.nickname = form.cleaned_data["nickname"]
            ownership.save()
            messages.success(request, "Device added successfully")
            return redirect("dashboard:device_list_view")
        else:
            form.fields["device"].queryset = Device.objects.none()
    else:
        form = DeviceForm()
        form.fields["device"].queryset = Device.objects.none()
    return render(
        request,
        "dashboard/device_add.html",
        {
            "club": club,
            "form": form,
        },
    )


@login_required
def club_create_view(request):
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = ClubForm(request.POST, request.FILES)
        # check whether it's valid:
        if form.is_valid():
            club = form.save(commit=False)
            club.creator = request.user
            club.save()
            form.save_m2m()
            messages.success(request, "Club created successfully")
            return redirect("dashboard:club_select_view")
    else:
        form = ClubForm(initial={"admins": request.user})
    form.fields["admins"].queryset = User.objects.filter(id=request.user.id)
    return render(
        request,
        "dashboard/club_create.html",
        {
            "form": form,
        },
    )


@login_required
def club_set_view(request, club_id):
    if request.user.is_superuser:
        club = get_object_or_404(
            Club,
            aid=club_id,
        )
    else:
        club = get_object_or_404(Club, aid=club_id, admins=request.user)
    request.session["dashboard_club"] = club.aid
    return redirect("dashboard:club_view")


@login_required
@requires_club_in_session
def club_view(request):
    club = request.club
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = ClubForm(request.POST, request.FILES, instance=club)
        # check whether it's valid:
        if form.is_valid():
            form.save()
            messages.success(request, "Changes saved successfully")
            return redirect("dashboard:club_view")
    else:
        form = ClubForm(instance=club)
    form.fields["admins"].queryset = User.objects.filter(id__in=club.admins.all())
    return render(
        request,
        "dashboard/club_view.html",
        {
            "club": club,
            "form": form,
        },
    )


@login_required
@requires_club_in_session
def club_custom_domain_view(request):
    club = request.club

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = ClubDomainForm(request.POST, instance=club)
        # check whether it's valid:
        if form.is_valid():
            form.save()
            messages.success(request, "Changes saved successfully")
            return redirect("dashboard:club_custom_domain_view")
    else:
        form = ClubDomainForm(instance=club)
    return render(
        request,
        "dashboard/custom_domain.html",
        {
            "club": club,
            "form": form,
        },
    )


@login_required
@requires_club_in_session
def club_delete_view(request):
    club = request.club

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        club.delete()
        messages.success(request, "Club deleted")
        return redirect("dashboard:club_select_view")
    return render(
        request,
        "dashboard/club_delete.html",
        {
            "club": club,
        },
    )


@login_required
@requires_club_in_session
def map_list_view(request):
    club = request.club

    map_list = Map.objects.filter(club=club).select_related("club")
    paginator = Paginator(map_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get("page")
    maps = paginator.get_page(page)
    return render(request, "dashboard/map_list.html", {"club": club, "maps": maps})


@login_required
@requires_club_in_session
def map_create_view(request):
    club = request.club

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = MapForm(request.POST, request.FILES)
        form.instance.club = club
        # check whether it's valid:
        if form.is_valid():
            form.save()
            messages.success(request, "Map created successfully")
            return redirect("dashboard:map_list_view")
    else:
        form = MapForm()
    return render(
        request,
        "dashboard/map_edit.html",
        {
            "club": club,
            "context": "create",
            "form": form,
        },
    )


@login_required
@requires_club_in_session
def map_edit_view(request, map_id):
    club = request.club

    raster_map = get_object_or_404(Map, aid=map_id, club=club)

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = MapForm(request.POST, request.FILES, instance=raster_map)
        form.instance.club = club
        # check whether it's valid:
        if form.is_valid():
            form.save()
            messages.success(request, "Changes saved successfully")
            return redirect("dashboard:map_list_view")
    else:
        form = MapForm(instance=raster_map)
    return render(
        request,
        "dashboard/map_edit.html",
        {
            "club": club,
            "context": "edit",
            "map": raster_map,
            "form": form,
        },
    )


@login_required
@requires_club_in_session
def map_delete_view(request, map_id):
    club = request.club

    raster_map = get_object_or_404(Map, aid=map_id, club=club)
    if request.method == "POST":
        raster_map.delete()
        messages.success(request, "Map deleted")
        return redirect("dashboard:map_list_view")
    return render(
        request,
        "dashboard/map_delete.html",
        {
            "club": club,
            "map": raster_map,
        },
    )


@login_required
@requires_club_in_session
def map_gpx_upload_view(request):
    club = request.club

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = UploadMapGPXForm(request.POST, request.FILES)
        # check whether it's valid:
        if form.is_valid():
            error = None
            try:
                gpx_file = form.cleaned_data["gpx_file"].read()
                data = minidom.parseString(gpx_file)
                gpx_file = data.toxml(encoding="utf-8")
            except Exception:
                error = "Couldn't decode file"
            if not error:
                try:
                    gpx = gpxpy.parse(gpx_file)
                except Exception:
                    error = "Couldn't parse file"
            if not error:
                has_points = False
                segments = []

                points = []
                prev_lon = None
                offset_lon = 0
                for point in gpx.waypoints:
                    lon = point.longitude + offset_lon
                    if prev_lon and abs(prev_lon - lon) > 180:
                        offset_lon += math.copysign(
                            360, (prev_lon + 180) % 360 - (lon + 180) % 360
                        )
                        lon = point.longitude + offset_lon
                    prev_lon = lon
                    points.append([round(point.latitude, 5), round(lon, 5)])
                if len(points) > 1:
                    has_points = True
                    segments.append(points)

                for route in gpx.routes:
                    points = []
                    prev_lon = None
                    offset_lon = 0
                    for point, _ in route.walk():
                        lon = point.longitude + offset_lon
                        if prev_lon and abs(prev_lon - lon) > 180:
                            offset_lon += math.copysign(
                                360, (prev_lon + 180) % 360 - (lon + 180) % 360
                            )
                            lon = point.longitude + offset_lon
                        prev_lon = lon
                        points.append([round(point.latitude, 5), round(lon, 5)])
                    if len(points) > 1:
                        has_points = True
                        segments.append(points)
                for track in gpx.tracks:
                    for segment in track.segments:
                        points = []
                        prev_lon = None
                        offset_lon = 0
                        for point in segment.points:
                            lon = point.longitude + offset_lon
                            if prev_lon and abs(prev_lon - lon) > 180:
                                offset_lon += math.copysign(
                                    360, (prev_lon + 180) % 360 - (lon + 180) % 360
                                )
                                lon = point.longitude + offset_lon
                            prev_lon = lon
                            points.append([round(point.latitude, 5), round(lon, 5)])
                        if len(points) > 1:
                            has_points = True
                            segments.append(points)
                if not has_points:
                    error = "Could not find points in this file"
                else:
                    new_map = Map.from_points(segments)
                    new_map.name = form.cleaned_data["gpx_file"].name[:-4]
                    new_map.club = club
                    new_map.save()
            if error:
                messages.error(request, error)
            else:
                messages.success(request, "The import of the map was successful")
                return redirect("dashboard:map_list_view")
    else:
        form = UploadMapGPXForm()
    return render(
        request,
        "dashboard/map_gpx_upload.html",
        {
            "club": club,
            "form": form,
        },
    )


@login_required
@requires_club_in_session
def map_kmz_upload_view(request):
    club = request.club

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = UploadKmzForm(request.POST, request.FILES)
        # check whether it's valid:
        if form.is_valid():
            new_map = None
            file = form.cleaned_data["file"]
            error = None
            if file.name.lower().endswith(".kml"):
                try:
                    kml = file.read()
                    name, image_path, corners_coords = extract_ground_overlay_info(kml)
                    if not name:
                        name = "Untitled"
                    if not image_path.startswith(
                        "http://"
                    ) and not image_path.startswith("https://"):
                        raise Exception("Fishy KML")

                    with tempfile.TemporaryFile() as dest:
                        headers = requests.utils.default_headers()
                        headers.update(
                            {
                                "User-Agent": "Python3/Requests/Routechoices.com",
                            }
                        )
                        r = requests.get(image_path, headers=headers)
                        if r.status_code != 200:
                            raise Exception("Could not reach image source")
                        dest.write(r.content)
                        dest.flush()
                        dest.seek(0)
                        new_map = Map(
                            club=club,
                            name=name,
                            corners_coordinates=corners_coords,
                        )
                        image_file = File(dest)
                        new_map.image.save("file", image_file, save=False)
                except Exception:
                    error = "An error occured while extracting the map from your file."
            elif file.name.lower().endswith(".kmz"):
                try:
                    dest = tempfile.mkdtemp("_kmz")
                    zf = zipfile.ZipFile(file)
                    zf.extractall(dest)
                    if os.path.exists(os.path.join(dest, "Doc.kml")):
                        doc_file = "Doc.kml"
                    elif os.path.exists(os.path.join(dest, "doc.kml")):
                        doc_file = "doc.kml"
                    else:
                        raise Exception("No valid doc.kml file")
                    with open(os.path.join(dest, doc_file), "r") as f:
                        kml = f.read().encode("utf8")
                    name, image_path, corners_coords = extract_ground_overlay_info(kml)
                    if not name:
                        name = "Untitled"
                    if image_path.startswith("http://") or image_path.startswith(
                        "https://"
                    ):
                        with tempfile.TemporaryFile() as dest:
                            headers = requests.utils.default_headers()
                            headers.update(
                                {
                                    "User-Agent": "Python3/Requests/Routechoices.com",
                                }
                            )
                            r = requests.get(image_path, headers=headers)
                            if r.status_code != 200:
                                raise Exception("Could not reach image source")
                            dest.write(r.content)
                            dest.flush()
                            dest.seek(0)
                            image_file = File(dest)
                            new_map = Map(
                                name=name,
                                club=club,
                                corners_coordinates=corners_coords,
                            )
                            new_map.image.save("file", image_file, save=True)
                    else:
                        image_path = os.path.abspath(os.path.join(dest, image_path))
                        if not image_path.startswith(dest):
                            raise Exception("Fishy KMZ")
                        image_file = File(open(image_path, "rb"))
                        new_map = Map(
                            name=name,
                            club=club,
                            corners_coordinates=corners_coords,
                        )
                        new_map.image.save("file", image_file, save=False)
                except Exception:
                    error = "An error occured while extracting the map from your file."
            if new_map:
                try:
                    new_map.strip_exif()
                except Image.DecompressionBombError:
                    error = "Image is too large, try to use lower resolution."
                else:
                    new_map.save()
            if error:
                messages.error(request, error)
            else:
                messages.success(request, "The import of the map was successful")
                return redirect("dashboard:map_list_view")
    else:
        form = UploadKmzForm()
    return render(
        request,
        "dashboard/map_kmz_upload.html",
        {
            "club": club,
            "form": form,
        },
    )


@login_required
@requires_club_in_session
def event_list_view(request):
    club = request.club

    event_list = Event.objects.filter(club=club).select_related("club")

    paginator = Paginator(event_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get("page")
    events = paginator.get_page(page)

    return render(
        request, "dashboard/event_list.html", {"club": club, "events": events}
    )


@login_required
@requires_club_in_session
def event_create_view(request):
    club = request.club

    map_list = Map.objects.filter(club=club).select_related("club")

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = EventForm(request.POST, request.FILES, club=club)
        form.fields["map"].queryset = map_list
        formset = CompetitorFormSet(request.POST)
        extra_map_formset = ExtraMapFormSet(request.POST)
        for mform in extra_map_formset.forms:
            mform.fields["map"].queryset = map_list
        notice_form = NoticeForm(request.POST)
        # check whether it's valid:
        if all(
            [
                form.is_valid(),
                formset.is_valid(),
                notice_form.is_valid(),
                extra_map_formset.is_valid(),
            ]
        ):
            event = form.save()
            formset.instance = event
            formset.save()
            extra_map_formset.instance = event
            extra_map_formset.save()
            notice = notice_form.save(commit=False)
            notice.event = event
            notice.save()
            messages.success(request, "Event created successfully")
            if request.POST.get("save_continue"):
                return redirect("dashboard:event_edit_view", event_id=event.aid)
            return redirect("dashboard:event_list_view")
        else:
            all_devices = set()
            for cform in formset.forms:
                if cform.cleaned_data.get("device"):
                    all_devices.add(cform.cleaned_data.get("device").id)
            dev_qs = Device.objects.filter(id__in=all_devices).prefetch_related(
                "club_ownerships"
            )
            dev_qs |= club.devices.all()
            cd = [
                {
                    "full": (d.id, d.get_display_str(club)),
                    "key": (d.get_nickname(club), d.get_display_str(club)),
                }
                for d in dev_qs
            ]
            cd.sort(key=lambda x: (x["key"][0] == "", x["key"]))
            c = [
                ["", "---------"],
            ] + [d["full"] for d in cd]
            for cform in formset.forms:
                cform.fields["device"].queryset = dev_qs
                cform.fields["device"].choices = c
    else:
        form = EventForm(club=club)
        form.fields["map"].queryset = map_list
        formset = CompetitorFormSet()
        extra_map_formset = ExtraMapFormSet()
        for mform in extra_map_formset.forms:
            mform.fields["map"].queryset = map_list
        notice_form = NoticeForm()
        dev_qs = club.devices.all().prefetch_related("club_ownerships")
        cd = [
            {
                "full": (d.id, d.get_display_str(club)),
                "key": (d.get_nickname(club), d.get_display_str(club)),
            }
            for d in dev_qs
        ]
        cd.sort(key=lambda x: (x["key"][0] == "", x["key"]))
        c = [
            ["", "---------"],
        ] + [d["full"] for d in cd]
        for cform in formset.forms:
            cform.fields["device"].queryset = dev_qs
            cform.fields["device"].choices = c
    return render(
        request,
        "dashboard/event_edit.html",
        {
            "club": club,
            "context": "create",
            "form": form,
            "formset": formset,
            "extra_map_formset": extra_map_formset,
            "notice_form": notice_form,
        },
    )


MAX_COMPETITORS_DISPLAYED_IN_EVENT = 100


@login_required
@requires_club_in_session
def event_edit_view(request, event_id):
    club = request.club

    map_list = Map.objects.filter(club=club).select_related("club")
    event = get_object_or_404(
        Event.objects.all().prefetch_related("notice", "competitors"),
        aid=event_id,
        club=club,
    )
    use_competitor_formset = (
        event.competitors.count() < MAX_COMPETITORS_DISPLAYED_IN_EVENT
    )
    if use_competitor_formset:
        comp_devices_id = event.competitors.all().values_list("device", flat=True)
    else:
        comp_devices_id = []

    own_devices = club.devices.all()
    own_devices_id = own_devices.values_list("id", flat=True)
    all_devices = set(list(comp_devices_id) + list(own_devices_id))

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = EventForm(request.POST, request.FILES, instance=event, club=club)
        form.fields["map"].queryset = map_list
        extra_map_formset = ExtraMapFormSet(request.POST, instance=event)
        for mform in extra_map_formset.forms:
            mform.fields["map"].queryset = map_list
        formset = CompetitorFormSet(
            request.POST,
            instance=event,
        )
        args = {}
        if event.has_notice:
            args = {"instance": event.notice}
        notice_form = NoticeForm(request.POST, **args)
        # check whether it's valid:
        if all(
            [
                form.is_valid(),
                formset.is_valid(),
                notice_form.is_valid(),
                extra_map_formset.is_valid(),
            ]
        ):
            form.save()
            formset.save()
            extra_map_formset.instance = event
            extra_map_formset.save()
            prev_text = ""
            if event.has_notice:
                notice_form.instance = event.notice
                event.notice.refresh_from_db()
                prev_text = event.notice.text
            if prev_text != notice_form.cleaned_data["text"]:
                if not event.has_notice:
                    notice = Notice(event=event)
                else:
                    notice = event.notice
                notice.text = notice_form.cleaned_data["text"]
                notice.save()
            messages.success(request, "Changes saved successfully")
            if request.POST.get("save_continue"):
                return redirect("dashboard:event_edit_view", event_id=event.aid)
            return redirect("dashboard:event_list_view")
        else:
            for cform in formset.forms:
                if cform.cleaned_data.get("device"):
                    all_devices.add(cform.cleaned_data.get("device").id)
            dev_qs = Device.objects.filter(id__in=all_devices).prefetch_related(
                "club_ownerships"
            )
            cd = [
                {
                    "full": (d.id, d.get_display_str(club)),
                    "key": (d.get_nickname(club), d.get_display_str(club)),
                }
                for d in dev_qs
            ]
            cd.sort(key=lambda x: (x["key"][0] == "", x["key"]))
            c = [
                ["", "---------"],
            ] + [d["full"] for d in cd]
            for cform in formset.forms:
                cform.fields["device"].queryset = dev_qs
                cform.fields["device"].choices = c
    else:
        form = EventForm(instance=event, club=club)
        form.fields["map"].queryset = map_list
        formset_qs = Competitor.objects.none() if not use_competitor_formset else None
        formset_args = {}
        if not use_competitor_formset:
            formset_args = {"queryset": formset_qs}
        formset = CompetitorFormSet(instance=event, **formset_args)
        extra_map_formset = ExtraMapFormSet(instance=event)
        for mform in extra_map_formset.forms:
            mform.fields["map"].queryset = map_list
        args = {}
        if event.has_notice:
            args = {"instance": event.notice}
        notice_form = NoticeForm(**args)
        dev_qs = Device.objects.filter(id__in=all_devices).prefetch_related(
            "club_ownerships"
        )
        cd = [
            {
                "full": (d.id, d.get_display_str(club)),
                "key": (d.get_nickname(club), d.get_display_str(club)),
            }
            for d in dev_qs
        ]
        cd.sort(key=lambda x: (x["key"][0] == "", x["key"]))
        c = [
            ["", "---------"],
        ] + [d["full"] for d in cd]
        for cform in formset.forms:
            cform.fields["device"].queryset = dev_qs
            cform.fields["device"].choices = c

    return render(
        request,
        "dashboard/event_edit.html",
        {
            "club": club,
            "context": "edit",
            "event": event,
            "form": form,
            "formset": formset,
            "extra_map_formset": extra_map_formset,
            "notice_form": notice_form,
            "use_competitor_formset": use_competitor_formset,
        },
    )


COMPETITORS_PAGE_SIZE = 50


@login_required
@requires_club_in_session
def event_competitors_view(request, event_id):
    club = request.club

    event = get_object_or_404(
        Event.objects.all().prefetch_related("notice", "competitors"),
        aid=event_id,
        club=club,
    )
    if event.competitors.count() < MAX_COMPETITORS_DISPLAYED_IN_EVENT:
        raise Http404()
    page = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")

    qs = event.competitors.all()
    if search_query:
        qs = qs.filter(
            Q(device__aid__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(short_name__icontains=search_query)
        )

    competitor_paginator = Paginator(qs, COMPETITORS_PAGE_SIZE)
    try:
        competitors = competitor_paginator.page(page)
    except Exception:
        raise Http404()
    comps = Competitor.objects.filter(id__in=[c.id for c in competitors.object_list])
    comp_devices_id = [c.device_id for c in competitors.object_list]
    own_devices = club.devices.all()
    own_devices_id = own_devices.values_list("id", flat=True)
    all_devices = set(list(comp_devices_id) + list(own_devices_id))
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        formset = CompetitorFormSet(
            request.POST,
            instance=event,
        )
        # check whether it's valid:
        if formset.is_valid():
            formset.save()
            messages.success(request, "Changes saved successfully")
            return redirect("dashboard:event_edit_view", event_id=event.aid)
        else:
            for cform in formset.forms:
                if cform.cleaned_data.get("device"):
                    all_devices.add(cform.cleaned_data.get("device").id)
            dev_qs = Device.objects.filter(id__in=all_devices).prefetch_related(
                "club_ownerships"
            )
            c = [
                ["", "---------"],
            ] + [[d.id, d.get_display_str(club)] for d in dev_qs]
            for cform in formset.forms:
                cform.fields["device"].queryset = dev_qs
                cform.fields["device"].choices = c
    else:
        formset = CompetitorFormSet(
            instance=event,
            queryset=comps,
        )
        formset.extra = 0
        dev_qs = Device.objects.filter(id__in=all_devices).prefetch_related(
            "club_ownerships"
        )
        c = [
            ["", "---------"],
        ] + [[d.id, d.get_display_str(club)] for d in dev_qs]
        for cform in formset.forms:
            cform.fields["device"].queryset = dev_qs
            cform.fields["device"].choices = c

    return render(
        request,
        "dashboard/event_competitors.html",
        {
            "club": club,
            "event": event,
            "formset": formset,
            "competitors": competitors,
            "search_query": search_query,
        },
    )


@login_required
@requires_club_in_session
def event_delete_view(request, event_id):
    club = request.club

    event = get_object_or_404(Event, aid=event_id, club=club)
    if request.method == "POST":
        event.delete()
        messages.success(request, "Event deleted")
        return redirect("dashboard:event_list_view")
    return render(
        request,
        "dashboard/event_delete.html",
        {
            "event": event,
        },
    )


@login_required
@requires_club_in_session
def event_chat_moderation_view(request, event_id):
    club = request.club

    event = get_object_or_404(
        Event,
        aid=event_id,
        club=club,
        allow_live_chat=True,
        start_date__lte=now(),
    )
    return render(
        request,
        "dashboard/event_chat_moderation.html",
        {"event": event, "chat_server": getattr(settings, "CHAT_SERVER", None)},
    )


@login_required
def event_view_live(request, event_id):
    if request.user.is_superuser:
        event = get_object_or_404(
            Event,
            aid=event_id,
            start_date__lte=now(),
            end_date__gte=now(),
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        event = get_object_or_404(
            Event,
            aid=event_id,
            club__in=club_list,
            start_date__lte=now(),
            end_date__gte=now(),
        )
    resp_args = {
        "event": event,
        "no_delay": True,
        "gps_server": getattr(settings, "GPS_SSE_SERVER", None),
    }
    if event.allow_live_chat:
        resp_args["chat_server"] = getattr(settings, "CHAT_SERVER", None)
    return render(request, "club/event.html", resp_args)


@login_required
def dashboard_map_download(request, map_id, *args, **kwargs):
    if request.user.is_superuser:
        raster_map = get_object_or_404(
            Map,
            aid=map_id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        raster_map = get_object_or_404(Map, aid=map_id, club__in=club_list)
    file_path = raster_map.path
    mime_type = raster_map.mime_type
    return serve_from_s3(
        settings.AWS_S3_BUCKET,
        request,
        "/internal/" + file_path,
        filename=f"{raster_map.name}_{raster_map.corners_coordinates_short.replace(',', '_')}_.{mime_type[6:]}",
        mime=mime_type,
    )


@login_required
def dashboard_logo_download(request, club_id, *args, **kwargs):
    if request.user.is_superuser:
        club = get_object_or_404(Club, aid=club_id, logo__isnull=False)
    else:
        club = Club.objects.filter(
            admins=request.user, aid=club_id, logo__isnull=False
        ).first()
    if not club:
        raise Http404()
    file_path = club.logo.name
    return serve_from_s3(
        settings.AWS_S3_BUCKET,
        request,
        "/internal/" + file_path,
        filename=f"{club.name}.png",
        mime="image/png",
    )


@login_required
def event_route_upload_view(request, event_id):
    if request.user.is_superuser:
        event = get_object_or_404(
            Event,
            aid=event_id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        event = get_object_or_404(Event, aid=event_id, club__in=club_list)
    competitors = event.competitors.all().order_by("name")
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = UploadGPXForm(request.POST, request.FILES)
        form.fields["competitor"].queryset = competitors
        # check whether it's valid:
        if form.is_valid():
            error = None
            try:
                gpx_file = form.cleaned_data["gpx_file"].read()
                data = minidom.parseString(gpx_file)
                gpx_file = data.toxml(encoding="utf-8")
            except Exception:
                error = "Couldn't decode file"
            if not error:
                try:
                    gpx = gpxpy.parse(gpx_file)
                except Exception:
                    error = "Couldn't parse file"
            if not error:
                device = Device.objects.create(
                    aid=f"{short_random_key()}_GPX", is_gpx=True
                )
                start_time = None
                points = []
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            if point.time and point.latitude and point.longitude:
                                points.append(
                                    (
                                        int(point.time.timestamp()),
                                        round(point.latitude, 5),
                                        round(point.longitude, 5),
                                    )
                                )
                                if not start_time:
                                    start_time = point.time
                device.add_locations(points, push_forward=False)
                competitor = form.cleaned_data["competitor"]
                competitor.device = device
                if start_time and event.start_date <= start_time <= event.end_date:
                    competitor.start_time = start_time
                competitor.save()
            if error:
                messages.error(request, error)
            else:
                messages.success(request, "The upload of the GPX file was successful")
                return redirect("dashboard:event_edit_view", event_id=event.aid)

    else:
        form = UploadGPXForm()
        form.fields["competitor"].queryset = competitors
    return render(
        request,
        "dashboard/event_gpx_upload.html",
        {
            "event": event,
            "form": form,
        },
    )


@receiver(password_reset)
@receiver(password_changed)
def logoutOtherSessionsAfterPassChange(request, user, **kwargs):
    user.session_set.exclude(session_key=request.session.session_key).delete()

import os

import tempfile
import zipfile

import requests

import gpxpy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files import File
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404

from routechoices.api.views import serve_from_s3
from routechoices.core.models import (
    Club,
    Map,
    Event,
    Device,
    DeviceOwnership,
    Notice,
)
from routechoices.dashboard.forms import (
    ClubForm, MapForm, EventForm,
    CompetitorFormSet, UploadGPXForm,
    UploadKmzForm, DeviceForm, NoticeForm,
    ExtraMapFormSet,
)
from routechoices.lib.kmz import extract_ground_overlay_info


DEFAULT_PAGE_SIZE = 25


@login_required
def home_view(request):
    return render(
        request,
        'dashboard/home.html',
    )


@login_required
def calibration_view(request):
    return render(
        request,
        'dashboard/calibration.html',
    )


@login_required
def pdf_to_jpg(request):
    return render(
        request,
        'dashboard/pdf_to_jpg.html',
    )


@login_required
def check_calibration_view(request):
    return render(
        request,
        'dashboard/check_calibration.html',
    )


@login_required
def account_edit_view(request):
    return render(
        request,
        'dashboard/account_edit.html',
    )


@login_required
def device_list_view(request):
    device_list = Device.objects.filter(owners=request.user)

    paginator = Paginator(device_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get('page')
    devices = paginator.get_page(page)

    return render(
        request,
        'dashboard/device_list.html',
        {
            'devices': devices
        }
    )


@login_required
def device_add_view(request):
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = DeviceForm(request.POST)
        # check whether it's valid:
        form.fields['device'].queryset = Device.objects.exclude(
            owners=request.user
        )
        if form.is_valid():
            device = form.cleaned_data['device']
            ownership = DeviceOwnership()
            ownership.user = request.user
            ownership.device = device
            ownership.save()
            return redirect('dashboard:device_list_view')
    else:
        form = DeviceForm()
        form.fields['device'].queryset = Device.objects.none()
    return render(
        request,
        'dashboard/device_add.html',
        {
            'form': form,
        }
    )


@login_required
def device_remove_view(request, id):
    ownership = DeviceOwnership.objects \
        .select_related('device') \
        .filter(
            device__aid=id,
            user=request.user
        ) \
        .first()

    if not ownership:
        raise Http404('No such device owned.')

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        ownership.delete()
        return redirect('dashboard:device_list_view')
    return render(
        request,
        'dashboard/device_remove.html',
        {
            'device': ownership.device,
        }
    )


@login_required
def club_list_view(request):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)

    paginator = Paginator(club_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get('page')
    clubs = paginator.get_page(page)

    return render(
        request,
        'dashboard/club_list.html',
        {
            'clubs': clubs
        }
    )


@login_required
def club_create_view(request):
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = ClubForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            club = form.save(commit=False)
            club.creator = request.user
            club.save()
            form.save_m2m()
            return redirect('dashboard:club_list_view')
    else:
        form = ClubForm()
    form.fields['admins'].queryset = User.objects.filter(id=request.user.id)
    return render(
        request,
        'dashboard/club_edit.html',
        {
            'context': 'create',
            'form': form,
        }
    )


@login_required
def club_edit_view(request, id):
    if request.user.is_superuser:
        club = get_object_or_404(
            Club,
            aid=id,
        )
    else:
        club = get_object_or_404(
            Club,
            aid=id,
            admins=request.user
        )

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = ClubForm(request.POST, instance=club)
        # check whether it's valid:
        if form.is_valid():
            club = form.save()
            return redirect('dashboard:club_list_view')
    else:
        form = ClubForm(instance=club)
    form.fields['admins'].queryset = User.objects.filter(
            id__in=club.admins.all()
        )
    return render(
        request,
        'dashboard/club_edit.html',
        {
            'context': 'edit',
            'club': club,
            'form': form,
        }
    )


@login_required
def club_delete_view(request, id):
    if request.user.is_superuser:
        club = get_object_or_404(
            Club,
            aid=id,
        )
    else:
        club = get_object_or_404(
            Club,
            aid=id,
            admins=request.user
        )

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        club.delete()
        return redirect('dashboard:club_list_view')
    return render(
        request,
        'dashboard/club_delete.html',
        {
            'club': club,
        }
    )


@login_required
def map_list_view(request):
    if request.user.is_superuser:
        map_list = Map.objects.all().select_related('club')
    else:
        club_list = Club.objects\
            .filter(admins=request.user)\
            .values_list('id', flat=True)
        map_list = Map.objects.filter(
            club_id__in=club_list
        ).select_related('club')

    paginator = Paginator(map_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get('page')
    maps = paginator.get_page(page)

    return render(
        request,
        'dashboard/map_list.html',
        {
            'maps': maps
        }
    )


@login_required
def map_create_view(request):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = MapForm(request.POST, request.FILES)
        form.fields['club'].queryset = club_list
        # check whether it's valid:
        if form.is_valid():
            form.save()
            return redirect('dashboard:map_list_view')
    else:
        form = MapForm()
        form.fields['club'].queryset = club_list
    return render(
        request,
        'dashboard/map_edit.html',
        {
            'context': 'create',
            'form': form,
        }
    )


@login_required
def map_kmz_upload_view(request):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = UploadKmzForm(request.POST, request.FILES)
        form.fields['club'].queryset = club_list
        # check whether it's valid:
        if form.is_valid():
            new_map = None
            file = form.cleaned_data['file']
            error = None
            if file.name.lower().endswith('.kml'):
                try:
                    kml = file.read()
                    name, image_path, corners_coords = \
                        extract_ground_overlay_info(kml)
                    if not name:
                        name = 'Untitled'
                    if not image_path.startswith('http://') and \
                            not image_path.startswith('https://'):
                        raise Exception('Fishy KML')

                    dest = tempfile.NamedTemporaryFile(delete=False)
                    headers = requests.utils.default_headers()
                    headers.update(
                        {
                            'User-Agent': 'Python3/Requests/Routechoices.com',
                        }
                    )
                    r = requests.get(image_path, headers=headers)
                    if r.status_code != 200:
                        raise Exception('Could not reach image source')
                    dest.write(r.content)
                    new_map = Map(
                        name=name,
                        club=form.cleaned_data['club'],
                        corners_coordinates=corners_coords,
                    )
                    image_file = File(open(dest.name, 'rb'))
                    new_map.image.save('file', image_file, save=False)
                    dest.close()
                except Exception:
                    error = 'An error occured while extracting the map from ' \
                            'your file.'
            elif file.name.lower().endswith('.kmz'):
                try:
                    dest = tempfile.mkdtemp('_kmz')
                    zf = zipfile.ZipFile(file)
                    zf.extractall(dest)
                    with open(os.path.join(dest, 'doc.kml'), 'r') as f:
                        kml = f.read().encode('utf8')
                    name, image_path, corners_coords = \
                        extract_ground_overlay_info(kml)
                    if not name:
                        name = 'Untitled'
                    if image_path.startswith('http://') or \
                            image_path.startswith('https://'):
                        dest = tempfile.NamedTemporaryFile(delete=False)
                        headers = requests.utils.default_headers()
                        headers.update(
                            {
                                'User-Agent':
                                    'Python3/Requests/Routechoices.com',
                            }
                        )
                        r = requests.get(image_path, headers=headers)
                        if r.status_code != 200:
                            raise Exception('Could not reach image source')
                        dest.write(r.content)
                        image_file = File(open(dest.name, 'rb'))
                        new_map = Map(
                            name=name,
                            club=form.cleaned_data['club'],
                            corners_coordinates=corners_coords,
                        )
                        new_map.image.save('file', image_file, save=True)
                        dest.close()
                    else:
                        image_path = os.path.abspath(
                            os.path.join(dest, image_path)
                        )
                        if not image_path.startswith(dest):
                            raise Exception('Fishy KMZ')
                        image_file = File(open(image_path, 'rb'))
                        new_map = Map(
                            name=name,
                            club=form.cleaned_data['club'],
                            corners_coordinates=corners_coords,
                        )
                        new_map.image.save('file', image_file, save=False)
                except Exception:
                    error = 'An error occured while extracting the map from ' \
                            'your file.'
            if new_map:
                new_map.strip_exif()
                new_map.save()
            if error:
                messages.error(request, error)
            else:
                messages.success(
                    request,
                    'The import of the map was successful'
                )
                return redirect('dashboard:map_list_view')
    else:
        form = UploadKmzForm()
        form.fields['club'].queryset = club_list
    return render(
        request,
        'dashboard/map_kmz_upload.html',
        {
            'form': form,
        }
    )


@login_required
def map_edit_view(request, id):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)
    rmap = get_object_or_404(
        Map,
        aid=id,
        club__in=club_list
    )

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = MapForm(request.POST, request.FILES, instance=rmap)
        form.fields['club'].queryset = club_list
        # check whether it's valid:
        if form.is_valid():
            form.save()
            return redirect('dashboard:map_list_view')
    else:
        form = MapForm(instance=rmap)
        form.fields['club'].queryset = club_list
    return render(
        request,
        'dashboard/map_edit.html',
        {
            'context': 'edit',
            'map': rmap,
            'form': form,
        }
    )


@login_required
def map_delete_view(request, id):
    if request.user.is_superuser:
        rmap = get_object_or_404(
            Map,
            aid=id
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        rmap = get_object_or_404(
            Map,
            aid=id,
            club__in=club_list
        )
    if request.method == 'POST':
        rmap.delete()
        return redirect('dashboard:map_list_view')
    return render(
        request,
        'dashboard/map_delete.html',
        {
            'map': rmap,
        }
    )


@login_required
def event_list_view(request):
    if request.user.is_superuser:
        event_list = Event.objects.all().select_related('club')
    else:
        club_list = Club.objects.filter(admins=request.user)
        event_list = Event.objects.filter(
            club__in=club_list
        ).select_related('club')

    paginator = Paginator(event_list, DEFAULT_PAGE_SIZE)
    page = request.GET.get('page')
    events = paginator.get_page(page)

    return render(
        request,
        'dashboard/event_list.html',
        {
            'events': events
        }
    )


@login_required
def event_create_view(request):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)
    map_list = Map.objects.filter(club__in=club_list).select_related('club')

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EventForm(request.POST, request.FILES)
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
        formset = CompetitorFormSet(request.POST)
        extra_map_formset = ExtraMapFormSet(request.POST)
        for mform in extra_map_formset.forms:
            mform.fields['map'].queryset = map_list
        notice_form = NoticeForm(request.POST)
        # check whether it's valid:
        if form.is_valid() and formset.is_valid() and notice_form.is_valid()\
                and extra_map_formset.is_valid():
            event = form.save()
            formset.instance = event
            formset.save()
            extra_map_formset.instance = event
            extra_map_formset.save()
            notice = notice_form.save(commit=False)
            notice.event = event
            notice.save()
            if request.POST.get('save_continue'):
                return redirect(
                    'dashboard:event_edit_view',
                    id=event.aid
                )
            return redirect('dashboard:event_list_view')
        else:
            devices = Device.objects.none()
            if request.user.is_authenticated:
                devices = request.user.devices.all()
            for cform in formset.forms:
                cform.fields['device'].queryset = devices
    else:
        form = EventForm()
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
        formset = CompetitorFormSet()
        extra_map_formset = ExtraMapFormSet()
        for mform in extra_map_formset.forms:
            mform.fields['map'].queryset = map_list
        notice_form = NoticeForm()
        devices = Device.objects.none()
        if request.user.is_authenticated:
            devices = request.user.devices.all()
        for cform in formset.forms:
            cform.fields['device'].queryset = devices
    return render(
        request,
        'dashboard/event_edit.html',
        {
            'context': 'create',
            'form': form,
            'formset': formset,
            'extra_map_formset': extra_map_formset,
            'notice_form': notice_form,
        }
    )


@login_required
def event_edit_view(request, id):
    if request.user.is_superuser:
        club_list = Club.objects.all()
    else:
        club_list = Club.objects.filter(admins=request.user)
    map_list = Map.objects.filter(club__in=club_list).select_related('club')
    event = get_object_or_404(
        Event.objects.all().prefetch_related('notice', 'competitors'),
        aid=id,
        club__in=club_list
    )
    comp_devices_id = event.competitors.all().values_list('device', flat=True)
    own_devices = Device.objects.none()
    if request.user.is_authenticated:
        own_devices = request.user.devices.all()
    own_devices_id = own_devices.values_list('id', flat=True)
    all_devices = list(comp_devices_id) + list(own_devices_id)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EventForm(request.POST, request.FILES, instance=event)
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
        extra_map_formset = ExtraMapFormSet(request.POST, instance=event)
        for mform in extra_map_formset.forms:
            mform.fields['map'].queryset = map_list
        formset = CompetitorFormSet(
            request.POST,
            instance=event,
        )
        args = {}
        if event.has_notice:
            args = {'instance': event.notice}
        notice_form = NoticeForm(request.POST, **args)
        # check whether it's valid:
        if form.is_valid() and formset.is_valid() and notice_form.is_valid()\
                and extra_map_formset.is_valid():
            form.save()
            formset.instance = event
            formset.save()
            extra_map_formset.instance = event
            extra_map_formset.save()
            prev_text = ''
            if event.has_notice:
                notice_form.instance = event.notice
                event.notice.refresh_from_db()
                prev_text = event.notice.text
            if prev_text != notice_form.cleaned_data['text']:
                if not event.has_notice:
                    notice = Notice(event=event)
                else:
                    notice = event.notice
                notice.text = notice_form.cleaned_data['text']
                notice.save()
            if request.POST.get('save_continue'):
                return redirect(
                    'dashboard:event_edit_view',
                    id=event.aid
                )
            return redirect('dashboard:event_list_view')
        else:
            dev_qs = Device.objects.filter(
                id__in=all_devices
            )
            for cform in formset.forms:
                cform.fields['device'].queryset = dev_qs
    else:
        form = EventForm(instance=event)
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
        formset = CompetitorFormSet(instance=event)
        extra_map_formset = ExtraMapFormSet(instance=event)
        for mform in extra_map_formset.forms:
            mform.fields['map'].queryset = map_list
        args = {}
        if event.has_notice:
            args = {'instance': event.notice}
        notice_form = NoticeForm(**args)
        dev_qs = Device.objects.filter(
            id__in=all_devices
        )
        for cform in formset.forms:
            cform.fields['device'].queryset = dev_qs
    return render(
        request,
        'dashboard/event_edit.html',
        {
            'context': 'edit',
            'event': event,
            'form': form,
            'formset': formset,
            'extra_map_formset': extra_map_formset,
            'notice_form': notice_form,
        }
    )


@login_required
def event_delete_view(request, id):
    if request.user.is_superuser:
        event = get_object_or_404(
            Event,
            aid=id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        event = get_object_or_404(
            Event,
            aid=id,
            club__in=club_list
        )

    if request.method == 'POST':
        event.delete()
        return redirect('dashboard:event_list_view')
    return render(
        request,
        'dashboard/event_delete.html',
        {
            'event': event,
        }
    )


@login_required
def dashboard_map_download(request, id, *args, **kwargs):
    if request.user.is_superuser:
        raster_map = get_object_or_404(
            Map,
            aid=id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        raster_map = get_object_or_404(
            Map,
            aid=id,
            club__in=club_list
        )
    file_path = raster_map.path
    mime_type = raster_map.mime_type
    return serve_from_s3(
        'routechoices-maps',
        request,
        '/internal/' + file_path,
        filename='{}_{}_.{}'.format(
            raster_map.name,
            raster_map.corners_coordinates_short.replace(',', '_'),
            mime_type[6:]
        ),
        mime=mime_type
    )


@login_required
def event_route_upload_view(request, id):
    if request.user.is_superuser:
        event = get_object_or_404(
            Event,
            aid=id,
        )
    else:
        club_list = Club.objects.filter(admins=request.user)
        event = get_object_or_404(
            Event,
            aid=id,
            club__in=club_list
        )
    competitors = event.competitors.all()
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = UploadGPXForm(request.POST, request.FILES)
        form.fields['competitor'].queryset = competitors
        # check whether it's valid:
        if form.is_valid():
            error = None
            try:
                gpx_file = form.cleaned_data['gpx_file'].read().decode('utf8')
            except UnicodeDecodeError:
                error = "Couldn't decode file"
            if not error:
                try:
                    gpx = gpxpy.parse(gpx_file)
                except Exception:
                    error = "Couldn't parse file"
            if not error:
                device = Device.objects.create()
                device.aid += '_GPX'
                device.is_gpx = True
                device.save()
                start_time = None
                points = {'timestamps': [], 'latitudes': [], 'longitudes': []}
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            if point.time \
                                    and point.latitude \
                                    and point.longitude:
                                points['timestamps'].append(
                                    point.time.timestamp()
                                )
                                points['latitudes'].append(
                                    round(point.latitude, 5)
                                )
                                points['longitudes'].append(
                                    round(point.longitude, 5)
                                )
                                if not start_time:
                                    start_time = point.time
                device.locations = points
                device.save()
                competitor = form.cleaned_data['competitor']
                competitor.device = device
                if start_time and event.start_date <= start_time \
                        and (
                            not event.end_date
                            or start_time <= event.end_date
                        ):
                    competitor.start_time = start_time
                competitor.save()
            if error:
                messages.error(request, error)
            else:
                messages.success(
                    request,
                    'The upload of the GPX file was successful'
                )
                return redirect('dashboard:event_edit_view', id=event.aid)

    else:
        form = UploadGPXForm()
        form.fields['competitor'].queryset = competitors
    return render(
        request,
        'dashboard/event_gpx_upload.html',
        {
            'event': event,
            'form': form,
        }
    )

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from routechoices.api.views import x_accel_redirect
from routechoices.core.models import Club, Map, Event
from routechoices.dashboard.forms import ClubForm, MapForm, EventForm


@login_required
def home_view(request):
    return render(
        request,
        'dashboard/home.html',
    )


@login_required
def account_edit_view(request):
    return render(
        request,
        'dashboard/account_edit.html',
    )


@login_required
def club_list_view(request):
    club_list = Club.objects.filter(admins=request.user)

    return render(
        request,
        'dashboard/club_list.html',
        {
            'clubs': club_list
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
            club.admins.add(request.user)
            club.save()
            return redirect('dashboard:club_list_view')
    else:
        form = ClubForm()
    return render(
        request,
        'dashboard/club_create.html',
        {
            'form': form,
        }
    )


@login_required
def club_edit_view(request, id):
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
            form.save()
            return redirect('dashboard:club_list_view')
    else:
        form = ClubForm(instance=club)
    return render(
        request,
        'dashboard/club_edit.html',
        {
            'club': club,
            'form': form,
        }
    )


@login_required
def map_list_view(request):
    club_list = Club.objects\
        .filter(admins=request.user)\
        .values_list('id', flat=True)
    map_list = Map.objects.filter(club_id__in=club_list)

    return render(
        request,
        'dashboard/map_list.html',
        {
            'maps': map_list
        }
    )


@login_required
def map_create_view(request):
    club_list = Club.objects.filter(admins=request.user)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = MapForm(request.POST, request.FILES)
        form.fields['club'].queryset = club_list
        # check whether it's valid:
        if form.is_valid():
            map = form.save()
            return redirect('dashboard:map_list_view')
    else:
        form = MapForm()
        form.fields['club'].queryset = club_list
    return render(
        request,
        'dashboard/map_create.html',
        {
            'form': form,
        }
    )


@login_required
def map_edit_view(request, id):
    club_list = Club.objects.filter(admins=request.user)
    map = get_object_or_404(
        Map,
        aid=id,
        club__in=club_list
    )

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = MapForm(request.POST, request.FILES, instance=map)
        form.fields['club'].queryset = club_list
        # check whether it's valid:
        if form.is_valid():
            form.save()
            return redirect('dashboard:map_list_view')
    else:
        form = MapForm(instance=map)
        form.fields['club'].queryset = club_list
    return render(
        request,
        'dashboard/map_edit.html',
        {
            'map': map,
            'form': form,
        }
    )


@login_required
def event_list_view(request):
    club_list = Club.objects.filter(admins=request.user)
    event_list = Event.objects.filter(club__in=club_list)

    return render(
        request,
        'dashboard/event_list.html',
        {
            'events': event_list
        }
    )


@login_required
def event_create_view(request):
    club_list = Club.objects.filter(admins=request.user)
    map_list = Map.objects.filter(club__in=club_list)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EventForm(request.POST)
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
        # check whether it's valid:
        if form.is_valid():
            event = form.save()
            return redirect('dashboard:event_list_view')
    else:
        form = EventForm()
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
    return render(
        request,
        'dashboard/event_create.html',
        {
            'form': form,
        }
    )


@login_required
def event_edit_view(request, id):
    club_list = Club.objects.filter(admins=request.user)
    map_list = Map.objects.filter(club__in=club_list)
    event = get_object_or_404(
        Event,
        aid=id,
        club__in=club_list
    )

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EventForm(request.POST, instance=event)
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
        # check whether it's valid:
        if form.is_valid():
            form.save()
            return redirect('dashboard:event_list_view')
    else:
        form = EventForm(instance=event)
        form.fields['club'].queryset = club_list
        form.fields['map'].queryset = map_list
    return render(
        request,
        'dashboard/event_edit.html',
        {
            'event': event,
            'form': form,
        }
    )



@login_required
def dashboard_map_download(request, id, *args, **kwargs):
    club_list = Club.objects.filter(admins=request.user)
    map = get_object_or_404(
        Map,
        aid=id,
        club__in=club_list
    )
    file_path = map.path
    return x_accel_redirect(
        request,
        file_path,
        filename='{}.{}'.format(map.name, map.mime_type[6:]),
        mime=map.mime_type
    )
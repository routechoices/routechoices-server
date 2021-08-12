from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail

from django.core.paginator import Paginator
from django.forms import HiddenInput

from django.shortcuts import get_object_or_404, redirect, render

from allauth.account.models import EmailAddress

from routechoices.core.models import (
    Event,
    PRIVACY_PUBLIC,
)

from routechoices.site.forms import ContactForm
from routechoices.lib.patreon_api import PatreonAPI


def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home_view')
    return render(
        request,
        'site/home.html',
    )


def event_shortcut(request, event_id):
    event = get_object_or_404(Event, aid=event_id)
    site = Site.objects.get(id=settings.SITE_ID)
    return redirect('http' + ('s' if request.is_secure() else '') + ':' + event.get_absolute_url())


def tracker_view(request):
    return render(
        request,
        'site/tracker.html',
    )


def events_view(request):
    event_list = Event.objects.filter(
        privacy=PRIVACY_PUBLIC
    ).select_related('map', 'club').prefetch_related('map_assignations')
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    events = paginator.get_page(page)
    return render(
        request,
        'site/event_list.html',
        {'events': events}
    )


def backers(request):
    access_token = settings.PATREON_CREATOR_ID
    api_client = PatreonAPI(access_token)

    # Get the campaign ID
    response = api_client.fetch_campaign_and_patrons()
    main_campaign = response['data'][0]
    creator_id = main_campaign['relationships']['creator']['data']['id']
    included = response.get('included')
    pledges = [obj for obj in included
               if obj['type'] == 'pledge' and obj['relationships']['creator']['data']['id'] == creator_id]
    patron_ids = [pledge['relationships']['patron']['data']['id'] for pledge in pledges]
    patrons = [obj for obj in included
               if obj['type'] == 'user' and obj['id'] in patron_ids]
    patron_attributes_map = {patron['id']: patron['attributes']
                             for patron in patrons
                             if 'full_name' in patron['attributes']}
    patronage_map = {}
    for pledge in pledges:
        if pledge['relationships']['patron']['data']['id'] in patron_attributes_map:
            patron_attributes = patron_attributes_map[pledge['relationships']['patron']['data']['id']]
            if 'full_name' in patron_attributes and 'amount_cents' in pledge['attributes']:
                relevant_info = {
                    'amount_cents': pledge['attributes']['amount_cents']
                }
                relevant_info['full_name'] = patron_attributes['full_name']
                patronage_map[patron_attributes['full_name']] = relevant_info
    return render(request, "site/backers.html", {'backers': [b.get('full_name') for b in patronage_map.values() if b.get('full_name')]})



def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = (
                'Routechoices.com contact form - '
                + form.cleaned_data['subject']
            )
            from_email = form.cleaned_data['from_email']
            message = form.cleaned_data['message']
            send_mail(
                subject,
                message,
                from_email,
                [settings.DEFAULT_FROM_EMAIL]
            )
            return redirect('site:contact_email_sent_view')
    else:
        form = ContactForm()
    if request.user.is_authenticated:
        form.fields['from_email'].initial = EmailAddress.objects.get_primary(
            request.user
        ).email
        form.fields['from_email'].widget = HiddenInput()
    return render(request, "site/contact.html", {'form': form})

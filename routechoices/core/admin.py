from base64 import b32encode
from datetime import timedelta

import arrow
from allauth.account.models import EmailAddress
from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.db.models import Case, Count, Exists, F, OuterRef, Prefetch, Value, When
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from hijack.contrib.admin import HijackUserAdminMixin
from kagi.models import BackupCode, TOTPDevice, WebAuthnKey

from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    DeviceArchiveReference,
    DeviceClubOwnership,
    Event,
    EventSet,
    ImeiDevice,
    Map,
    MapAssignation,
    Notice,
    SpotDevice,
    SpotFeed,
    TcpDeviceCommand,
)
from routechoices.lib.helpers import epoch_to_datetime, get_device_name


class ImeiDeviceClubFilter(admin.SimpleListFilter):
    title = "which club owns it"
    parameter_name = "club"

    def lookups(self, request, model_admin):
        qs = DeviceClubOwnership.objects.select_related("club")
        qs = qs.distinct("club__name").order_by("club__name")
        for club_dev in qs:
            yield (club_dev.club_id, club_dev.club.name)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device__club_ownerships__club_id=self.value())
        return queryset


class EventDateRangeFilter(admin.SimpleListFilter):
    title = "when"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return [
            ("now", "Now"),
            ("today", "Today"),
            ("yesterday", "Yesterday"),
            ("future", "Future"),
            ("this_week", "This week to date"),
            ("last_week", "Last week"),
            ("last_7_days", "Last 7 days"),
            ("this_month", "This month to date"),
            ("last_month", "Last month"),
            ("last_30_days", "Last 30 days"),
            ("this_year", "This year to date"),
            ("last_year", "Last year"),
            ("last_365_days", "Last 365 days"),
        ]

    def queryset(self, request, queryset):
        time_now = arrow.utcnow()
        if self.value() == "now":
            return queryset.filter(
                start_date__lte=time_now.datetime,
                end_date__gte=time_now.datetime,
            )
        if self.value() == "future":
            return queryset.filter(start_date__gt=time_now.datetime)
        if self.value() == "today":
            today = time_now.date()
            return queryset.filter(
                end_date__date__gte=today,
                start_date__date__lte=today,
            )
        if self.value() == "yesterday":
            yesterday = time_now.shift(days=-1).date()
            return queryset.filter(
                end_date__date__gte=yesterday,
                start_date__date__lte=yesterday,
            )
        if self.value() == "last_7_days":
            return queryset.filter(
                end_date__date__gte=time_now.shift(days=-7).date(),
                start_date__lte=time_now.datetime,
            )
        if self.value() == "last_30_days":
            return queryset.filter(
                end_date__date__gte=time_now.shift(days=-30).date(),
                start_date__lte=time_now.datetime,
            )
        if self.value() == "last_365_days":
            return queryset.filter(
                end_date__date__gte=time_now.shift(days=-365).date(),
                start_date__lte=time_now.datetime,
            )
        if self.value() == "this_week":
            return queryset.filter(
                end_date__date__gte=time_now.floor("week").date(),
                start_date__lte=time_now.datetime,
            )
        if self.value() == "this_month":
            return queryset.filter(
                end_date__date__gte=time_now.floor("month").date(),
                start_date__lte=time_now.datetime,
            )
        if self.value() == "this_year":
            return queryset.filter(
                end_date__date__gte=time_now.floor("year").date(),
                start_date__lte=time_now.datetime,
            )
        if self.value() == "last_week":
            one_week_ago = time_now.shift(days=-7)
            return queryset.filter(
                end_date__date__gte=one_week_ago.floor("week").date(),
                start_date__date__lte=one_week_ago.ceil("week").date(),
            )
        if self.value() == "last_month":
            one_month_ago = time_now.shift(months=-1)
            return queryset.filter(
                end_date__date__gte=one_month_ago.floor("month").date(),
                start_date__date__lte=one_month_ago.ceil("month").date(),
            )
        if self.value() == "last_year":
            one_year_ago = time_now.shift(years=-1)
            return queryset.filter(
                end_date__date__gte=one_year_ago.floor("year").date(),
                start_date__date__lte=one_year_ago.ceil("year").date(),
            )
        if self.value():
            return queryset


class ModifiedDateFilter(admin.SimpleListFilter):
    title = "when was it last modified"
    parameter_name = "modified"

    def lookups(self, request, model_admin):
        return [
            ("all", "All"),
            (None, "Today"),
            ("yesterday", "Yesterday"),
            ("this_week", "This week to date"),
            ("last_week", "Last week"),
            ("last_7_days", "Last 7 days"),
            ("this_month", "This month to date"),
            ("last_month", "Last month"),
            ("last_30_days", "Last 30 days"),
            ("this_year", "This year to date"),
            ("last_year", "Last year"),
            ("last_365_days", "Last 365 days"),
        ]

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": cl.get_query_string(
                    {
                        self.parameter_name: lookup,
                    },
                    [],
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        time_now = arrow.utcnow()
        if self.value() == "all":
            return queryset.all()
        if self.value() == "yesterday":
            return queryset.filter(
                modification_date__date=time_now.shift(days=-1).date(),
            )
        if self.value() == "last_7_days":
            return queryset.filter(
                modification_date__date__gte=time_now.shift(days=-7).date()
            )
        if self.value() == "last_30_days":
            return queryset.filter(
                modification_date__date__gte=time_now.shift(days=-7).date()
            )
        if self.value() == "last_365_days":
            return queryset.filter(
                modification_date__date__gte=time_now.shift(days=-365).date()
            )
        if self.value() == "this_week":
            return queryset.filter(
                modification_date__date__gte=time_now.floor("week").date()
            )
        if self.value() == "this_month":
            return queryset.filter(
                modification_date__date__gte=time_now.floor("month").date()
            )
        if self.value() == "this_year":
            return queryset.filter(
                modification_date__date__gte=time_now.floor("year").date()
            )
        if self.value() == "last_week":
            one_week_ago = time_now.shift(days=-7)
            return queryset.filter(
                modification_date__date__gte=one_week_ago.floor("week").date(),
                modification_date__date__lte=one_week_ago.ceil("week").date(),
            )
        if self.value() == "last_month":
            one_month_ago = time_now.shift(months=-1)
            return queryset.filter(
                modification_date__date__gte=one_month_ago.floor("month").date(),
                modification_date__date__lte=one_month_ago.ceil("month").date(),
            )
        if self.value() == "last_year":
            one_year_ago = time_now.shift(years=-1)
            return queryset.filter(
                modification_date__date__gte=one_year_ago.floor("year").date(),
                modification_date__date__lte=one_year_ago.ceil("year").date(),
            )
        return queryset.filter(modification_date__date=time_now.date())


class HasLocationFilter(admin.SimpleListFilter):
    title = "whether it has locations"
    parameter_name = "has_locations"

    def lookups(self, request, model_admin):
        return [
            ("true", "With locations"),
            ("false", "Without locations"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(_location_count=0)
        if self.value():
            return queryset.filter(_location_count__gt=0)


class HasCompetitorFilter(admin.SimpleListFilter):
    title = "whether it has competitors associated with"
    parameter_name = "has_competitors"

    def lookups(self, request, model_admin):
        return [
            ("true", "With competitors"),
            ("false", "Without competitors"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(competitor_count=0)
        if self.value():
            return queryset.filter(competitor_count__gt=0)


class HasEventsFilter(admin.SimpleListFilter):
    title = "whether any events use it"
    parameter_name = "has_events"

    def lookups(self, request, model_admin):
        return [
            ("true", "With events"),
            ("false", "Without events"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(event_count=0)
        if self.value():
            return queryset.filter(event_count__gt=0)


class HasMapsFilter(admin.SimpleListFilter):
    title = "whether it use maps"
    parameter_name = "has_maps"

    def lookups(self, request, model_admin):
        return [
            ("true", "With maps"),
            ("false", "Without maps"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(map_count=0)
        if self.value():
            return queryset.filter(map_count__gt=0)


class HasClubsFilter(admin.SimpleListFilter):
    title = "whether it admins a club"
    parameter_name = "has_club"

    def lookups(self, request, model_admin):
        return [
            ("true", "With clubs"),
            ("false", "Without clubs"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(club_count=0)
        if self.value():
            return queryset.filter(club_count__gt=0)


class IsGPXFilter(admin.SimpleListFilter):
    title = "whether it is an actual device"
    parameter_name = "device_type"

    def lookups(self, request, model_admin):
        return [
            ("all", "All"),
            (None, "Real Devices"),
            ("virtual", "Virtual Devices"),
        ]

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": cl.get_query_string(
                    {
                        self.parameter_name: lookup,
                    },
                    [],
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        if self.value() == "virtual":
            return queryset.filter(is_gpx=True)
        if self.value():
            return queryset.all()
        return queryset.filter(is_gpx=False)


@admin.register(EventSet)
class EventSetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "club_link",
        "creation_date",
        "event_count",
        "page",
    )
    list_filter = (
        HasEventsFilter,
        "club",
    )
    show_facets = False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("club").annotate(
            event_count=Count("events", distinct=True)
        )

    def event_count(self, obj):
        return obj.event_count

    event_count.admin_order_field = "event_count"

    def page(self, obj):
        if not obj.create_page:
            return ""
        link = obj.url
        return format_html('<a href="{}">Open</a>', link)

    def club_link(self, obj):
        link = f"/core/club/{obj.club_id}/change/"
        return format_html('<a href="{}">{}</a>', link, obj.club)

    club_link.short_description = "Club"


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "o_club",
        "creation_date",
        "slug",
        "admin_list",
        "event_count",
        "map_count",
        "upgraded",
        "domain",
    )
    list_filter = (HasEventsFilter, HasMapsFilter, "upgraded")
    show_facets = False
    search_fields = ("name",)

    actions = ["mark_as_o_club"]

    def mark_as_o_club(self, request, queryset):
        for q in queryset:
            q.o_club = True
            q.save()

    def get_ordering(self, request):
        if request.resolver_match.url_name == "core_club_changelist":
            return ("-creation_date",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("admins")
            .annotate(event_count=Count("events", distinct=True))
            .annotate(map_count=Count("maps", distinct=True))
        )

    def event_count(self, obj):
        return format_html(
            '<a href="/core/event/?club__id__exact={}">{}</a>',
            obj.pk,
            obj.event_count,
        )

    def map_count(self, obj):
        return format_html(
            '<a href="/core/map/?club__id__exact={}">{}</a>',
            obj.pk,
            obj.map_count,
        )

    def admin_list(self, obj):
        return mark_safe(
            ", ".join(
                (
                    format_html(
                        '<a href="/auth/user/{}/change">{}</a>', a.id, a.username
                    )
                    for a in obj.admins.all()
                )
            )
        )

    event_count.admin_order_field = "event_count"
    map_count.admin_order_field = "map_count"


class ExtraMapInline(admin.TabularInline):
    verbose_name = "Extra Map"
    verbose_name_plural = "Extra Maps"
    model = MapAssignation
    fields = (
        "map",
        "title",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("map__club")


class CompetitorInline(admin.TabularInline):
    model = Competitor
    fields = (
        "device",
        "name",
        "short_name",
        "start_time",
    )
    autocomplete_fields = ("device",)


class NoticeInline(admin.TabularInline):
    model = Notice
    fields = ("text",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event_set_link",
        "club_link",
        "start_date",
        "db_duration",
        "db_is_live",
        "privacy",
        "on_frontpage",
        "competitor_count",
        "map_count",
        "link",
    )
    list_filter = (
        EventDateRangeFilter,
        HasCompetitorFilter,
        HasMapsFilter,
        "privacy",
        "club",
    )
    search_fields = ("name", "event_set__name", "club__name")
    inlines = [ExtraMapInline, NoticeInline, CompetitorInline]
    show_facets = False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("event_set", "club")
            .annotate(
                db_duration=F("end_date") - F("start_date"),
                competitor_count=Count("competitors", distinct=True),
                main_map_count=Case(
                    When(map_id__isnull=True, then=Value(0)),
                    default=Value(1),
                ),
                alt_map_count=Count("map_assignations", distinct=True),
                map_count=F("main_map_count") + F("alt_map_count"),
                db_is_live=Case(
                    When(
                        start_date__lt=Value(now()),
                        end_date__gt=Value(now()),
                        then=Value(1),
                    ),
                    default=Value(0),
                ),
            )
        )

    def db_duration(self, obj):
        return obj.db_duration

    db_duration.admin_order_field = "db_duration"
    db_duration.short_description = "Duration"

    @admin.display(boolean=True)
    def on_frontpage(self, obj):
        return obj.on_events_page

    on_frontpage.admin_order_field = "on_events_page"
    on_frontpage.short_description = "On Frontpage"

    @admin.display(boolean=True)
    def db_is_live(self, obj):
        return obj.db_is_live

    db_is_live.admin_order_field = "db_is_live"
    db_is_live.short_description = "Is Live"

    def map_count(self, obj):
        return obj.map_count

    map_count.admin_order_field = "map_count"

    def link(self, obj):
        link = obj.shortcut or obj.get_absolute_url()
        return format_html('<a href="{}">Open</a>', link)

    def competitor_count(self, obj):
        return obj.competitor_count

    competitor_count.admin_order_field = "competitor_count"

    def club_link(self, obj):
        link = f"/core/club/{obj.club_id}/change/"
        return format_html('<a href="{}">{}</a>', link, obj.club)

    club_link.short_description = "Club"

    def event_set_link(self, obj):
        if not obj.event_set_id:
            return None
        link = f"/core/eventset/{obj.event_set_id}/change/"
        return format_html('<a href="{}">{}</a>', link, obj.event_set)

    club_link.short_description = "Club"


class DeviceCompetitorInline(admin.TabularInline):
    model = Competitor
    fields = ("event", "name", "short_name", "start_time", "link")
    readonly_fields = ("link",)
    ordering = ("-start_time",)

    def link(self, obj):
        return format_html('<a href="{}">Open</a>', obj.event.get_absolute_url())


class DeviceOwnershipInline(admin.TabularInline):
    model = DeviceClubOwnership
    fields = ("club", "nickname")
    ordering = ("creation_date",)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    class Media:
        js = [
            "/static/vendor/bn-5.2.1/bn.min.js",
            "/static/vendor/gps-encoding-2023.04.13/gps-encoding.js",
            "/static/scripts/admin/device.js?v=1.1",
        ]

    list_display = (
        "aid",
        "device_name",
        "creation_date",
        "modification_date",
        "last_location_datetime",
        "last_coordinates",
        "location_count",
        "battery_level",
        "competitor_count",
    )
    readonly_fields = ("locations_sample", "download_gpx", "imei")
    actions = ["clean_positions"]
    search_fields = ("aid",)
    inlines = [
        DeviceCompetitorInline,
        DeviceOwnershipInline,
    ]
    list_filter = (
        IsGPXFilter,
        ModifiedDateFilter,
        HasCompetitorFilter,
        HasLocationFilter,
    )
    show_full_result_count = False

    def download_gpx(self, obj):
        return mark_safe(
            '<input value="Download GPX File" '
            'name="_download_gpx_button" type="button">'
        )

    def locations_sample(self, obj):
        if obj.location_count <= 30:
            return "\n".join(
                [
                    f"time: {epoch_to_datetime(x[0])}, latlon: {x[1]}, {x[2]}"
                    for x in obj.locations_series
                ]
            )
        return "\n.\n.\n.\n".join(
            [
                "\n".join(
                    [
                        f"time: {epoch_to_datetime(x[0])}, latlon: {x[1]}, {x[2]}"
                        for x in obj.locations_series[:15]
                    ]
                ),
                "\n".join(
                    [
                        f"time: {epoch_to_datetime(x[0])}, latlon: {x[1]}, {x[2]}"
                        for x in obj.locations_series[-15:]
                    ]
                ),
            ]
        )

    ordering = ["-modification_date", "aid"]
    show_facets = False

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .annotate(competitor_count=Count("competitor_set"))
        )
        return qs

    def location_count(self, obj):
        return obj._location_count

    def competitor_count(self, obj):
        return obj.competitor_count

    def last_location_datetime(self, obj):
        return obj._last_location_datetime

    def imei(self, obj):
        if obj.physical_device:
            return obj.physical_device.imei
        return ""

    def last_coordinates(self, obj):
        lat = obj._last_location_latitude
        lon = obj._last_location_longitude
        if not lat or not lon:
            return "-"
        lat, lon = round(lat, 5), round(lon, 5)
        return format_html(
            '<a href="http://www.openstreetmap.org/?mlat={}&mlon={}" target="_blank">{}, {}</a>',
            lat,
            lon,
            lat,
            lon,
        )

    location_count.admin_order_field = "_location_count"
    competitor_count.admin_order_field = "competitor_count"
    last_location_datetime.admin_order_field = "_last_location_datetime"

    def clean_positions(self, request, queryset):
        for obj in queryset:
            obj.remove_duplicates()

    clean_positions.short_description = "Remove duplicate positions from storage"

    def device_name(self, obj):
        return get_device_name(obj.user_agent) or obj.user_agent


@admin.register(DeviceArchiveReference)
class DeviceArchiveReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "archive",
        "original_link",
        "creation_date",
    )

    def original_link(self, obj):
        return format_html(
            '<a href="/core/device/{}/change">{}</a>', obj.original_id, obj.original
        )

    original_link.short_description = "Original"


@admin.register(ImeiDevice)
class ImeiDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "imei",
        "device_link",
        "creation_date",
        "clubs",
    )

    list_filter = (ImeiDeviceClubFilter,)

    search_fields = ("imei", "device__aid")

    def device_link(self, obj):
        return format_html(
            '<a href="/core/device/{}/change">{}</a>', obj.device_id, obj.device
        )

    def clubs(self, obj):
        return mark_safe(
            ", ".join(
                format_html(
                    '<a href="/core/club/{}/change">{}</a>', c.club.id, c.club.name
                )
                for c in obj.device.club_ownerships.all()
            )
        )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                Prefetch(
                    "device__club_ownerships",
                    queryset=DeviceClubOwnership.objects.select_related("club"),
                )
            )
        )


@admin.register(SpotDevice)
class SpotDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "messenger_id",
        "device",
        "creation_date",
    )


@admin.register(SpotFeed)
class SpotFeedAdmin(admin.ModelAdmin):
    list_display = ("feed_id",)


@admin.register(Map)
class MapAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "club_link",
        "creation_date",
        "center_link",
        "resolution_rounded",
        "max_zoom",
        "north_declination",
        "area",
        "event_count",
    )
    list_filter = (
        HasEventsFilter,
        "club",
    )
    list_select_related = ("club",)
    show_facets = False

    search_fields = ("name", "club__name")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                event_main_map_count=Count("events_main_map", distinct=True),
                event_alt_map_count=Count("map_assignations", distinct=True),
                event_count=F("event_main_map_count") + F("event_alt_map_count"),
            )
        )

    def center_link(self, obj):
        center = obj.center
        lat = round(center["lat"], 5)
        lon = round(center["lon"], 5)
        return format_html(
            '<a href="http://www.openstreetmap.org/?mlat={}&mlon={}" target="_blank">{}, {}</a>',
            lat,
            lon,
            lat,
            lon,
        )

    center_link.short_description = "Center"

    def resolution_rounded(self, obj):
        return round(obj.resolution, 3)

    resolution_rounded.short_description = "Resolution"

    def event_count(self, obj):
        return obj.event_count

    event_count.admin_order_field = "event_count"

    def club_link(self, obj):
        return format_html(
            '<a href="/core/club/{}/change">{}</a>', obj.club_id, obj.club
        )

    club_link.short_description = "Club"


@admin.register(DeviceClubOwnership)
class DeviceClubOwnershipAdmin(admin.ModelAdmin):
    list_display = ("device", "club_link", "nickname")
    list_filter = ("club",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("club", "device")
            .defer("device__locations_encoded")
            .order_by("club", "device__aid")
        )

    search_fields = ("device__aid", "nickname")

    def club_link(self, obj):
        link = f"/core/club/{obj.club_id}/change/"
        return format_html('<a href="{}">{}</a>', link, obj.club)

    club_link.short_description = "Club"


@admin.register(TcpDeviceCommand)
class TcpDeviceCommandAdmin(admin.ModelAdmin):
    list_display = ("target", "modification_date", "comment", "sent")
    autocomplete_fields = ("target",)
    actions = ["mark_as_not_sent"]

    def mark_as_not_sent(self, request, queryset):
        queryset.update(sent=False)


UserModel = get_user_model()
admin.site.unregister(UserModel)
admin.site.unregister(Group)


@admin.register(UserModel)
class MyUserAdmin(HijackUserAdminMixin, UserAdmin):
    list_display = (
        "username",
        "email",
        "has_verified_email",
        "date_joined",
        "clubs",
    )
    actions = [
        "clean_fake_users",
    ]
    show_facets = False

    @property
    def media(self):
        return super(UserAdmin, self).media + forms.Media(
            js=["scripts/admin/hijack.min.js"]
        )

    def get_list_filter(self, request):
        return super().get_list_filter(request) + (HasClubsFilter,)

    def get_hijack_user(self, obj):
        return obj

    def get_ordering(self, request):
        if request.resolver_match.url_name == "auth_user_changelist":
            return ("-date_joined",)
        return ("username",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("club_set")
            .annotate(
                club_count=Count("club"),
                has_verified_email=Exists(
                    EmailAddress.objects.filter(user_id=OuterRef("pk"), verified=True)
                ),
            )
        )

    @admin.display(boolean=True)
    def has_verified_email(self, obj):
        return obj.has_verified_email

    has_verified_email.short_description = "Is email verified"
    has_verified_email.admin_order_field = "has_verified_email"

    def clubs(self, obj):
        return mark_safe(
            ", ".join(
                (
                    format_html('<a href="/core/club/{}/change">{}</a>', c.id, c.name)
                    for c in obj.club_set.all()
                )
            )
        )

    def clean_fake_users(self, request, queryset):
        two_weeks_ago = now() - timedelta(days=14)
        users = queryset.filter(date_joined__lt=two_weeks_ago)
        for obj in users:
            has_verified_email = EmailAddress.objects.filter(
                user=obj, verified=True
            ).exists()
            if not has_verified_email:
                obj.delete()


@admin.register(BackupCode)
class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "code")


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "secret_base32")

    def secret_base32(self, obj):
        return b32encode(obj.key).decode()


admin.site.unregister(WebAuthnKey)


@admin.register(WebAuthnKey)
class WebAuthnKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "key_name")


ADMIN_COMMAND_LIST = [
    "import_from_gpsseuranta",
    "import_from_livelox",
    "import_from_loggator",
    "import_from_otracker",
    "import_from_sportrec",
    "import_from_tractrac",
    "export_device_list",
    "export_email_list",
    "clean_admin_logs",
]

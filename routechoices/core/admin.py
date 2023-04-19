from base64 import b32encode
from datetime import timedelta

import arrow
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Prefetch
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from kagi.models import BackupCode, TOTPDevice, WebAuthnKey

from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    DeviceArchiveReference,
    DeviceClubOwnership,
    Event,
    ImeiDevice,
    Map,
    MapAssignation,
    Notice,
    SpotDevice,
    SpotFeed,
    TcpDeviceCommand,
)
from routechoices.lib.helpers import epoch_to_datetime, get_device_name


class ModifiedDateFilter(admin.SimpleListFilter):
    title = "when was it modified"
    parameter_name = "modified"

    def lookups(self, request, model_admin):
        return [
            ("whenever", "All"),
            (None, "Today"),
            ("last_week", "This Week"),
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
        from_date = arrow.utcnow().shift(days=-1).datetime
        if self.value() == "last_week":
            from_date = arrow.utcnow().shift(weeks=-1).datetime
            return queryset.filter(modification_date__gte=from_date)
        elif self.value():
            return queryset.all()
        return queryset.filter(modification_date__gte=from_date)


class HasLocationFilter(admin.SimpleListFilter):
    title = "Whether it has locations"
    parameter_name = "has_locations"

    def lookups(self, request, model_admin):
        return [
            ("true", "With locations"),
            ("false", "Without locations"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(_location_count=0)
        elif self.value():
            return queryset.filter(_location_count__gt=0)


class HasCompetitorFilter(admin.SimpleListFilter):
    title = "Whether it has competitors associated with"
    parameter_name = "has_competitors"

    def lookups(self, request, model_admin):
        return [
            ("true", "With competitors"),
            ("false", "Without competitors"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "false":
            return queryset.filter(competitor_count=0)
        elif self.value():
            return queryset.filter(competitor_count__gt=0)


class IsGPXFilter(admin.SimpleListFilter):
    title = "Whether it is an actual device"
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
        elif self.value():
            return queryset.all()
        return queryset.filter(is_gpx=False)


class TimeStatusFilter(admin.SimpleListFilter):
    title = "when it is"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return [
            (None, "All"),
            ("future", "Future"),
            ("live", "Live"),
            ("past", "Past"),
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
        if self.value() == "past":
            return queryset.filter(end_date__lt=now())
        elif self.value() == "future":
            return queryset.filter(start_date__gt=now())
        elif self.value() == "live":
            return queryset.filter(start_date__lte=now(), end_date__gte=now())
        else:
            return queryset.all()


class ClubAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "creation_date",
        "slug",
        "admin_list",
        "event_count",
        "domain",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("admins")
            .annotate(event_count=Count("events"))
        )

    def event_count(self, obj):
        return obj.event_count

    def admin_list(self, obj):
        return ", ".join((a.username for a in obj.admins.all()))

    event_count.admin_order_field = "event_count"


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


class EventAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event_set",
        "club",
        "start_date",
        "privacy",
        "competitor_count",
        "shortcut_link",
    )
    list_filter = (TimeStatusFilter, "privacy", "club")
    inlines = [ExtraMapInline, NoticeInline, CompetitorInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("event_set")
            .annotate(competitor_count=Count("competitors"))
        )

    def shortcut_link(self, obj):
        link = obj.shortcut or obj.get_absolute_url()
        return mark_safe(f'<a href="{link}">{link}</a>')

    def competitor_count(self, obj):
        return obj.competitor_count

    competitor_count.admin_order_field = "competitor_count"


class DeviceCompetitorInline(admin.TabularInline):
    model = Competitor
    fields = ("event", "name", "short_name", "start_time", "link")
    readonly_fields = ("link",)
    ordering = ("-start_time",)

    def link(self, obj):
        return mark_safe(f'<a href="{obj.event.get_absolute_url()}">View on Site</a>')


class DeviceOwnershipInline(admin.TabularInline):
    model = DeviceClubOwnership
    fields = ("club", "nickname")
    ordering = ("creation_date",)


class DeviceAdmin(admin.ModelAdmin):
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
    readonly_fields = ("last_hundred_locations", "imei")
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

    def last_hundred_locations(self, obj):
        return "\n".join(
            [
                f"time: {epoch_to_datetime(x[0])}, latlon: {x[1]}, {x[2]}"
                for x in obj.locations_series[-100:]
            ]
        )

    def get_ordering(self, request):
        return ["-modification_date", "aid"]

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
        return obj._last_location_latitude, obj._last_location_longitude

    location_count.admin_order_field = "_location_count"
    competitor_count.admin_order_field = "competitor_count"
    last_location_datetime.admin_order_field = "_last_location_datetime"

    def clean_positions(self, request, queryset):
        for obj in queryset:
            obj.remove_duplicates()

    clean_positions.short_description = "Remove duplicate positions from storage"

    def device_name(self, obj):
        return get_device_name(obj.user_agent) or obj.user_agent


class DeviceArchiveReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "archive",
        "original",
        "creation_date",
    )


class ImeiDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "imei",
        "device",
        "creation_date",
    )
    search_fields = ("imei", "device__aid")


class SpotDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "messenger_id",
        "device",
        "creation_date",
    )


class SpotFeedAdmin(admin.ModelAdmin):
    list_display = ("feed_id",)


class MapAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "club",
        "creation_date",
        "resolution",
        "max_zoom",
        "rotation",
    )
    list_filter = ("club",)


class DeviceClubOwnershipAdmin(admin.ModelAdmin):
    list_display = ("device", "club", "nickname")
    list_filter = ("club",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("club", "device")
            .order_by("club", "device__aid")
        )

    search_fields = ("device__aid", "nickname")


class TcpDeviceCommandAdmin(admin.ModelAdmin):
    list_display = ("target", "creation_date", "modification_date", "sent")
    autocomplete_fields = ("target",)


admin.site.register(Club, ClubAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceArchiveReference, DeviceArchiveReferenceAdmin)
admin.site.register(ImeiDevice, ImeiDeviceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Map, MapAdmin)
admin.site.register(SpotDevice, SpotDeviceAdmin)
admin.site.register(SpotFeed, SpotFeedAdmin)
admin.site.register(DeviceClubOwnership, DeviceClubOwnershipAdmin)
admin.site.register(TcpDeviceCommand, TcpDeviceCommandAdmin)


class MyUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + (
        "date_joined",
        "has_verified_email",
        "clubs",
    )
    actions = [
        "clean_fake_users",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("club_set")
            .prefetch_related(
                Prefetch(
                    "emailaddress_set",
                    queryset=EmailAddress.objects.filter(verified=True),
                )
            )
        )

    @admin.display(boolean=True)
    def has_verified_email(self, obj):
        return obj.emailaddress_set.exists()

    def clubs(self, obj):
        return ", ".join((c.name for c in obj.club_set.all()))

    def clean_fake_users(self, request, queryset):
        two_weeks_ago = now() - timedelta(days=14)
        users = queryset.filter(date_joined__lt=two_weeks_ago)
        for obj in users:
            has_verified_email = EmailAddress.objects.filter(
                user=obj, verified=True
            ).exists()
            if not has_verified_email:
                obj.delete()


UserModel = get_user_model()
admin.site.unregister(UserModel)
admin.site.register(UserModel, MyUserAdmin)


class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "code")


class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "secret_base32")

    def secret_base32(self, obj):
        return b32encode(obj.key).decode()


class WebAuthnKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "key_name")


admin.site.register(BackupCode, BackupCodeAdmin)
admin.site.register(TOTPDevice, TOTPDeviceAdmin)
admin.site.unregister(WebAuthnKey)
admin.site.register(WebAuthnKey, WebAuthnKeyAdmin)

ADMIN_COMMAND_LIST = [
    "import_from_gpsseuranta",
    "import_from_livelox",
    "import_from_loggator",
    "import_from_otracker",
    "import_from_sportrec",
    "import_from_tractrac",
    "create_certificate",
]

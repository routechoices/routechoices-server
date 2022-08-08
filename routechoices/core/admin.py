from datetime import timedelta

import arrow
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from routechoices.core.models import (
    ChatMessage,
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
    QueclinkCommand,
    SpotDevice,
    SpotFeed,
)
from routechoices.lib.helpers import get_device_name


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
    title = "wether it has locations"
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
    title = "wether it has competitors associated with"
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
    title = "wether it is an actual device"
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


class ClubAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "domain",
        "creation_date",
        "event_count",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(event_count=Count("events"))

    def event_count(self, obj):
        return obj.event_count

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
        "privacy",
        "club",
        "start_date",
        "shortcut_link",
    )
    list_filter = ("club", "privacy")
    inlines = [ExtraMapInline, NoticeInline, CompetitorInline]

    def shortcut_link(self, obj):
        return mark_safe(f'<a href="{obj.shortcut}">Open</a>')


class DeviceCompetitorInline(admin.TabularInline):
    model = Competitor
    fields = ("event", "name", "short_name", "start_time", "link")
    readonly_fields = ("link",)
    ordering = ("-start_time",)

    def link(self, obj):
        return mark_safe(f'<a href="{obj.event.get_absolute_url()}">View on Site</a>')


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "aid",
        "device_name",
        "creation_date",
        "modification_date",
        "last_position_at",
        "last_position",
        "location_count",
        "battery_level",
        "competitor_count",
    )
    actions = ["clean_positions"]
    search_fields = ("aid",)
    inlines = [
        DeviceCompetitorInline,
    ]
    list_filter = (
        IsGPXFilter,
        ModifiedDateFilter,
        HasCompetitorFilter,
        HasLocationFilter,
    )
    show_full_result_count = False

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

    def last_position_at(self, obj):
        return obj._last_location_datetime

    location_count.admin_order_field = "_location_count"
    competitor_count.admin_order_field = "competitor_count"
    last_position_at.admin_order_field = "_last_location_datetime"

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
    )
    list_filter = ("club",)


class ChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "creation_date",
        "event",
        "ip_address",
        "nickname",
        "message",
    )
    list_filter = ("event",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("event")


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


class QueclinkCommandAdmin(admin.ModelAdmin):
    list_display = ("target", "creation_date", "modification_date", "sent")


admin.site.register(ChatMessage, ChatMessageAdmin)
admin.site.register(Club, ClubAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceArchiveReference, DeviceArchiveReferenceAdmin)
admin.site.register(ImeiDevice, ImeiDeviceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Map, MapAdmin)
admin.site.register(SpotDevice, SpotDeviceAdmin)
admin.site.register(SpotFeed, SpotFeedAdmin)
admin.site.register(DeviceClubOwnership, DeviceClubOwnershipAdmin)
admin.site.register(QueclinkCommand, QueclinkCommandAdmin)


class MyUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + (
        "date_joined",
        "has_verified_email",
    )
    actions = [
        "clean_fake_users",
    ]

    def has_verified_email(self, obj):
        return EmailAddress.objects.filter(user=obj, verified=True).exists()

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

ADMIN_COMMAND_LIST = [
    "import_from_gpsseuranta",
    "import_from_livelox",
    "import_from_loggator",
    "import_from_otracker",
    "import_from_sportrec",
    "import_from_tractrac",
]

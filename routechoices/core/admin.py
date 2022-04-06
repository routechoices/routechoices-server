from datetime import timedelta

import arrow
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.paginator import Paginator
from django.db.models import Case, Count, Value, When
from django.db.models.expressions import RawSQL
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from routechoices.core.models import (
    ChatMessage,
    Club,
    Competitor,
    Device,
    DeviceArchiveReference,
    Event,
    ImeiDevice,
    Map,
    MapAssignation,
    Notice,
    SpotDevice,
    SpotFeed,
)
from routechoices.lib.helpers import epoch_to_datetime, get_device_name


class ModifiedDateFilter(admin.SimpleListFilter):
    title = "When Was It Modified"
    parameter_name = "modified"

    def lookups(self, request, model_admin):
        return [
            (None, "Today"),
            ("week", "This Week"),
            ("all", "All"),
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
        if self.value() == "week":
            from_date = arrow.utcnow().shift(weeks=-1).datetime
            return queryset.filter(modification_date__gte=from_date)
        elif self.value():
            return queryset.all()
        return queryset.filter(modification_date__gte=from_date)


class HasLocationFilter(admin.SimpleListFilter):
    title = "Wether It Has Locations"
    parameter_name = "has_locations"

    def lookups(self, request, model_admin):
        return [
            ("has_locations", "With locations"),
            ("has_no_locations", "Without locations"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "has_no_locations":
            return queryset.filter(location_count_sql=0)
        elif self.value():
            return queryset.filter(location_count_sql__gt=0)


class HasCompetitorFilter(admin.SimpleListFilter):
    title = "Wether It Has Competitors"
    parameter_name = "has_competitors"

    def lookups(self, request, model_admin):
        return [
            ("has_competitors", "With competitors"),
            ("has_no_competitors", "Without competitors"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "has_no_competitors":
            return queryset.filter(competitor_count=0)
        elif self.value():
            return queryset.filter(competitor_count__gt=0)


class IsGPXFilter(admin.SimpleListFilter):
    title = "Wether It Is From An External System"
    parameter_name = "is_live"

    def lookups(self, request, model_admin):
        return [
            (None, "Supported Device"),
            ("gpx", "External Device"),
            ("all", "All"),
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
        if self.value() == "gpx":
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
        "shortcut",
    )
    list_filter = ("club", "privacy")
    inlines = [ExtraMapInline, NoticeInline, CompetitorInline]


class DeviceCompetitorInline(admin.TabularInline):
    model = Competitor
    fields = ("event", "name", "short_name", "start_time", "link")
    readonly_fields = ("link",)
    ordering = ("-start_time",)

    def link(self, obj):
        return mark_safe(f'<a href="{obj.event.get_absolute_url()}">View on Site</a>')


class DevicePaginator(Paginator):
    @cached_property
    def count(self):
        qs = self.object_list.all()
        qs.query.annotations.clear()
        qs = qs.annotate(competitor_count=Count("competitor_set")).annotate(
            location_count_sql=Case(
                When(locations_raw="", then=Value(0)),
                default=RawSQL(
                    "json_array_length(locations_raw::json->'timestamps')", ()
                ),
            )
        )
        return qs.count()


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "aid",
        "device_name",
        "creation_date",
        "modification_date",
        "last_position_at",
        "last_position",
        "location_count",
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
            .annotate(
                last_position_at=Case(
                    When(locations_raw="", then=Value("")),
                    default=RawSQL("locations_raw::json->'timestamps'->>-1", ()),
                )
            )
            .annotate(
                location_count_sql=Case(
                    When(locations_raw="", then=Value(0)),
                    default=RawSQL(
                        "json_array_length(locations_raw::json->'timestamps')", ()
                    ),
                )
            )
        )
        return qs

    def get_paginator(
        self, request, queryset, per_page, orphans=0, allow_empty_first_page=True
    ):
        return DevicePaginator(queryset, per_page, orphans, allow_empty_first_page)

    def location_count(self, obj):
        return obj.location_count_sql

    def competitor_count(self, obj):
        return obj.competitor_count

    def last_position_at(self, obj):
        if not obj.last_position_at:
            return None
        return epoch_to_datetime(obj.last_position_at)

    location_count.admin_order_field = "location_count_sql"
    competitor_count.admin_order_field = "competitor_count"
    last_position_at.admin_order_field = "last_position_at"

    def clean_positions(self, request, queryset):
        for obj in queryset:
            obj.remove_duplicates()

    clean_positions.short_description = "Remove duplicate positions from storage"

    def device_name(self, obj):
        return get_device_name(obj.user_agent) or obj.user_agent


class DeviceArchiveReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "creation_date",
        "original",
        "archive",
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


admin.site.register(ChatMessage, ChatMessageAdmin)
admin.site.register(Club, ClubAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceArchiveReference, DeviceArchiveReferenceAdmin)
admin.site.register(ImeiDevice, ImeiDeviceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Map, MapAdmin)
admin.site.register(SpotDevice, SpotDeviceAdmin)
admin.site.register(SpotFeed, SpotFeedAdmin)


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

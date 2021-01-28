from django.contrib import admin
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.db.models.functions import Length

from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    Event,
    ImeiDevice,
    Map,
    Notice,
    MapAssignation,
)


class HasLocationFilter(admin.SimpleListFilter):
    title = 'Wether It Has Locations'
    parameter_name = 'has_locations'

    def lookups(self, request, model_admin):
        return [
            ('has_locations', 'With locations'),
            ('has_no_locations', 'Without locations'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'has_no_locations':
            return queryset.filter(
                locations_raw_length=53
            )
        elif self.value():
            return queryset.filter(
                locations_raw_length__gt=53
            )


class HasCompetitorFilter(admin.SimpleListFilter):
    title = 'Wether It Has Competitors'
    parameter_name = 'has_competitors'

    def lookups(self, request, model_admin):
        return [
            ('has_competitors', 'With competitors'),
            ('has_no_competitors', 'Without competitors'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'has_no_competitors':
            return queryset.filter(
                competitor_count=0
            )
        elif self.value():
            return queryset.filter(
                competitor_count__gt=0
            )


class ClubAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'event_count',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
                event_count=Count('events')
            )

    def event_count(self, obj):
        return obj.event_count

    event_count.admin_order_field = 'event_count'


class ExtraMapInline(admin.TabularInline):
    verbose_name = "Extra Map"
    verbose_name_plural = "Extra Maps"
    model = MapAssignation
    fields = (
        'map',
        'title',
    )


class CompetitorInline(admin.TabularInline):
    model = Competitor
    fields = (
        'device',
        'name',
        'short_name',
        'start_time',
    )


class NoticeInline(admin.TabularInline):
    model = Notice
    fields = (
        'text',
    )


class EventAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'privacy',
        'club',
        'start_date',
    )
    list_filter = ('club', 'privacy')
    inlines = [ExtraMapInline, NoticeInline, CompetitorInline]


class DeviceCompetitorInline(admin.TabularInline):
    model = Competitor
    fields = (
        'event',
        'name',
        'short_name',
        'start_time',
        'link'
    )
    readonly_fields = ('link', )
    ordering = ('-start_time', )

    def link(self, obj):
        return mark_safe(
            f'<a href="{obj.event.get_absolute_url()}">View on Site</a>'
        )


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'aid',
        'creation_date',
        'last_date_viewed',
        'last_position',
        'location_count',
        'competitor_count',
    )
    actions = ['clean_positions']
    search_fields = ('aid', )
    inlines = [DeviceCompetitorInline, ]
    list_filter = (HasCompetitorFilter, HasLocationFilter, )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
                locations_raw_length=Length('locations_raw')
            ).annotate(
                competitor_count=Count('competitor_set')
            )

    def location_count(self, obj):
        return obj.location_count

    def competitor_count(self, obj):
        return obj.competitor_count

    location_count.admin_order_field = 'locations_raw_length'
    competitor_count.admin_order_field = 'competitor_count'

    def clean_positions(self, request, queryset):
        for obj in queryset:
            obj.remove_duplicates()

    clean_positions.short_description = \
        "Remove duplicate positions from storage"


class ImeiDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'imei',
        'device'
    )


class MapAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'club',
        'creation_date',
    )
    list_filter = ('club', )


admin.site.register(Club, ClubAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(ImeiDevice, ImeiDeviceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Map, MapAdmin)

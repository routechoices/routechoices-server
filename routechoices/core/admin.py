from django.contrib import admin
from django.utils.safestring import mark_safe

from routechoices.core.models import (
    Club,
    Competitor,
    Device,
    Event,
    ImeiDevice,
    Map,
    Notice,
)


class ClubAdmin(admin.ModelAdmin):
    list_display = (
        'name',
    )


class CompetitorInline(admin.TabularInline):
    model = Competitor
    fields = (
        'device',
        'name',
        'short_name',
        'start_time',
    )
    list_filter = ('event', 'device', )


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
    inlines = [CompetitorInline, NoticeInline]


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
        return mark_safe(f'<a href="{obj.event.get_absolute_url()}">View on Site</a>')


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'aid',
        'creation_date',
        'last_date_viewed',
        'last_position',
        'location_count',
    )
    actions = ['clean_positions']
    search_fields = ('aid', )
    inlines = [DeviceCompetitorInline, ]

    def get_queryset(self, request):
        return super().get_queryset(request).extra(
            select={'locations_raw_length': 'Length(locations_raw)'}
        )

    def location_count(self, obj):
        return obj.location_count

    location_count.admin_order_field = 'locations_raw_length'

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

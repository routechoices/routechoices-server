from django.contrib import admin

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
        'club',
        'start_date',
    )
    list_filter = ('club', )
    inlines = [CompetitorInline, NoticeInline]


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
    )
    list_filter = ('club', )


admin.site.register(Club, ClubAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(ImeiDevice, ImeiDeviceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Map, MapAdmin)

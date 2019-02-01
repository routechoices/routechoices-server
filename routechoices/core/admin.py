from django.contrib import admin

from routechoices.core.models import Club, Competitor, Device, Event, Map


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


class EventAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'club',
        'start_date',
    )
    list_filter = ('club', )
    inlines = [CompetitorInline, ]


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'aid',
    )


class MapAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'club',
    )
    list_filter = ('club', )


admin.site.register(Club, ClubAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Map, MapAdmin)

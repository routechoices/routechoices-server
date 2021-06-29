from datetime import timedelta
import arrow

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.db.models.functions import Length
from django.utils.timezone import now
from django.db.models.expressions import RawSQL
from django.utils.safestring import mark_safe

from allauth.account.models import EmailAddress
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

NO_LOCATIONS_LENGTH = len(
    '{"timestamps": [], "latitudes": [], "longitudes": []}'
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
                locations_raw_length__lte=NO_LOCATIONS_LENGTH
            )
        elif self.value():
            return queryset.filter(
                locations_raw_length__gt=NO_LOCATIONS_LENGTH
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('map__club')


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
        'shortcut',
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
        return mark_safe(f'<a href="{obj.event.get_absolute_url()}">View on Site</a>')


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'aid',
        'creation_date',
        'last_position_at',
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
            ).annotate(
                last_position_at=RawSQL(
                    "(SELECT REGEXP_MATCHES(locations_raw, 'timestamp:[,\[](\d+)]'))[1]", 
                    ()
                )
            ).annotate(
                location_count_sql=RawSQL(
                    "CHAR_LENGTH(locations_raw) - CHAR_LENGTH(REPLACE(locations_raw, ',', ''))", 
                    ()
                )
            )

    def location_count(self, obj):
        return obj.location_count

    def competitor_count(self, obj):
        return obj.competitor_count

    def last_position_at(self, obj):
        if not obj.last_position_at:
            return None
        return arrow.get(int(obj.last_position_at)).datetime

    location_count.admin_order_field = 'location_count_sql'
    competitor_count.admin_order_field = 'competitor_count'
    last_position_at.admin_order_field = 'last_position_at'

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


class MyUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('has_verified_email', )
    actions = ['clean_fake_users', ]

    def has_verified_email(self, obj):
        return EmailAddress.objects.filter(user=obj, verified=True).exists()

    def clean_fake_users(self, request, queryset):
        two_weeks_ago = now() - timedelta(days=14)
        users = queryset.filter(date_joined__lt=two_weeks_ago)
        for obj in users:
            has_verified_email = EmailAddress.objects.filter(
                user=obj,
                verified=True
            ).exists()
            if not has_verified_email:
                obj.delete()


UserModel = get_user_model()
admin.site.unregister(UserModel)
admin.site.register(UserModel, MyUserAdmin)

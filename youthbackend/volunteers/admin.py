from django.contrib import admin

from .models import Roster, VolunteerAssignment, VolunteerAvailability, VolunteerPosition


class VolunteerAssignmentInline(admin.TabularInline):
    model = VolunteerAssignment
    extra = 0
    autocomplete_fields = ['position', 'person']
    readonly_fields = ['requested_at', 'responded_at']


@admin.register(VolunteerPosition)
class VolunteerPositionAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name']
    autocomplete_fields = ['group']


@admin.register(Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ['event', 'status', 'published_at']
    list_filter = ['status']
    search_fields = ['event__name']
    inlines = [VolunteerAssignmentInline]


@admin.register(VolunteerAssignment)
class VolunteerAssignmentAdmin(admin.ModelAdmin):
    list_display = ['person', 'position', 'roster', 'status', 'call_start']
    list_filter = ['status']
    autocomplete_fields = ['position', 'person', 'group', 'roster']


@admin.register(VolunteerAvailability)
class VolunteerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['person', 'starts_at', 'ends_at']
    autocomplete_fields = ['person']

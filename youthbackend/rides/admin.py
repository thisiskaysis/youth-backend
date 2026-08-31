from django.contrib import admin

from .models import RideRequest


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ['person', 'direction', 'status', 'requested_date', 'assigned_leader']
    list_filter = ['status', 'direction']
    search_fields = ['person__username', 'area']
    autocomplete_fields = ['person', 'assigned_leader', 'event']

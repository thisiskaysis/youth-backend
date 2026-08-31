from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'starts_at', 'status', 'audience_everyone']
    list_filter = ['status', 'audience_everyone']
    search_fields = ['name']
    filter_horizontal = ['audience_groups']

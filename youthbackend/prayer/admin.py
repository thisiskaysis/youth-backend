from django.contrib import admin

from .models import PrayerRequest, PrayerSupport


@admin.register(PrayerRequest)
class PrayerRequestAdmin(admin.ModelAdmin):
    list_display = ['author', 'visibility', 'status', 'is_anonymous', 'created_at']
    list_filter = ['visibility', 'status', 'is_anonymous', 'category']
    search_fields = ['author__username', 'body']
    autocomplete_fields = ['author', 'moderated_by']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PrayerSupport)
class PrayerSupportAdmin(admin.ModelAdmin):
    list_display = ['person', 'prayer_request', 'created_at']
    autocomplete_fields = ['person', 'prayer_request']

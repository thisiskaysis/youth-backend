from django.contrib import admin

from .models import DeviceToken, Notification, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['person', 'push_enabled', 'email_enabled', 'quiet_hours_enabled']
    autocomplete_fields = ['person']


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['person', 'platform', 'is_active', 'updated_at']
    list_filter = ['platform', 'is_active']
    autocomplete_fields = ['person']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['person', 'notification_type', 'channel', 'status', 'scheduled_at', 'sent_at']
    list_filter = ['category', 'channel', 'status']
    search_fields = ['title', 'body', 'person__username']
    autocomplete_fields = ['person']
    readonly_fields = ['created_at', 'updated_at']

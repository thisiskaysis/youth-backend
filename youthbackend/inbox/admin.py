from django.contrib import admin

from .models import InboxMessage


@admin.register(InboxMessage)
class InboxMessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'created_at', 'read_at']
    search_fields = ['sender__username', 'recipient__username', 'body']
    autocomplete_fields = ['sender', 'recipient']
    readonly_fields = ['created_at']

from django.contrib import admin

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'actor', 'action', 'entity_type', 'entity_id']
    list_filter = ['action', 'entity_type']
    search_fields = ['entity_id', 'reason', 'actor__username']
    readonly_fields = [f.name for f in AuditEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

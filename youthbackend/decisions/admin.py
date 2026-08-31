from django.contrib import admin

from .models import Decision, FollowUp


class FollowUpInline(admin.StackedInline):
    model = FollowUp
    extra = 0
    autocomplete_fields = ['assignee', 'assigned_by']


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ['person', 'decision_type', 'occurred_at', 'recorded_by']
    list_filter = ['decision_type']
    search_fields = ['person__username', 'notes']
    autocomplete_fields = ['person', 'event', 'recorded_by']
    inlines = [FollowUpInline]


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ['decision', 'assignee', 'status', 'due_at', 'completed_at']
    list_filter = ['status']
    autocomplete_fields = ['decision', 'assignee', 'assigned_by']

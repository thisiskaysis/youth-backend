from django.contrib import admin

from .models import AttendanceRecord, AttendanceSession


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    readonly_fields = ['person', 'signed_in_at', 'signed_out_at']
    autocomplete_fields = ['person']


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ['event', 'status', 'opened_at', 'closed_at']
    list_filter = ['status']
    inlines = [AttendanceRecordInline]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['person', 'session', 'signed_in_at', 'signed_out_at', 'sign_in_source']
    list_filter = ['sign_in_source', 'sign_out_source']
    autocomplete_fields = ['person']

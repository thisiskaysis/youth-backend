from django.contrib import admin

from .models import FormAssignment, FormDefinition, FormSubmission


class FormAssignmentInline(admin.TabularInline):
    model = FormAssignment
    extra = 0
    autocomplete_fields = ['person']


@admin.register(FormDefinition)
class FormDefinitionAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'created_by']
    list_filter = ['status']
    search_fields = ['title']
    inlines = [FormAssignmentInline]


@admin.register(FormAssignment)
class FormAssignmentAdmin(admin.ModelAdmin):
    list_display = ['person', 'form', 'status', 'due_at']
    list_filter = ['status']
    search_fields = ['person__username', 'form__title']
    autocomplete_fields = ['form', 'person']


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'submitted_by', 'created_at']
    autocomplete_fields = ['assignment', 'submitted_by']

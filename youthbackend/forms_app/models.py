from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class FormDefinition(TimeStampedModel):
    """Deliberately simpler than a full form-builder: a JSON field schema
    rather than a dedicated question/field editor (see VOLUNTEERS/BACKEND
    PLAN docs: "could start simpler than a fully generic form builder")."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        ARCHIVED = 'ARCHIVED', 'Archived'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # e.g. [{"key": "medical_notes", "label": "Medical notes", "type": "text", "required": false}]
    schema = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class FormAssignment(TimeStampedModel):
    class Status(models.TextChoices):
        OUTSTANDING = 'OUTSTANDING', 'Outstanding'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        WAIVED = 'WAIVED', 'Waived'

    form = models.ForeignKey(FormDefinition, on_delete=models.CASCADE, related_name='assignments')
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='form_assignments')
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OUTSTANDING)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['due_at']
        constraints = [
            models.UniqueConstraint(fields=['form', 'person'], name='unique_form_assignment_per_person'),
        ]

    def __str__(self):
        return f'{self.form} -> {self.person} ({self.status})'


class FormSubmission(TimeStampedModel):
    assignment = models.OneToOneField(FormAssignment, on_delete=models.CASCADE, related_name='submission')
    answers = models.JSONField(default=dict, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    def __str__(self):
        return f'Submission for {self.assignment}'

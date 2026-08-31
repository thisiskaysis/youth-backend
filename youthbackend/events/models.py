from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from groups.models import Group


class Event(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        PUBLISHED = 'PUBLISHED', 'Published'
        EXPIRED = 'EXPIRED', 'Expired'
        ARCHIVED = 'ARCHIVED', 'Archived'

    class RunsheetVisibility(models.TextChoices):
        SCHEDULED_VOLUNTEERS = 'SCHEDULED_VOLUNTEERS', 'Scheduled volunteers only'
        ALL_VOLUNTEERS = 'ALL_VOLUNTEERS', 'All volunteers'
        LEADERS_ONLY = 'LEADERS_ONLY', 'Leaders only'

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    banner_image = models.URLField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True)
    registration_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    # Audience targeting: everyone, specific groups, and/or specific school
    # years. Reused as-is by navigation/content/notifications later.
    audience_everyone = models.BooleanField(default=True)
    audience_groups = models.ManyToManyField(Group, blank=True, related_name='targeted_events')
    audience_school_years = models.JSONField(blank=True, default=list, help_text='e.g. [11, 12]')

    # Launch keeps run-of-show planning in an external Google Sheet rather
    # than building a run-sheet editor.
    runsheet_url = models.URLField(blank=True)
    runsheet_visibility = models.CharField(
        max_length=25, choices=RunsheetVisibility.choices, default=RunsheetVisibility.LEADERS_ONLY
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-starts_at']

    def __str__(self):
        return self.name

    def is_visible_to(self, user):
        """Draft/scheduled content is staff-only; published content
        respects audience targeting."""
        if self.status != self.Status.PUBLISHED:
            return user.is_authenticated and (user.is_leader_or_admin or user.is_superuser)
        if self.audience_everyone:
            return True
        if self.audience_school_years and user.school_year in self.audience_school_years:
            return True
        return self.audience_groups.filter(memberships__person=user, memberships__is_active=True).exists()

    def resolve_audience_queryset(self):
        """The reverse of is_visible_to: every active person this event's
        audience settings target, for notification fan-out."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if self.audience_everyone:
            return User.objects.filter(status=User.Status.ACTIVE)

        # Start from "nobody" and OR in only the targeting mechanisms that
        # are actually configured - failing closed if neither is set,
        # rather than accidentally matching everyone.
        query = models.Q(pk__in=[])
        if self.audience_school_years:
            query |= models.Q(school_year__in=self.audience_school_years)
        if self.audience_groups.exists():
            query |= models.Q(
                group_memberships__group__in=self.audience_groups.all(), group_memberships__is_active=True
            )
        return User.objects.filter(query, status=User.Status.ACTIVE).distinct()


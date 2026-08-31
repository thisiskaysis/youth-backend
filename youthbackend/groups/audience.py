"""Shared 'everyone, or these groups/school-years' audience targeting,
reused by content and navigation. Event predates this mixin and keeps its
own inline copy of the identical logic - deliberately left alone to avoid
an unrelated migration/refactor risk (see repo memory)."""
from django.db import models


class AudienceTargetMixin(models.Model):
    audience_everyone = models.BooleanField(default=True)
    audience_groups = models.ManyToManyField(
        'groups.Group', blank=True, related_name='%(app_label)s_%(class)s_audience'
    )
    audience_school_years = models.JSONField(blank=True, default=list, help_text='e.g. [11, 12]')

    class Meta:
        abstract = True

    def resolve_audience_queryset(self):
        """Every active person this item's audience settings target, for
        notification fan-out - the reverse of is_in_audience()."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if self.audience_everyone:
            return User.objects.filter(status=User.Status.ACTIVE)

        # Start from "nobody" and OR in only the targeting mechanisms that
        # are actually configured - failing closed rather than accidentally
        # matching everyone.
        query = models.Q(pk__in=[])
        if self.audience_school_years:
            query |= models.Q(school_year__in=self.audience_school_years)
        if self.audience_groups.exists():
            query |= models.Q(
                group_memberships__group__in=self.audience_groups.all(), group_memberships__is_active=True
            )
        return User.objects.filter(query, status=User.Status.ACTIVE).distinct()

    def is_in_audience(self, user):
        if self.audience_everyone:
            return True
        if self.audience_school_years and user.school_year in self.audience_school_years:
            return True
        return self.audience_groups.filter(memberships__person=user, memberships__is_active=True).exists()

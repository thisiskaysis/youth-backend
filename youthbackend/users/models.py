import secrets

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def generate_qr_token():
    # High-entropy opaque token; never derived from the DB primary key and
    # carries no personal data, so it is safe to render as a QR code.
    return secrets.token_urlsafe(32)


class User(AbstractUser):
    class Role(models.TextChoices):
        YOUTH = 'YOUTH', 'Youth'
        LEADER = 'LEADER', 'Leader'
        PASTOR = 'PASTOR', 'Pastor'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        ARCHIVED = 'ARCHIVED', 'Archived'

    email = models.EmailField(unique=True, blank=True, null=True)
    profile_image = models.URLField(blank=True, null=True)

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.YOUTH)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    date_of_birth = models.DateField(blank=True, null=True)
    school_year = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text='High school year, e.g. 7-12.',
    )
    phone_number = models.CharField(max_length=32, blank=True)

    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_phone = models.CharField(max_length=32, blank=True)
    guardian_email = models.EmailField(blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)

    is_provisional = models.BooleanField(
        default=False,
        help_text='True for first-time-visitor profiles created at check-in without a full account.',
    )
    qr_token = models.CharField(max_length=64, unique=True, default=generate_qr_token, editable=False)

    def save(self, *args, **kwargs):
        # Store blank emails as NULL so multiple provisional/no-email
        # profiles don't collide against the unique constraint.
        if not self.email:
            self.email = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    @property
    def is_leader_or_pastor(self):
        return self.role in (self.Role.LEADER, self.Role.PASTOR)



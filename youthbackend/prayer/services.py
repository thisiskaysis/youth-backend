from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from inbox.services import send_message
from notifications.catalog import Category, NotificationType
from notifications.services import notify_many

from .models import PrayerRequest

User = get_user_model()


class PrayerError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def staff_users():
    return User.objects.filter(role__in=[User.Role.LEADER, User.Role.PASTOR])


def create_request(*, author, body, category='', location='', visibility=PrayerRequest.Visibility.LEADERS_ONLY, is_anonymous=False):
    prayer_request = PrayerRequest.objects.create(
        author=author, body=body, category=category, location=location,
        visibility=visibility, is_anonymous=is_anonymous,
    )
    if prayer_request.visibility == PrayerRequest.Visibility.LEADERS_ONLY:
        notify_many(
            staff_users(), Category.LEADER_PRAYER, NotificationType.PRIVATE_PRAYER_NEW,
            title='New leaders-only prayer request',
            body='A private prayer request needs review.',
            deep_link_type='prayer_request', deep_link_id=prayer_request.id,
            data={'prayer_request_id': prayer_request.id},
        )
    return prayer_request


@transaction.atomic
def moderate(prayer_request, actor, new_status, note=''):
    if new_status not in PrayerRequest.Status.values:
        raise PrayerError('INVALID_STATUS', 'Not a recognised moderation status.')

    prayer_request.status = new_status
    prayer_request.moderated_by = actor
    prayer_request.moderated_at = timezone.now()
    prayer_request.moderation_note = note
    prayer_request.save()

    if new_status == PrayerRequest.Status.ESCALATED:
        notify_many(
            User.objects.filter(role=User.Role.PASTOR), Category.LEADER_PRAYER, NotificationType.PRAYER_ESCALATED,
            title='Prayer request escalated',
            body='A prayer request has been escalated and needs pastoral attention.',
            deep_link_type='prayer_request', deep_link_id=prayer_request.id,
            data={'prayer_request_id': prayer_request.id}, urgent=True,
        )
    return prayer_request


def respond(prayer_request, actor, body):
    message = send_message(
        sender=actor, recipient=prayer_request.author, body=body,
        related_type='prayer_request', related_id=prayer_request.id,
        category=Category.PRAYER, notification_type=NotificationType.PRAYER_RESPONSE_AVAILABLE,
        notify_title='A leader has responded to your prayer request',
    )
    return message


def toggle_support(prayer_request, person):
    from .models import PrayerSupport

    support, created = PrayerSupport.objects.get_or_create(prayer_request=prayer_request, person=person)
    if not created:
        support.delete()
        return False
    return True

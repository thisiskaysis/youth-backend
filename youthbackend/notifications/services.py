"""Central entry point for creating notifications. Other domains should
call notify()/notify_many() rather than writing Notification rows
directly, so preference/quiet-hours/channel-eligibility logic - and any
future queueing - lives in exactly one place.
"""
from django.core.mail import send_mail
from django.utils import timezone

from .backends import get_push_backend
from .models import DeviceToken, Notification, NotificationPreference


def get_or_create_preference(person):
    preference, _ = NotificationPreference.objects.get_or_create(person=person)
    return preference


def _resolve_send_time(preference, scheduled_at, urgent):
    send_at = scheduled_at or timezone.now()
    if urgent or not preference.is_quiet_now(send_at):
        return send_at
    # Defer non-urgent sends to the end of the quiet-hours window rather
    # than firing overnight.
    local = timezone.localtime(send_at)
    deferred = local.replace(
        hour=preference.quiet_hours_end.hour,
        minute=preference.quiet_hours_end.minute,
        second=0,
        microsecond=0,
    )
    if deferred <= local:
        deferred += timezone.timedelta(days=1)
    return deferred


def notify(
    person, category, notification_type, title, body='',
    deep_link_type='', deep_link_id='', data=None, scheduled_at=None, urgent=False,
):
    """Create the eligible channel row(s) for one recipient, respecting
    their preferences and quiet hours. Immediate (non-future) sends are
    dispatched synchronously - fine at this scale; move to a queue only
    once bulk sends actually appear (see NOTIFICATIONS.xlsx sheet 09).
    Returns the Notification rows created (may be empty if the recipient
    has disabled every channel for this category).
    """
    preference = get_or_create_preference(person)
    channels = preference.channels_for(category)
    send_at = _resolve_send_time(preference, scheduled_at, urgent)

    created = []
    for channel, enabled in (
        (Notification.Channel.PUSH, channels['push']),
        (Notification.Channel.EMAIL, channels['email']),
    ):
        if not enabled:
            continue
        created.append(Notification.objects.create(
            person=person,
            category=category,
            notification_type=notification_type,
            channel=channel,
            title=title,
            body=body,
            deep_link_type=deep_link_type,
            deep_link_id=str(deep_link_id) if deep_link_id else '',
            data=data or {},
            scheduled_at=send_at,
        ))

    if send_at <= timezone.now():
        dispatch_due_notifications(person=person)
    return created


def notify_many(people, *args, **kwargs):
    results = []
    for person in people:
        results.extend(notify(person, *args, **kwargs))
    return results


def dispatch_due_notifications(person=None, now=None):
    """Send every PENDING notification whose scheduled_at has passed.
    Called synchronously by notify() for immediate sends, and by the
    `send_due_notifications` management command for anything scheduled -
    safe to call repeatedly/on an interval."""
    now = now or timezone.now()
    queryset = Notification.objects.filter(status=Notification.Status.PENDING, scheduled_at__lte=now)
    if person is not None:
        queryset = queryset.filter(person=person)

    push_backend = get_push_backend()
    sent = 0
    for notification in queryset.select_related('person'):
        try:
            if notification.channel == Notification.Channel.PUSH:
                _dispatch_push(notification, push_backend)
            else:
                _dispatch_email(notification)
        except Exception as exc:  # provider/network errors must not crash the caller
            notification.status = Notification.Status.FAILED
            notification.error_message = str(exc)[:500]
            notification.save(update_fields=['status', 'error_message'])
            continue
        sent += 1
    return sent


def _dispatch_push(notification, backend):
    tokens = list(
        DeviceToken.objects.filter(person_id=notification.person_id, is_active=True).values_list('token', flat=True)
    )
    if not tokens:
        notification.status = Notification.Status.SKIPPED
        notification.error_message = 'No active device tokens.'
        notification.save(update_fields=['status', 'error_message'])
        return

    backend.send(
        tokens=tokens,
        title=notification.title,
        body=notification.body,
        data={
            'type': notification.notification_type,
            'deep_link_type': notification.deep_link_type,
            'deep_link_id': notification.deep_link_id,
            **notification.data,
        },
    )
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=['status', 'sent_at'])


def _dispatch_email(notification):
    person = notification.person
    if not person.email:
        notification.status = Notification.Status.SKIPPED
        notification.error_message = 'No email address on file.'
        notification.save(update_fields=['status', 'error_message'])
        return

    send_mail(
        subject=notification.title,
        message=notification.body,
        from_email=None,
        recipient_list=[person.email],
        fail_silently=False,
    )
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=['status', 'sent_at'])

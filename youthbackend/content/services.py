"""Content lifecycle logic. Publishing/expiry state transitions live here
so both the API action and the scheduled command share one implementation.
"""
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications.catalog import Category, NotificationType
from notifications.services import notify_many

from .models import ContentItem

User = get_user_model()


def publish(content_item):
    now = timezone.now()
    if content_item.publish_at and content_item.publish_at > now:
        content_item.status = ContentItem.Status.SCHEDULED
    else:
        content_item.status = ContentItem.Status.PUBLISHED
    content_item.save(update_fields=['status'])
    return content_item


def process_scheduled():
    """Flip SCHEDULED->PUBLISHED and PUBLISHED->EXPIRED as their windows
    are crossed. Called by `publish_scheduled_content` on a cron interval."""
    now = timezone.now()
    published = 0
    failed = 0

    due_to_publish = ContentItem.objects.filter(status=ContentItem.Status.SCHEDULED, publish_at__lte=now)
    for item in due_to_publish:
        try:
            item.status = ContentItem.Status.PUBLISHED
            item.save(update_fields=['status'])
            published += 1
        except Exception as exc:
            failed += 1
            notify_many(
                User.objects.filter(role__in=[User.Role.LEADER, User.Role.ADMIN]),
                Category.LEADER_CMS, NotificationType.CONTENT_PUBLISH_FAILED,
                title=f'Failed to publish: {item.title}',
                body=str(exc)[:200],
                deep_link_type='content_item', deep_link_id=item.id,
                data={'content_item_id': item.id}, urgent=True,
            )

    expired = ContentItem.objects.filter(
        status=ContentItem.Status.PUBLISHED, expire_at__lte=now
    ).update(status=ContentItem.Status.EXPIRED)

    return {'published': published, 'expired': expired, 'failed': failed}

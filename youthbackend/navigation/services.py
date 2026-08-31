"""Navigation lifecycle logic - same publish/expire pattern as content."""
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications.catalog import Category, NotificationType
from notifications.services import notify_many

from .models import NavigationItem

User = get_user_model()


def publish(nav_item):
    now = timezone.now()
    if nav_item.publish_at and nav_item.publish_at > now:
        nav_item.status = NavigationItem.Status.SCHEDULED
    else:
        nav_item.status = NavigationItem.Status.PUBLISHED
    nav_item.save(update_fields=['status'])
    return nav_item


def process_scheduled():
    now = timezone.now()
    published = 0
    failed = 0

    due_to_publish = NavigationItem.objects.filter(status=NavigationItem.Status.SCHEDULED, publish_at__lte=now)
    for item in due_to_publish:
        try:
            item.status = NavigationItem.Status.PUBLISHED
            item.save(update_fields=['status'])
            published += 1
        except Exception as exc:
            failed += 1
            notify_many(
                User.objects.filter(role__in=[User.Role.LEADER, User.Role.PASTOR]),
                Category.LEADER_CMS, NotificationType.CONTENT_PUBLISH_FAILED,
                title=f'Failed to publish navigation item: {item.label}',
                body=str(exc)[:200],
                deep_link_type='navigation_item', deep_link_id=item.id,
                data={'navigation_item_id': item.id}, urgent=True,
            )

    expired = NavigationItem.objects.filter(
        status=NavigationItem.Status.PUBLISHED, expire_at__lte=now
    ).update(status=NavigationItem.Status.EXPIRED)

    return {'published': published, 'expired': expired, 'failed': failed}

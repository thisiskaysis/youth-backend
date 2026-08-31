"""Sending an inbox message always goes through send_message() so the
paired notification is never forgotten and other domains (e.g. prayer
responses) can reuse it with a more specific notification category/type."""
from notifications.catalog import Category, NotificationType
from notifications.services import notify

from .models import InboxMessage


def send_message(
    *, sender, recipient, body, related_type='', related_id='',
    category=Category.INBOX, notification_type=NotificationType.MESSAGE_RECEIVED, notify_title=None,
):
    message = InboxMessage.objects.create(
        sender=sender, recipient=recipient, body=body,
        related_type=related_type, related_id=str(related_id) if related_id else '',
    )
    notify(
        recipient, category, notification_type,
        title=notify_title or f'New message from {sender}',
        body=body[:140],
        deep_link_type='inbox_message', deep_link_id=message.id,
        data={'message_id': message.id},
    )
    return message

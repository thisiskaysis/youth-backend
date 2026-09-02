"""Sending an inbox message always goes through send_message() so the
paired notification is never forgotten and other domains (e.g. prayer
responses) can reuse it with a more specific notification category/type."""
from django.contrib.auth import get_user_model
from django.db import models

from notifications.catalog import Category, NotificationType
from notifications.services import notify

from .models import InboxMessage

User = get_user_model()


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
        # deep_link_id is the *other participant's* user id (not the message
        # id) so the frontend can jump straight to `/inbox/<id>`.
        deep_link_type='inbox_message', deep_link_id=sender.id,
        data={'message_id': message.id},
    )
    return message


def get_contactable_people_queryset(user):
    """Who `user` may start a *new* Inbox conversation with.

    Leaders/Admins may message anyone. Everyone else may only start a
    conversation with a Leader/Admin of a group they're an active member
    of - see `has_existing_conversation()` for replying to someone
    outside that scope (e.g. a prayer response from an unconnected
    leader), which is always allowed regardless of this scoping.
    """
    if user.is_leader_or_admin or user.is_superuser:
        return User.objects.exclude(pk=user.pk)

    from groups.models import GroupMembership

    my_group_ids = GroupMembership.objects.filter(
        person=user, is_active=True,
    ).values_list('group_id', flat=True)
    leader_ids = GroupMembership.objects.filter(
        group_id__in=my_group_ids,
        membership_role=GroupMembership.MembershipRole.LEADER,
        is_active=True,
    ).values_list('person_id', flat=True)
    return User.objects.filter(id__in=leader_ids)


def has_existing_conversation(user_a, user_b):
    return InboxMessage.objects.filter(
        models.Q(sender=user_a, recipient=user_b) | models.Q(sender=user_b, recipient=user_a)
    ).exists()


def list_conversations(user):
    """One entry per person `user` has exchanged messages with, newest
    conversation first with an unread count - the Inbox's DM-list view."""
    messages = (
        InboxMessage.objects.filter(models.Q(sender=user) | models.Q(recipient=user))
        .select_related('sender', 'recipient')
        .order_by('-created_at')
    )

    conversations = {}
    for message in messages:
        other = message.recipient if message.sender_id == user.id else message.sender
        # Messages are walked newest-first, so the first time we see a
        # given counterpart is already their most recent message.
        entry = conversations.setdefault(other.id, {
            'participant': other, 'last_message': message, 'unread_count': 0,
        })
        if message.recipient_id == user.id and message.read_at is None:
            entry['unread_count'] += 1
    return sorted(conversations.values(), key=lambda entry: entry['last_message'].created_at, reverse=True)

from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.pagination import StandardResultsSetPagination
from users.serializers import UserBasicSerializer
from .models import InboxMessage
from .serializers import ConversationSerializer, InboxMessageSerializer, SendMessageInputSerializer
from .services import get_contactable_people_queryset, has_existing_conversation, list_conversations, send_message

User = get_user_model()


class InboxMessageViewSet(viewsets.ModelViewSet):
    """A proper two-way inbox: anyone may reply within a conversation
    they're already part of, and may start a new one with whoever
    `get_contactable_people_queryset()` allows for their role (see
    services.py). Reading is open to anyone for their own sent/received
    messages."""

    serializer_class = InboxMessageSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        queryset = InboxMessage.objects.filter(
            models.Q(recipient=user) | models.Q(sender=user)
        ).select_related('sender', 'recipient')

        other_id = self.request.query_params.get('with')
        if other_id:
            # A single conversation thread reads oldest-first, like a chat.
            queryset = queryset.filter(
                models.Q(sender_id=other_id) | models.Q(recipient_id=other_id)
            ).order_by('created_at')
        return queryset

    def list(self, request, *args, **kwargs):
        other_id = request.query_params.get('with')
        if other_id:
            # Opening a thread marks the other person's messages read.
            InboxMessage.objects.filter(
                sender_id=other_id, recipient=request.user, read_at__isnull=True
            ).update(read_at=timezone.now())
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = SendMessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = request.user
        recipient = get_object_or_404(User, pk=serializer.validated_data['recipient_id'])
        if recipient.pk == sender.pk:
            raise PermissionDenied("You can't message yourself.")
        if not (
            get_contactable_people_queryset(sender).filter(pk=recipient.pk).exists()
            or has_existing_conversation(sender, recipient)
        ):
            raise PermissionDenied('You are not authorised to message this person.')

        message = send_message(sender=sender, recipient=recipient, body=serializer.validated_data['body'])
        return Response(InboxMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        message = self.get_object()
        if message.recipient_id != request.user.id:
            raise PermissionDenied('Only the recipient can mark this message read.')
        if not message.read_at:
            message.read_at = timezone.now()
            message.save(update_fields=['read_at'])
        return Response(InboxMessageSerializer(message).data)

    @action(detail=False, methods=['get'], url_path='conversations')
    def conversations(self, request):
        """The Inbox's DM-list view: one row per person messaged, newest
        conversation first."""
        conversations = list_conversations(request.user)
        serializer = ConversationSerializer(conversations, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='contacts')
    def contacts(self, request):
        """Who the requester may start a new conversation with."""
        queryset = get_contactable_people_queryset(request.user)

        query = request.query_params.get('q')
        if query:
            queryset = queryset.filter(
                models.Q(first_name__icontains=query) | models.Q(last_name__icontains=query)
                | models.Q(email__icontains=query) | models.Q(username__icontains=query)
            )
        queryset = queryset.order_by('first_name', 'last_name').distinct()

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = UserBasicSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

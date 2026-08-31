from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.permissions import IsLeaderOrPastor
from users.permissions import get_manageable_people_queryset
from .models import InboxMessage
from .serializers import InboxMessageSerializer, SendMessageInputSerializer
from .services import send_message

User = get_user_model()


class InboxMessageViewSet(viewsets.ModelViewSet):
    """Sending is Leader/Pastor-only and scoped to people they're
    authorised to contact (same scope as people search/management).
    Reading is open to anyone for their own sent/received messages."""

    serializer_class = InboxMessageSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [IsLeaderOrPastor()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        return InboxMessage.objects.filter(
            models.Q(recipient=user) | models.Q(sender=user)
        ).select_related('sender', 'recipient')

    def create(self, request, *args, **kwargs):
        serializer = SendMessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient = get_object_or_404(User, pk=serializer.validated_data['recipient_id'])
        if not get_manageable_people_queryset(request.user).filter(pk=recipient.pk).exists():
            raise PermissionDenied('You are not authorised to message this person.')

        message = send_message(sender=request.user, recipient=recipient, body=serializer.validated_data['body'])
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

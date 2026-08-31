from rest_framework import serializers

from users.serializers import UserBasicSerializer
from .models import InboxMessage


class InboxMessageSerializer(serializers.ModelSerializer):
    sender = UserBasicSerializer(read_only=True)
    recipient = UserBasicSerializer(read_only=True)

    class Meta:
        model = InboxMessage
        fields = [
            'id', 'sender', 'recipient', 'body', 'read_at',
            'related_type', 'related_id', 'created_at',
        ]
        read_only_fields = fields


class SendMessageInputSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    body = serializers.CharField(allow_blank=False)

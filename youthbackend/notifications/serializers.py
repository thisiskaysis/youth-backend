from rest_framework import serializers

from .models import DeviceToken, Notification, NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'push_enabled', 'email_enabled',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'category_overrides',
        ]


class DeviceTokenSerializer(serializers.ModelSerializer):
    # Declared explicitly (rather than auto-generated) so DRF does not add
    # its default UniqueValidator - re-registering an existing token is a
    # normal upsert (see DeviceTokenViewSet.perform_create), not an error.
    token = serializers.CharField(max_length=255)

    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'platform', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'category', 'notification_type', 'channel', 'title', 'body',
            'deep_link_type', 'deep_link_id', 'data', 'status',
            'scheduled_at', 'sent_at', 'read_at',
        ]
        read_only_fields = fields

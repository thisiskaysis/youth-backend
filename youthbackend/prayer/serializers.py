from rest_framework import serializers

from users.serializers import UserBasicSerializer
from .models import PrayerRequest


class PrayerRequestSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    prayed_count = serializers.SerializerMethodField()
    prayed_by_me = serializers.SerializerMethodField()

    class Meta:
        model = PrayerRequest
        fields = [
            'id', 'body', 'category', 'location', 'visibility', 'is_anonymous',
            'status', 'author', 'prayed_count', 'prayed_by_me', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'author', 'prayed_count', 'prayed_by_me', 'created_at']

    def get_author(self, obj):
        if obj.is_anonymous:
            return None
        return UserBasicSerializer(obj.author).data

    def get_prayed_count(self, obj):
        return obj.supporters.count()

    def get_prayed_by_me(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.supporters.filter(person=request.user).exists()


class PrayerModerationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PrayerRequest.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default='')


class PrayerRespondSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=False)

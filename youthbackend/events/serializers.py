from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'banner_image', 'starts_at', 'ends_at',
            'location', 'registration_url', 'status',
            'audience_everyone', 'audience_groups', 'audience_school_years',
            'runsheet_url', 'runsheet_visibility',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

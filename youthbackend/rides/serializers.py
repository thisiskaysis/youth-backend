from rest_framework import serializers

from users.serializers import UserBasicSerializer
from .models import RideRequest


class RideRequestSerializer(serializers.ModelSerializer):
    person = UserBasicSerializer(read_only=True)
    assigned_leader = UserBasicSerializer(read_only=True)

    class Meta:
        model = RideRequest
        fields = [
            'id', 'person', 'event', 'requested_date', 'direction', 'area', 'notes',
            'status', 'assigned_leader', 'created_at',
        ]
        read_only_fields = ['id', 'person', 'status', 'assigned_leader', 'created_at']


class RideRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = ['event', 'requested_date', 'direction', 'area', 'notes']


class RideRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = ['status', 'assigned_leader', 'notes']

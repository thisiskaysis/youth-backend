from django.contrib.auth import get_user_model
from rest_framework import serializers

from events.models import Event
from users.serializers import UserBasicSerializer
from .models import Roster, VolunteerAssignment, VolunteerAvailability, VolunteerPosition

User = get_user_model()


class VolunteerPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VolunteerPosition
        fields = ['id', 'group', 'name', 'is_active', 'sort_order']
        read_only_fields = ['id']


class RosterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Roster
        fields = ['id', 'event', 'status', 'published_at']
        read_only_fields = fields


class VolunteerAssignmentSerializer(serializers.ModelSerializer):
    person = UserBasicSerializer(read_only=True)
    position_name = serializers.CharField(source='position.name', read_only=True)

    class Meta:
        model = VolunteerAssignment
        fields = [
            'id', 'roster', 'group', 'position', 'position_name', 'person',
            'status', 'call_start', 'call_end', 'notes',
            'requested_at', 'responded_at', 'decline_reason', 'decline_note',
        ]
        read_only_fields = [
            'id', 'roster', 'group', 'person', 'status',
            'requested_at', 'responded_at', 'decline_reason', 'decline_note',
        ]


class VolunteerAssignmentUpdateSerializer(serializers.ModelSerializer):
    """Only what a roster manager may change with a plain PATCH - status
    transitions always go through the dedicated respond/publish/cancel
    actions so the state machine can't be bypassed."""

    class Meta:
        model = VolunteerAssignment
        fields = ['position', 'call_start', 'call_end', 'notes']


class AssignVolunteerInputSerializer(serializers.Serializer):
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    position = serializers.PrimaryKeyRelatedField(queryset=VolunteerPosition.objects.all())
    person = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    call_start = serializers.DateTimeField(required=False, allow_null=True)
    call_end = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    add_to_group = serializers.BooleanField(required=False, default=False)


class PublishRequestsInputSerializer(serializers.Serializer):
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    assignment_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class RespondInputSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    decline_reason = serializers.CharField(required=False, allow_blank=True, default='')
    decline_note = serializers.CharField(required=False, allow_blank=True, default='')


class VolunteerAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = VolunteerAvailability
        fields = ['id', 'starts_at', 'ends_at', 'note']
        read_only_fields = ['id']

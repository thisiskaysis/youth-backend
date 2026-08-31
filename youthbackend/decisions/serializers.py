from django.contrib.auth import get_user_model
from rest_framework import serializers

from users.serializers import UserBasicSerializer
from .models import Decision, FollowUp

User = get_user_model()


class FollowUpSerializer(serializers.ModelSerializer):
    assignee = UserBasicSerializer(read_only=True)

    class Meta:
        model = FollowUp
        fields = ['id', 'decision', 'assignee', 'status', 'due_at', 'completed_at', 'notes']
        read_only_fields = ['id', 'decision', 'assignee', 'status', 'completed_at']


class DecisionSerializer(serializers.ModelSerializer):
    person = UserBasicSerializer(read_only=True)
    recorded_by = UserBasicSerializer(read_only=True)
    follow_up = serializers.SerializerMethodField()

    class Meta:
        model = Decision
        fields = [
            'id', 'person', 'event', 'decision_type', 'occurred_at', 'notes',
            'recorded_by', 'follow_up', 'created_at',
        ]
        read_only_fields = fields

    def get_follow_up(self, obj):
        follow_up = getattr(obj, 'follow_up', None)
        return FollowUpSerializer(follow_up).data if follow_up else None


class DecisionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = ['person', 'event', 'decision_type', 'occurred_at', 'notes']


class AssignFollowUpInputSerializer(serializers.Serializer):
    # Follow-up is staff accountability, not peer/youth assignment.
    assignee_id = serializers.PrimaryKeyRelatedField(
        source='assignee', queryset=User.objects.filter(role__in=[User.Role.LEADER, User.Role.PASTOR])
    )
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class UpdateFollowUpStatusInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=FollowUp.Status.choices)
    notes = serializers.CharField(required=False, allow_blank=True)

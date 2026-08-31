from django.contrib.auth import get_user_model
from rest_framework import serializers

from users.serializers import UserBasicSerializer
from .models import Group, GroupMembership

User = get_user_model()


class GroupMembershipSerializer(serializers.ModelSerializer):
    person = UserBasicSerializer(read_only=True)
    person_id = serializers.PrimaryKeyRelatedField(
        source='person', queryset=User.objects.all(), write_only=True
    )

    class Meta:
        model = GroupMembership
        fields = ['id', 'group', 'person', 'person_id', 'membership_role', 'is_active', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    leader_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'group_type', 'description', 'schedule', 'location',
            'is_active', 'member_count', 'leader_count', 'created_at', 'updated_at',
        ]

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def get_leader_count(self, obj):
        return obj.memberships.filter(
            is_active=True, membership_role=GroupMembership.MembershipRole.LEADER
        ).count()


class GroupDetailSerializer(GroupSerializer):
    memberships = GroupMembershipSerializer(many=True, read_only=True)

    class Meta(GroupSerializer.Meta):
        fields = GroupSerializer.Meta.fields + ['memberships']

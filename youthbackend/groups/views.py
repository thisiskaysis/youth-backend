from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.audit import log_audit
from core.permissions import IsLeaderOrPastor
from .models import Group, GroupMembership
from .permissions import CanManageGroup, user_leads_group
from .serializers import GroupDetailSerializer, GroupMembershipSerializer, GroupSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    permission_classes = [CanManageGroup]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GroupDetailSerializer
        return GroupSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        group_type = self.request.query_params.get('type')
        if group_type:
            qs = qs.filter(group_type=group_type.upper())
        return qs

    @action(detail=False, methods=['get'], url_path='mine')
    def mine(self, request):
        """Groups the current user belongs to - "My Groups"."""
        memberships = GroupMembership.objects.filter(
            person=request.user, is_active=True
        ).select_related('group')
        groups = [m.group for m in memberships]
        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data)


class GroupMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMembershipSerializer
    permission_classes = [IsLeaderOrPastor]

    def get_queryset(self):
        qs = GroupMembership.objects.select_related('group', 'person')
        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs

    def perform_create(self, serializer):
        group = serializer.validated_data['group']
        if not user_leads_group(self.request.user, group):
            raise PermissionDenied('You do not manage this group.')
        membership = serializer.save()
        log_audit(actor=self.request.user, action='group.membership_added', entity=membership)

    def perform_destroy(self, instance):
        if not user_leads_group(self.request.user, instance.group):
            raise PermissionDenied('You do not manage this group.')
        # Soft-remove so membership history remains traceable.
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        log_audit(actor=self.request.user, action='group.membership_removed', entity=instance)

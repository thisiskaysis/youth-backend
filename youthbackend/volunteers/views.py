from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsLeaderOrAdmin
from events.models import Event
from groups.models import Group, GroupMembership
from groups.permissions import user_leads_group
from notifications.catalog import Category, NotificationType
from notifications.services import notify
from .models import Roster, VolunteerAssignment, VolunteerAvailability, VolunteerPosition
from .serializers import (
    AssignVolunteerInputSerializer,
    PublishRequestsInputSerializer,
    RespondInputSerializer,
    RosterSerializer,
    VolunteerAssignmentSerializer,
    VolunteerAssignmentUpdateSerializer,
    VolunteerAvailabilitySerializer,
    VolunteerPositionSerializer,
)
from .services import (
    VolunteerError,
    assign_draft,
    cancel_assignment,
    find_conflicts,
    get_or_create_roster,
    publish_requests,
    respond,
)

User = get_user_model()


def _manageable_group_ids(user):
    if user.role == User.Role.ADMIN or user.is_superuser:
        return Group.objects.values_list('id', flat=True)
    return GroupMembership.objects.filter(
        person=user, membership_role=GroupMembership.MembershipRole.LEADER, is_active=True
    ).values_list('group_id', flat=True)


class EventRosterView(APIView):
    """Get-or-create the (single, launch-model) roster container for an
    event - clients only ever deal in event ids, never roster ids."""

    permission_classes = [IsLeaderOrAdmin]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)
        roster = get_or_create_roster(event, request.user)
        return Response(RosterSerializer(roster).data)


class VolunteerPositionViewSet(viewsets.ModelViewSet):
    serializer_class = VolunteerPositionSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated()]
        return [IsLeaderOrAdmin()]

    def get_queryset(self):
        qs = VolunteerPosition.objects.select_related('group')
        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs

    def perform_create(self, serializer):
        group = serializer.validated_data['group']
        if not user_leads_group(self.request.user, group):
            raise PermissionDenied('You do not manage this team.')
        serializer.save()

    def perform_update(self, serializer):
        if not user_leads_group(self.request.user, serializer.instance.group):
            raise PermissionDenied('You do not manage this team.')
        serializer.save()

    def perform_destroy(self, instance):
        if not user_leads_group(self.request.user, instance.group):
            raise PermissionDenied('You do not manage this team.')
        # Soft-remove: past assignments may already reference this position.
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class VolunteerAvailabilityViewSet(viewsets.ModelViewSet):
    """Every volunteer manages only their own availability."""

    serializer_class = VolunteerAvailabilitySerializer

    def get_queryset(self):
        return VolunteerAvailability.objects.filter(person=self.request.user)

    def perform_create(self, serializer):
        serializer.save(person=self.request.user)


class VolunteerAssignmentViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'respond_action'):
            return [IsAuthenticated()]
        return [IsLeaderOrAdmin()]

    def get_serializer_class(self):
        if self.action == 'create':
            return AssignVolunteerInputSerializer
        if self.action in ('update', 'partial_update'):
            return VolunteerAssignmentUpdateSerializer
        return VolunteerAssignmentSerializer

    def get_queryset(self):
        qs = VolunteerAssignment.objects.select_related('position', 'person', 'group', 'roster__event')
        event_id = self.request.query_params.get('event')
        if event_id:
            qs = qs.filter(roster__event_id=event_id)

        user = self.request.user
        if user.role == User.Role.ADMIN or user.is_superuser:
            return qs
        led_group_ids = GroupMembership.objects.filter(
            person=user, membership_role=GroupMembership.MembershipRole.LEADER, is_active=True
        ).values_list('group_id', flat=True)
        # Leaders see their team's roster rows; everyone always sees their
        # own assignments regardless of role - this doubles as "My Serving".
        return qs.filter(models.Q(group_id__in=led_group_ids) | models.Q(person=user)).distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        position = data['position']

        if not user_leads_group(request.user, position.group):
            raise PermissionDenied('You do not manage this team.')

        roster = get_or_create_roster(data['event'], request.user)
        try:
            assignment = assign_draft(
                roster=roster, position=position, person=data['person'], actor=request.user,
                call_start=data.get('call_start'), call_end=data.get('call_end'),
                notes=data.get('notes', ''), add_to_group=data.get('add_to_group', False),
            )
        except VolunteerError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)

        conflicts = find_conflicts(
            data['person'], assignment.call_start, assignment.call_end, exclude_assignment_id=assignment.id
        )
        return Response({
            'assignment': VolunteerAssignmentSerializer(assignment).data,
            'conflicts': VolunteerAssignmentSerializer(conflicts, many=True).data,
        }, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        assignment = self.get_object()
        if not user_leads_group(self.request.user, assignment.group):
            raise PermissionDenied('You do not manage this team.')
        if assignment.status in (VolunteerAssignment.Status.CANCELLED, VolunteerAssignment.Status.COMPLETED):
            raise ValidationError('This assignment can no longer be edited.')

        was_notified = assignment.status in (VolunteerAssignment.Status.PENDING, VolunteerAssignment.Status.ACCEPTED)
        prev_snapshot = (assignment.position_id, assignment.call_start, assignment.call_end)

        updated = serializer.save()

        if was_notified and prev_snapshot != (updated.position_id, updated.call_start, updated.call_end):
            notify(
                updated.person, Category.VOLUNTEER_CHANGES, NotificationType.VOLUNTEER_ASSIGNMENT_CHANGED,
                title=f'Update to your {updated.position.name} assignment',
                body=f'Details for {updated.roster.event.name} have changed - please check the app.',
                deep_link_type='volunteer_assignment', deep_link_id=updated.id,
                data={'assignment_id': updated.id}, urgent=True,
            )

    @action(detail=False, methods=['post'], url_path='publish')
    def publish(self, request):
        serializer = PublishRequestsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.validated_data['event']
        requested_ids = serializer.validated_data.get('assignment_ids')

        roster = get_or_create_roster(event, request.user)
        eligible = roster.assignments.filter(
            status=VolunteerAssignment.Status.DRAFT, group_id__in=_manageable_group_ids(request.user)
        )
        if requested_ids:
            eligible = eligible.filter(id__in=requested_ids)

        published = publish_requests(roster, list(eligible.values_list('id', flat=True)))
        return Response(VolunteerAssignmentSerializer(published, many=True).data)

    @action(detail=True, methods=['post'], url_path='respond')
    def respond_action(self, request, pk=None):
        assignment = self.get_object()
        serializer = RespondInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = respond(assignment, request.user, **serializer.validated_data)
        except VolunteerError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(VolunteerAssignmentSerializer(assignment).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_action(self, request, pk=None):
        assignment = self.get_object()
        if not user_leads_group(request.user, assignment.group):
            raise PermissionDenied('You do not manage this team.')
        try:
            assignment = cancel_assignment(assignment, reason=request.data.get('reason', ''))
        except VolunteerError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(VolunteerAssignmentSerializer(assignment).data)

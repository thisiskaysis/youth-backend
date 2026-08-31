from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.permissions import IsLeaderOrPastor
from .models import Decision, FollowUp
from .serializers import (
    AssignFollowUpInputSerializer,
    DecisionCreateSerializer,
    DecisionSerializer,
    FollowUpSerializer,
    UpdateFollowUpStatusInputSerializer,
)
from .services import FollowUpError, assign_follow_up, create_decision, update_follow_up_status

User = get_user_model()


def _can_manage_follow_up(user, decision):
    """Pastor manages any follow-up. A Leader may (re)assign only if they
    recorded the decision or are the current assignee handing it off -
    matches the docs' "scoped" framing for decisions.follow_up."""
    if user.role == User.Role.PASTOR or user.is_superuser:
        return True
    if decision.recorded_by_id == user.id:
        return True
    follow_up = getattr(decision, 'follow_up', None)
    return bool(follow_up and follow_up.assignee_id == user.id)


class DecisionViewSet(viewsets.ModelViewSet):
    """Highly sensitive pastoral data - Leader/Pastor only, never surfaced
    to the youth it's about. Decisions themselves are append-only from the
    API's point of view; only the follow-up moves after creation."""

    permission_classes = [IsLeaderOrPastor]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return DecisionCreateSerializer
        return DecisionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Decision.objects.select_related('person', 'recorded_by', 'event', 'follow_up__assignee')
        if user.role == User.Role.PASTOR or user.is_superuser:
            return qs
        return qs.filter(models.Q(recorded_by=user) | models.Q(follow_up__assignee=user)).distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = create_decision(recorded_by=request.user, **serializer.validated_data)
        return Response(DecisionSerializer(decision).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='follow-up')
    def follow_up_action(self, request, pk=None):
        decision = self.get_object()
        if not _can_manage_follow_up(request.user, decision):
            raise PermissionDenied('You are not authorised to assign follow-up for this decision.')

        serializer = AssignFollowUpInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        follow_up = assign_follow_up(decision, actor=request.user, **serializer.validated_data)
        return Response(FollowUpSerializer(follow_up).data, status=status.HTTP_201_CREATED)


class FollowUpViewSet(viewsets.ReadOnlyModelViewSet):
    """Every assignee sees their own outstanding follow-ups; Pastors see
    everyone's, for the leadership dashboard."""

    serializer_class = FollowUpSerializer
    permission_classes = [IsLeaderOrPastor]

    def get_queryset(self):
        user = self.request.user
        qs = FollowUp.objects.select_related('decision__person', 'assignee')
        if user.role == User.Role.PASTOR or user.is_superuser:
            return qs
        return qs.filter(assignee=user)

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        follow_up = self.get_object()
        serializer = UpdateFollowUpStatusInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            follow_up = update_follow_up_status(follow_up, request.user, **serializer.validated_data)
        except FollowUpError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FollowUpSerializer(follow_up).data)

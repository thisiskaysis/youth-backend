from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsLeaderOrAdmin
from inbox.serializers import InboxMessageSerializer
from .models import PrayerRequest, PrayerSupport
from .serializers import PrayerModerationSerializer, PrayerRequestSerializer, PrayerRespondSerializer
from .services import PrayerError, create_request, moderate, respond, toggle_support


class PrayerRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PrayerRequestSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('moderate_action',):
            return [IsLeaderOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = PrayerRequest.objects.select_related('author').prefetch_related('supporters')

        if self.request.query_params.get('wall'):
            return qs.filter(visibility=PrayerRequest.Visibility.PUBLIC, status=PrayerRequest.Status.APPROVED)

        # The approved public wall is visible to everyone regardless of
        # role - "pray"/detail access must work for posts you didn't author.
        wall = models.Q(visibility=PrayerRequest.Visibility.PUBLIC, status=PrayerRequest.Status.APPROVED)
        own = models.Q(author=user)

        if user.is_leader_or_admin or user.is_superuser:
            # Moderation/leadership queue: leaders-only and pending/escalated
            # requests, plus the wall and their own.
            return qs.filter(
                wall
                | own
                | models.Q(visibility=PrayerRequest.Visibility.LEADERS_ONLY)
                | models.Q(status__in=[PrayerRequest.Status.PENDING, PrayerRequest.Status.ESCALATED])
            ).distinct()

        return qs.filter(wall | own).distinct()

    def perform_create(self, serializer):
        prayer_request = create_request(author=self.request.user, **serializer.validated_data)
        serializer.instance = prayer_request

    @action(detail=True, methods=['post'], url_path='moderate')
    def moderate_action(self, request, pk=None):
        prayer_request = self.get_object()
        serializer = PrayerModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prayer_request = moderate(
                prayer_request, request.user,
                serializer.validated_data['status'], serializer.validated_data['note'],
            )
        except PrayerError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PrayerRequestSerializer(prayer_request, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], url_path='pray')
    def pray_action(self, request, pk=None):
        prayer_request = self.get_object()
        now_supporting = toggle_support(prayer_request, request.user)
        # Query fresh rather than via prayer_request.supporters - that
        # manager was populated by get_queryset()'s prefetch_related
        # *before* toggle_support() ran, so .count() would return a stale,
        # cached figure otherwise.
        fresh_count = PrayerSupport.objects.filter(prayer_request=prayer_request).count()
        return Response({'prayed': now_supporting, 'prayed_count': fresh_count})

    @action(detail=True, methods=['post'], url_path='respond', permission_classes=[IsLeaderOrAdmin])
    def respond_action(self, request, pk=None):
        prayer_request = self.get_object()
        serializer = PrayerRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = respond(prayer_request, request.user, serializer.validated_data['body'])
        return Response(InboxMessageSerializer(message).data, status=status.HTTP_201_CREATED)

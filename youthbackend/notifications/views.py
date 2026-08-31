from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardResultsSetPagination
from .models import DeviceToken, Notification
from .serializers import DeviceTokenSerializer, NotificationPreferenceSerializer, NotificationSerializer
from .services import get_or_create_preference


class MyNotificationPreferenceView(APIView):
    """Every person manages only their own preferences - there is no
    concept of a Leader editing someone else's notification settings."""

    def get(self, request):
        preference = get_or_create_preference(request.user)
        return Response(NotificationPreferenceSerializer(preference).data)

    def patch(self, request):
        preference = get_or_create_preference(request.user)
        serializer = NotificationPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DeviceTokenViewSet(viewsets.ModelViewSet):
    serializer_class = DeviceTokenSerializer
    pagination_class = None

    def get_queryset(self):
        return DeviceToken.objects.filter(person=self.request.user)

    def perform_create(self, serializer):
        # Upsert by token so a re-installed app / rotated token never hits
        # the unique constraint or creates a duplicate row.
        obj, _ = DeviceToken.objects.update_or_create(
            token=serializer.validated_data['token'],
            defaults={
                'person': self.request.user,
                'platform': serializer.validated_data['platform'],
                'is_active': True,
            },
        )
        serializer.instance = obj

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class MyNotificationsViewSet(viewsets.ReadOnlyModelViewSet):
    """In-app notification history/inbox for the current user."""

    serializer_class = NotificationSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Notification.objects.filter(person=self.request.user).order_by('-scheduled_at')

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response(NotificationSerializer(notification).data)

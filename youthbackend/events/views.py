from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsLeaderOrAdminOrReadOnly
from notifications.catalog import Category, NotificationType
from notifications.services import notify_many
from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsLeaderOrAdminOrReadOnly]

    def get_queryset(self):
        qs = Event.objects.all().prefetch_related('audience_groups')
        user = self.request.user
        if user.is_authenticated and (user.is_leader_or_admin or user.is_superuser):
            return qs
        # Youth only ever see published content targeted at them - never
        # rely on the client to hide draft/unpublished/other-audience events.
        visible_ids = [event.id for event in qs if event.is_visible_to(user)]
        return qs.filter(id__in=visible_ids)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        previous = self.get_object()
        was_published = previous.status == Event.Status.PUBLISHED
        prev_snapshot = (previous.starts_at, previous.location, previous.status)

        event = serializer.save()

        if was_published and prev_snapshot != (event.starts_at, event.location, event.status):
            self._notify_audience(
                event, NotificationType.EVENT_CHANGED_CANCELLED,
                title=f'{event.name} has changed',
                body=self._change_summary(prev_snapshot, event),
                urgent=True,
            )

    def _change_summary(self, prev_snapshot, event):
        prev_starts_at, prev_location, _prev_status = prev_snapshot
        if event.status in (Event.Status.ARCHIVED, Event.Status.EXPIRED):
            return f'{event.name} has been cancelled.'
        bits = []
        if prev_starts_at != event.starts_at:
            bits.append(f'new time: {timezone.localtime(event.starts_at):%a %d %b, %I:%M %p}')
        if prev_location != event.location:
            bits.append(f"new location: {event.location or 'TBC'}")
        return '; '.join(bits) or 'Details have been updated.'

    def _notify_audience(self, event, notification_type, title, body, urgent=False):
        notify_many(
            event.resolve_audience_queryset(), Category.EVENTS, notification_type, title, body,
            deep_link_type='event', deep_link_id=event.id, data={'event_id': event.id}, urgent=urgent,
        )

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        """Publishing is a deliberate step separate from create/edit so
        draft content never notifies anyone by accident, and the CMS
        publisher explicitly opts in to sending a push (`notify: true`)."""
        event = self.get_object()
        event.status = Event.Status.PUBLISHED
        event.save(update_fields=['status', 'updated_at'])

        if request.data.get('notify'):
            self._notify_audience(
                event, NotificationType.EVENT_ANNOUNCED,
                title=request.data.get('title') or event.name,
                body=request.data.get('body') or 'Check the app for details.',
            )

        return Response(EventSerializer(event).data)


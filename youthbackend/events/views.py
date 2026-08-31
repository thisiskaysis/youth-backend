from rest_framework import viewsets

from core.permissions import IsLeaderOrPastorOrReadOnly
from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsLeaderOrPastorOrReadOnly]

    def get_queryset(self):
        qs = Event.objects.all().prefetch_related('audience_groups')
        user = self.request.user
        if user.is_authenticated and (user.is_leader_or_pastor or user.is_superuser):
            return qs
        # Youth only ever see published content targeted at them - never
        # rely on the client to hide draft/unpublished/other-audience events.
        visible_ids = [event.id for event in qs if event.is_visible_to(user)]
        return qs.filter(id__in=visible_ids)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

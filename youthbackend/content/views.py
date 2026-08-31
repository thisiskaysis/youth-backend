from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsLeaderOrPastorOrReadOnly
from .models import ContentItem
from .serializers import ContentItemSerializer
from .services import publish


class ContentItemViewSet(viewsets.ModelViewSet):
    serializer_class = ContentItemSerializer
    permission_classes = [IsLeaderOrPastorOrReadOnly]

    def get_queryset(self):
        qs = ContentItem.objects.all().prefetch_related('audience_groups')
        user = self.request.user
        if user.is_authenticated and (user.is_leader_or_pastor or user.is_superuser):
            return qs
        # Youth only ever see published content targeted at them - never
        # rely on the client to hide draft/unpublished/other-audience posts.
        visible_ids = [item.id for item in qs if item.is_visible_to(user)]
        return qs.filter(id__in=visible_ids)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='publish')
    def publish_action(self, request, pk=None):
        item = publish(self.get_object())
        return Response(ContentItemSerializer(item).data)

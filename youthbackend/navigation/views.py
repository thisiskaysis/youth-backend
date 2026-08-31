from django.db import transaction
from django.db.models import Max
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from core.permissions import IsLeaderOrPastorOrReadOnly
from .models import NavigationItem
from .serializers import NavigationItemSerializer
from .services import publish


def _is_pastor(user):
    return user.role == user.Role.PASTOR or user.is_superuser


class NavigationItemViewSet(viewsets.ModelViewSet):
    serializer_class = NavigationItemSerializer
    permission_classes = [IsLeaderOrPastorOrReadOnly]

    def get_queryset(self):
        qs = NavigationItem.objects.all().prefetch_related('audience_groups')
        user = self.request.user
        if user.is_authenticated and (user.is_leader_or_pastor or user.is_superuser):
            return qs
        visible_ids = [item.id for item in qs if item.is_visible_to(user)]
        return qs.filter(id__in=visible_ids)

    def perform_create(self, serializer):
        if serializer.validated_data.get('is_protected') and not _is_pastor(self.request.user):
            raise PermissionDenied('Only a Pastor can create a protected navigation item.')
        next_order = (NavigationItem.objects.aggregate(Max('sort_order'))['sort_order__max'] or 0) + 1
        serializer.save(created_by=self.request.user, sort_order=next_order)

    def perform_update(self, serializer):
        instance = serializer.instance
        changing_protection = (
            'is_protected' in serializer.validated_data
            and serializer.validated_data['is_protected'] != instance.is_protected
        )
        if changing_protection and not _is_pastor(self.request.user):
            raise PermissionDenied('Only a Pastor can change protection on a navigation item.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_protected:
            raise ValidationError('This navigation item is protected and cannot be deleted.')
        instance.delete()

    @action(detail=True, methods=['post'], url_path='publish')
    def publish_action(self, request, pk=None):
        item = publish(self.get_object())
        return Response(NavigationItemSerializer(item).data)

    @action(detail=False, methods=['patch'], url_path='reorder')
    def reorder(self, request):
        """Bulk drag-and-drop save - send the complete ordered list of IDs,
        not deltas. Assigns sort_order from each item's position."""
        ordered_ids = request.data.get('ordered_ids')
        if not isinstance(ordered_ids, list) or not ordered_ids:
            return Response({'detail': 'ordered_ids (a list of item IDs) is required.'}, status=400)

        matched = set(NavigationItem.objects.filter(id__in=ordered_ids).values_list('id', flat=True))
        if len(matched) != len(set(ordered_ids)):
            return Response({'detail': 'One or more ordered_ids were not found.'}, status=400)

        with transaction.atomic():
            for index, item_id in enumerate(ordered_ids):
                NavigationItem.objects.filter(pk=item_id).update(sort_order=index)

        items = NavigationItem.objects.filter(id__in=ordered_ids).order_by('sort_order')
        return Response(NavigationItemSerializer(items, many=True).data)

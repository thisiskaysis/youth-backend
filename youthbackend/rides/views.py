from rest_framework import status, viewsets
from rest_framework.response import Response

from core.permissions import IsLeaderOrAdmin
from .models import RideRequest
from .serializers import RideRequestCreateSerializer, RideRequestSerializer, RideRequestUpdateSerializer
from .services import create_ride_request, update_ride


class RideRequestViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('update', 'partial_update'):
            return [IsLeaderOrAdmin()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'create':
            return RideRequestCreateSerializer
        if self.action in ('update', 'partial_update'):
            return RideRequestUpdateSerializer
        return RideRequestSerializer

    def get_queryset(self):
        user = self.request.user
        qs = RideRequest.objects.select_related('person', 'assigned_leader', 'event')
        if user.is_leader_or_admin or user.is_superuser:
            return qs
        return qs.filter(person=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(RideRequestSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(RideRequestSerializer(serializer.instance).data)

    def perform_create(self, serializer):
        ride = create_ride_request(person=self.request.user, **serializer.validated_data)
        serializer.instance = ride

    def perform_update(self, serializer):
        ride = update_ride(serializer.instance, **serializer.validated_data)
        serializer.instance = ride

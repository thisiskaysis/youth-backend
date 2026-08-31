from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsLeaderOrPastor
from .models import FormAssignment, FormDefinition
from .serializers import (
    AssignFormInputSerializer,
    FormAssignmentSerializer,
    FormDefinitionSerializer,
    SubmitFormInputSerializer,
)
from .services import FormError, assign_form, submit_form


class FormDefinitionViewSet(viewsets.ModelViewSet):
    """Managing form definitions is Leader/Pastor-only; there's no
    per-team scoping in the docs for this, unlike volunteer positions."""

    serializer_class = FormDefinitionSerializer
    permission_classes = [IsLeaderOrPastor]
    queryset = FormDefinition.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        form = self.get_object()
        serializer = AssignFormInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = assign_form(
            form, serializer.validated_data['person_ids'], request.user,
            due_at=serializer.validated_data.get('due_at'),
        )
        return Response(FormAssignmentSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class FormAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    """Outstanding-consent visibility: Leaders/Pastors see every
    assignment; everyone else only ever sees their own."""

    serializer_class = FormAssignmentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = FormAssignment.objects.select_related('form', 'submission')
        if user.is_leader_or_pastor or user.is_superuser:
            return qs
        return qs.filter(person=user)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        assignment = self.get_object()
        serializer = SubmitFormInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submission = submit_form(assignment, request.user, serializer.validated_data['answers'])
        except FormError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        assignment.refresh_from_db()
        return Response(FormAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

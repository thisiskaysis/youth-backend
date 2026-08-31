from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.permissions import IsLeaderOrAdmin
from users.serializers import UserBasicSerializer
from .models import AttendanceSession
from .realtime import broadcast_session_update
from .serializers import AttendanceRecordSerializer, AttendanceSessionSerializer
from .services import AttendanceError, resolve_person, sign_in, sign_out
from .services import close_session as close_session_service

User = get_user_model()


class AttendanceSessionViewSet(viewsets.ModelViewSet):
    """Attendance is staff-only end to end - a hidden scanner UI is not a
    security boundary, so every action here also requires attendance.manage
    (modelled here as the Leader/Admin role)."""

    queryset = AttendanceSession.objects.select_related('event').all()
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsLeaderOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get('event')
        status_param = self.request.query_params.get('status')
        if event_id:
            qs = qs.filter(event_id=event_id)
        if status_param:
            qs = qs.filter(status=status_param.upper())
        return qs

    def perform_create(self, serializer):
        event = serializer.validated_data['event']
        if AttendanceSession.objects.filter(event=event, status=AttendanceSession.Status.OPEN).exists():
            raise ValidationError('This event already has an open attendance session.')
        serializer.save(opened_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='sign-in')
    def sign_in_action(self, request, pk=None):
        session = self.get_object()
        try:
            person = resolve_person(request.data.get('qr_token'), request.data.get('person_id'))
            record, result = sign_in(session, person, request.user, request.data.get('source', 'MANUAL'))
        except AttendanceError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        broadcast_session_update(session.id)
        return Response({
            'result': result,
            'person': UserBasicSerializer(person).data,
            'record': AttendanceRecordSerializer(record).data,
        })

    @action(detail=True, methods=['post'], url_path='sign-out')
    def sign_out_action(self, request, pk=None):
        session = self.get_object()
        try:
            person = resolve_person(request.data.get('qr_token'), request.data.get('person_id'))
            record = sign_out(session, person, request.user, request.data.get('source', 'MANUAL'))
        except AttendanceError as exc:
            return Response({'code': exc.code, 'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        broadcast_session_update(session.id)
        return Response({
            'result': 'SIGNED_OUT',
            'person': UserBasicSerializer(person).data,
            'record': AttendanceRecordSerializer(record).data,
        })

    @action(detail=True, methods=['get'], url_path='live')
    def live(self, request, pk=None):
        session = self.get_object()
        records = session.records.all()
        on_site = records.filter(signed_in_at__isnull=False, signed_out_at__isnull=True)
        return Response({
            'session_id': session.id,
            'status': session.status,
            'currently_on_site': on_site.count(),
            'total_signed_in': records.filter(signed_in_at__isnull=False).count(),
            'signed_out': records.filter(signed_out_at__isnull=False).count(),
            'first_time_visitors': on_site.filter(person__is_provisional=True).count(),
        })

    @action(detail=True, methods=['get'], url_path='on-site')
    def on_site(self, request, pk=None):
        session = self.get_object()
        records = session.records.filter(
            signed_in_at__isnull=False, signed_out_at__isnull=True
        ).select_related('person').order_by('signed_in_at')
        return Response(AttendanceRecordSerializer(records, many=True).data)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        session = self.get_object()
        try:
            close_session_service(
                session,
                request.user,
                force=bool(request.data.get('force')),
                reason=request.data.get('reason', ''),
            )
        except AttendanceError as exc:
            payload = {'code': exc.code, 'detail': exc.message}
            if exc.code == 'REMAINING_ON_SITE':
                remaining = session.records.filter(
                    signed_in_at__isnull=False, signed_out_at__isnull=True
                ).select_related('person')
                payload['people'] = UserBasicSerializer([r.person for r in remaining], many=True).data
            return Response(payload, status=status.HTTP_409_CONFLICT)
        broadcast_session_update(session.id, event_type='attendance.session.closed')
        session.refresh_from_db()
        return Response(AttendanceSessionSerializer(session).data)

from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.serializers import AttendanceRecordSerializer
from core.permissions import IsLeaderOrPastor
from decisions.serializers import DecisionSerializer, FollowUpSerializer
from forms_app.serializers import FormAssignmentSerializer
from rides.serializers import RideRequestSerializer
from users.serializers import UserBasicSerializer
from . import queries


class DashboardView(APIView):
    """Core KPI cards in one payload - counts/breakdowns only. Each card
    has a matching drill-down endpoint below for the underlying records."""

    permission_classes = [IsLeaderOrPastor]

    def get(self, request):
        filters = queries.get_filters(request)
        return Response({
            'filters': {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in filters.items()},
            'attendance': queries.attendance_summary(filters),
            'school_year_breakdown': queries.school_year_breakdown(filters),
            'group_participation': queries.group_participation(filters),
            'decisions': queries.decisions_summary(filters),
            'prayer': queries.prayer_volume(filters),
            'rides': queries.rides_summary(filters),
            'outstanding_consent': queries.outstanding_consent_queryset(filters).count(),
        })


class AttendanceTrendView(APIView):
    permission_classes = [IsLeaderOrPastor]

    def get(self, request):
        weeks = int(request.query_params.get('weeks', 8))
        return Response({'weeks': weeks, 'trend': queries.attendance_trend(weeks)})


class RosterSummaryView(APIView):
    permission_classes = [IsLeaderOrPastor]

    def get(self, request):
        event_id = request.query_params.get('event')
        if not event_id:
            return Response({'detail': 'event query param is required.'}, status=400)
        return Response(queries.roster_summary(event_id))


class AttendanceDrilldownView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        return queries.attendance_queryset(queries.get_filters(self.request)).order_by('-signed_in_at')


class FirstTimeVisitorsView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = UserBasicSerializer

    def get_queryset(self):
        filters = queries.get_filters(self.request)
        person_ids = queries.attendance_queryset(filters).filter(person__is_provisional=True).values_list(
            'person_id', flat=True
        ).distinct()
        return queries.User.objects.filter(id__in=person_ids).order_by('first_name', 'last_name')


class UnassignedYouthView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = UserBasicSerializer

    def get_queryset(self):
        return queries.unassigned_youth_queryset()


class DecisionsDrilldownView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = DecisionSerializer

    def get_queryset(self):
        return queries.decisions_queryset(queries.get_filters(self.request))


class OutstandingFollowUpsView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = FollowUpSerializer

    def get_queryset(self):
        return queries.outstanding_follow_ups_queryset()


class OutstandingConsentView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = FormAssignmentSerializer

    def get_queryset(self):
        return queries.outstanding_consent_queryset(queries.get_filters(self.request))


class RidesDrilldownView(ListAPIView):
    permission_classes = [IsLeaderOrPastor]
    serializer_class = RideRequestSerializer

    def get_queryset(self):
        return queries.rides_queryset(queries.get_filters(self.request))

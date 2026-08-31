from rest_framework import serializers

from users.serializers import UserBasicSerializer
from .models import AttendanceRecord, AttendanceSession


class AttendanceSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = ['id', 'event', 'status', 'opened_at', 'opened_by', 'closed_at', 'closed_by']
        read_only_fields = ['id', 'status', 'opened_at', 'opened_by', 'closed_at', 'closed_by']


class AttendanceRecordSerializer(serializers.ModelSerializer):
    person = UserBasicSerializer(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'session', 'person', 'signed_in_at', 'signed_in_by',
            'sign_in_source', 'signed_out_at', 'signed_out_by', 'sign_out_source',
            'correction_note',
        ]
        read_only_fields = fields

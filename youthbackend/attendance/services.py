"""Attendance domain logic. The backend is the sole source of truth for
sign-in/out state - the frontend never decides attendance truth. All state
transitions run inside a transaction with row locking so two devices
scanning the same person at once cannot create conflicting records.
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import AttendanceRecord, AttendanceSession

User = get_user_model()


class AttendanceError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def resolve_person(qr_token=None, person_id=None):
    if qr_token:
        try:
            return User.objects.get(qr_token=qr_token)
        except User.DoesNotExist:
            raise AttendanceError('INVALID_QR', 'QR code not recognised.')
    if person_id:
        try:
            return User.objects.get(pk=person_id)
        except User.DoesNotExist:
            raise AttendanceError('PERSON_NOT_FOUND', 'Person not found.')
    raise AttendanceError('MISSING_IDENTIFIER', 'Provide a qr_token or person_id.')


@transaction.atomic
def sign_in(session, person, actor, source):
    session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
    if session.status != AttendanceSession.Status.OPEN:
        raise AttendanceError('SESSION_CLOSED', 'This attendance session is closed.')

    record, created = AttendanceRecord.objects.select_for_update().get_or_create(
        session=session,
        person=person,
        defaults={
            'signed_in_at': timezone.now(),
            'signed_in_by': actor,
            'sign_in_source': source,
        },
    )
    if created:
        return record, 'SIGNED_IN'

    if record.is_on_site:
        # Idempotent - never toggle a duplicate scan into a sign-out.
        return record, 'ALREADY_SIGNED_IN'

    # Previously signed out earlier in the same session (e.g. stepped out
    # and returned) - re-open the single record for this person/session.
    record.signed_in_at = timezone.now()
    record.signed_in_by = actor
    record.sign_in_source = source
    record.signed_out_at = None
    record.signed_out_by = None
    record.sign_out_source = ''
    record.save()
    return record, 'SIGNED_IN'


@transaction.atomic
def sign_out(session, person, actor, source):
    session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
    if session.status != AttendanceSession.Status.OPEN:
        raise AttendanceError('SESSION_CLOSED', 'This attendance session is closed.')

    try:
        record = AttendanceRecord.objects.select_for_update().get(session=session, person=person)
    except AttendanceRecord.DoesNotExist:
        raise AttendanceError('NOT_SIGNED_IN', 'This person is not currently signed in.')

    if not record.is_on_site:
        raise AttendanceError('NOT_SIGNED_IN', 'This person is not currently signed in.')

    record.signed_out_at = timezone.now()
    record.signed_out_by = actor
    record.sign_out_source = source
    record.save()
    return record


@transaction.atomic
def close_session(session, actor, force=False, reason=''):
    from core.audit import log_audit

    session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
    if session.status == AttendanceSession.Status.CLOSED:
        raise AttendanceError('ALREADY_CLOSED', 'Session is already closed.')

    remaining_count = session.records.filter(
        signed_in_at__isnull=False, signed_out_at__isnull=True
    ).count()
    if remaining_count and not force:
        raise AttendanceError(
            'REMAINING_ON_SITE', f'{remaining_count} people are still marked on site.'
        )

    session.status = AttendanceSession.Status.CLOSED
    session.closed_at = timezone.now()
    session.closed_by = actor
    session.save()

    if remaining_count and force:
        log_audit(
            actor=actor,
            action='attendance.session.force_closed',
            entity=session,
            changes={'remaining_on_site': remaining_count},
            reason=reason,
        )
    return session


@transaction.atomic
def correct_record(record, actor, reason, **fields):
    from core.audit import log_audit

    record = AttendanceRecord.objects.select_for_update().get(pk=record.pk)
    before = {
        'signed_in_at': record.signed_in_at,
        'signed_out_at': record.signed_out_at,
    }
    for field, value in fields.items():
        setattr(record, field, value)
    record.correction_note = reason
    record.save()

    log_audit(
        actor=actor,
        action='attendance.record.corrected',
        entity=record,
        changes={
            'before': {k: str(v) for k, v in before.items()},
            'after': {k: str(getattr(record, k)) for k in before},
        },
        reason=reason,
    )
    return record

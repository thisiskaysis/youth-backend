from .models import AuditEntry


def log_audit(*, actor, action, entity, changes=None, reason=''):
    """Persist an audit trail entry for a sensitive mutation.

    `actor` may be an AnonymousUser or None (e.g. system-initiated changes);
    only authenticated users are attributed on the record.
    """
    AuditEntry.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        changes=changes or {},
        reason=reason,
    )

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_session_update(session_id, event_type='attendance.updated'):
    """Notify connected leader/pastor dashboards that a session's
    authoritative state changed. This is a broadcast of a REST-committed
    fact, never the write path itself."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f'attendance_session_{session_id}',
        {'type': 'attendance.update', 'session_id': session_id, 'event_type': event_type},
    )

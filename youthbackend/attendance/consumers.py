from channels.generic.websocket import AsyncJsonWebsocketConsumer


class AttendanceConsumer(AsyncJsonWebsocketConsumer):
    """Read-only broadcast channel for one attendance session. Clients
    receive a lightweight ping and are expected to refetch the REST
    live/on-site endpoints - the socket is never the source of truth."""

    async def connect(self):
        user = self.scope.get('user')
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f'attendance_session_{self.session_id}'

        if not user or not user.is_authenticated or not getattr(user, 'is_leader_or_pastor', False):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def attendance_update(self, event):
        await self.send_json({
            'type': event.get('event_type', 'attendance.updated'),
            'session_id': event['session_id'],
        })

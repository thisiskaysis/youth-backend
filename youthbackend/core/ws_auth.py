"""JWT authentication for Channels WebSocket connections.

The REST API authenticates with SimpleJWT bearer tokens, which has no
concept of a browser session cookie. Mobile/websocket clients instead pass
the access token as a query string parameter, e.g.:

    wss://host/ws/attendance/<session_id>/?token=<access_token>
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def _get_user_from_token(token):
    try:
        auth = JWTAuthentication()
        validated_token = auth.get_validated_token(token)
        return auth.get_user(validated_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        token = parse_qs(query_string).get('token', [None])[0]
        scope['user'] = await _get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)

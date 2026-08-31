"""
ASGI config for youthbackend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youthbackend.settings')

# Must be created before importing anything that touches models/routing,
# since this is what loads Django's app registry.
django_asgi_app = get_asgi_application()

from core.ws_auth import JWTAuthMiddlewareStack  # noqa: E402
from attendance.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})

"""Pluggable push delivery, mirroring Django's own EMAIL_BACKEND pattern.

Swap `NOTIFICATIONS_PUSH_BACKEND` in settings for a real Expo/FCM/APNs
adapter once credentials exist. The console backend keeps the rest of the
system fully wired and testable without one.
"""
import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger('notifications.push')


class BasePushBackend:
    def send(self, *, tokens, title, body, data):
        raise NotImplementedError


class ConsolePushBackend(BasePushBackend):
    def send(self, *, tokens, title, body, data):
        logger.info('PUSH -> %s | %s | %s | data=%s', tokens, title, body, data)
        return {'sent': len(tokens)}


def get_push_backend():
    path = getattr(settings, 'NOTIFICATIONS_PUSH_BACKEND', 'notifications.backends.ConsolePushBackend')
    return import_string(path)()

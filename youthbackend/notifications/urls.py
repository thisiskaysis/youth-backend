from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('device-tokens', views.DeviceTokenViewSet, basename='device-token')
router.register('', views.MyNotificationsViewSet, basename='notification')

urlpatterns = [
    path('preferences/me/', views.MyNotificationPreferenceView.as_view(), name='notification-preferences'),
] + router.urls

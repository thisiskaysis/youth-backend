from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('positions', views.VolunteerPositionViewSet, basename='volunteer-position')
router.register('availability', views.VolunteerAvailabilityViewSet, basename='volunteer-availability')
router.register('assignments', views.VolunteerAssignmentViewSet, basename='volunteer-assignment')

urlpatterns = [
    path('rosters/<int:event_id>/', views.EventRosterView.as_view(), name='event-roster'),
] + router.urls

from rest_framework.routers import DefaultRouter

from .views import DecisionViewSet, FollowUpViewSet

router = DefaultRouter()
router.register('follow-ups', FollowUpViewSet, basename='follow-up')
router.register('', DecisionViewSet, basename='decision')

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .views import GroupMembershipViewSet, GroupViewSet

router = DefaultRouter()
router.register('memberships', GroupMembershipViewSet, basename='group-membership')
router.register('', GroupViewSet, basename='group')

urlpatterns = router.urls

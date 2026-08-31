from rest_framework.routers import DefaultRouter

from .views import RideRequestViewSet

router = DefaultRouter()
router.register('requests', RideRequestViewSet, basename='ride-request')

urlpatterns = router.urls

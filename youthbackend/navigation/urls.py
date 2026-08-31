from rest_framework.routers import DefaultRouter

from .views import NavigationItemViewSet

router = DefaultRouter()
router.register('', NavigationItemViewSet, basename='navigation-item')

urlpatterns = router.urls

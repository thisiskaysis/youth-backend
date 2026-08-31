from rest_framework.routers import DefaultRouter

from .views import ContentItemViewSet

router = DefaultRouter()
router.register('', ContentItemViewSet, basename='content-item')

urlpatterns = router.urls

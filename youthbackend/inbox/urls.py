from rest_framework.routers import DefaultRouter

from .views import InboxMessageViewSet

router = DefaultRouter()
router.register('messages', InboxMessageViewSet, basename='inbox-message')

urlpatterns = router.urls

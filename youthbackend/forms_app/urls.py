from rest_framework.routers import DefaultRouter

from .views import FormAssignmentViewSet, FormDefinitionViewSet

router = DefaultRouter()
router.register('definitions', FormDefinitionViewSet, basename='form-definition')
router.register('assignments', FormAssignmentViewSet, basename='form-assignment')

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from apps.etl.views import (
    CompletedInspectionViewSet,
    ImportJobViewSet,
    ManualInputViewSet,
)

router = DefaultRouter()
router.register('jobs', ImportJobViewSet, basename='jobs')
router.register('inspections/completed', CompletedInspectionViewSet, basename='completed-inspections')
router.register('manual-inputs', ManualInputViewSet, basename='manual-inputs')

urlpatterns = router.urls

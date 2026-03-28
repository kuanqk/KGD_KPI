from rest_framework.routers import DefaultRouter

from apps.core.views import AuditLogViewSet, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('audit-logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = router.urls

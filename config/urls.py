from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from config.views import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health, name='health'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/', include([
        path('auth/', include('apps.core.urls')),
        path('regions/', include('apps.regions.urls')),
        path('etl/', include('apps.etl.urls')),
        path('kpi/', include('apps.kpi.urls')),
        path('reports/', include('apps.reports.urls')),
        path('admin/', include('apps.core.admin_urls')),
    ])),
]

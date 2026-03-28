from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.kpi.views import (
    CalculateView,
    KPIFormulaViewSet,
    KPIResultViewSet,
    KPISummaryViewSet,
)

router = DefaultRouter()
router.register('formulas', KPIFormulaViewSet, basename='formulas')
router.register('results', KPIResultViewSet, basename='results')
router.register('summary', KPISummaryViewSet, basename='summary')

urlpatterns = router.urls + [
    path('calculate/', CalculateView.as_view(), name='kpi-calculate'),
]

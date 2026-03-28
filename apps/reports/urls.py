from django.urls import path

from apps.reports.views import (
    ApproveView,
    ExportPDFView,
    ExportXLSXView,
    PendingReportsView,
    RecalculateView,
    RejectView,
)

urlpatterns = [
    path('pending/', PendingReportsView.as_view(), name='pending-reports'),
    path('<int:pk>/approve/', ApproveView.as_view(), name='report-approve'),
    path('<int:pk>/reject/', RejectView.as_view(), name='report-reject'),
    path('<int:pk>/recalculate/', RecalculateView.as_view(), name='report-recalculate'),
    path('<int:pk>/export/xlsx/', ExportXLSXView.as_view(), name='report-export-xlsx'),
    path('<int:pk>/export/pdf/', ExportPDFView.as_view(), name='report-export-pdf'),
]

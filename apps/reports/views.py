"""
Reports API — утверждение отчётов и экспорт.

Эндпоинты:
  GET   /api/v1/reports/pending/            — список на утверждение (Проверяющий)
  POST  /api/v1/reports/{id}/approve/       — утвердить (Проверяющий)
  POST  /api/v1/reports/{id}/reject/        — вернуть на доработку (Проверяющий)
  POST  /api/v1/reports/{id}/recalculate/   — запросить пересчёт (Проверяющий)
  GET   /api/v1/reports/{id}/export/xlsx/   — экспорт XLSX (все роли)
  GET   /api/v1/reports/{id}/export/pdf/    — экспорт PDF (все роли)
"""
import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import RegionScopedMixin, RegionScopedQuerySet
from apps.core.models import AuditLog
from apps.core.permissions import IsReviewer
from apps.kpi.models import KPISummary
from apps.kpi.tasks import calculate_kpi
from apps.reports.models import ReportApproval
from apps.reports.serializers import (
    ApprovalActionSerializer,
    PendingSummarySerializer,
)

logger = logging.getLogger(__name__)


def _get_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# Pending reports (список ожидающих утверждения)
# ---------------------------------------------------------------------------

class PendingReportsView(RegionScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/reports/pending/

    Возвращает KPISummary со статусом 'submitted'.
    Reviewer видит все регионы; Viewer — только свои (RLS).
    Пагинация отключена — записей не более 20.
    """
    queryset = RegionScopedQuerySet(model=KPISummary, using='default')
    serializer_class = PendingSummarySerializer
    permission_classes = [IsReviewer]
    pagination_class = None

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(status='submitted')
            .select_related('region')
            .prefetch_related('approvals__actor')
            .order_by('rank', 'region__order')
        )


# ---------------------------------------------------------------------------
# Вспомогательная функция для action-вью
# ---------------------------------------------------------------------------

def _get_summary_for_reviewer(pk: int, request) -> KPISummary:
    """Получить KPISummary по PK. Reviewer видит все регионы."""
    return get_object_or_404(KPISummary, pk=pk)


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

class ApproveView(APIView):
    """
    POST /api/v1/reports/{id}/approve/

    Утверждает отчёт: submitted → approved.
    Body (необязательно): {"comment": "..."}
    """
    permission_classes = [IsReviewer]

    def post(self, request, pk: int):
        summary = _get_summary_for_reviewer(pk, request)

        if summary.status != 'submitted':
            detail = (
                f'Нельзя утвердить отчёт со статусом «{summary.get_status_display()}». '
                'Ожидается статус «На утверждении».'
            )
            return Response(
                {'detail': detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ReportApproval.objects.create(
            summary=summary,
            action='approve',
            actor=request.user,
            comment=serializer.validated_data['comment'],
        )
        summary.status = 'approved'
        summary.save(update_fields=['status'])

        AuditLog.log(
            event='approval',
            user=request.user,
            ip_address=_get_ip(request),
            details={
                'action': 'approve',
                'summary_id': summary.pk,
                'region_id': summary.region_id,
                'date_from': str(summary.date_from),
                'date_to': str(summary.date_to),
            },
        )
        logger.info('KPISummary #%d approved by %s', summary.pk, request.user)

        return Response(
            {'detail': 'Отчёт утверждён.', 'summary_id': summary.pk, 'status': 'approved'},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------

class RejectView(APIView):
    """
    POST /api/v1/reports/{id}/reject/

    Возвращает отчёт на доработку: submitted → rejected.
    Body: {"comment": "..."} — комментарий обязателен при отклонении.
    """
    permission_classes = [IsReviewer]

    def post(self, request, pk: int):
        summary = _get_summary_for_reviewer(pk, request)

        if summary.status != 'submitted':
            return Response(
                {'detail': f'Нельзя отклонить отчёт со статусом «{summary.get_status_display()}».'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.validated_data['comment']

        if not comment:
            return Response(
                {'comment': 'Комментарий обязателен при отклонении отчёта.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ReportApproval.objects.create(
            summary=summary,
            action='reject',
            actor=request.user,
            comment=comment,
        )
        summary.status = 'rejected'
        summary.save(update_fields=['status'])

        AuditLog.log(
            event='approval',
            user=request.user,
            ip_address=_get_ip(request),
            details={
                'action': 'reject',
                'summary_id': summary.pk,
                'region_id': summary.region_id,
                'comment': comment,
            },
        )
        logger.info('KPISummary #%d rejected by %s', summary.pk, request.user)

        return Response(
            {'detail': 'Отчёт возвращён на доработку.', 'summary_id': summary.pk, 'status': 'rejected'},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Recalculate
# ---------------------------------------------------------------------------

class RecalculateView(APIView):
    """
    POST /api/v1/reports/{id}/recalculate/

    Запрашивает пересчёт KPI для данного периода и региона.
    Ставит задачу calculate_kpi в очередь Celery.
    Body (необязательно): {"comment": "..."}
    """
    permission_classes = [IsReviewer]

    def post(self, request, pk: int):
        summary = _get_summary_for_reviewer(pk, request)

        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ReportApproval.objects.create(
            summary=summary,
            action='recalc',
            actor=request.user,
            comment=serializer.validated_data['comment'],
        )
        # Сбрасываем статус в draft перед пересчётом
        summary.status = 'draft'
        summary.save(update_fields=['status'])

        task = calculate_kpi.delay(
            date_from=str(summary.date_from),
            date_to=str(summary.date_to),
            region_ids=[summary.region_id],
            user_id=request.user.pk,
        )

        AuditLog.log(
            event='kpi_calc',
            user=request.user,
            ip_address=_get_ip(request),
            details={
                'action': 'recalculate',
                'summary_id': summary.pk,
                'region_id': summary.region_id,
                'date_from': str(summary.date_from),
                'date_to': str(summary.date_to),
                'task_id': task.id,
            },
        )
        logger.info(
            'KPISummary #%d recalculation queued: task_id=%s by %s',
            summary.pk, task.id, request.user,
        )

        return Response(
            {
                'detail': 'Пересчёт поставлен в очередь.',
                'summary_id': summary.pk,
                'task_id': task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class ExportXLSXView(APIView):
    """
    GET /api/v1/reports/{id}/export/xlsx/

    Генерирует XLSX-файл синхронно и отдаёт его как вложение.
    Параллельно ставит фоновую задачу в Celery для записи в AuditLog.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        from apps.reports.services.xlsx_exporter import XLSXExporter
        from apps.reports.tasks import export_to_xlsx

        summary = get_object_or_404(KPISummary.objects.select_related('region'), pk=pk)

        try:
            buf = XLSXExporter(summary).generate()
        except Exception as exc:
            logger.error('ExportXLSXView: summary_id=%d error: %s', pk, exc)
            return Response(
                {'detail': 'Ошибка генерации XLSX. Попробуйте позже.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        AuditLog.log(
            event='export',
            user=request.user,
            ip_address=_get_ip(request),
            details={
                'format': 'xlsx',
                'summary_id': pk,
                'region': str(summary.region),
                'period': f'{summary.date_from} — {summary.date_to}',
            },
        )

        # Фоновая задача для дополнительной обработки (расширяемость)
        export_to_xlsx.delay(summary_id=pk, user_id=request.user.pk)

        filename = (
            f'kpi_report_{summary.region.code}_'
            f'{summary.date_from}_{summary.date_to}.xlsx'
        )
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ExportPDFView(APIView):
    """
    GET /api/v1/reports/{id}/export/pdf/

    Генерирует PDF-файл синхронно и отдаёт его как вложение.
    Параллельно ставит фоновую задачу в Celery для записи в AuditLog.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        from apps.reports.services.pdf_exporter import PDFExporter
        from apps.reports.tasks import export_to_pdf

        summary = get_object_or_404(KPISummary.objects.select_related('region'), pk=pk)

        try:
            buf = PDFExporter(summary).generate()
        except Exception as exc:
            logger.error('ExportPDFView: summary_id=%d error: %s', pk, exc)
            return Response(
                {'detail': 'Ошибка генерации PDF. Попробуйте позже.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        AuditLog.log(
            event='export',
            user=request.user,
            ip_address=_get_ip(request),
            details={
                'format': 'pdf',
                'summary_id': pk,
                'region': str(summary.region),
                'period': f'{summary.date_from} — {summary.date_to}',
            },
        )

        # Фоновая задача для дополнительной обработки (расширяемость)
        export_to_pdf.delay(summary_id=pk, user_id=request.user.pk)

        filename = (
            f'kpi_report_{summary.region.code}_'
            f'{summary.date_from}_{summary.date_to}.pdf'
        )
        response = HttpResponse(buf.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

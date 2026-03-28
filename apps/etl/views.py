"""
ETL API — только для Оператора.

Эндпоинты:
  GET/POST          /api/v1/etl/jobs/                      — список и запуск импорта
  GET               /api/v1/etl/jobs/{id}/                 — детали задачи
  GET               /api/v1/etl/inspections/completed/     — нормализованные проверки
  PATCH             /api/v1/etl/inspections/completed/{id}/ — is_counted / is_anomaly
  GET/POST          /api/v1/etl/manual-inputs/             — ручные вводы
  PUT/PATCH         /api/v1/etl/manual-inputs/{id}/        — обновление
"""
import logging

from rest_framework import mixins, viewsets
from rest_framework.pagination import CursorPagination

from apps.core.models import AuditLog
from apps.core.permissions import IsOperator
from apps.etl.models import CompletedInspection, ImportJob, ManualInput
from apps.etl.serializers import (
    CompletedInspectionSerializer,
    ImportJobSerializer,
    ManualInputSerializer,
)
from apps.etl.tasks import run_import_job

logger = logging.getLogger(__name__)


def _get_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class _JobPagination(CursorPagination):
    page_size = 50
    ordering = '-started_at'


class _InspectionPagination(CursorPagination):
    page_size = 100
    ordering = '-created_at'


# ---------------------------------------------------------------------------
# ImportJob
# ---------------------------------------------------------------------------

class ImportJobViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET    /api/v1/etl/jobs/       — список задач импорта
    POST   /api/v1/etl/jobs/       — создать задачу и запустить Celery-задачу
    GET    /api/v1/etl/jobs/{id}/  — детали задачи (статус, счётчики)

    Body для POST: {"source": "inis"} или {"source": "appeals", "params": {...}}
    """
    queryset = (
        ImportJob.objects
        .select_related('started_by')
        .order_by('-started_at')
    )
    serializer_class = ImportJobSerializer
    permission_classes = [IsOperator]
    pagination_class = _JobPagination
    filterset_fields = ['source', 'status']

    def perform_create(self, serializer):
        job = serializer.save(started_by=self.request.user)
        run_import_job.delay(job.pk)
        logger.info(
            'ImportJob #%d (%s) queued by %s',
            job.pk, job.source, self.request.user,
        )


# ---------------------------------------------------------------------------
# CompletedInspection
# ---------------------------------------------------------------------------

class CompletedInspectionViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET   /api/v1/etl/inspections/completed/       — список нормализованных проверок
    PATCH /api/v1/etl/inspections/completed/{id}/  — пометить is_counted / is_anomaly

    Только PATCH (partial_update). PUT не поддерживается.
    Фильтрация: ?region=&management=&is_anomaly=&source=
    """
    queryset = (
        CompletedInspection.objects
        .select_related('region', 'import_job')
        .order_by('-created_at')
    )
    serializer_class = CompletedInspectionSerializer
    permission_classes = [IsOperator]
    pagination_class = _InspectionPagination
    http_method_names = ['get', 'patch', 'head', 'options']
    filterset_fields = ['region', 'management', 'source', 'is_anomaly', 'is_counted', 'is_accepted']

    def perform_update(self, serializer):
        instance = serializer.save()
        AuditLog.log(
            event='correction',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'model': 'CompletedInspection',
                'id': instance.pk,
                'source_id': instance.source_id,
                'changes': self.request.data,
            },
        )


# ---------------------------------------------------------------------------
# ManualInput
# ---------------------------------------------------------------------------

class ManualInputViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET        /api/v1/etl/manual-inputs/       — список ручных вводов
    POST       /api/v1/etl/manual-inputs/       — создать (region + year уникальны)
    PUT/PATCH  /api/v1/etl/manual-inputs/{id}/  — обновить kbk_share_pct / staff_count

    Оператор заполняет 1 раз в год: доли по КБК и штат по каждому ДГД.
    """
    queryset = (
        ManualInput.objects
        .select_related('region', 'entered_by')
        .order_by('-year', 'region__order')
    )
    serializer_class = ManualInputSerializer
    permission_classes = [IsOperator]
    pagination_class = None   # записей мало (20 ДГД × несколько лет)
    filterset_fields = ['region', 'year']

    def perform_create(self, serializer):
        instance = serializer.save(entered_by=self.request.user)
        AuditLog.log(
            event='manual_input',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'action': 'create',
                'manual_input_id': instance.pk,
                'region_id': instance.region_id,
                'year': instance.year,
            },
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        AuditLog.log(
            event='manual_input',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'action': 'update',
                'manual_input_id': instance.pk,
                'region_id': instance.region_id,
                'year': instance.year,
                'changes': self.request.data,
            },
        )

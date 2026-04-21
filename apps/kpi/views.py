"""
KPI API.

Эндпоинты:
  GET/POST  /api/v1/kpi/formulas/         — список и создание формул (Оператор)
  GET       /api/v1/kpi/formulas/{id}/    — детали формулы
  GET       /api/v1/kpi/results/          — результаты KPI (все роли, RLS)
  GET       /api/v1/kpi/results/{id}/     — детали результата
  GET       /api/v1/kpi/summary/          — рейтинг ДГД (все роли, RLS)
  GET       /api/v1/kpi/summary/{id}/     — детали сводки
  POST      /api/v1/kpi/calculate/        — запустить расчёт (Оператор)
"""
import logging

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import RegionScopedMixin, RegionScopedQuerySet
from apps.core.models import AuditLog
from apps.core.permissions import IsOperator
from apps.kpi.filters import KPIFormulaFilter, KPIResultFilter, KPISummaryFilter
from apps.kpi.models import KPIFormula, KPIResult, KPISummary
from apps.kpi.serializers import (
    CalculateRequestSerializer,
    KPIFormulaSerializer,
    KPIResultSerializer,
    KPISummarySerializer,
)
from apps.kpi.tasks import calculate_kpi

logger = logging.getLogger(__name__)


def _get_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class _ResultPagination(CursorPagination):
    page_size = 100
    ordering = '-calculated_at'


class _SummaryPagination(CursorPagination):
    page_size = 50
    # «Хвост» pk обязателен для cursor pagination — иначе при равных rank/order
    # строка может дублироваться на границах страниц.
    ordering = ('rank', 'region__order', 'pk')


# ---------------------------------------------------------------------------
# KPIFormula
# ---------------------------------------------------------------------------

class KPIFormulaViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET   /api/v1/kpi/formulas/       — список всех версий формул
    POST  /api/v1/kpi/formulas/       — создать новую версию формулы
    GET   /api/v1/kpi/formulas/{id}/  — детали формулы

    При создании:
      - version назначается автоматически (max существующей + 1)
      - предыдущая активная версия того же kpi_type деактивируется
      - логируется событие formula_change в AuditLog
    """
    queryset = KPIFormula.objects.select_related('created_by').order_by('kpi_type', '-version')
    serializer_class = KPIFormulaSerializer
    permission_classes = [IsOperator]
    pagination_class = None  # формул мало
    filterset_class = KPIFormulaFilter

    def perform_create(self, serializer):
        kpi_type = serializer.validated_data['kpi_type']

        with transaction.atomic():
            latest = (
                KPIFormula.objects
                .filter(kpi_type=kpi_type)
                .order_by('-version')
                .select_for_update()
                .first()
            )
            next_version = (latest.version + 1) if latest else 1

            # Деактивируем предыдущую активную версию
            KPIFormula.objects.filter(kpi_type=kpi_type, is_active=True).update(is_active=False)

            formula = serializer.save(
                version=next_version,
                created_by=self.request.user,
            )

        AuditLog.log(
            event='formula_change',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'action': 'created',
                'kpi_type': formula.kpi_type,
                'version': formula.version,
                'formula_id': formula.pk,
            },
        )
        logger.info(
            'KPIFormula created: %s v%d by %s',
            formula.kpi_type, formula.version, self.request.user,
        )


# ---------------------------------------------------------------------------
# KPIResult
# ---------------------------------------------------------------------------

class KPIResultViewSet(
    RegionScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET /api/v1/kpi/results/       — список результатов KPI (с RLS для viewer)
    GET /api/v1/kpi/results/{id}/  — детали

    Фильтрация: ?region=&kpi_type=&date_from=&date_to=&status=
    """
    # RegionScopedQuerySet необходим для работы RegionScopedMixin.for_user()
    queryset = RegionScopedQuerySet(model=KPIResult, using='default')
    serializer_class = KPIResultSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = _ResultPagination
    filterset_class = KPIResultFilter
    ordering_fields = ['calculated_at', 'score', 'region__order']

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related('region', 'formula', 'calculated_by')
            .order_by('-calculated_at')
        )


# ---------------------------------------------------------------------------
# KPISummary
# ---------------------------------------------------------------------------

class KPISummaryViewSet(
    RegionScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET /api/v1/kpi/summary/       — рейтинг ДГД (с RLS для viewer)
    GET /api/v1/kpi/summary/{id}/  — детали сводки

    Фильтрация: ?region=&date_from=&date_to=&status=
    """
    queryset = RegionScopedQuerySet(model=KPISummary, using='default')
    serializer_class = KPISummarySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = _SummaryPagination
    filterset_class = KPISummaryFilter
    ordering_fields = ['rank', 'score_total', 'region__order']

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related('region')
            .order_by('rank', 'region__order', 'pk')
        )


# ---------------------------------------------------------------------------
# Запуск расчёта
# ---------------------------------------------------------------------------

class CalculateView(APIView):
    """
    POST /api/v1/kpi/calculate/

    Body:
      {
        "date_from": "2025-01-01",
        "date_to":   "2025-06-30",
        "region_ids": [1, 2, 3]   // опционально; null → все ДГД
      }

    Ставит задачу calculate_kpi в очередь Celery.
    Возвращает 202 Accepted с task_id для отслеживания.
    Доступно только Оператору.
    """
    permission_classes = [IsOperator]

    def post(self, request):
        serializer = CalculateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        date_from = str(serializer.validated_data['date_from'])
        date_to = str(serializer.validated_data['date_to'])
        region_ids = serializer.validated_data.get('region_ids')

        task = calculate_kpi.delay(
            date_from=date_from,
            date_to=date_to,
            region_ids=region_ids,
            user_id=request.user.pk,
        )

        logger.info(
            'KPI calculation queued: task_id=%s, period=%s–%s, regions=%s, by=%s',
            task.id, date_from, date_to, region_ids, request.user,
        )

        return Response(
            {
                'task_id': task.id,
                'status': 'queued',
                'date_from': date_from,
                'date_to': date_to,
                'region_ids': region_ids,
            },
            status=status.HTTP_202_ACCEPTED,
        )

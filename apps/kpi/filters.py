"""
django-filter FilterSet-ы для KPI API.
Позволяют фильтровать результаты и сводки по региону, периоду и типу KPI.
"""
import django_filters

from apps.kpi.models import KPIFormula, KPIResult, KPISummary


class KPIResultFilter(django_filters.FilterSet):
    """
    Фильтры для KPIResultViewSet.
    Примеры:
      ?region=5&kpi_type=assessment
      ?region_code=62xx
      ?date_from=2025-01-01&date_to=2025-06-30
      ?status=approved
    """
    region_code = django_filters.CharFilter(
        field_name='region__code',
        lookup_expr='exact',
        help_text='Код региона (как в URL /kpi/:regionCode)',
    )
    date_from = django_filters.DateFilter(
        field_name='date_from', lookup_expr='gte',
        help_text='Период начинается не раньше указанной даты',
    )
    date_to = django_filters.DateFilter(
        field_name='date_to', lookup_expr='lte',
        help_text='Период заканчивается не позже указанной даты',
    )

    class Meta:
        model = KPIResult
        fields = ['region', 'region_code', 'kpi_type', 'date_from', 'date_to', 'status']


class KPISummaryFilter(django_filters.FilterSet):
    """
    Фильтры для KPISummaryViewSet.
    Примеры:
      ?region=3&date_from=2025-01-01
      ?region_code=62xx
      ?status=submitted
    """
    region_code = django_filters.CharFilter(
        field_name='region__code',
        lookup_expr='exact',
    )
    date_from = django_filters.DateFilter(
        field_name='date_from', lookup_expr='gte',
    )
    date_to = django_filters.DateFilter(
        field_name='date_to', lookup_expr='lte',
    )

    class Meta:
        model = KPISummary
        fields = ['region', 'region_code', 'date_from', 'date_to', 'status']


class KPIFormulaFilter(django_filters.FilterSet):
    class Meta:
        model = KPIFormula
        fields = ['kpi_type', 'is_active']

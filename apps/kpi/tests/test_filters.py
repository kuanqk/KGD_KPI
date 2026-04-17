"""Тесты django-filter для KPI API."""
from datetime import date

from django.http import QueryDict
from django.test import TestCase

from apps.kpi.filters import KPISummaryFilter
from apps.kpi.tests.test_models import make_region, make_summary


class KPISummaryFilterTest(TestCase):
    def test_range_overlaps_multiple_periods_same_region(self):
        """Без period_exact Q1 и год оба попадают в окно 2026-01-01 … 2027-01-01."""
        region = make_region()
        make_summary(
            region,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 3, 31),
            score_total=10,
        )
        make_summary(
            region,
            date_from=date(2026, 1, 1),
            date_to=date(2027, 1, 1),
            score_total=20,
        )
        qs = KPISummary.objects.all()
        data = QueryDict(
            'date_from=2026-01-01&date_to=2027-01-01',
            mutable=True,
        )
        f = KPISummaryFilter(data=data, queryset=qs)
        self.assertEqual(f.qs.count(), 2)

    def test_period_exact_single_row(self):
        """С period_exact=1 возвращается только сводка с точной парой дат."""
        region = make_region()
        make_summary(
            region,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 3, 31),
            score_total=10,
        )
        make_summary(
            region,
            date_from=date(2026, 1, 1),
            date_to=date(2027, 1, 1),
            score_total=20,
        )
        qs = KPISummary.objects.all()
        data = QueryDict(
            'date_from=2026-01-01&date_to=2027-01-01&period_exact=1',
            mutable=True,
        )
        f = KPISummaryFilter(data=data, queryset=qs)
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.get().score_total, 20)

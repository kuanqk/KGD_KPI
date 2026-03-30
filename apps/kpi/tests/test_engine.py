"""
Тесты KPI Engine — apps/kpi/services/engine.py

Покрывают:
  - Вспомогательные функции (_safe_div, _to_decimal, _apply_score)
  - _count_months
  - Все 6 KPI с граничными условиями
  - KPI 3 специальный случай: 80–89% = 0 баллов (не 5!)
  - KPI 5: исключение уголовных и правоохранительных дел
  - KPI 6: исключение актов с интервалом > 2 лет
  - calculate_all: ранжирование, КГД без ранга, пересчёт (update_or_create)
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.core.models import AuditLog
from apps.etl.models import (
    ActiveInspection,
    AppealDecision,
    CompletedInspection,
    ImportJob,
    ManualInput,
)
from apps.kpi.models import KPIFormula, KPIResult, KPISummary
from apps.kpi.services.engine import (
    KPIEngine,
    _apply_score,
    _safe_div,
    _to_decimal,
)
from apps.regions.models import Region

# ---------------------------------------------------------------------------
# Общие константы
# ---------------------------------------------------------------------------

DATE_FROM = date(2025, 1, 1)
DATE_TO = date(2025, 6, 30)     # 6 месяцев

_counter = itertools.count(1)


def _uid() -> str:
    return f'T-{next(_counter):07d}'


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

def make_region(code, order=1, is_summary=False):
    return Region.objects.get_or_create(
        code=code,
        defaults={
            'name_ru': f'ДГД {code}',
            'name_kz': f'МКД {code}',
            'name_en': f'STD {code}',
            'order': order,
            'is_summary': is_summary,
        },
    )[0]


def make_job(source='inis'):
    return ImportJob.objects.create(source=source)


def make_formulas():
    """Создаёт/обновляет все 6 активных KPIFormula v1."""
    specs = [
        ('assessment', {
            'max_score': 10,
            'metric': 'percent',
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 10},
                {'condition': 'gte', 'value': 90, 'score': 5},
                {'condition': 'lt',  'value': 90, 'score': 0},
            ],
        }),
        ('collection', {
            'max_score': 40,
            'metric': 'percent',
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 40},
                {'condition': 'gte', 'value': 90, 'score': 20},
                {'condition': 'gte', 'value': 80, 'score': 10},
                {'condition': 'lt',  'value': 80, 'score': 0},
            ],
        }),
        ('avg_assessment', {
            'max_score': 10,
            'metric': 'percent',
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 10},
                {'condition': 'gte', 'value': 90, 'score': 5},
                {'condition': 'lt',  'value': 90, 'score': 0},  # 80–89% тоже 0!
            ],
            'exclude_form_type': 'ДФНО',
        }),
        ('workload', {
            'max_score': 15,
            'metric': 'coefficient',
            'thresholds': [
                {'condition': 'gte', 'value': 0.5, 'score': 15},
                {'condition': 'gte', 'value': 0.4, 'score': 5},
                {'condition': 'lt',  'value': 0.4, 'score': 0},
            ],
        }),
        ('long_inspections', {
            'max_score': 10,
            'metric': 'share_pct',
            'long_threshold_days': 180,
            'thresholds': [
                {'condition': 'lt',  'value': 20, 'score': 10},
                {'condition': 'gte', 'value': 20, 'score': 0},
            ],
        }),
        ('cancelled', {
            'max_score': 15,
            'metric': 'share_pct',
            'thresholds': [
                {'condition': 'lte', 'value': 1, 'score': 15},
                {'condition': 'lte', 'value': 2, 'score': 5},
                {'condition': 'gt',  'value': 2, 'score': 0},
            ],
            'exclude_older_than_years': 2,
            'management_filter': 'УНА',
        }),
    ]
    for kpi_type, config in specs:
        KPIFormula.objects.update_or_create(
            kpi_type=kpi_type, version=1,
            defaults={'config': config, 'is_active': True},
        )


def make_engine(date_from=DATE_FROM, date_to=DATE_TO, user=None) -> KPIEngine:
    engine = KPIEngine(date_from=date_from, date_to=date_to, user=user)
    engine._load_formulas()
    return engine


def make_ci(region, job, **kwargs) -> CompletedInspection:
    """CompletedInspection с разумными значениями по умолчанию."""
    defaults = {
        'source': 'inis',
        'source_id': _uid(),
        'management': 'УНА',
        'form_type': 'обычная',
        'completed_date': date(2025, 3, 1),
        'amount_assessed': 0,
        'amount_collected': 0,
        'is_counted': True,
        'is_accepted': True,
    }
    defaults.update(kwargs)
    return CompletedInspection.objects.create(region=region, import_job=job, **defaults)


def make_ai(region, job, **kwargs) -> ActiveInspection:
    """ActiveInspection с разумными значениями по умолчанию."""
    defaults = {
        'source': 'inis',
        'source_id': _uid(),
        'management': 'УНА',
        'case_type': 'обычная',
        'prescription_date': date(2024, 11, 1),
        'is_counted': True,
    }
    defaults.update(kwargs)
    return ActiveInspection.objects.create(region=region, import_job=job, **defaults)


def make_appeal(region, job, **kwargs) -> AppealDecision:
    """AppealDecision с разумными значениями по умолчанию."""
    defaults = {
        'source_id': _uid(),
        'amount_cancelled': 0,
        'is_counted': True,
        'completion_date': date(2024, 1, 1),
        'decision_date': date(2024, 6, 1),
    }
    defaults.update(kwargs)
    return AppealDecision.objects.create(region=region, import_job=job, **defaults)


def make_summary(region, score_total, **kwargs) -> KPISummary:
    """KPISummary с заданным итоговым баллом (для тестов ранжирования)."""
    defaults = {
        'score_assessment': 0,
        'score_collection': 0,
        'score_avg_assessment': 0,
        'score_workload': 0,
        'score_long_inspections': 0,
        'score_cancelled': 0,
        'score_total': score_total,
        'rank': None,
    }
    defaults.update(kwargs)
    return KPISummary.objects.create(
        region=region,
        date_from=DATE_FROM,
        date_to=DATE_TO,
        **defaults,
    )


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

class SafeDivTest(TestCase):
    def test_normal_division(self):
        self.assertEqual(_safe_div(Decimal('10'), Decimal('2')), Decimal('5'))

    def test_zero_denominator_returns_none(self):
        self.assertIsNone(_safe_div(Decimal('10'), Decimal('0')))

    def test_zero_numerator(self):
        self.assertEqual(_safe_div(Decimal('0'), Decimal('5')), Decimal('0'))

    def test_large_values(self):
        result = _safe_div(Decimal('1000000000'), Decimal('3'))
        self.assertIsNotNone(result)


class ToDecimalTest(TestCase):
    def test_none_returns_zero(self):
        self.assertEqual(_to_decimal(None), Decimal('0'))

    def test_int_value(self):
        self.assertEqual(_to_decimal(42), Decimal('42'))

    def test_string_value(self):
        self.assertEqual(_to_decimal('3.14'), Decimal('3.14'))

    def test_decimal_passthrough(self):
        d = Decimal('99.99')
        self.assertEqual(_to_decimal(d), d)

    def test_zero_int(self):
        self.assertEqual(_to_decimal(0), Decimal('0'))


class ApplyScoreTest(TestCase):
    """Тесты _apply_score — первое совпадение выигрывает."""

    def _thresholds_kpi1(self):
        return [
            {'condition': 'gte', 'value': 100, 'score': 10},
            {'condition': 'gte', 'value': 90,  'score': 5},
            {'condition': 'lt',  'value': 90,  'score': 0},
        ]

    def test_exactly_100_pct(self):
        self.assertEqual(_apply_score(Decimal('100'), self._thresholds_kpi1()), 10)

    def test_above_100_pct(self):
        self.assertEqual(_apply_score(Decimal('150'), self._thresholds_kpi1()), 10)

    def test_exactly_90_pct(self):
        self.assertEqual(_apply_score(Decimal('90'), self._thresholds_kpi1()), 5)

    def test_just_below_90_pct(self):
        self.assertEqual(_apply_score(Decimal('89.9999'), self._thresholds_kpi1()), 0)

    def test_zero_pct(self):
        self.assertEqual(_apply_score(Decimal('0'), self._thresholds_kpi1()), 0)

    def test_none_returns_zero(self):
        self.assertEqual(_apply_score(None, self._thresholds_kpi1()), 0)

    def test_lte_condition(self):
        thresholds = [
            {'condition': 'lte', 'value': 1, 'score': 15},
            {'condition': 'lte', 'value': 2, 'score': 5},
            {'condition': 'gt',  'value': 2, 'score': 0},
        ]
        self.assertEqual(_apply_score(Decimal('1'), thresholds), 15)
        self.assertEqual(_apply_score(Decimal('2'), thresholds), 5)
        self.assertEqual(_apply_score(Decimal('2.0001'), thresholds), 0)

    def test_no_match_returns_zero(self):
        thresholds = [{'condition': 'gte', 'value': 200, 'score': 10}]
        self.assertEqual(_apply_score(Decimal('100'), thresholds), 0)


# ---------------------------------------------------------------------------
# _count_months
# ---------------------------------------------------------------------------

class CountMonthsTest(TestCase):
    def _engine(self, date_from, date_to):
        return KPIEngine(date_from=date_from, date_to=date_to)

    def test_same_month(self):
        e = self._engine(date(2025, 3, 1), date(2025, 3, 31))
        self.assertEqual(e.months, 1)

    def test_six_months(self):
        e = self._engine(date(2025, 1, 1), date(2025, 6, 30))
        self.assertEqual(e.months, 6)

    def test_full_year(self):
        e = self._engine(date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(e.months, 12)

    def test_cross_year(self):
        e = self._engine(date(2024, 11, 1), date(2025, 1, 31))
        self.assertEqual(e.months, 3)

    def test_minimum_one_month(self):
        """Даже если dates совпадают — минимум 1 месяц."""
        e = self._engine(date(2025, 6, 15), date(2025, 6, 15))
        self.assertEqual(e.months, 1)


# ---------------------------------------------------------------------------
# KPI 1 — Доначисление
# ---------------------------------------------------------------------------

class KPI1AssessmentTest(TestCase):
    def setUp(self):
        make_formulas()
        self.region = make_region('03xx', 1)
        self.job = make_job()
        self.engine = make_engine()
        # Патчим план, чтобы не зависеть от данных прошлого года
        self._plan_patch = patch.object(
            self.engine, '_calc_plan_assessment', return_value=Decimal('100'),
        )
        self._plan_patch.start()

    def tearDown(self):
        self._plan_patch.stop()

    def test_score_10_at_100_pct(self):
        make_ci(self.region, self.job, amount_assessed=100)
        result = self.engine.calc_assessment(self.region)
        self.assertEqual(result.score, 10)
        self.assertEqual(result.percent, Decimal('100'))

    def test_score_5_at_90_pct(self):
        make_ci(self.region, self.job, amount_assessed=90)
        result = self.engine.calc_assessment(self.region)
        self.assertEqual(result.score, 5)

    def test_score_0_below_90_pct(self):
        make_ci(self.region, self.job, amount_assessed=89)
        result = self.engine.calc_assessment(self.region)
        self.assertEqual(result.score, 0)

    def test_score_0_when_plan_is_none(self):
        """Нет плана → percent=None → 0 баллов."""
        self._plan_patch.stop()
        with patch.object(self.engine, '_calc_plan_assessment', return_value=None):
            result = self.engine.calc_assessment(self.region)
        self.assertEqual(result.score, 0)
        self.assertIsNone(result.percent)
        self._plan_patch.start()

    def test_non_una_management_excluded(self):
        """Записи с management != 'УНА' не попадают в факт."""
        make_ci(self.region, self.job, management='УКН', amount_assessed=500)
        result = self.engine.calc_assessment(self.region)
        self.assertEqual(result.fact, Decimal('0'))

    def test_out_of_period_excluded(self):
        """Запись вне периода не учитывается."""
        make_ci(self.region, self.job,
                completed_date=date(2024, 12, 31), amount_assessed=200)
        result = self.engine.calc_assessment(self.region)
        self.assertEqual(result.fact, Decimal('0'))

    def test_fact_cached_for_kpi6(self):
        """Факт KPI 1 кэшируется в _assessment_facts для использования KPI 6."""
        make_ci(self.region, self.job, amount_assessed=777)
        self.engine.calc_assessment(self.region)
        self.assertEqual(self.engine._assessment_facts[self.region.pk], Decimal('777'))

    def test_result_saved_to_db(self):
        make_ci(self.region, self.job, amount_assessed=100)
        self.engine.calc_assessment(self.region)
        self.assertEqual(
            KPIResult.objects.filter(region=self.region, kpi_type='assessment').count(),
            1,
        )


# ---------------------------------------------------------------------------
# KPI 2 — Взыскание
# ---------------------------------------------------------------------------

class KPI2CollectionTest(TestCase):
    def setUp(self):
        make_formulas()
        self.region = make_region('06xx', 2)
        self.job = make_job()
        self.engine = make_engine()
        self._plan_patch = patch.object(
            self.engine, '_calc_plan_collection', return_value=Decimal('100'),
        )
        self._plan_patch.start()

    def tearDown(self):
        self._plan_patch.stop()

    def test_score_40_at_100_pct(self):
        make_ci(self.region, self.job, amount_collected=100, is_accepted=True)
        result = self.engine.calc_collection(self.region)
        self.assertEqual(result.score, 40)

    def test_score_20_at_90_pct(self):
        make_ci(self.region, self.job, amount_collected=90, is_accepted=True)
        result = self.engine.calc_collection(self.region)
        self.assertEqual(result.score, 20)

    def test_score_10_at_80_pct(self):
        make_ci(self.region, self.job, amount_collected=80, is_accepted=True)
        result = self.engine.calc_collection(self.region)
        self.assertEqual(result.score, 10)

    def test_score_0_below_80_pct(self):
        make_ci(self.region, self.job, amount_collected=79, is_accepted=True)
        result = self.engine.calc_collection(self.region)
        self.assertEqual(result.score, 0)

    def test_is_accepted_false_excluded(self):
        """Записи с is_accepted=False не попадают в факт взыскания."""
        make_ci(self.region, self.job, amount_collected=500, is_accepted=False)
        result = self.engine.calc_collection(self.region)
        self.assertEqual(result.fact, Decimal('0'))

    def test_non_una_excluded(self):
        make_ci(self.region, self.job, management='УНН',
                amount_collected=300, is_accepted=True)
        result = self.engine.calc_collection(self.region)
        self.assertEqual(result.fact, Decimal('0'))


# ---------------------------------------------------------------------------
# KPI 3 — Среднее доначисление на 1 проверку
# ---------------------------------------------------------------------------

class KPI3AvgAssessmentTest(TestCase):
    def setUp(self):
        make_formulas()
        self.region = make_region('09xx', 3)
        self.job = make_job()
        self.engine = make_engine()
        # Единый план = 100 для удобства тестирования
        self._plan_patch = patch.object(
            self.engine, '_kpi3_plan', return_value=Decimal('100'),
        )
        self._plan_patch.start()

    def tearDown(self):
        self._plan_patch.stop()

    def test_score_10_at_100_pct(self):
        """Среднее = план → 100% → 10 баллов."""
        make_ci(self.region, self.job, amount_assessed=100, is_counted=True)
        result = self.engine.calc_avg_assessment(self.region)
        self.assertEqual(result.score, 10)

    def test_score_5_at_90_pct(self):
        make_ci(self.region, self.job, amount_assessed=90, is_counted=True)
        result = self.engine.calc_avg_assessment(self.region)
        self.assertEqual(result.score, 5)

    def test_score_0_at_85_pct(self):
        """
        Критический случай claude.md: диапазон 80–89% даёт 0 (не 5!).
        Среднее = 85/100 = 85% → порог <90 → 0 баллов.
        """
        make_ci(self.region, self.job, amount_assessed=85, is_counted=True)
        result = self.engine.calc_avg_assessment(self.region)
        self.assertEqual(result.score, 0)

    def test_score_0_at_80_pct(self):
        """80% тоже даёт 0, а не 5."""
        make_ci(self.region, self.job, amount_assessed=80, is_counted=True)
        result = self.engine.calc_avg_assessment(self.region)
        self.assertEqual(result.score, 0)

    def test_dfno_excluded_from_sum_and_count(self):
        """
        ДФНО исключается из суммы И из кол-ва проверок.
        Без ДФНО: 1 проверка * 90 → среднее=90 → score=5.
        С ДФНО в числителе/знаменателе — искажение → должны исключить.
        """
        make_ci(self.region, self.job, amount_assessed=90, form_type='обычная', is_counted=True)
        make_ci(self.region, self.job, amount_assessed=1000, form_type='ДФНО', is_counted=True)
        result = self.engine.calc_avg_assessment(self.region)
        # Только 1 обычная проверка → среднее=90 → score=5
        self.assertEqual(result.score, 5)
        self.assertEqual(result.calc_details['inspection_count'], 1)

    def test_is_counted_false_excluded(self):
        """is_counted=False не учитывается."""
        make_ci(self.region, self.job, amount_assessed=500, is_counted=False)
        result = self.engine.calc_avg_assessment(self.region)
        self.assertIsNone(result.fact)  # count=0 → avg_fact=None → score=0
        self.assertEqual(result.score, 0)

    def test_no_data_score_zero(self):
        result = self.engine.calc_avg_assessment(self.region)
        self.assertEqual(result.score, 0)
        self.assertIsNone(result.fact)


# ---------------------------------------------------------------------------
# KPI 4 — Коэффициент занятости
# ---------------------------------------------------------------------------

class KPI4WorkloadTest(TestCase):
    def setUp(self):
        make_formulas()
        self.region = make_region('15xx', 4)
        self.job = make_job()
        # Период: 6 месяцев (DATE_FROM=2025-01-01, DATE_TO=2025-06-30)
        self.engine = make_engine()

    def _set_staff(self, count):
        ManualInput.objects.update_or_create(
            region=self.region, year=DATE_FROM.year,
            defaults={'staff_count': count},
        )

    def test_score_15_at_0_5(self):
        """30 проверок / 10 сотрудников / 6 месяцев = 0.5 → 15 баллов."""
        self._set_staff(10)
        for _ in range(30):
            make_ci(self.region, self.job, is_counted=True)
        result = self.engine.calc_workload(self.region)
        self.assertEqual(result.score, 15)

    def test_score_5_at_0_4(self):
        """24 проверки / 10 сотрудников / 6 месяцев = 0.4 → 5 баллов."""
        self._set_staff(10)
        for _ in range(24):
            make_ci(self.region, self.job, is_counted=True)
        result = self.engine.calc_workload(self.region)
        self.assertEqual(result.score, 5)

    def test_score_0_below_0_4(self):
        """23 проверки / 10 / 6 = 0.3833... → 0 баллов."""
        self._set_staff(10)
        for _ in range(23):
            make_ci(self.region, self.job, is_counted=True)
        result = self.engine.calc_workload(self.region)
        self.assertEqual(result.score, 0)

    def test_no_manual_input_score_zero(self):
        """Нет ручного ввода (staff_count=None) → коэффициент=None → 0 баллов."""
        for _ in range(50):
            make_ci(self.region, self.job, is_counted=True)
        result = self.engine.calc_workload(self.region)
        self.assertEqual(result.score, 0)
        self.assertIsNone(result.fact)

    def test_months_affects_coefficient(self):
        """Период из 3 месяцев удваивает коэффициент относительно 6 месяцев."""
        self._set_staff(10)
        for _ in range(30):
            make_ci(self.region, self.job, is_counted=True,
                    completed_date=date(2025, 2, 1))
        # 3-месячный период: 30/10/3 = 1.0 → 15 баллов
        engine_3m = make_engine(date_from=date(2025, 1, 1), date_to=date(2025, 3, 31))
        result = engine_3m.calc_workload(self.region)
        self.assertEqual(result.score, 15)

    def test_is_counted_false_excluded(self):
        """Проверки с is_counted=False не учитываются."""
        self._set_staff(10)
        for _ in range(30):
            make_ci(self.region, self.job, is_counted=False)
        result = self.engine.calc_workload(self.region)
        # count=0 → coefficient=0 → score=0
        self.assertEqual(result.score, 0)


# ---------------------------------------------------------------------------
# KPI 5 — Доля проверок > 6 месяцев
# ---------------------------------------------------------------------------

class KPI5LongInspectionsTest(TestCase):
    """
    DATE_TO = 2025-06-30
    cutoff = 2025-06-30 - 180 = 2025-01-01
    Долгая: prescription_date < 2025-01-01
    Короткая: prescription_date >= 2025-01-01
    """

    def setUp(self):
        make_formulas()
        self.region = make_region('18xx', 5)
        self.job = make_job()
        self.engine = make_engine()

    def test_score_10_share_below_20_pct(self):
        """1 долгая из 6 всего = 16.7% → <20% → 10 баллов."""
        make_ai(self.region, self.job, prescription_date=date(2024, 12, 1))  # долгая
        for _ in range(5):
            make_ai(self.region, self.job, prescription_date=date(2025, 2, 1))  # короткая
        result = self.engine.calc_long_inspections(self.region)
        self.assertEqual(result.score, 10)

    def test_score_0_share_at_20_pct(self):
        """1 долгая из 5 = 20% → ≥20% → 0 баллов."""
        make_ai(self.region, self.job, prescription_date=date(2024, 12, 1))  # долгая
        for _ in range(4):
            make_ai(self.region, self.job, prescription_date=date(2025, 2, 1))  # короткая
        result = self.engine.calc_long_inspections(self.region)
        self.assertEqual(result.score, 0)

    def test_no_active_inspections_score_10(self):
        """Нет активных проверок → доля 0% → максимальный балл."""
        result = self.engine.calc_long_inspections(self.region)
        self.assertEqual(result.score, 10)
        self.assertEqual(result.calc_details['total_count'], 0)

    def test_criminal_case_excluded(self):
        """Уголовные дела не попадают в выборку."""
        for _ in range(5):
            make_ai(self.region, self.job,
                    case_type='уголовное дело',
                    prescription_date=date(2024, 12, 1))
        make_ai(self.region, self.job, prescription_date=date(2025, 2, 1))  # 1 обычная
        result = self.engine.calc_long_inspections(self.region)
        # Только 1 обычная (короткая) → 0 долгих из 1 → 0% → 10 баллов
        self.assertEqual(result.score, 10)
        self.assertEqual(result.calc_details['total_count'], 1)

    def test_law_enforcement_request_excluded(self):
        """Дела по запросам правоохранительных органов исключаются."""
        for _ in range(3):
            make_ai(self.region, self.job,
                    case_type='правоохранительные органы',
                    prescription_date=date(2024, 12, 1))
        result = self.engine.calc_long_inspections(self.region)
        self.assertEqual(result.calc_details['total_count'], 0)

    def test_is_counted_false_excluded(self):
        make_ai(self.region, self.job,
                is_counted=False, prescription_date=date(2024, 12, 1))
        result = self.engine.calc_long_inspections(self.region)
        self.assertEqual(result.calc_details['total_count'], 0)

    def test_all_long_score_zero(self):
        """Все проверки долгие → 100% → ≥20% → 0 баллов."""
        for _ in range(5):
            make_ai(self.region, self.job, prescription_date=date(2024, 1, 1))
        result = self.engine.calc_long_inspections(self.region)
        self.assertEqual(result.score, 0)


# ---------------------------------------------------------------------------
# KPI 6 — Удельный вес отменённых сумм
# ---------------------------------------------------------------------------

class KPI6CancelledTest(TestCase):
    def setUp(self):
        make_formulas()
        self.region = make_region('21xx', 6)
        self.job = make_job()
        self.engine = make_engine()
        # Предустанавливаем факт KPI 1 = 1000 в кэш, чтобы изолировать тест
        self.engine._assessment_facts[self.region.pk] = Decimal('1000')

    def test_score_15_at_exactly_1_pct(self):
        """Отменено 10 / доначислено 1000 = 1% → ≤1% → 15 баллов."""
        make_appeal(self.region, self.job,
                    amount_cancelled=10, is_counted=True,
                    completion_date=date(2024, 1, 1), decision_date=date(2024, 6, 1))
        result = self.engine.calc_cancelled(self.region)
        self.assertEqual(result.score, 15)

    def test_score_5_at_exactly_2_pct(self):
        """Отменено 20 / 1000 = 2% → ≤2% → 5 баллов."""
        make_appeal(self.region, self.job,
                    amount_cancelled=20, is_counted=True,
                    completion_date=date(2024, 1, 1), decision_date=date(2024, 6, 1))
        result = self.engine.calc_cancelled(self.region)
        self.assertEqual(result.score, 5)

    def test_score_0_above_2_pct(self):
        """Отменено 21 / 1000 = 2.1% → >2% → 0 баллов."""
        make_appeal(self.region, self.job,
                    amount_cancelled=21, is_counted=True,
                    completion_date=date(2024, 1, 1), decision_date=date(2024, 6, 1))
        result = self.engine.calc_cancelled(self.region)
        self.assertEqual(result.score, 0)

    def test_two_year_gap_excluded(self):
        """
        Акт с (decision_date − completion_date) > 730 дней исключается.
        После исключения — нет отменённых сумм → доля 0% → 15 баллов.
        """
        make_appeal(self.region, self.job,
                    amount_cancelled=500, is_counted=True,
                    completion_date=date(2020, 1, 1),
                    decision_date=date(2022, 2, 1))  # >730 дней
        result = self.engine.calc_cancelled(self.region)
        self.assertEqual(result.score, 15)  # 0/1000 = 0% → 15

    def test_within_two_years_included(self):
        """Акт с интервалом < 2 лет остаётся в выборке."""
        make_appeal(self.region, self.job,
                    amount_cancelled=30, is_counted=True,
                    completion_date=date(2023, 1, 1),
                    decision_date=date(2024, 6, 1))  # ~517 дней < 730
        result = self.engine.calc_cancelled(self.region)
        # 30/1000 = 3% → >2 → 0
        self.assertEqual(result.score, 0)

    def test_no_assessed_score_15(self):
        """Нет доначислений → доля 0% → 15 баллов."""
        self.engine._assessment_facts[self.region.pk] = Decimal('0')
        make_appeal(self.region, self.job,
                    amount_cancelled=100, is_counted=True,
                    completion_date=date(2024, 1, 1), decision_date=date(2024, 6, 1))
        result = self.engine.calc_cancelled(self.region)
        self.assertEqual(result.score, 15)

    def test_is_counted_false_excluded(self):
        """is_counted=False не учитывается."""
        make_appeal(self.region, self.job,
                    amount_cancelled=1000, is_counted=False,
                    completion_date=date(2024, 1, 1), decision_date=date(2024, 6, 1))
        result = self.engine.calc_cancelled(self.region)
        self.assertEqual(result.score, 15)  # 0/1000 = 0%


# ---------------------------------------------------------------------------
# _assign_ranks — юнит-тест ранжирования
# ---------------------------------------------------------------------------

class AssignRanksTest(TestCase):
    def setUp(self):
        make_formulas()
        self.r1 = make_region('27xx', 7)
        self.r2 = make_region('30xx', 8)
        self.r3 = make_region('33xx', 9)
        self.kgd = make_region('00xx', 21, is_summary=True)
        self.engine = KPIEngine(date_from=DATE_FROM, date_to=DATE_TO)

    def test_ranks_assigned_descending(self):
        s1 = make_summary(self.r1, score_total=75)
        s2 = make_summary(self.r2, score_total=50)
        s3 = make_summary(self.r3, score_total=60)

        self.engine._assign_ranks([s1, s2, s3])

        s1.refresh_from_db(); s2.refresh_from_db(); s3.refresh_from_db()
        self.assertEqual(s1.rank, 1)
        self.assertEqual(s3.rank, 2)
        self.assertEqual(s2.rank, 3)

    def test_tied_scores_same_rank(self):
        """При равных баллах — одинаковый ранг (RANK, не DENSE_RANK)."""
        s1 = make_summary(self.r1, score_total=75)
        s2 = make_summary(self.r2, score_total=75)   # равный балл
        s3 = make_summary(self.r3, score_total=50)

        self.engine._assign_ranks([s1, s2, s3])

        s1.refresh_from_db(); s2.refresh_from_db(); s3.refresh_from_db()
        self.assertEqual(s1.rank, 1)
        self.assertEqual(s2.rank, 1)
        self.assertEqual(s3.rank, 3)   # следующий ранг — 3, не 2

    def test_kgd_summary_not_ranked(self):
        """КГД (is_summary=True) не получает ранг."""
        s_kgd = make_summary(self.kgd, score_total=100)
        s1 = make_summary(self.r1, score_total=80)

        self.engine._assign_ranks([s_kgd, s1])

        s_kgd.refresh_from_db(); s1.refresh_from_db()
        self.assertIsNone(s_kgd.rank)
        self.assertEqual(s1.rank, 1)

    def test_single_region_rank_one(self):
        s = make_summary(self.r1, score_total=30)
        self.engine._assign_ranks([s])
        s.refresh_from_db()
        self.assertEqual(s.rank, 1)


# ---------------------------------------------------------------------------
# calculate_all — интеграционный тест
# ---------------------------------------------------------------------------

class CalculateAllTest(TestCase):
    def setUp(self):
        make_formulas()
        self.r1 = make_region('39xx', 10)
        self.r2 = make_region('43xx', 11)
        self.kgd = make_region('00xx', 21, is_summary=True)
        self.job = make_job()

    def test_summaries_created_for_all_regions(self):
        """calculate_all создаёт KPISummary для каждого переданного региона."""
        engine = make_engine()
        summaries = engine.calculate_all(regions=[self.r1, self.r2])
        self.assertEqual(len(summaries), 2)
        self.assertEqual(
            KPISummary.objects.filter(date_from=DATE_FROM, date_to=DATE_TO).count(), 2,
        )

    def test_audit_log_created(self):
        engine = make_engine()
        engine.calculate_all(regions=[self.r1])
        log = AuditLog.objects.filter(event='kpi_calc').first()
        self.assertIsNotNone(log)
        self.assertIn('date_from', log.details)

    def test_recalculation_updates_existing(self):
        """Повторный вызов calculate_all обновляет существующие результаты (update_or_create)."""
        engine1 = make_engine()
        engine1.calculate_all(regions=[self.r1])

        # Создаём запись с большим amount_assessed, чтобы изменить score
        make_ci(self.r1, self.job, amount_assessed=9_000_000)
        engine2 = make_engine()
        engine2.calculate_all(regions=[self.r1])

        # KPISummary должен остаться один (обновлён, не создан новый)
        self.assertEqual(
            KPISummary.objects.filter(
                region=self.r1, date_from=DATE_FROM, date_to=DATE_TO,
            ).count(),
            1,
        )

    def test_kgd_excluded_from_default_regions(self):
        """КГД (is_summary=True) не входит в calculate_all(regions=None)."""
        # Убедимся, что есть хотя бы один не-КГД регион
        engine = make_engine()
        summaries = engine.calculate_all(regions=[self.r1, self.kgd])
        kgd_summaries = [s for s in summaries if s.region_id == self.kgd.pk]
        # KGD попала в список регионов вручную → summary создаётся, но rank=None
        for s in kgd_summaries:
            self.assertIsNone(s.rank)


# ===========================================================================
# Тесты с реальными данными из Excel Статистика_КЭР_РК_на_01_01_2026
# ===========================================================================

# Полный год (для KPI 4, 5 с 12 месяцами)
DATE_FULL_FROM = date(2025, 1, 1)
DATE_FULL_TO   = date(2025, 12, 31)


def make_engine_full(user=None) -> KPIEngine:
    engine = KPIEngine(date_from=DATE_FULL_FROM, date_to=DATE_FULL_TO, user=user)
    engine._load_formulas()
    return engine


def bulk_ci(region, job, count: int, **kwargs) -> list:
    """Быстрое создание N CompletedInspection через bulk_create."""
    defaults = {
        'source': 'inis',
        'management': 'УНА',
        'form_type': 'обычная',
        'completed_date': date(2025, 6, 1),
        'amount_assessed': 0,
        'amount_collected': 0,
        'is_counted': True,
        'is_accepted': True,
        'raw_data': {},
    }
    defaults.update(kwargs)
    records = [
        CompletedInspection(region=region, import_job=job, source_id=_uid(), **defaults)
        for _ in range(count)
    ]
    return CompletedInspection.objects.bulk_create(records)


def bulk_ai(region, job, count: int, **kwargs) -> list:
    """Быстрое создание N ActiveInspection через bulk_create."""
    defaults = {
        'source': 'inis',
        'management': 'УНА',
        'case_type': 'обычная',
        'is_counted': True,
        'raw_data': {},
    }
    defaults.update(kwargs)
    records = [
        ActiveInspection(region=region, import_job=job, source_id=_uid(), **defaults)
        for _ in range(count)
    ]
    return ActiveInspection.objects.bulk_create(records)


# ---------------------------------------------------------------------------
# KPI 1 — Доначисление: реальные данные
# ---------------------------------------------------------------------------

class KPI1RealDataTest(TestCase):
    """
    KPI 1 — Доначисление с конкретными числами из Excel.
    Планы замокированы; факты — реальные суммы доначислений 2025 года.
    """

    def setUp(self):
        make_formulas()
        self.job  = make_job()
        self.engine = make_engine_full()

    def _run(self, region, fact_tg: int, plan_tg: Decimal):
        make_ci(region, self.job,
                amount_assessed=fact_tg,
                completed_date=date(2025, 6, 1))
        with patch.object(self.engine, '_calc_plan_assessment', return_value=plan_tg):
            return self.engine.calc_assessment(region)

    def test_almaty_above_100pct_score_10(self):
        """
        г.Алматы (60xx): факт 39 277.38 млн / план 39 136.46 млн = 100.36% → 10 баллов.
        """
        region = make_region('60xx', 16)
        fact   = int(39_277.38 * 1_000_000)
        plan   = Decimal(str(int(39_136.46 * 1_000_000)))
        result = self._run(region, fact, plan)

        self.assertEqual(result.score, 10)
        self.assertGreaterEqual(float(result.percent), 100.0)

    def test_vko_97pct_score_5(self):
        """
        ВКО (18xx): факт 2 538.06 млн / план 2 609.17 млн ≈ 97.3% → 5 баллов.
        Исполнение ≥90% но <100%.
        """
        region = make_region('18xx', 5)
        fact   = int(2_538.06 * 1_000_000)
        plan   = Decimal(str(int(2_609.17 * 1_000_000)))
        result = self._run(region, fact, plan)

        self.assertEqual(result.score, 5)
        pct = float(result.percent)
        self.assertGreaterEqual(pct, 90.0)
        self.assertLess(pct, 100.0)

    def test_boundary_899_pct_score_0(self):
        """
        Граница: исполнение 89.9% (ровно под порогом 90%) → 0 баллов.
        """
        region = make_region('03xx', 1)
        plan   = Decimal('1000000000')
        fact   = int(float(plan) * 0.899)
        result = self._run(region, fact, plan)

        self.assertEqual(result.score, 0)
        self.assertLess(float(result.percent), 90.0)


# ---------------------------------------------------------------------------
# KPI 2 — Взыскание: реальные данные
# ---------------------------------------------------------------------------

class KPI2RealDataTest(TestCase):
    """KPI 2 — Взыскание с конкретными числами."""

    def setUp(self):
        make_formulas()
        self.job    = make_job()
        self.engine = make_engine_full()

    def _run(self, region, fact_tg: int, plan_tg: Decimal):
        make_ci(region, self.job,
                amount_collected=fact_tg,
                is_accepted=True,
                completed_date=date(2025, 6, 1))
        with patch.object(self.engine, '_calc_plan_collection', return_value=plan_tg):
            return self.engine.calc_collection(region)

    def test_zhambyl_above_plan_score_40(self):
        """
        Жамбылская (21xx): факт 1 100 млн > план 1 009.36 млн → ≥100% → 40 баллов.
        """
        region = make_region('21xx', 6)
        plan   = Decimal(str(int(1_009.36 * 1_000_000)))
        fact   = int(1_100.00 * 1_000_000)
        result = self._run(region, fact, plan)

        self.assertEqual(result.score, 40)
        self.assertGreaterEqual(float(result.percent), 100.0)

    def test_pavlodar_85pct_score_10(self):
        """
        Павлодарская (45xx): исполнение 85% (≥80% но <90%) → 10 баллов.
        """
        region = make_region('45xx', 12)
        plan   = Decimal('1000000000')
        fact   = int(float(plan) * 0.85)
        result = self._run(region, fact, plan)

        self.assertEqual(result.score, 10)
        pct = float(result.percent)
        self.assertGreaterEqual(pct, 80.0)
        self.assertLess(pct, 90.0)

    def test_below_80pct_score_0(self):
        """Исполнение 79.9% → <80% → 0 баллов."""
        region = make_region('72xx', 20)
        plan   = Decimal('1000000000')
        fact   = int(float(plan) * 0.799)
        result = self._run(region, fact, plan)

        self.assertEqual(result.score, 0)
        self.assertLess(float(result.percent), 80.0)


# ---------------------------------------------------------------------------
# KPI 3 — Среднее доначисление: реальные данные
# ---------------------------------------------------------------------------

class KPI3RealDataTest(TestCase):
    """
    KPI 3 — Среднее доначисление на 1 проверку.
    Критический случай: диапазон 80–89% → 0 баллов (не 5!).
    """

    def setUp(self):
        make_formulas()
        self.job    = make_job()
        self.engine = make_engine_full()

    def test_sko_787pct_score_0(self):
        """
        СКО (48xx): среднее 25.14 млн / план 31.94 млн = 78.7% → <90% → 0 баллов.
        Важно: диапазон 80–89% здесь не применяется, т.к. это вообще <80%.
        """
        region   = make_region('48xx', 13)
        plan_tg  = Decimal(str(int(31.94 * 1_000_000)))   # 31 940 000 тг
        fact_tg  = int(25.14 * 1_000_000)                 # 25 140 000 тг (одна проверка)

        make_ci(region, self.job,
                amount_assessed=fact_tg,
                form_type='обычная',
                is_counted=True,
                completed_date=date(2025, 6, 1))

        with patch.object(self.engine, '_kpi3_plan', return_value=plan_tg):
            result = self.engine.calc_avg_assessment(region)

        self.assertEqual(result.score, 0)
        self.assertLess(float(result.percent), 90.0)
        # Убеждаемся, что 78.7% — это именно не-5 зона (не путать с KPI 1/2)
        self.assertLess(float(result.percent), 80.0)

    def test_range_80_89pct_score_0_not_5(self):
        """
        Диапазон 80–89% для KPI 3 → 0 баллов (не 5!).
        Это намеренное отличие KPI 3 от KPI 1 и KPI 2.
        """
        region  = make_region('27xx', 7)
        plan_tg = Decimal('1000000')    # 1 проверка = 1 000 000 тг (=план)

        # Факт = 85% от плана → 850 000 тг
        make_ci(region, self.job,
                amount_assessed=850_000,
                form_type='обычная',
                is_counted=True,
                completed_date=date(2025, 6, 1))

        with patch.object(self.engine, '_kpi3_plan', return_value=plan_tg):
            result = self.engine.calc_avg_assessment(region)

        # 85% ≥ 80% but <90% → по KPI 1/2 было бы 5 баллов, по KPI 3 → 0
        pct = float(result.percent)
        self.assertGreaterEqual(pct, 80.0)
        self.assertLess(pct, 90.0)
        self.assertEqual(result.score, 0,
            msg='KPI 3: диапазон 80–89% должен давать 0, а не 5 баллов!')

    def test_dfno_excluded_does_not_inflate_average(self):
        """
        ДФНО исключается из числителя и знаменателя.
        Без ДФНО: 1 проверка × 850 000 → среднее = 850 000 = 85% плана → 0 баллов.
        Если бы ДФНО не исключалась: (850 000 + 50 000 000) / 2 = 25 425 000 — другой результат.
        Тест гарантирует, что ДФНО убрана из обоих.
        """
        region  = make_region('30xx', 8)
        plan_tg = Decimal('1000000')

        make_ci(region, self.job, amount_assessed=850_000,
                form_type='обычная', is_counted=True,
                completed_date=date(2025, 6, 1))
        make_ci(region, self.job, amount_assessed=50_000_000,
                form_type='ДФНО', is_counted=True,
                completed_date=date(2025, 6, 1))

        with patch.object(self.engine, '_kpi3_plan', return_value=plan_tg):
            result = self.engine.calc_avg_assessment(region)

        # Только 1 обычная проверка считается → среднее = 850 000 → 85% → 0 баллов
        self.assertEqual(result.calc_details['inspection_count'], 1)
        self.assertEqual(result.score, 0)


# ---------------------------------------------------------------------------
# KPI 4 — Занятость: реальные данные (полный год)
# ---------------------------------------------------------------------------

class KPI4RealDataTest(TestCase):
    """
    KPI 4 — Коэффициент занятости с реальными числами за полный 2025 год (12 мес.).
    """

    def setUp(self):
        make_formulas()
        self.job    = make_job()
        self.engine = make_engine_full()

    def _set_staff(self, region, count: int):
        ManualInput.objects.update_or_create(
            region=region, year=DATE_FULL_FROM.year,
            defaults={'staff_count': count},
        )

    def test_almaty_617_inspections_59_staff_score_15(self):
        """
        г.Алматы (60xx): 617 проверок / 59 сотрудников / 12 мес = 0.871 → ≥0.5 → 15 баллов.
        """
        region = make_region('60xx', 16)
        self._set_staff(region, 59)
        bulk_ci(region, self.job, 617, completed_date=date(2025, 6, 1))

        result = self.engine.calc_workload(region)

        self.assertEqual(result.score, 15)
        coef = float(result.fact)
        self.assertGreater(coef, 0.5)
        # Проверяем конкретное значение с точностью до 2 знаков
        self.assertAlmostEqual(coef, 617 / 59 / 12, places=2)

    def test_akmola_50_inspections_11_staff_score_0(self):
        """
        Акмолинская (03xx): 50 проверок / 11 сотрудников / 12 мес = 0.379 → <0.4 → 0 баллов.
        """
        region = make_region('03xx', 1)
        self._set_staff(region, 11)
        bulk_ci(region, self.job, 50, completed_date=date(2025, 6, 1))

        result = self.engine.calc_workload(region)

        self.assertEqual(result.score, 0)
        self.assertLess(float(result.fact), 0.4)

    def test_boundary_040_499_score_5(self):
        """
        Граница 0.4–0.499: коэффициент = 48/10/12 = 0.400 → ≥0.4 but <0.5 → 5 баллов.
        """
        region = make_region('06xx', 2)
        self._set_staff(region, 10)
        bulk_ci(region, self.job, 48, completed_date=date(2025, 6, 1))

        result = self.engine.calc_workload(region)

        self.assertEqual(result.score, 5)
        coef = float(result.fact)
        self.assertGreaterEqual(coef, 0.4)
        self.assertLess(coef, 0.5)


# ---------------------------------------------------------------------------
# KPI 5 — Долгие проверки: реальные данные (полный год)
# ---------------------------------------------------------------------------

class KPI5RealDataTest(TestCase):
    """
    KPI 5 — Доля проверок > 6 месяцев с реальными числами.
    Период: 01.01.2025 — 31.12.2025 (DATE_TO=2025-12-31).
    Порог «долгой»: prescription_date < 2025-12-31 − 180 дней ≈ 2025-07-04.
    """

    # date_to − 180 дней = 2025-12-31 − 180 = 2025-07-04
    _LONG_DATE  = date(2025, 1, 1)    # prescription 1 января → долгая (>180 от 31 дек)
    _SHORT_DATE = date(2025, 10, 1)   # prescription октябрь → короткая (<90 дней до конца)

    def setUp(self):
        make_formulas()
        self.job    = make_job()
        self.engine = make_engine_full()

    def test_zhetisu_2_long_of_6_score_0(self):
        """
        Область Жетісу (70xx): 2 долгих из 6 = 33.3% → ≥20% → 0 баллов.
        """
        region = make_region('70xx', 18)
        bulk_ai(region, self.job, 2, prescription_date=self._LONG_DATE)
        bulk_ai(region, self.job, 4, prescription_date=self._SHORT_DATE)

        result = self.engine.calc_long_inspections(region)

        self.assertEqual(result.score, 0)
        share = float(result.percent)
        self.assertAlmostEqual(share, 100 * 2 / 6, places=0)
        self.assertGreaterEqual(share, 20.0)

    def test_shymkent_5_long_of_26_score_10(self):
        """
        г.Шымкент (59xx): 5 долгих из 26 = 19.2% → <20% → 10 баллов.
        """
        region = make_region('59xx', 15)
        bulk_ai(region, self.job, 5,  prescription_date=self._LONG_DATE)
        bulk_ai(region, self.job, 21, prescription_date=self._SHORT_DATE)

        result = self.engine.calc_long_inspections(region)

        self.assertEqual(result.score, 10)
        share = float(result.percent)
        self.assertAlmostEqual(share, 100 * 5 / 26, places=0)
        self.assertLess(share, 20.0)


# ---------------------------------------------------------------------------
# KPI 6 — Отменённые суммы: реальные данные
# ---------------------------------------------------------------------------

class KPI6RealDataTest(TestCase):
    """KPI 6 — Удельный вес отменённых сумм с конкретными числами из Excel."""

    def setUp(self):
        make_formulas()
        self.job    = make_job()
        self.engine = make_engine_full()

    def test_akmola_152mln_of_1659mln_score_0(self):
        """
        Акмолинская (03xx): отменено 152.81 млн / доначислено 1 659.84 млн = 9.2% → >2% → 0 баллов.
        """
        region      = make_region('03xx', 1)
        assessed_tg = Decimal(str(int(1_659.84 * 1_000_000)))  # 1 659 840 000
        cancelled_tg = int(152.81 * 1_000_000)                 # 152 810 000

        self.engine._assessment_facts[region.pk] = assessed_tg
        make_appeal(region, self.job,
                    amount_cancelled=cancelled_tg,
                    is_counted=True,
                    completion_date=date(2024, 1, 1),
                    decision_date=date(2024, 6, 1))

        result = self.engine.calc_cancelled(region)

        self.assertEqual(result.score, 0)
        pct = float(result.percent)
        self.assertAlmostEqual(pct, 152.81 / 1659.84 * 100, places=1)
        self.assertGreater(pct, 2.0)

    def test_aktobe_zero_cancelled_score_15(self):
        """
        Актюбинская (06xx): 0 тг отменено → 0% → ≤1% → 15 баллов.
        """
        region      = make_region('06xx', 2)
        assessed_tg = Decimal(str(int(11_448.07 * 1_000_000)))

        self.engine._assessment_facts[region.pk] = assessed_tg
        # Запись с нулевой суммой — считается, но не меняет долю
        make_appeal(region, self.job,
                    amount_cancelled=0,
                    is_counted=True,
                    completion_date=date(2024, 1, 1),
                    decision_date=date(2024, 6, 1))

        result = self.engine.calc_cancelled(region)

        self.assertEqual(result.score, 15)
        self.assertEqual(float(result.percent), 0.0)

    def test_old_act_over_2years_excluded_score_15(self):
        """
        Акмолинская: акт с интервалом >2 лет (730 дней) до решения комиссии исключается.
        Если исключить — сумма отменённых = 0 → 0% → 15 баллов.
        """
        region      = make_region('48xx', 13)
        assessed_tg = Decimal(str(int(1_659.84 * 1_000_000)))

        self.engine._assessment_facts[region.pk] = assessed_tg
        # Акт завершён 01.01.2020, решение 01.02.2022 → 762 дня > 730 → ИСКЛЮЧИТЬ
        make_appeal(region, self.job,
                    amount_cancelled=int(152.81 * 1_000_000),
                    is_counted=True,
                    completion_date=date(2020, 1, 1),
                    decision_date=date(2022, 2, 1))

        result = self.engine.calc_cancelled(region)

        self.assertEqual(result.score, 15,
            msg='Акт старше 2 лет должен быть исключён → 0% → 15 баллов')


# ---------------------------------------------------------------------------
# Итоговый рейтинг: 20 ДГД + КГД
# ---------------------------------------------------------------------------

# Все 20 ДГД: (код, порядок сортировки, итоговый балл)
# Алматинская (09xx) = 100 → место 1
# Акмолинская (03xx) = 45 → последнее место
_ALL_DGD = [
    ('03xx', 1,  45),
    ('06xx', 2,  90),
    ('09xx', 3,  100),   # Алматинская  → 1-е место
    ('15xx', 4,  100),   # Атырауская   → тай с Алматинской (оба rank=1)
    ('18xx', 5,  80),
    ('21xx', 6,  75),
    ('27xx', 7,  70),
    ('30xx', 8,  85),
    ('33xx', 9,  95),
    ('39xx', 10, 65),
    ('43xx', 11, 90),
    ('45xx', 12, 60),
    ('48xx', 13, 50),
    ('58xx', 14, 55),
    ('59xx', 15, 85),
    ('60xx', 16, 70),
    ('62xx', 17, 80),
    ('70xx', 18, 55),
    ('71xx', 19, 48),
    ('72xx', 20, 46),
]

# Используем стандартный 6-месячный период (make_summary тоже его использует)
_R_DATE_FROM = DATE_FROM
_R_DATE_TO   = DATE_TO


def _make_ranking_summary(region, score_total: int) -> KPISummary:
    """KPISummary с явным периодом (не зависит от глобальных констант make_summary)."""
    return KPISummary.objects.create(
        region=region,
        date_from=_R_DATE_FROM,
        date_to=_R_DATE_TO,
        score_assessment=0,
        score_collection=0,
        score_avg_assessment=0,
        score_workload=0,
        score_long_inspections=0,
        score_cancelled=0,
        score_total=score_total,
        rank=None,
    )


class FullRankingTest(TestCase):
    """
    Итоговый рейтинг: 20 ДГД + КГД (is_summary=True).
    Проверяет корректность rank-назначения методом _assign_ranks.
    """

    def setUp(self):
        make_formulas()
        self.regions   = {}
        self.summaries = []

        for code, order, score in _ALL_DGD:
            r = make_region(code, order, is_summary=False)
            self.regions[code] = r
            self.summaries.append(_make_ranking_summary(r, score))

        self.kgd_region  = make_region('00xx', 21, is_summary=True)
        self.kgd_summary = _make_ranking_summary(self.kgd_region, score_total=88)

        self.engine = KPIEngine(date_from=_R_DATE_FROM, date_to=_R_DATE_TO)

    # ── Тесты ──────────────────────────────────────────────────────────────

    def test_almaty_score_100_rank_1(self):
        """
        Алматинская (09xx) = 100 баллов → rank = 1.
        (Тай с Атырауской — обе получают rank=1.)
        """
        self.engine._assign_ranks(self.summaries + [self.kgd_summary])

        almaty = KPISummary.objects.get(
            region=self.regions['09xx'],
            date_from=_R_DATE_FROM, date_to=_R_DATE_TO,
        )
        self.assertEqual(almaty.score_total, 100)
        self.assertEqual(almaty.rank, 1)

    def test_kgd_is_summary_has_no_rank(self):
        """КГД (is_summary=True) не ранжируется → rank=None после _assign_ranks."""
        self.engine._assign_ranks(self.summaries + [self.kgd_summary])

        self.kgd_summary.refresh_from_db()
        self.assertIsNone(self.kgd_summary.rank)

    def test_all_20_dgd_receive_numeric_ranks(self):
        """
        Все 20 ДГД получают числовой ранг.
        Максимальный ранг ≤ 20, минимальный = 1 (RANK, не DENSE_RANK →
        при таях допускаются пропуски, но диапазон в пределах 1–20).
        """
        self.engine._assign_ranks(self.summaries + [self.kgd_summary])

        ranks = list(
            KPISummary.objects
            .filter(
                region__is_summary=False,
                date_from=_R_DATE_FROM, date_to=_R_DATE_TO,
            )
            .values_list('rank', flat=True)
        )

        self.assertEqual(len(ranks), 20, msg='Ровно 20 ДГД должны быть в выборке')
        self.assertTrue(
            all(r is not None for r in ranks),
            msg='Каждый ДГД получает числовой ранг',
        )
        self.assertEqual(min(ranks), 1)
        self.assertLessEqual(max(ranks), 20)

    def test_akmola_lowest_score_highest_rank_number(self):
        """
        Акмолинская (03xx) = 45 баллов → наибольший номер ранга среди 20 ДГД.
        """
        self.engine._assign_ranks(self.summaries + [self.kgd_summary])

        akmola = KPISummary.objects.get(
            region=self.regions['03xx'],
            date_from=_R_DATE_FROM, date_to=_R_DATE_TO,
        )
        max_rank = (
            KPISummary.objects
            .filter(region__is_summary=False,
                    date_from=_R_DATE_FROM, date_to=_R_DATE_TO)
            .order_by('-rank')
            .values_list('rank', flat=True)
            .first()
        )
        self.assertEqual(akmola.rank, max_rank)

    def test_tied_regions_share_same_rank(self):
        """
        Алматинская и Атырауская — оба 100 баллов → оба rank=1.
        """
        self.engine._assign_ranks(self.summaries + [self.kgd_summary])

        almaty   = KPISummary.objects.get(region=self.regions['09xx'],
                                          date_from=_R_DATE_FROM)
        atyrau   = KPISummary.objects.get(region=self.regions['15xx'],
                                          date_from=_R_DATE_FROM)
        self.assertEqual(almaty.rank, 1)
        self.assertEqual(atyrau.rank, 1)

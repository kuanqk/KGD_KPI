from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import User
from apps.kpi.models import KPIFormula, KPIResult, KPISummary
from apps.regions.models import Region

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD = (date(2025, 1, 1), date(2025, 3, 31))


def make_region(code='03xx', order=1):
    return Region.objects.create(
        code=code, name_ru=f'ДГД {code}',
        name_kz=f'МКД {code}', name_en=f'STD {code}', order=order,
    )


def make_user(username='op', role='operator'):
    return User.objects.create_user(username=username, password='pass', role=role)


def make_formula(kpi_type='assessment', version=1, is_active=True, config=None):
    return KPIFormula.objects.create(
        kpi_type=kpi_type,
        version=version,
        config=config or {'max_score': 10, 'thresholds': []},
        is_active=is_active,
    )


def make_result(region, formula, kpi_type='assessment', score=10, **kwargs):
    defaults = dict(
        date_from=PERIOD[0],
        date_to=PERIOD[1],
        plan=1_000_000,
        fact=1_050_000,
        percent=105,
        score=score,
    )
    defaults.update(kwargs)
    return KPIResult.objects.create(
        region=region, kpi_type=kpi_type, formula=formula, **defaults,
    )


def make_summary(region, rank=1, score_total=80, **kwargs):
    defaults = dict(
        date_from=PERIOD[0],
        date_to=PERIOD[1],
        score_assessment=10,
        score_collection=40,
        score_avg_assessment=10,
        score_workload=15,
        score_long_inspections=10,
        score_cancelled=15,
        score_total=score_total,
        rank=rank,
    )
    defaults.update(kwargs)
    return KPISummary.objects.create(region=region, **defaults)


# ---------------------------------------------------------------------------
# KPIFormula
# ---------------------------------------------------------------------------

class KPIFormulaTest(TestCase):
    def test_create(self):
        f = make_formula()
        self.assertEqual(f.kpi_type, 'assessment')
        self.assertEqual(f.version, 1)
        self.assertTrue(f.is_active)

    def test_str(self):
        f = make_formula(kpi_type='collection', version=2)
        self.assertIn('KPI 2', str(f))
        self.assertIn('v2', str(f))

    def test_unique_together_kpi_type_version(self):
        make_formula(kpi_type='assessment', version=1)
        with self.assertRaises(IntegrityError):
            make_formula(kpi_type='assessment', version=1)

    def test_same_type_different_version_ok(self):
        make_formula(kpi_type='workload', version=1)
        make_formula(kpi_type='workload', version=2)
        self.assertEqual(KPIFormula.objects.filter(kpi_type='workload').count(), 2)

    def test_get_active_returns_latest_version(self):
        make_formula(kpi_type='cancelled', version=1, is_active=True)
        make_formula(kpi_type='cancelled', version=2, is_active=True)
        active = KPIFormula.get_active('cancelled')
        self.assertEqual(active.version, 2)

    def test_get_active_ignores_inactive(self):
        make_formula(kpi_type='workload', version=1, is_active=False)
        make_formula(kpi_type='workload', version=2, is_active=True)
        active = KPIFormula.get_active('workload')
        self.assertEqual(active.version, 2)

    def test_get_active_raises_if_none(self):
        with self.assertRaises(ObjectDoesNotExist):
            KPIFormula.get_active('assessment')

    def test_all_kpi_types_valid(self):
        for i, (kpi_type, _) in enumerate(KPIFormula.KPI_TYPES, start=1):
            f = make_formula(kpi_type=kpi_type, version=i)
            self.assertEqual(f.kpi_type, kpi_type)

    def test_config_json_stored(self):
        cfg = {
            'max_score': 40,
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 40},
            ],
        }
        f = make_formula(kpi_type='collection', config=cfg)
        f.refresh_from_db()
        self.assertEqual(f.config['max_score'], 40)
        self.assertEqual(len(f.config['thresholds']), 1)

    def test_created_by_nullable(self):
        f = make_formula()
        self.assertIsNone(f.created_by)

    def test_created_by_set_null_on_user_delete(self):
        user = make_user()
        f = KPIFormula.objects.create(
            kpi_type='long_inspections', version=1,
            config={}, created_by=user,
        )
        user.delete()
        f.refresh_from_db()
        self.assertIsNone(f.created_by)


# ---------------------------------------------------------------------------
# KPIResult
# ---------------------------------------------------------------------------

class KPIResultTest(TestCase):
    def setUp(self):
        self.region = make_region()
        self.formula = make_formula()

    def test_create(self):
        r = make_result(self.region, self.formula)
        self.assertEqual(r.score, 10)
        self.assertEqual(r.status, 'draft')

    def test_str(self):
        r = make_result(self.region, self.formula)
        s = str(r)
        self.assertIn(str(self.region), s)
        self.assertIn('10', s)

    def test_unique_together(self):
        make_result(self.region, self.formula)
        with self.assertRaises(IntegrityError):
            make_result(self.region, self.formula)

    def test_different_formula_same_period_ok(self):
        f2 = make_formula(version=2)
        make_result(self.region, self.formula)
        make_result(self.region, f2)
        self.assertEqual(KPIResult.objects.count(), 2)

    def test_different_period_same_formula_ok(self):
        make_result(self.region, self.formula, date_from=date(2025, 1, 1), date_to=date(2025, 3, 31))
        make_result(self.region, self.formula, date_from=date(2025, 4, 1), date_to=date(2025, 6, 30))
        self.assertEqual(KPIResult.objects.count(), 2)

    def test_all_statuses(self):
        for status, _ in KPIResult.STATUSES:
            r = KPIResult.objects.create(
                region=self.region,
                kpi_type='assessment',
                formula=self.formula,
                date_from=date(2025, 1, 1),
                date_to=date(2025, 12, 31),
                status=status,
            )
            self.assertEqual(r.status, status)
            r.delete()

    def test_calc_details_json(self):
        r = make_result(
            self.region, self.formula,
            calc_details={'sum_assessed': 5_000_000, 'count': 12},
        )
        r.refresh_from_db()
        self.assertEqual(r.calc_details['sum_assessed'], 5_000_000)

    def test_plan_fact_percent_nullable(self):
        r = KPIResult.objects.create(
            region=self.region, kpi_type='assessment',
            formula=self.formula, date_from=PERIOD[0], date_to=PERIOD[1],
        )
        self.assertIsNone(r.plan)
        self.assertIsNone(r.fact)
        self.assertIsNone(r.percent)

    def test_score_default_zero(self):
        r = KPIResult.objects.create(
            region=self.region, kpi_type='assessment',
            formula=self.formula, date_from=PERIOD[0], date_to=PERIOD[1],
        )
        self.assertEqual(r.score, 0)

    def test_calculated_by_set_null_on_user_delete(self):
        user = make_user()
        r = make_result(self.region, self.formula, calculated_by=user)
        user.delete()
        r.refresh_from_db()
        self.assertIsNone(r.calculated_by)


# ---------------------------------------------------------------------------
# KPISummary
# ---------------------------------------------------------------------------

class KPISummaryTest(TestCase):
    def setUp(self):
        self.region = make_region()

    def test_create(self):
        s = make_summary(self.region)
        self.assertEqual(s.score_total, 80)
        self.assertEqual(s.rank, 1)
        self.assertEqual(s.status, 'draft')

    def test_str_with_rank(self):
        s = make_summary(self.region, rank=3, score_total=75)
        self.assertIn('#3', str(s))
        self.assertIn('75', str(s))

    def test_str_kgd_no_rank(self):
        kgd = Region.objects.create(
            code='00xx', name_ru='КГД', name_kz='ҚМД', name_en='KGD',
            is_summary=True, order=21,
        )
        s = make_summary(kgd, rank=None, score_total=0)
        self.assertIn('КГД', str(s))

    def test_unique_together_region_period(self):
        make_summary(self.region)
        with self.assertRaises(IntegrityError):
            make_summary(self.region)

    def test_different_period_same_region_ok(self):
        make_summary(self.region, date_from=date(2025, 1, 1), date_to=date(2025, 3, 31))
        make_summary(self.region, date_from=date(2025, 4, 1), date_to=date(2025, 6, 30))
        self.assertEqual(KPISummary.objects.count(), 2)

    def test_rank_nullable(self):
        s = make_summary(self.region, rank=None)
        self.assertIsNone(s.rank)

    def test_max_scores(self):
        s = make_summary(
            self.region,
            score_assessment=10,
            score_collection=40,
            score_avg_assessment=10,
            score_workload=15,
            score_long_inspections=10,
            score_cancelled=15,
            score_total=100,
        )
        self.assertEqual(s.score_total, 100)

    def test_recalculate_total(self):
        s = make_summary(
            self.region,
            score_assessment=10,
            score_collection=20,
            score_avg_assessment=5,
            score_workload=5,
            score_long_inspections=0,
            score_cancelled=5,
            score_total=0,   # намеренно неверный
        )
        s.recalculate_total()
        self.assertEqual(s.score_total, 45)

    def test_all_statuses(self):
        for status, _ in KPIResult.STATUSES:
            s = KPISummary.objects.create(
                region=self.region,
                date_from=date(2025, 1, 1),
                date_to=date(2025, 12, 31),
                status=status,
            )
            self.assertEqual(s.status, status)
            s.delete()

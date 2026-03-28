from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import User
from apps.etl.models import (
    ActiveInspection,
    AppealDecision,
    CompletedInspection,
    ImportJob,
    ManualInput,
)
from apps.regions.models import Region


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_region(code='03xx', order=1):
    return Region.objects.create(
        code=code, name_ru=f'ДГД {code}',
        name_kz=f'МКД {code}', name_en=f'STD {code}', order=order,
    )


def make_user(username='op', role='operator'):
    return User.objects.create_user(username=username, password='pass', role=role)


def make_job(user=None, source='inis', status='pending'):
    return ImportJob.objects.create(source=source, status=status, started_by=user)


def make_completed(job, region, source='inis', source_id='CI-001', **kwargs):
    defaults = dict(
        management='УНА',
        form_type='обычная',
        completed_date=date(2025, 3, 1),
        amount_assessed=1_000_000,
        amount_collected=500_000,
    )
    defaults.update(kwargs)
    return CompletedInspection.objects.create(
        source=source, source_id=source_id,
        import_job=job, region=region, **defaults,
    )


def make_active(job, region, source='inis', source_id='AI-001', **kwargs):
    defaults = dict(
        management='УНА',
        case_type='обычная',
        prescription_date=date(2025, 1, 15),
    )
    defaults.update(kwargs)
    return ActiveInspection.objects.create(
        source=source, source_id=source_id,
        import_job=job, region=region, **defaults,
    )


def make_appeal(job, region, source_id='AP-001', **kwargs):
    defaults = dict(
        amount_cancelled=200_000,
        completion_date=date(2024, 6, 1),
        decision_date=date(2024, 8, 1),
    )
    defaults.update(kwargs)
    return AppealDecision.objects.create(
        source_id=source_id, import_job=job, region=region, **defaults,
    )


# ---------------------------------------------------------------------------
# ImportJob
# ---------------------------------------------------------------------------

class ImportJobTest(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_create_minimal(self):
        job = ImportJob.objects.create(source='inis')
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.records_total, 0)
        self.assertEqual(job.records_imported, 0)
        self.assertEqual(job.error_message, '')
        self.assertEqual(job.params, {})

    def test_all_sources_valid(self):
        for src, _ in ImportJob.SOURCES:
            job = ImportJob.objects.create(source=src)
            self.assertEqual(job.source, src)

    def test_all_statuses_valid(self):
        for st, _ in ImportJob.STATUSES:
            job = ImportJob.objects.create(source='inis', status=st)
            self.assertEqual(job.status, st)

    def test_status_properties(self):
        job = make_job(status='running')
        self.assertTrue(job.is_running)
        self.assertFalse(job.is_done)
        self.assertFalse(job.has_error)

        job.status = 'done'
        self.assertTrue(job.is_done)

        job.status = 'error'
        self.assertTrue(job.has_error)

    def test_started_by_nullable(self):
        job = ImportJob.objects.create(source='isna')
        self.assertIsNone(job.started_by)

    def test_started_by_set_null_on_user_delete(self):
        user = make_user('temp')
        job = make_job(user=user)
        user.delete()
        job.refresh_from_db()
        self.assertIsNone(job.started_by)

    def test_str(self):
        job = make_job(source='inis', status='pending')
        self.assertIn('ИНИС', str(job))
        self.assertIn('Ожидание', str(job))

    def test_params_json(self):
        job = ImportJob.objects.create(
            source='dgd',
            params={'date_from': '2025-01-01', 'date_to': '2025-03-31'},
        )
        self.assertEqual(job.params['date_from'], '2025-01-01')


# ---------------------------------------------------------------------------
# CompletedInspection
# ---------------------------------------------------------------------------

class CompletedInspectionTest(TestCase):
    def setUp(self):
        self.region = make_region()
        self.job = make_job()

    def test_create(self):
        ci = make_completed(self.job, self.region)
        self.assertEqual(ci.amount_assessed, 1_000_000)
        self.assertEqual(ci.amount_collected, 500_000)
        self.assertFalse(ci.is_counted)
        self.assertFalse(ci.is_accepted)
        self.assertFalse(ci.is_anomaly)

    def test_amounts_are_big_integer(self):
        large = 999_999_999_999
        ci = make_completed(self.job, self.region, amount_assessed=large, amount_collected=large)
        ci.refresh_from_db()
        self.assertEqual(ci.amount_assessed, large)
        self.assertEqual(ci.amount_collected, large)

    def test_unique_together_source_source_id(self):
        make_completed(self.job, self.region, source='inis', source_id='X-001')
        with self.assertRaises(IntegrityError):
            make_completed(self.job, self.region, source='inis', source_id='X-001')

    def test_same_source_id_different_source_ok(self):
        make_completed(self.job, self.region, source='inis', source_id='SAME-001')
        make_completed(self.job, self.region, source='isna', source_id='SAME-001')
        self.assertEqual(CompletedInspection.objects.count(), 2)

    def test_dfno_form_type(self):
        ci = make_completed(self.job, self.region, form_type='ДФНО', source_id='DF-001')
        self.assertEqual(ci.form_type, 'ДФНО')

    def test_raw_data_json(self):
        ci = make_completed(
            self.job, self.region,
            source_id='RD-001',
            raw_data={'original_id': 42, 'extra': 'data'},
        )
        self.assertEqual(ci.raw_data['original_id'], 42)

    def test_str(self):
        ci = make_completed(self.job, self.region)
        s = str(ci)
        self.assertIn('INIS', s)
        self.assertIn('CI-001', s)


# ---------------------------------------------------------------------------
# ActiveInspection
# ---------------------------------------------------------------------------

class ActiveInspectionTest(TestCase):
    def setUp(self):
        self.region = make_region('06xx', 2)
        self.job = make_job()

    def test_create(self):
        ai = make_active(self.job, self.region)
        self.assertFalse(ai.is_counted)
        self.assertEqual(ai.case_type, 'обычная')

    def test_unique_together_source_source_id(self):
        make_active(self.job, self.region, source='inis', source_id='A-001')
        with self.assertRaises(IntegrityError):
            make_active(self.job, self.region, source='inis', source_id='A-001')

    def test_same_id_different_source_ok(self):
        make_active(self.job, self.region, source='inis', source_id='DUP')
        make_active(self.job, self.region, source='isna', source_id='DUP')
        self.assertEqual(ActiveInspection.objects.count(), 2)

    def test_str(self):
        ai = make_active(self.job, self.region)
        self.assertIn('INIS', str(ai))
        self.assertIn('AI-001', str(ai))

    def test_exclude_criminal_case_type(self):
        """Поле case_type сохраняет значение — фильтрация по уголовным делам на уровне KPI Engine."""
        ai = make_active(
            self.job, self.region,
            source_id='CR-001', case_type='уголовное дело',
        )
        self.assertEqual(ai.case_type, 'уголовное дело')


# ---------------------------------------------------------------------------
# AppealDecision
# ---------------------------------------------------------------------------

class AppealDecisionTest(TestCase):
    def setUp(self):
        self.region = make_region('09xx', 3)
        self.job = make_job(source='appeals')

    def test_create(self):
        ad = make_appeal(self.job, self.region)
        self.assertEqual(ad.amount_cancelled, 200_000)
        self.assertFalse(ad.is_counted)

    def test_amount_big_integer(self):
        large = 5_000_000_000
        ad = make_appeal(self.job, self.region, source_id='BIG', amount_cancelled=large)
        ad.refresh_from_db()
        self.assertEqual(ad.amount_cancelled, large)

    def test_source_id_unique(self):
        make_appeal(self.job, self.region, source_id='UNIQ-1')
        with self.assertRaises(IntegrityError):
            make_appeal(self.job, self.region, source_id='UNIQ-1')

    def test_decision_date_stored(self):
        ad = make_appeal(self.job, self.region, decision_date=date(2025, 6, 15))
        ad.refresh_from_db()
        self.assertEqual(ad.decision_date, date(2025, 6, 15))

    def test_str(self):
        ad = make_appeal(self.job, self.region)
        self.assertIn('AP-001', str(ad))

    def test_two_year_exclusion_field_exists(self):
        """completion_date и decision_date присутствуют — KPI Engine проверяет разницу >2 лет."""
        ad = make_appeal(
            self.job, self.region,
            source_id='OLD-1',
            completion_date=date(2020, 1, 1),
            decision_date=date(2023, 2, 1),
        )
        diff = (ad.decision_date - ad.completion_date).days
        self.assertGreater(diff, 730)


# ---------------------------------------------------------------------------
# ManualInput
# ---------------------------------------------------------------------------

class ManualInputTest(TestCase):
    def setUp(self):
        self.region = make_region('15xx', 4)
        self.user = make_user()

    def test_create(self):
        mi = ManualInput.objects.create(
            region=self.region,
            year=2025,
            kbk_share_pct='5.1234',
            staff_count=12,
            entered_by=self.user,
        )
        self.assertEqual(mi.year, 2025)
        self.assertAlmostEqual(float(mi.kbk_share_pct), 5.1234, places=4)
        self.assertEqual(mi.staff_count, 12)

    def test_unique_together_region_year(self):
        ManualInput.objects.create(region=self.region, year=2025)
        with self.assertRaises(IntegrityError):
            ManualInput.objects.create(region=self.region, year=2025)

    def test_same_year_different_region_ok(self):
        r2 = make_region('18xx', 5)
        ManualInput.objects.create(region=self.region, year=2025)
        ManualInput.objects.create(region=r2, year=2025)
        self.assertEqual(ManualInput.objects.count(), 2)

    def test_nullable_fields(self):
        mi = ManualInput.objects.create(region=self.region, year=2024)
        self.assertIsNone(mi.kbk_share_pct)
        self.assertIsNone(mi.staff_count)
        self.assertIsNone(mi.entered_by)

    def test_entered_by_set_null_on_user_delete(self):
        user2 = make_user('tmp2')
        mi = ManualInput.objects.create(region=self.region, year=2023, entered_by=user2)
        user2.delete()
        mi.refresh_from_db()
        self.assertIsNone(mi.entered_by)

    def test_str(self):
        mi = ManualInput.objects.create(region=self.region, year=2025)
        self.assertIn('2025', str(mi))
        self.assertIn(str(self.region), str(mi))

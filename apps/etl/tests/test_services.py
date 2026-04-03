"""
Тесты ETL-сервисного слоя: DataNormalizer и KGDImporter.
Используют mock-данные и фикстуры регионов — без реального подключения к БД КГД.
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from apps.core.models import AuditLog, User
from apps.etl.models import (
    ActiveInspection,
    AppealDecision,
    CompletedInspection,
    ImportJob,
)
from apps.etl.services.importer import KGDImporter
from apps.etl.services.normalizer import DataNormalizer, _detect_source
from apps.regions.models import Region


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_region(code='03xx', order=1):
    return Region.objects.get_or_create(
        code=code,
        defaults={
            'name_ru': f'ДГД {code}', 'name_kz': f'МКД {code}',
            'name_en': f'STD {code}', 'order': order,
        },
    )[0]


def make_user():
    return User.objects.create_user(username='op', password='pass', role='operator')


def make_job(source='inis', user=None):
    return ImportJob.objects.create(source=source, started_by=user)


# ---------------------------------------------------------------------------
# Source routing
# ---------------------------------------------------------------------------

class SourceRoutingTest(TestCase):
    def test_before_cutoff_is_inis(self):
        self.assertEqual(_detect_source(date(2025, 7, 8)), 'inis')

    def test_cutoff_day_is_isna(self):
        self.assertEqual(_detect_source(date(2025, 7, 9)), 'isna')

    def test_after_cutoff_is_isna(self):
        self.assertEqual(_detect_source(date(2025, 12, 31)), 'isna')

    def test_far_before_cutoff_is_inis(self):
        self.assertEqual(_detect_source(date(2024, 1, 1)), 'inis')


# ---------------------------------------------------------------------------
# DataNormalizer — CompletedInspection
# ---------------------------------------------------------------------------

class NormalizerCompletedTest(TestCase):
    def setUp(self):
        self.region = make_region('03xx', 1)
        make_region('06xx', 2)
        self.job = make_job()
        self.norm = DataNormalizer(self.job)

    def _row(self, **overrides):
        base = {
            'source_id': 'CI-001',
            'region_code': '03xx',
            'management': 'УНА',
            'form_type': 'обычная',
            'completed_date': '2025-02-15',
            'amount_assessed': 5_000_000,
            'amount_collected': 3_000_000,
            'is_counted': True,
            'is_accepted': True,
        }
        base.update(overrides)
        return base

    def test_source_inis_before_cutoff(self):
        obj = self.norm.normalize_completed_inspection(self._row(completed_date='2025-06-01'))
        self.assertEqual(obj.source, 'inis')

    def test_source_isna_after_cutoff(self):
        obj = self.norm.normalize_completed_inspection(self._row(
            source_id='CI-002', completed_date='2025-08-01',
        ))
        self.assertEqual(obj.source, 'isna')

    def test_fields_mapped_correctly(self):
        obj = self.norm.normalize_completed_inspection(self._row())
        self.assertEqual(obj.source_id, 'CI-001')
        self.assertEqual(obj.region, self.region)
        self.assertEqual(obj.management, 'УНА')
        self.assertEqual(obj.form_type, 'обычная')
        self.assertEqual(obj.completed_date, date(2025, 2, 15))
        self.assertEqual(obj.amount_assessed, 5_000_000)
        self.assertEqual(obj.amount_collected, 3_000_000)
        self.assertTrue(obj.is_counted)
        self.assertTrue(obj.is_accepted)

    def test_import_job_assigned(self):
        obj = self.norm.normalize_completed_inspection(self._row())
        self.assertEqual(obj.import_job, self.job)

    def test_dfno_form_type(self):
        obj = self.norm.normalize_completed_inspection(self._row(form_type='ДФНО', source_id='CI-D'))
        self.assertEqual(obj.form_type, 'ДФНО')

    def test_null_amounts_default_zero(self):
        obj = self.norm.normalize_completed_inspection(
            self._row(amount_assessed=None, amount_collected=None, source_id='CI-N')
        )
        self.assertEqual(obj.amount_assessed, 0)
        self.assertEqual(obj.amount_collected, 0)

    def test_raw_data_stored(self):
        row = self._row()
        obj = self.norm.normalize_completed_inspection(row)
        self.assertEqual(obj.raw_data['source_id'], 'CI-001')

    def test_unknown_region_raises(self):
        with self.assertRaises(ValueError):
            self.norm.normalize_completed_inspection(self._row(region_code='UNKNOWN'))

    def test_region_cache(self):
        """Повторный вызов с тем же region_code не обращается к БД дважды."""
        self.norm.normalize_completed_inspection(self._row(source_id='CI-R1'))
        self.norm.normalize_completed_inspection(self._row(source_id='CI-R2'))
        self.assertIn('03xx', self.norm._region_cache)

    def test_date_as_date_object(self):
        obj = self.norm.normalize_completed_inspection(
            self._row(completed_date=date(2025, 3, 1), source_id='CI-DO')
        )
        self.assertEqual(obj.completed_date, date(2025, 3, 1))


# ---------------------------------------------------------------------------
# DataNormalizer — ActiveInspection
# ---------------------------------------------------------------------------

class NormalizerActiveTest(TestCase):
    def setUp(self):
        self.region = make_region('09xx', 3)
        self.job = make_job(source='dgd')
        self.norm = DataNormalizer(self.job)

    def _row(self, **overrides):
        base = {
            'source_id': 'AI-001',
            'region_code': '09xx',
            'management': 'УНА',
            'case_type': 'обычная',
            'prescription_date': '2024-11-01',
            'is_counted': True,
        }
        base.update(overrides)
        return base

    def test_source_from_prescription_date(self):
        obj = self.norm.normalize_active_inspection(self._row(prescription_date='2025-01-01'))
        self.assertEqual(obj.source, 'inis')

    def test_source_isna_after_cutoff(self):
        obj = self.norm.normalize_active_inspection(
            self._row(prescription_date='2025-09-01', source_id='AI-002')
        )
        self.assertEqual(obj.source, 'isna')

    def test_fields_mapped(self):
        obj = self.norm.normalize_active_inspection(self._row())
        self.assertEqual(obj.region, self.region)
        self.assertEqual(obj.management, 'УНА')
        self.assertEqual(obj.case_type, 'обычная')
        self.assertEqual(obj.prescription_date, date(2024, 11, 1))
        self.assertTrue(obj.is_counted)

    def test_criminal_case_type_stored(self):
        """case_type='уголовное дело' сохраняется — KPI Engine сам фильтрует."""
        obj = self.norm.normalize_active_inspection(
            self._row(case_type='уголовное дело', source_id='AI-CR')
        )
        self.assertEqual(obj.case_type, 'уголовное дело')

    def test_unknown_region_raises(self):
        with self.assertRaises(ValueError):
            self.norm.normalize_active_inspection(self._row(region_code='ZZZZ'))


# ---------------------------------------------------------------------------
# DataNormalizer — AppealDecision
# ---------------------------------------------------------------------------

class NormalizerAppealTest(TestCase):
    def setUp(self):
        self.region = make_region('15xx', 4)
        self.job = make_job(source='appeals')
        self.norm = DataNormalizer(self.job)

    def _row(self, **overrides):
        base = {
            'source_id': 'AP-001',
            'region_code': '15xx',
            'amount_cancelled': 2_000_000,
            'is_counted': True,
            'completion_date': '2024-03-01',
            'decision_date': '2024-05-20',
        }
        base.update(overrides)
        return base

    def test_fields_mapped(self):
        obj = self.norm.normalize_appeal(self._row())
        self.assertEqual(obj.source_id, 'AP-001')
        self.assertEqual(obj.region, self.region)
        self.assertEqual(obj.amount_cancelled, 2_000_000)
        self.assertTrue(obj.is_counted)
        self.assertEqual(obj.completion_date, date(2024, 3, 1))
        self.assertEqual(obj.decision_date, date(2024, 5, 20))

    def test_null_amount_defaults_zero(self):
        obj = self.norm.normalize_appeal(self._row(amount_cancelled=None, source_id='AP-N'))
        self.assertEqual(obj.amount_cancelled, 0)

    def test_two_year_dates_preserved(self):
        """completion_date и decision_date нужны для проверки правила >2 лет в KPI 6."""
        obj = self.norm.normalize_appeal(
            self._row(completion_date='2020-01-01', decision_date='2023-02-01')
        )
        diff = (obj.decision_date - obj.completion_date).days
        self.assertGreater(diff, 730)


# ---------------------------------------------------------------------------
# KGDImporter — интеграционные тесты (с реальной БД, stub fetch)
# ---------------------------------------------------------------------------

class KGDImporterTest(TestCase):
    fixtures = ['regions']

    def setUp(self):
        self.user = make_user()

    def test_run_completed_inspections(self):
        job = make_job(source='inis', user=self.user)
        importer = KGDImporter(job)
        importer.run()

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)
        self.assertGreater(job.records_total, 0)
        self.assertGreater(CompletedInspection.objects.count(), 0)

    def test_run_active_inspections(self):
        job = make_job(source='dgd', user=self.user)
        KGDImporter(job).run()
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertGreater(ActiveInspection.objects.count(), 0)

    def test_run_appeals(self):
        job = make_job(source='appeals', user=self.user)
        KGDImporter(job).run()
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertGreater(AppealDecision.objects.count(), 0)

    def test_audit_log_created(self):
        job = make_job(source='inis', user=self.user)
        KGDImporter(job).run()
        log = AuditLog.objects.filter(event='import').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details['source'], 'inis')

    def test_duplicate_records_ignored(self):
        """Повторный запуск не дублирует записи (ignore_conflicts)."""
        job1 = make_job(source='inis', user=self.user)
        KGDImporter(job1).run()
        count_after_first = CompletedInspection.objects.count()

        job2 = make_job(source='inis', user=self.user)
        KGDImporter(job2).run()
        count_after_second = CompletedInspection.objects.count()

        self.assertEqual(count_after_first, count_after_second)

    def test_source_routing_in_stub(self):
        """Запись с датой >= 09.07.2025 должна получить source='isna'."""
        job = make_job(source='inis', user=self.user)
        KGDImporter(job).run()
        isna_records = CompletedInspection.objects.filter(source='isna')
        self.assertGreater(isna_records.count(), 0)

    def test_error_status_on_fetch_failure(self):
        job = make_job(source='inis', user=self.user)
        importer = KGDImporter(job)

        with patch.object(importer, '_fetch_from_kgd_db', side_effect=RuntimeError('DB down')):
            with self.assertRaises(RuntimeError):
                importer.run()

        job.refresh_from_db()
        self.assertEqual(job.status, 'error')
        self.assertIn('DB down', job.error_message)
        self.assertIsNotNone(job.finished_at)

    def test_records_imported_count(self):
        job = make_job(source='inis', user=self.user)
        KGDImporter(job).run()
        job.refresh_from_db()
        self.assertEqual(job.records_imported, CompletedInspection.objects.count())

    def test_normalizer_error_skips_row(self):
        """Строки с неизвестным region_code пропускаются, импорт не прерывается."""
        bad_row = {
            'source_id': 'BAD-001',
            'region_code': 'UNKNOWN',
            'management': 'УНА',
            'form_type': 'обычная',
            'completed_date': '2025-01-01',
            'amount_assessed': 100,
            'amount_collected': 50,
            'is_counted': True,
            'is_accepted': True,
        }
        job = make_job(source='inis', user=self.user)
        importer = KGDImporter(job)

        with patch.object(
            importer, '_fetch_from_kgd_db',
            return_value=[bad_row],
        ):
            importer.run()  # не должен бросить исключение

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(CompletedInspection.objects.count(), 0)


# ---------------------------------------------------------------------------
# KGDImporter — _bulk_create unit tests
# ---------------------------------------------------------------------------

class BulkCreateTest(TestCase):
    fixtures = ['regions']

    def setUp(self):
        self.job = make_job(source='inis')
        self.region = Region.objects.get(code='03xx')

    def test_bulk_create_returns_count(self):
        importer = KGDImporter(self.job)
        objs = [
            CompletedInspection(
                source='inis', source_id=f'BC-{i:03d}',
                import_job=self.job, region=self.region,
                management='УНА', form_type='обычная',
                completed_date=date(2025, 1, i + 1),
                amount_assessed=i * 1000,
            )
            for i in range(5)
        ]
        count = importer._bulk_create(objs)
        self.assertEqual(count, 5)
        self.assertEqual(CompletedInspection.objects.count(), 5)

    def test_bulk_create_empty_list(self):
        importer = KGDImporter(self.job)
        count = importer._bulk_create([])
        self.assertEqual(count, 0)

    def test_bulk_create_ignores_duplicates(self):
        importer = KGDImporter(self.job)
        obj = CompletedInspection(
            source='inis', source_id='DUP-001',
            import_job=self.job, region=self.region,
            management='УНА', form_type='обычная',
            completed_date=date(2025, 1, 1),
        )
        importer._bulk_create([obj])
        importer._bulk_create([obj])  # дубликат
        self.assertEqual(CompletedInspection.objects.filter(source_id='DUP-001').count(), 1)

"""
ETL импортёр: оркестрирует загрузку данных из БД КГД.

Жизненный цикл ImportJob:
  pending → running → done
                   ↘ error

Реальное подключение к БД КГД реализуется в Спринте 18
после получения schema от Олжаса. Сейчас — заглушка с тестовыми данными.
"""

import logging
import traceback
from datetime import datetime, timezone

from django.db import IntegrityError

from apps.core.models import AuditLog
from apps.etl.models import ImportJob
from apps.etl.services.normalizer import DataNormalizer

logger = logging.getLogger(__name__)

# Размер пакета для bulk_create
_BATCH_SIZE = 500


class KGDImporter:
    """
    Импортирует данные из БД КГД и сохраняет в нормализованные таблицы.

    Использование:
        job = ImportJob.objects.create(source='inis', started_by=user)
        importer = KGDImporter(job)
        importer.run()
    """

    def __init__(self, job: ImportJob):
        self.job = job
        self.normalizer = DataNormalizer(job)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> ImportJob:
        """
        Запускает полный цикл импорта.
        Обновляет job.status, records_total, records_imported, error_message.
        """
        self._mark_running()
        try:
            raw_records = self._fetch_from_kgd_db()
            self.job.records_total = len(raw_records)
            self.job.save(update_fields=['records_total'])

            normalized = self._normalize_all(raw_records)
            imported = self._bulk_create(normalized)

            self.job.records_imported = imported
            self._mark_done()

            AuditLog.log(
                event='import',
                user=self.job.started_by,
                details={
                    'job_id': self.job.pk,
                    'source': self.job.source,
                    'records_total': self.job.records_total,
                    'records_imported': imported,
                },
            )
            logger.info(
                'Import job #%d done: %d/%d records',
                self.job.pk, imported, self.job.records_total,
            )
        except Exception as exc:
            self._mark_error(exc)
            logger.error('Import job #%d failed: %s', self.job.pk, exc)
            raise

        return self.job

    # ------------------------------------------------------------------
    # Private: fetch
    # ------------------------------------------------------------------

    def _fetch_from_kgd_db(self) -> list[dict]:
        """
        Заглушка получения данных из БД КГД.

        В Спринте 18 заменить на реальное подключение:
            conn = psycopg2.connect(
                host=settings.KGD_DB_HOST, port=settings.KGD_DB_PORT,
                dbname=settings.KGD_DB_NAME, user=settings.KGD_DB_USER,
                password=settings.KGD_DB_PASSWORD,
            )
        Параметры диапазона берутся из self.job.params ('date_from', 'date_to').
        """
        source = self.job.source

        if source in ('inis', 'isna'):
            return _STUB_COMPLETED_INSPECTIONS
        if source == 'appeals':
            return _STUB_APPEALS
        # 'dgd' — данные ДГД (активные проверки)
        return _STUB_ACTIVE_INSPECTIONS

    # ------------------------------------------------------------------
    # Private: normalize
    # ------------------------------------------------------------------

    def _normalize_all(self, raw_records: list[dict]) -> list:
        """Нормализует все сырые строки в зависимости от типа источника."""
        source = self.job.source
        result = []
        errors = 0

        for row in raw_records:
            try:
                if source in ('inis', 'isna'):
                    result.append(self.normalizer.normalize_completed_inspection(row))
                elif source == 'dgd':
                    result.append(self.normalizer.normalize_active_inspection(row))
                elif source == 'appeals':
                    result.append(self.normalizer.normalize_appeal(row))
            except (ValueError, KeyError) as exc:
                errors += 1
                logger.warning('Skipping row source_id=%s: %s', row.get('source_id'), exc)

        if errors:
            logger.warning('Skipped %d rows due to normalization errors', errors)

        return result

    # ------------------------------------------------------------------
    # Private: persist
    # ------------------------------------------------------------------

    def _bulk_create(self, records: list) -> int:
        """
        Пакетная вставка записей с игнорированием дубликатов.

        Возвращает количество фактически вставленных записей.
        """
        if not records:
            return 0

        model_class = type(records[0])
        imported = 0

        for i in range(0, len(records), _BATCH_SIZE):
            batch = records[i: i + _BATCH_SIZE]
            try:
                created = model_class.objects.bulk_create(
                    batch,
                    ignore_conflicts=True,
                    batch_size=_BATCH_SIZE,
                )
                imported += len(created)
            except IntegrityError as exc:
                # Fallback: вставляем по одной с пропуском конфликтов
                logger.warning('bulk_create batch failed, falling back to row-by-row: %s', exc)
                for obj in batch:
                    try:
                        obj.save()
                        imported += 1
                    except IntegrityError:
                        pass  # дубликат — пропускаем

        return imported

    # ------------------------------------------------------------------
    # Private: status helpers
    # ------------------------------------------------------------------

    def _mark_running(self):
        self.job.status = 'running'
        self.job.started_at = datetime.now(tz=timezone.utc)
        self.job.save(update_fields=['status', 'started_at'])

    def _mark_done(self):
        self.job.status = 'done'
        self.job.finished_at = datetime.now(tz=timezone.utc)
        self.job.save(update_fields=['status', 'finished_at', 'records_imported'])

    def _mark_error(self, exc: Exception):
        self.job.status = 'error'
        self.job.finished_at = datetime.now(tz=timezone.utc)
        self.job.error_message = f'{type(exc).__name__}: {exc}\n{traceback.format_exc()}'
        self.job.save(update_fields=['status', 'finished_at', 'error_message'])


# ---------------------------------------------------------------------------
# Тестовые данные (заглушка — удалить/заменить в Спринте 18)
#
# Используют условные имена полей из claude.md раздел "Условные поля БД".
# Код региона '03xx' должен присутствовать в фикстуре regions.json.
# ---------------------------------------------------------------------------

_STUB_COMPLETED_INSPECTIONS: list[dict] = [
    {
        'source_id': 'STUB-CI-0001',
        'region_code': '03xx',
        'management': 'УНА',
        'form_type': 'обычная',
        'completed_date': '2025-02-15',
        'amount_assessed': 5_000_000,
        'amount_collected': 3_500_000,
        'is_counted': True,
        'is_accepted': True,
    },
    {
        'source_id': 'STUB-CI-0002',
        'region_code': '06xx',
        'management': 'УНА',
        'form_type': 'ДФНО',
        'completed_date': '2025-03-10',
        'amount_assessed': 12_000_000,
        'amount_collected': 8_000_000,
        'is_counted': True,
        'is_accepted': False,
    },
    {
        'source_id': 'STUB-CI-0003',
        'region_code': '62xx',
        'management': 'УКН',
        'form_type': 'обычная',
        'completed_date': '2025-07-20',   # >= 09.07.2025 → isna
        'amount_assessed': 2_500_000,
        'amount_collected': 2_500_000,
        'is_counted': False,
        'is_accepted': False,
    },
]

_STUB_ACTIVE_INSPECTIONS: list[dict] = [
    {
        'source_id': 'STUB-AI-0001',
        'region_code': '03xx',
        'management': 'УНА',
        'case_type': 'обычная',
        'prescription_date': '2024-11-01',
        'is_counted': True,
    },
    {
        'source_id': 'STUB-AI-0002',
        'region_code': '09xx',
        'management': 'УНА',
        'case_type': 'уголовное дело',
        'prescription_date': '2024-12-15',
        'is_counted': False,
    },
]

_STUB_APPEALS: list[dict] = [
    {
        'source_id': 'STUB-AP-0001',
        'region_code': '03xx',
        'amount_cancelled': 1_000_000,
        'is_counted': True,
        'completion_date': '2024-06-01',
        'decision_date': '2024-08-15',
    },
]

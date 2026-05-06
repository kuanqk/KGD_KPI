"""
ETL импортёр: оркестрирует загрузку данных из БД КГД.

Жизненный цикл ImportJob:
  pending → running → done
                   ↘ error

Источник данных — витрины audit_kpi_data_gold (схема в БД isna_audit, Алихан 06.05.2026):
  completed_acts       → CompletedInspection  (source='inis'/'isna')
  ongoing_acts         → ActiveInspection     (source='dgd')
  act_collected_amount → JOIN к completed_acts (суммы взысканий)
  AppealDecision       → ⏳ данные обжалований обсуждаются с МинФин

Подключение к КГД DB активируется при наличии KGD_DB_HOST в окружении.
Без него (CI, local dev) используются заглушки _STUB_*.
"""

import logging
import traceback
from datetime import datetime, timezone

from django.db import IntegrityError

from apps.core.models import AuditLog
from apps.etl.models import ImportJob
from apps.etl.services.normalizer import UNA_DEPARTMENT_IDS, DataNormalizer  # noqa: F401

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
        Получение данных из витрин КГД (схема audit_kpi_data_gold).

        Параметры диапазона берутся из self.job.params ('date_from', 'date_to').
        Подключение активируется при наличии KGD_DB_HOST в окружении.
        Без него (CI, local dev) используются заглушки _STUB_*.
        """
        import psycopg2
        from decouple import UndefinedValueError, config
        from psycopg2.extras import RealDictCursor

        source = self.job.source
        params = self.job.params or {}
        date_from = params.get('date_from', '2025-01-01')
        date_to = params.get('date_to', '2026-01-01')

        try:
            kgd_host = config('KGD_DB_HOST')
        except UndefinedValueError:
            kgd_host = None

        if not kgd_host:
            return self._fetch_stub(source)

        conn = psycopg2.connect(
            host=kgd_host,
            port=config('KGD_DB_PORT', cast=int, default=5432),
            dbname=config('KGD_DB_NAME'),
            user=config('KGD_DB_USER'),
            password=config('KGD_DB_PASSWORD'),
        )
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if source in ('inis', 'isna'):
                    return self._fetch_completed_acts(cur, date_from, date_to)
                if source == 'dgd':
                    return self._fetch_ongoing_acts(cur, date_from, date_to)
                if source == 'appeals':
                    logger.info('Appeals vitrine not yet available — returning empty list')
                    return []
        finally:
            conn.close()

        return []

    def _fetch_completed_acts(self, cur, date_from: str, date_to: str) -> list[dict]:
        """
        Завершённые проверки из витрин completed_acts + act_collected_amount.

        Одна строка в витрине = один КБК одного акта.
        GROUP BY act_number агрегирует суммы всех КБК в единую запись.

        amount_assessed = SUM(accrued + penalty + koap_fine + zan_fine - reduced)
        amount_collected = SUM(collected_amount) из act_collected_amount
            методы 1 (платёжное поручение) и 2 (переплата) уже включены;
            метод 3 (ДФНО) отсеян при построении витрины.
        """
        cur.execute("""
            WITH aggregated AS (
                SELECT
                    act_number                                                   AS source_id,
                    LEFT(code_nk, 2) || 'xx'                                   AS region_code,
                    'УНА'                                                        AS management,
                    MIN(completion_date)::date                                  AS completed_date,
                    MIN(case_exe_date)::date                                    AS create_date,
                    SUM(accrued + penalty + koap_fine + zan_fine - reduced)    AS amount_assessed
                FROM audit_kpi_data_gold.completed_acts
                WHERE completion_date >= %(date_from)s
                  AND completion_date <  %(date_to)s
                GROUP BY act_number, LEFT(code_nk, 2) || 'xx'
            ),
            collected AS (
                SELECT
                    act_number,
                    SUM(collected_amount) AS amount_collected
                FROM audit_kpi_data_gold.act_collected_amount
                GROUP BY act_number
            )
            SELECT
                a.source_id,
                a.region_code,
                a.management,
                a.completed_date,
                a.create_date,
                a.amount_assessed,
                COALESCE(c.amount_collected, 0) AS amount_collected
            FROM aggregated a
            LEFT JOIN collected c ON c.act_number = a.source_id
        """, {'date_from': date_from, 'date_to': date_to})
        return [dict(row) for row in cur.fetchall()]

    def _fetch_ongoing_acts(self, cur, date_from: str, date_to: str) -> list[dict]:
        """
        Проводимые (активные) проверки из витрины ongoing_acts.

        Уголовные/прокурорские основания уже исключены витриной.
        is_counted=True устанавливается нормализатором по умолчанию.
        """
        cur.execute("""
            SELECT
                act_number                              AS source_id,
                LEFT(code_nk, 2) || 'xx'              AS region_code,
                'УНА'                                   AS management,
                MIN(case_notif_delivery_date)::date    AS prescription_date,
                MIN(case_exe_date)::date               AS create_date
            FROM audit_kpi_data_gold.ongoing_acts
            WHERE case_exe_date >= %(date_from)s
              AND case_exe_date <  %(date_to)s
            GROUP BY act_number, LEFT(code_nk, 2) || 'xx'
        """, {'date_from': date_from, 'date_to': date_to})
        return [dict(row) for row in cur.fetchall()]

    def _fetch_stub(self, source: str) -> list[dict]:
        """Заглушка для CI и local dev без KGD_DB_HOST."""
        if source in ('inis', 'isna'):
            return _STUB_COMPLETED_INSPECTIONS
        if source == 'appeals':
            return _STUB_APPEALS
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
# Тестовые данные (заглушка при отсутствии KGD_DB_HOST)
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

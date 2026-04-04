"""
ETL импортёр: оркестрирует загрузку данных из БД КГД.

Жизненный цикл ImportJob:
  pending → running → done
                   ↘ error

Реальное подключение к БД КГД реализуется в Спринте 18.
Сейчас _fetch_from_kgd_db() возвращает заглушку.
SQL-каркас закомментирован внутри метода — раскомментировать после получения:
  - таблицы/колонки сумм (amount_assessed, amount_collected)
  - справочника форм de_audit_form (код ДФНО)
  - правила выбора финального approval_date при дублях ri_tax_act_audit
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
        Получение данных из БД КГД.

        Параметры диапазона берутся из self.job.params ('date_from', 'date_to').

        Подключение через переменные окружения:
            KGD_DB_HOST, KGD_DB_PORT, KGD_DB_NAME, KGD_DB_USER, KGD_DB_PASSWORD

        Раскомментировать SQL-блоки ниже после получения от Алихана:
          ⏳ таблицы/колонки сумм (amount_assessed, amount_collected)
          ⏳ справочника форм de_audit_form (код ДФНО)
          ⏳ правила выбора финального approval_date при дублях ri_tax_act_audit
          ⏳ таблицы обжалований (для source='appeals')
        """
        source = self.job.source

        # ------------------------------------------------------------------
        # КГД DB — SQL-каркас (Спринт 18)
        # Раскомментировать когда все ⏳ будут закрыты.
        # ------------------------------------------------------------------
        #
        # import psycopg2
        # from decouple import config
        # from psycopg2.extras import RealDictCursor
        #
        # params = self.job.params or {}
        # date_from = params.get('date_from', '2025-01-01')
        # date_to   = params.get('date_to',   '2026-01-01')
        #
        # conn = psycopg2.connect(
        #     host=config('KGD_DB_HOST'),
        #     port=config('KGD_DB_PORT', cast=int),
        #     dbname=config('KGD_DB_NAME'),
        #     user=config('KGD_DB_USER'),
        #     password=config('KGD_DB_PASSWORD'),
        # )
        #
        # try:
        #     with conn.cursor(cursor_factory=RealDictCursor) as cur:
        #
        #         if source in ('inis', 'isna'):
        #             # --------------------------------------------------
        #             # Завершённые проверки
        #             #
        #             # Цепочка: ri_tax_case → ri_tax_act → ri_tax_act_audit
        #             #           → re_user → справочник ДГД → de_department
        #             #
        #             # ⏳ Заменить заглушки:
        #             #   '<таблица_сумм>.<колонка_доначислений>'
        #             #   '<таблица_сумм>.<колонка_взысканий>'
        #             #   правило MAX(approval_date) vs конкретный ri_tax_act_audit_id
        #             # --------------------------------------------------
        #             cur.execute("""
        #                 SELECT
        #                     tc.document_number          AS source_id,
        #                     dgd.code_nk                 AS region_code,
        #                     tc.de_department_id         AS de_department_id,
        #                     af.name_ru                  AS form_type,
        #                     MAX(taa.approval_date)::date AS completed_date,
        #                     tc.create_date::date        AS create_date,
        #                     0                           AS amount_assessed,   -- ⏳
        #                     0                           AS amount_collected    -- ⏳
        #                 FROM ri_tax_case tc
        #                 JOIN ri_tax_act ta
        #                     ON ta.ri_tax_case_id = tc.ri_tax_case_id
        #                 JOIN ri_tax_act_audit taa
        #                     ON taa.ri_tax_act_id = ta.ri_tax_act_id          -- ⏳ уточнить FK-колонку
        #                 JOIN re_user u
        #                     ON u.user_id = tc.creator_id
        #                 JOIN <справочник_ДГД> dgd
        #                     ON dgd.id = u.dgd_id                              -- ⏳ уточнить имя таблицы
        #                 LEFT JOIN de_audit_form af
        #                     ON af.id = tc.de_audit_form_id                    -- ⏳ уточнить имя таблицы
        #                 WHERE
        #                     tc.de_department_id IN %(una_ids)s
        #                     AND MAX(taa.approval_date) BETWEEN %(date_from)s AND %(date_to)s
        #                 GROUP BY
        #                     tc.document_number, dgd.code_nk, tc.de_department_id,
        #                     af.name_ru, tc.create_date
        #             """, {
        #                 'una_ids': tuple(UNA_DEPARTMENT_IDS),
        #                 'date_from': date_from,
        #                 'date_to': date_to,
        #             })
        #             return [dict(row) for row in cur.fetchall()]
        #
        #         if source == 'dgd':
        #             # --------------------------------------------------
        #             # Проводимые (активные) проверки
        #             #
        #             # Признак активности: ri_tax_case_audit.audit_period_end IS NULL
        #             #   ИЛИ отсутствие записи в ri_tax_act (проверка не завершена)
        #             #
        #             # ⏳ Уточнить у Алихана финальный критерий "проверка ещё идёт"
        #             # ⏳ Заменить текстовый поиск оснований на конкретные ID:
        #             #   audit_reason_id NOT IN (<id_уголовных>, <id_прокуратуры>)
        #             # --------------------------------------------------
        #             cur.execute("""
        #                 SELECT
        #                     tc.document_number               AS source_id,
        #                     dgd.code_nk                      AS region_code,
        #                     tc.de_department_id              AS de_department_id,
        #                     tc.delivery_case_date::date      AS prescription_date,
        #                     tc.create_date::date             AS create_date,
        #                     dar.name_ru                      AS audit_reason_text,
        #                     dar.name_ru                      AS case_type
        #                 FROM ri_tax_case tc
        #                 JOIN ri_tax_case_audit tca
        #                     ON tca.ri_tax_case_id = tc.ri_tax_case_id
        #                 LEFT JOIN ri_tax_case_audit_reason tcar
        #                     ON tcar.ri_tax_case_audit_id = tca.ri_tax_case_audit_id
        #                 LEFT JOIN de_tax_payer_audit_reason dar
        #                     ON dar.id = tcar.de_tax_payer_audit_reason_id
        #                 JOIN re_user u
        #                     ON u.user_id = tc.creator_id
        #                 JOIN <справочник_ДГД> dgd
        #                     ON dgd.id = u.dgd_id                              -- ⏳ уточнить имя таблицы
        #                 WHERE
        #                     tc.de_department_id IN %(una_ids)s
        #                     AND tca.audit_period_end IS NULL                  -- ⏳ финальный критерий
        #                     AND tc.create_date BETWEEN %(date_from)s AND %(date_to)s
        #             """, {
        #                 'una_ids': tuple(UNA_DEPARTMENT_IDS),
        #                 'date_from': date_from,
        #                 'date_to': date_to,
        #             })
        #             return [dict(row) for row in cur.fetchall()]
        #
        #         if source == 'appeals':
        #             # ⏳ Таблица обжалований не предоставлена — ждём от Алихана
        #             return []
        #
        # finally:
        #     conn.close()
        #
        # ------------------------------------------------------------------
        # Заглушка (удалить после раскомментирования SQL выше)
        # ------------------------------------------------------------------
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

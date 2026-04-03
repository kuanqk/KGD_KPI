"""
ETL нормализатор: маппинг условных полей БД КГД → модели Django.

Маршрутизация источника по дате (claude.md):
  completed_date < 09.07.2025  →  source = 'inis'
  completed_date >= 09.07.2025 →  source = 'isna'

Условные поля (заменить в Спринте 18 после получения реальной schema от Олжаса):

  CompletedInspection / ActiveInspection:
    region_code      → region (ForeignKey lookup)
    management       → management
    form_type        → form_type
    amount_assessed  → amount_assessed
    amount_collected → amount_collected
    is_counted       → is_counted
    is_accepted      → is_accepted
    completed_date   → completed_date

  ActiveInspection:
    prescription_date → prescription_date
    case_type         → case_type

  AppealDecision:
    region_code      → region (ForeignKey lookup)
    amount_cancelled → amount_cancelled
    is_counted       → is_counted
    completion_date  → completion_date
    decision_date    → decision_date
"""

import logging
from datetime import date

from apps.etl.models import ActiveInspection, AppealDecision, CompletedInspection, ImportJob
from apps.regions.models import Region

logger = logging.getLogger(__name__)

# Дата переключения ИНИС → ИСНА (claude.md)
_ISNA_START = date(2025, 7, 9)


def _parse_date(value) -> date:
    """Приводит строку или date к объекту date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _detect_source(record_date: date) -> str:
    """Определяет источник по дате записи."""
    return 'isna' if record_date >= _ISNA_START else 'inis'


class DataNormalizer:
    """
    Нормализует сырые строки из БД КГД в Django-модели (без сохранения).

    Использование:
        normalizer = DataNormalizer(job)
        obj = normalizer.normalize_completed_inspection(raw_row)
        # obj не сохранён — передать в KGDImporter._bulk_create()
    """

    def __init__(self, job: ImportJob):
        self.job = job
        self._region_cache: dict[str, Region] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize_completed_inspection(self, raw_row: dict) -> CompletedInspection:
        """
        Нормализует строку завершённой проверки (ИНИС/ИСНА).

        Ожидаемые ключи raw_row (условные имена — заменить в Спринте 18):
          region_code, management, form_type, completed_date,
          amount_assessed, amount_collected,
          is_counted, is_accepted,
          source_id (уникальный ID в источнике)
        """
        completed_date = _parse_date(raw_row['completed_date'])
        source = _detect_source(completed_date)
        region = self._get_region(raw_row['region_code'])

        return CompletedInspection(
            source=source,
            source_id=str(raw_row['source_id']),
            import_job=self.job,
            region=region,
            management=raw_row.get('management', ''),
            form_type=raw_row.get('form_type', ''),
            completed_date=completed_date,
            amount_assessed=int(raw_row.get('amount_assessed', 0) or 0),
            amount_collected=int(raw_row.get('amount_collected', 0) or 0),
            is_counted=bool(raw_row.get('is_counted', False)),
            is_accepted=bool(raw_row.get('is_accepted', False)),
            raw_data=raw_row,
        )

    def normalize_active_inspection(self, raw_row: dict) -> ActiveInspection:
        """
        Нормализует строку проводимой (активной) проверки.

        Ожидаемые ключи raw_row:
          region_code, management, case_type, prescription_date,
          is_counted, source_id
        """
        prescription_date = _parse_date(raw_row['prescription_date'])
        # Источник активных проверок определяется по дате начала (предписания)
        source = _detect_source(prescription_date)
        region = self._get_region(raw_row['region_code'])

        return ActiveInspection(
            source=source,
            source_id=str(raw_row['source_id']),
            import_job=self.job,
            region=region,
            management=raw_row.get('management', ''),
            case_type=raw_row.get('case_type', ''),
            prescription_date=prescription_date,
            is_counted=bool(raw_row.get('is_counted', False)),
            raw_data=raw_row,
        )

    def normalize_appeal(self, raw_row: dict) -> AppealDecision:
        """
        Нормализует строку обжалования (отменённого акта).

        Ожидаемые ключи raw_row:
          region_code, amount_cancelled, is_counted,
          completion_date, decision_date, source_id
        """
        region = self._get_region(raw_row['region_code'])

        return AppealDecision(
            source_id=str(raw_row['source_id']),
            import_job=self.job,
            region=region,
            amount_cancelled=int(raw_row.get('amount_cancelled', 0) or 0),
            is_counted=bool(raw_row.get('is_counted', False)),
            completion_date=_parse_date(raw_row['completion_date']),
            decision_date=_parse_date(raw_row['decision_date']),
            raw_data=raw_row,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_region(self, region_code: str) -> Region:
        """Ищет регион по коду с кэшированием в рамках одного импорта."""
        if region_code not in self._region_cache:
            try:
                self._region_cache[region_code] = Region.objects.get(code=region_code)
            except Region.DoesNotExist:
                logger.error('Region not found: code=%s', region_code)
                raise ValueError(f'Регион с кодом "{region_code}" не найден в справочнике.')
        return self._region_cache[region_code]

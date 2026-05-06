"""
ETL нормализатор: маппинг полей витрин БД КГД → модели Django.

Маршрутизация источника по дате (data_sources.md):
  create_date < 09.07.2025  →  source = 'inis'
  create_date >= 09.07.2025 →  source = 'isna'

Витрины (схема audit_kpi_data_gold в БД isna_audit, Алихан 06.05.2026):

  CompletedInspection ← витрина completed_acts + act_collected_amount:
    source_id        ← act_number (GROUP BY в SQL — одна строка на акт)
    region_code      ← LEFT(code_nk, 2) || 'xx'  (e.g. '0601' → '06xx'; в БД — только латинские 'x')
    management       ← 'УНА' (витрина уже фильтрована по УНА)
    form_type        ← '' (не предоставляется витриной)
    completed_date   ← completion_date
    amount_assessed  ← SUM(accrued + penalty + koap_fine + zan_fine - reduced)
    amount_collected ← JOIN с act_collected_amount по act_number, SUM(collected_amount)
                        методы 1 (платёжное поручение) и 2 (переплата) — оба в KPI;
                        метод 3 (ДФНО) уже отсеян витриной

  ActiveInspection ← витрина ongoing_acts:
    source_id         ← act_number
    region_code       ← LEFT(code_nk, 2) || 'xx' (латинские x в SQL; кириллические «х» нормализуются в коде)
    management        ← 'УНА' (витрина уже фильтрована)
    prescription_date ← case_notif_delivery_date
    is_counted        ← True (уголовные/прокурорские исключения уже сделаны в витрине)

  AppealDecision:
    ⏳ данные обжалований обсуждаются с МинФин (зашифрованные суммы)
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from apps.etl.models import ActiveInspection, AppealDecision, CompletedInspection, ImportJob
from apps.regions.models import Region

logger = logging.getLogger(__name__)

# Дата переключения ИНИС → ИСНА (data_sources.md)
_ISNA_START = date(2025, 7, 9)

# ---------------------------------------------------------------------------
# УНА: whitelist ID подразделений аудита (de_department_id)
#
# Источник: old/sprint18/una_departments.csv (76 записей)
# Состав: Отдел аудита №1–6, Управление аудита, Управление налогового аудита,
#         Отдел ЭКНА, ЭКНА
#
# ℹ️  Витрина audit_kpi_data_gold уже фильтрована по УНА —
#     _resolve_management() используется только при прямых RAW-запросах к КГД.
# ---------------------------------------------------------------------------
UNA_DEPARTMENT_IDS: frozenset[int] = frozenset({
    4, 10, 14, 61, 66, 67, 83, 84, 88, 89, 98, 99,
    130, 163, 164, 165, 166, 177, 178, 181, 183, 185, 186, 188,
    189, 190, 191, 193, 194, 197, 198, 207, 208, 210, 211, 212,
    214, 217, 218, 219, 231, 232, 233, 243, 252, 267, 268, 282,
    288, 290, 303, 307, 309, 311, 313, 314, 325, 330, 334, 344,
    374, 375, 393, 394, 401, 407, 409, 425, 719, 730, 821, 987,
    1004, 2001, 2566, 3115,
})

# ---------------------------------------------------------------------------
# Исключения для KPI 5 (ActiveInspection.is_counted)
#
# Основания для исключения из de_tax_payer_audit_reason:
#   - пп.7) п.5 ст.144 — орган уголовного преследования
#   - пп.9 п.3 ст.144  — орган уголовного преследования
#   - пп.4) п.5 ст.144 — органы прокуратуры
#   - пп.5 п.3  ст.144 — органы прокуратуры
#
# ⏳ Конкретные de_tax_payer_audit_reason_id — уточнить у Алихана.
#    Пока фильтр работает через текстовое совпадение в _is_excluded_audit_reason().
# ---------------------------------------------------------------------------
_EXCLUDED_AUDIT_REASON_KEYWORDS = (
    'уголовного преследования',
    'органов прокуратуры',
    'органа прокуратуры',
)


def _parse_amount(value) -> int:
    """
    Converts a numeric value (int, float, or string) to int tenge.

    Handles amounts that may arrive as formatted strings, e.g. '4 404 945' or '2 706,93'.
    Vitrine normalises amounts to numeric types in the DB, but string values may appear
    when reading raw XML exports or running unit tests.
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    cleaned = str(value).replace('\xa0', '').replace(' ', '').replace(',', '.')
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0


def _json_safe_raw(value):
    """
    Значения для JSONField raw_data: psycopg2 отдаёт date/datetime/Decimal —
    стандартный json их не сериализует при INSERT в PostgreSQL.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe_raw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_raw(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _normalize_region_code(region_code) -> str:
    """
    Приводит код ДГД к виду в справочнике Region (латиница, нижний регистр для суффикса xx).

    На практике встречается кириллическая буква «х» вместо латинской «x» (27хх vs 27xx),
    пробелы по краям и «XX» в верхнем регистре — без этого Region.objects.get падает.
    """
    if region_code is None:
        return ''
    s = str(region_code).strip()
    # Cyrillic small/capital ha (looks like Latin x)
    s = s.replace('\u0445', 'x').replace('\u0425', 'x')
    return s.lower()


def _parse_date(value) -> date | None:
    """Приводит строку или date к объекту date. Возвращает None при пустом значении."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _detect_source(record_date: date) -> str:
    """Определяет источник по дате записи."""
    return 'isna' if record_date >= _ISNA_START else 'inis'


def _resolve_management(department_id) -> str:
    """
    Определяет управление по de_department_id из ri_tax_case.

    Возвращает 'УНА' если отдел входит в whitelist, иначе 'OTHER'.
    SQL-запрос в importer.py должен включать de_department_id в результат.
    """
    try:
        return 'УНА' if int(department_id) in UNA_DEPARTMENT_IDS else 'OTHER'
    except (TypeError, ValueError):
        logger.warning('Не удалось определить управление: de_department_id=%r', department_id)
        return 'OTHER'


def _is_excluded_audit_reason(reason_text: str) -> bool:
    """
    Проверяет, является ли основание проверки исключением для KPI 5
    (уголовное преследование / прокуратура).

    ⏳ Временная реализация через ключевые слова — заменить на проверку по
       de_tax_payer_audit_reason_id как только Алихан предоставит конкретные ID.
    """
    if not reason_text:
        return False
    lower = reason_text.lower()
    return any(kw in lower for kw in _EXCLUDED_AUDIT_REASON_KEYWORDS)


class DataNormalizer:
    """
    Нормализует сырые строки из БД КГД в Django-модели (без сохранения).

    SQL-запрос в KGDImporter._fetch_from_kgd_db() должен возвращать строки
    с алиасами колонок, соответствующими ключам raw_row (см. docstring методов).

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
        Нормализует строку завершённой проверки.

        Ожидаемые ключи raw_row (витрина audit_kpi_data_gold.completed_acts):
          source_id        ← act_number (уникальный ключ акта, GROUP BY в SQL)
          region_code      ← LEFT(code_nk, 2) || 'xx'  (e.g. '06xx')
          management       ← 'УНА' (или de_department_id для прямых RAW-запросов)
          form_type        ← '' (отсутствует в витрине — не нужен в KPI)
          completed_date   ← completion_date
          amount_assessed  ← SUM(accrued + penalty + koap_fine + zan_fine - reduced)
          amount_collected ← SUM(collected_amount) из act_collected_amount (0 если нет)
          is_counted       ← нет в витрине, False по умолчанию (вручную оператором)
          is_accepted      ← нет в витрине, False по умолчанию (вручную оператором)
        """
        completed_date = _parse_date(raw_row['completed_date'])
        source = _detect_source(completed_date)
        region = self._get_region(raw_row['region_code'])

        if 'de_department_id' in raw_row:
            management = _resolve_management(raw_row['de_department_id'])
        else:
            management = raw_row.get('management', 'УНА')

        return CompletedInspection(
            source=source,
            source_id=str(raw_row['source_id']),
            import_job=self.job,
            region=region,
            management=management,
            form_type=raw_row.get('form_type', ''),
            completed_date=completed_date,
            amount_assessed=_parse_amount(raw_row.get('amount_assessed', 0)),
            amount_collected=_parse_amount(raw_row.get('amount_collected', 0)),
            is_counted=bool(raw_row.get('is_counted', False)),
            is_accepted=bool(raw_row.get('is_accepted', False)),
            raw_data=_json_safe_raw(raw_row),
        )

    def normalize_active_inspection(self, raw_row: dict) -> ActiveInspection:
        """
        Нормализует строку проводимой (активной) проверки.

        Ожидаемые ключи raw_row (витрина audit_kpi_data_gold.ongoing_acts):
          source_id         ← act_number (GROUP BY в SQL)
          region_code       ← LEFT(code_nk, 2) || 'xx'
          management        ← 'УНА' (витрина уже фильтрована)
          prescription_date ← case_notif_delivery_date (может быть NULL)
          case_type         ← '' (уголовные исключены витриной, текст не передаётся)
          is_counted        ← True по умолчанию (исключения сделаны в витрине)
        """
        prescription_date_raw = raw_row.get('prescription_date')
        prescription_date = _parse_date(prescription_date_raw)

        if prescription_date is None:
            # Если дата вручения отсутствует — использовать дату создания дела для маршрутизации
            create_date = _parse_date(raw_row.get('create_date'))
            source = _detect_source(create_date) if create_date else 'inis'
            logger.warning(
                'prescription_date=NULL для source_id=%s, create_date=%s использован для source',
                raw_row.get('source_id'), raw_row.get('create_date'),
            )
        else:
            source = _detect_source(prescription_date)

        region = self._get_region(raw_row['region_code'])

        if 'de_department_id' in raw_row:
            management = _resolve_management(raw_row['de_department_id'])
        else:
            management = raw_row.get('management', 'OTHER')

        # is_counted: исключаем уголовные дела и запросы прокуратуры
        # ⏳ Временно через текст — заменить на проверку по ID после уточнения у Алихана
        audit_reason_text = raw_row.get('audit_reason_text', raw_row.get('case_type', ''))
        if 'is_counted' in raw_row:
            is_counted = bool(raw_row['is_counted'])
        else:
            is_counted = not _is_excluded_audit_reason(audit_reason_text)

        return ActiveInspection(
            source=source,
            source_id=str(raw_row['source_id']),
            import_job=self.job,
            region=region,
            management=management,
            case_type=audit_reason_text,
            prescription_date=prescription_date,
            is_counted=is_counted,
            raw_data=_json_safe_raw(raw_row),
        )

    def normalize_appeal(self, raw_row: dict) -> AppealDecision:
        """
        Нормализует строку обжалования (отменённого акта).

        ⏳ Таблица обжалований в БД КГД не предоставлена (см. docs/sprints/etl_kgd_gold_vitrines.md).
        Текущие ключи — из заглушки. Обновить после получения schema от Алихана.

        Ожидаемые ключи raw_row:
          source_id       ← ⏳ уточнить
          region_code     ← ⏳ уточнить
          amount_cancelled← ⏳ уточнить
          is_counted      ← ⏳ уточнить
          completion_date ← ⏳ уточнить
          decision_date   ← ⏳ уточнить
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
            raw_data=_json_safe_raw(raw_row),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_region(self, region_code: str) -> Region:
        """Ищет регион по коду с кэшированием в рамках одного импорта."""
        key = _normalize_region_code(region_code)
        if not key:
            logger.error('Region code empty after normalize: raw=%r', region_code)
            raise ValueError('Код региона пустой или некорректный.')
        if key not in self._region_cache:
            try:
                self._region_cache[key] = Region.objects.get(code=key)
            except Region.DoesNotExist:
                logger.error('Region not found: code=%r (normalized from %r)', key, region_code)
                raise ValueError(f'Регион с кодом "{key}" не найден в справочнике.')
        return self._region_cache[key]

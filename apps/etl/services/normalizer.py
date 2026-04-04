"""
ETL нормализатор: маппинг реальных полей БД КГД → модели Django.

Маршрутизация источника по дате (data_sources.md):
  create_date < 09.07.2025  →  source = 'inis'
  create_date >= 09.07.2025 →  source = 'isna'

Реальные поля БД КГД (Спринт 18, docs/business/data_sources.md):

  CompletedInspection:
    region_code      ← SQL alias для: ri_tax_case.creator_tax_org_id → справочник ДГД → code_nk
    de_department_id ← ri_tax_case.de_department_id (→ управление через UNA_DEPARTMENT_IDS)
    form_type        ← SQL alias для: de_audit_form.name_ru  ⏳ нужен справочник форм
    completed_date   ← SQL alias для: ri_tax_act_audit.approval_date  ⚠️ аномалия дублей
    amount_assessed  ← ⏳ уточнить у Алихана (таблица/колонка сумм)
    amount_collected ← ⏳ уточнить у Алихана
    source_id        ← ri_tax_case.document_number (номер предписания)

  ActiveInspection:
    region_code       ← SQL alias для: dgd_code (4-символьный)
    de_department_id  ← ri_tax_case.de_department_id
    prescription_date ← SQL alias для: delivery_case_date  ⚠️ бывает NULL
    audit_reason_id   ← de_tax_payer_audit_reason_id  ⏳ нужны конкретные ID для исключений
    source_id         ← ri_tax_case.document_number

  AppealDecision:
    ⏳ таблица обжалований не предоставлена — всё поле-маппинги pending
"""

import logging
from datetime import date

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
# ⚠️ Уточнить у Алихана: входит ли ЭКНА в расчёт KPI как УНА?
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


def _parse_date(value) -> date | None:
    """Приводит строку или date к объекту date. Возвращает None при пустом значении."""
    if value is None or value == '':
        return None
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
        Нормализует строку завершённой проверки (ИНИС/ИСНА).

        Ожидаемые ключи raw_row (реальные поля → SQL алиасы):
          source_id        ← ri_tax_case.document_number
          region_code      ← справочник_ДГД.code_nk (4 символа, e.g. '6001')
          de_department_id ← ri_tax_case.de_department_id  (→ resolves management)
          form_type        ← de_audit_form.name_ru  ⏳ нужен справочник форм
          completed_date   ← ri_tax_act_audit.approval_date  ⚠️ аномалия дублей
          amount_assessed  ← ⏳ уточнить у Алихана
          amount_collected ← ⏳ уточнить у Алихана
          is_counted       ← нет в БД КГД, False по умолчанию (проставляется вручную)
          is_accepted      ← нет в БД КГД, False по умолчанию (проставляется вручную)
        """
        completed_date = _parse_date(raw_row['completed_date'])
        source = _detect_source(completed_date)
        region = self._get_region(raw_row['region_code'])

        # management: из de_department_id если есть, иначе из поля 'management' (заглушки)
        if 'de_department_id' in raw_row:
            management = _resolve_management(raw_row['de_department_id'])
        else:
            management = raw_row.get('management', 'OTHER')

        return CompletedInspection(
            source=source,
            source_id=str(raw_row['source_id']),
            import_job=self.job,
            region=region,
            management=management,
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

        Ожидаемые ключи raw_row (реальные поля → SQL алиасы):
          source_id         ← ri_tax_case.document_number
          region_code       ← справочник_ДГД.code_nk (4 символа)
          de_department_id  ← ri_tax_case.de_department_id  (→ resolves management)
          prescription_date ← ri_tax_case.delivery_case_date  ⚠️ бывает NULL
          audit_reason_text ← de_tax_payer_audit_reason.name_ru  ⏳ временный ключевой поиск
          case_type         ← de_tax_payer_audit_reason.name_ru (текст основания)
          is_counted        ← вычисляется из audit_reason_text (не уголовное + не прокуратура)
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
            raw_data=raw_row,
        )

    def normalize_appeal(self, raw_row: dict) -> AppealDecision:
        """
        Нормализует строку обжалования (отменённого акта).

        ⏳ Таблица обжалований в БД КГД не предоставлена (Спринт 18).
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

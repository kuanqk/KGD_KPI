"""
KPI Engine — центральный расчётный модуль.

Формулы строго по claude.md. Порядок работы:
  1. KPIEngine(date_from, date_to, user)
  2. engine.calculate_all()        ← все регионы
     или engine.calc_assessment(region)  ← один KPI

Зависимости:
  - Нормализованные данные из ETL (CompletedInspection, ActiveInspection, AppealDecision)
  - Ручные вводы (ManualInput) — kbk_share_pct, staff_count
  - Активные формулы (KPIFormula.get_active)

Важные нюансы из claude.md / Олжас 2026:
  - KPI 3: диапазон 80–89% → 0 баллов (не 5!)
  - KPI 3: числитель и знаменатель = тот же набор завершённых УНА, что и KPI 1 (без is_counted / без исключения ДФНО)
  - KPI 5: исключить уголовные дела и запросы правоохран. органов
  - KPI 6: отменённые суммы (is_counted=True); без отсечения по сроку до решения комиссии (снято с Excel 2026)
  - КГД (is_summary=True) — ранг не назначается
"""
import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation

from django.db import transaction
from django.db.models import Sum

from apps.core.models import AuditLog
from apps.etl.models import (
    ActiveInspection,
    AppealDecision,
    CompletedInspection,
    ManualInput,
)
from apps.kpi.models import KPIFormula, KPIResult, KPISummary
from apps.regions.models import Region

logger = logging.getLogger(__name__)

_D = Decimal      # удобный алиас
_ZERO = Decimal('0')
_ONE_HUNDRED = Decimal('100')
_FOUR = Decimal('0.0001')

# Типы уголовных/правоохранительных дел (KPI 5) — условные значения до Спринта 18
_EXCLUDED_CASE_TYPES = frozenset([
    'уголовное дело',
    'правоохранительные органы',
    'запрос правоохранительных органов',
])


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Деление с защитой от нуля. Возвращает None при нулевом знаменателе."""
    if not denominator:
        return None
    try:
        return numerator / denominator
    except (DivisionByZero, InvalidOperation):
        return None


def _to_decimal(value) -> Decimal:
    """Конвертирует числовое значение в Decimal."""
    if value is None:
        return _ZERO
    return _D(str(value))


def _apply_score(value: Decimal | None, thresholds: list[dict]) -> int:
    """
    Применяет список правил-порогов, возвращает балл первого совпадения.

    Формат порога: {'condition': 'gte'|'gt'|'lte'|'lt', 'value': ..., 'score': ...}
    Правила применяются сверху вниз — первое совпадение выигрывает.
    """
    if value is None:
        return 0
    for rule in thresholds:
        t_val = _D(str(rule['value']))
        cond = rule['condition']
        if cond == 'gte' and value >= t_val:
            return rule['score']
        if cond == 'gt' and value > t_val:
            return rule['score']
        if cond == 'lte' and value <= t_val:
            return rule['score']
        if cond == 'lt' and value < t_val:
            return rule['score']
    return 0


class KPIEngine:
    """
    Расчётный движок KPI.

    Параметры:
        date_from — начало периода (накопленный итог: обычно 01.01)
        date_to   — конец периода / дата отчёта
        user      — User, инициировавший расчёт (для AuditLog и KPIResult.calculated_by)
    """

    def __init__(self, date_from: date, date_to: date, user=None):
        self.date_from = date_from
        self.date_to = date_to
        self.user = user
        self.months = self._count_months()
        self._prev_year = date_from.year - 1
        # Кэш fact из KPI 1: region.pk → Decimal (нужен для KPI 6)
        self._assessment_facts: dict[int, Decimal] = {}
        # Ленивый кэш единого порога KPI 3
        self._kpi3_plan_value: Decimal | None | object = _UNSET
        # Кэш формул (загружается один раз)
        self._formulas: dict[str, KPIFormula] = {}

    # ------------------------------------------------------------------
    # Public: полный расчёт
    # ------------------------------------------------------------------

    def calculate_all(self, regions=None) -> list[KPISummary]:
        """
        Рассчитывает все 6 KPI для переданных (или всех ДГД) регионов.
        Сохраняет KPIResult + KPISummary, назначает ранги, пишет AuditLog.
        """
        if regions is None:
            regions = list(Region.objects.filter(is_summary=False).order_by('order'))

        self._load_formulas()

        summaries: list[KPISummary] = []
        with transaction.atomic():
            for region in regions:
                summary = self._calculate_region(region)
                summaries.append(summary)
            self._assign_ranks(summaries)

        AuditLog.log(
            event='kpi_calc',
            user=self.user,
            details={
                'date_from': str(self.date_from),
                'date_to': str(self.date_to),
                'regions': [r.pk for r in regions],
                'summaries': [s.pk for s in summaries],
            },
        )
        logger.info(
            'KPI calculated for %d regions, period %s–%s',
            len(regions), self.date_from, self.date_to,
        )
        return summaries

    # ------------------------------------------------------------------
    # Public: отдельные KPI
    # ------------------------------------------------------------------

    def calc_assessment(self, region: Region) -> KPIResult:
        """
        KPI 1 — Доначисление (макс. 10 баллов).

        Факт  = SUM(amount_assessed) WHERE management='УНА', period
        План  = kbk_share_pct / 100 * SUM(прошлогодних планов всех ДГД) * 1.20
        Баллы: ≥100%→10, ≥90%→5, <90%→0
        """
        formula = self._get_formula('assessment')

        fact = _to_decimal(
            CompletedInspection.objects
            .filter(
                region=region,
                management='УНА',
                completed_date__gte=self.date_from,
                completed_date__lte=self.date_to,
            )
            .aggregate(s=Sum('amount_assessed'))['s']
        )

        # Кэшируем fact для KPI 6
        self._assessment_facts[region.pk] = fact

        plan = self._calc_plan_assessment(region)
        percent = _safe_div(fact * _ONE_HUNDRED, plan) if plan else None
        score = _apply_score(percent, formula.config['thresholds'])

        return self._save_result(
            region=region,
            kpi_type='assessment',
            formula=formula,
            plan=plan,
            fact=fact,
            percent=percent,
            score=score,
            calc_details={
                'sum_assessed': int(fact),
                'kbk_share_pct': str(self._get_kbk_share(region)),
                'prev_year_plan_total': str(self._prev_year_plan_total('assessment')),
                'management_filter': 'УНА',
            },
        )

    def calc_collection(self, region: Region) -> KPIResult:
        """
        KPI 2 — Взыскание (макс. 40 баллов).

        Факт  = SUM(amount_collected) WHERE management='УНА', is_accepted=True, period
        ИСНА: суммы по de_collection_method_id=3 (доп. налоговые отчётности) в KPI не входят —
        исключать при ETL или в сыром raw; Олжас 2026.
        План  = kbk_share_pct / 100 * SUM(прошлогодних планов взысканий) * 1.20
        Баллы: ≥100%→40, ≥90%→20, ≥80%→10, <80%→0
        """
        formula = self._get_formula('collection')

        fact = _to_decimal(
            CompletedInspection.objects
            .filter(
                region=region,
                management='УНА',
                is_accepted=True,
                completed_date__gte=self.date_from,
                completed_date__lte=self.date_to,
            )
            .aggregate(s=Sum('amount_collected'))['s']
        )

        plan = self._calc_plan_collection(region)
        percent = _safe_div(fact * _ONE_HUNDRED, plan) if plan else None
        score = _apply_score(percent, formula.config['thresholds'])

        return self._save_result(
            region=region,
            kpi_type='collection',
            formula=formula,
            plan=plan,
            fact=fact,
            percent=percent,
            score=score,
            calc_details={
                'sum_collected': int(fact),
                'is_accepted_filter': True,
                'kbk_share_pct': str(self._get_kbk_share(region)),
                'prev_year_plan_total': str(self._prev_year_plan_total('collection')),
                'management_filter': 'УНА',
            },
        )

    def calc_avg_assessment(self, region: Region) -> KPIResult:
        """
        KPI 3 — Среднее доначисление на 1 проверку (макс. 10 баллов).

        Среднее_факт = SUM(amount_assessed) / COUNT(inspections)
                       WHERE management='УНА', период — тот же набор, что KPI 1 (Олжас 2026).
        План = единый порог для всех ДГД = (среднее по всем 20 ДГД за прошлый год) * 1.20
        Баллы: ≥100%→10, ≥90%→5, <90%→0  (80–89% тоже 0!)
        """
        formula = self._get_formula('avg_assessment')

        qs = CompletedInspection.objects.filter(
            region=region,
            management='УНА',
            completed_date__gte=self.date_from,
            completed_date__lte=self.date_to,
        )

        agg = qs.aggregate(s=Sum('amount_assessed'))
        total_sum = _to_decimal(agg['s'])
        count = qs.count()

        avg_fact = _safe_div(total_sum, _D(str(count))) if count else None
        plan = self._kpi3_plan()
        percent = _safe_div(avg_fact * _ONE_HUNDRED, plan) if (avg_fact and plan) else None
        score = _apply_score(percent, formula.config['thresholds'])

        return self._save_result(
            region=region,
            kpi_type='avg_assessment',
            formula=formula,
            plan=plan,
            fact=avg_fact,
            percent=percent,
            score=score,
            calc_details={
                'sum_assessed': int(total_sum),
                'inspection_count': count,
                'avg_fact': str(avg_fact) if avg_fact else None,
                'plan_unified': str(plan) if plan else None,
                'aligned_with_kpi1': True,
                'management_filter': 'УНА',
            },
        )

    def calc_workload(self, region: Region) -> KPIResult:
        """
        KPI 4 — Коэффициент занятости (макс. 15 баллов).

        Коэф = Проверок / Сотрудников / Месяцев
               WHERE management='УНА', is_counted=True
        Баллы: ≥0.5→15, ≥0.4→5, <0.4→0
        """
        formula = self._get_formula('workload')

        count = CompletedInspection.objects.filter(
            region=region,
            management='УНА',
            is_counted=True,
            completed_date__gte=self.date_from,
            completed_date__lte=self.date_to,
        ).count()

        manual = self._get_manual(region)
        staff = manual.staff_count if manual and manual.staff_count else None

        if staff and self.months > 0:
            coefficient = _D(str(count)) / _D(str(staff)) / _D(str(self.months))
        else:
            coefficient = None

        score = _apply_score(coefficient, formula.config['thresholds'])

        return self._save_result(
            region=region,
            kpi_type='workload',
            formula=formula,
            plan=None,
            fact=coefficient,
            percent=None,
            score=score,
            calc_details={
                'inspection_count': count,
                'staff_count': staff,
                'months': self.months,
                'coefficient': str(coefficient) if coefficient is not None else None,
                'management_filter': 'УНА',
            },
        )

    def calc_long_inspections(self, region: Region) -> KPIResult:
        """
        KPI 5 — Доля проверок > 6 месяцев (макс. 10 баллов).

        Все проводимые: is_counted=True, исключить уголовные и правоохранит.
        Долгие: (date_to − prescription_date) > 180 дней
        Доля = Долгие / Все * 100%
        Баллы: <20%→10, ≥20%→0
        """
        formula = self._get_formula('long_inspections')

        base_qs = ActiveInspection.objects.filter(
            region=region,
            is_counted=True,
        ).exclude(case_type__in=_EXCLUDED_CASE_TYPES)

        total_count = base_qs.count()

        # Долгие: prescription_date < date_to − 180 дней
        cutoff = self.date_to - timedelta(days=180)
        long_count = base_qs.filter(prescription_date__lt=cutoff).count()

        if total_count > 0:
            share_pct = _D(str(long_count)) / _D(str(total_count)) * _ONE_HUNDRED
        else:
            # Нет активных проверок — считаем долю 0% → максимальный балл
            share_pct = _ZERO

        score = _apply_score(share_pct, formula.config['thresholds'])

        return self._save_result(
            region=region,
            kpi_type='long_inspections',
            formula=formula,
            plan=None,
            fact=share_pct,
            percent=share_pct,
            score=score,
            calc_details={
                'total_count': total_count,
                'long_count': long_count,
                'share_pct': str(share_pct),
                'cutoff_date': str(cutoff),
                'long_threshold_days': 180,
                'excluded_case_types': list(_EXCLUDED_CASE_TYPES),
            },
        )

    def calc_cancelled(self, region: Region) -> KPIResult:
        """
        KPI 6 — Удельный вес отменённых сумм (макс. 15 баллов).

        Отменено = SUM(amount_cancelled) WHERE is_counted=True (без отсечения по сроку — Олжас 2026)
        Доначислено = Факт из KPI 1 (для того же региона и периода)
        Доля = Отменено / Доначислено * 100%
        Баллы: ≤1%→15, ≤2%→5, >2%→0
        """
        formula = self._get_formula('cancelled')

        appeals_qs = AppealDecision.objects.filter(region=region, is_counted=True)

        amount_cancelled = _to_decimal(
            appeals_qs.aggregate(s=Sum('amount_cancelled'))['s']
        )

        # Доначислено = fact из KPI 1 (должен быть рассчитан ранее в _calculate_region)
        amount_assessed = self._assessment_facts.get(region.pk)
        if amount_assessed is None:
            # Fallback: читаем из сохранённого KPIResult
            try:
                r1 = KPIResult.objects.filter(
                    region=region,
                    kpi_type='assessment',
                    date_from=self.date_from,
                    date_to=self.date_to,
                ).latest('calculated_at')
                amount_assessed = _to_decimal(r1.fact)
            except KPIResult.DoesNotExist:
                amount_assessed = _ZERO

        if amount_assessed > _ZERO:
            share_pct = amount_cancelled / amount_assessed * _ONE_HUNDRED
        else:
            # Нет доначислений → нет отменённых → доля 0% → максимальный балл
            share_pct = _ZERO

        score = _apply_score(share_pct, formula.config['thresholds'])

        return self._save_result(
            region=region,
            kpi_type='cancelled',
            formula=formula,
            plan=None,
            fact=share_pct,
            percent=share_pct,
            score=score,
            calc_details={
                'amount_cancelled': int(amount_cancelled),
                'amount_assessed_kpi1': int(amount_assessed),
                'share_pct': str(share_pct),
            },
        )

    # ------------------------------------------------------------------
    # Private: вспомогательные расчёты
    # ------------------------------------------------------------------

    def _calculate_region(self, region: Region) -> KPISummary:
        """Рассчитывает все 6 KPI для одного региона и сохраняет KPISummary."""
        r1 = self.calc_assessment(region)
        r2 = self.calc_collection(region)
        r3 = self.calc_avg_assessment(region)
        r4 = self.calc_workload(region)
        r5 = self.calc_long_inspections(region)
        r6 = self.calc_cancelled(region)

        score_total = r1.score + r2.score + r3.score + r4.score + r5.score + r6.score

        summary, _ = KPISummary.objects.update_or_create(
            region=region,
            date_from=self.date_from,
            date_to=self.date_to,
            defaults={
                'score_assessment':       r1.score,
                'score_collection':       r2.score,
                'score_avg_assessment':   r3.score,
                'score_workload':         r4.score,
                'score_long_inspections': r5.score,
                'score_cancelled':        r6.score,
                'score_total':            score_total,
                'rank':                   None,   # назначается в _assign_ranks
            },
        )
        return summary

    def _assign_ranks(self, summaries: list[KPISummary]) -> None:
        """
        Назначает ранги по убыванию score_total среди не-сводных регионов.
        КГД (is_summary=True) ранг не получает (rank=None).
        При равных баллах — одинаковый ранг (RANK, не DENSE_RANK).
        """
        rankable = [
            s for s in summaries
            if not s.region.is_summary
        ]
        rankable.sort(key=lambda s: -s.score_total)

        current_rank = 1
        for i, summary in enumerate(rankable):
            if i > 0 and rankable[i].score_total < rankable[i - 1].score_total:
                current_rank = i + 1
            summary.rank = current_rank
            summary.save(update_fields=['rank'])

    def _save_result(
        self,
        region: Region,
        kpi_type: str,
        formula: KPIFormula,
        plan,
        fact,
        percent,
        score: int,
        calc_details: dict,
    ) -> KPIResult:
        """Сохраняет (или обновляет) KPIResult и возвращает его."""
        result, _ = KPIResult.objects.update_or_create(
            region=region,
            kpi_type=kpi_type,
            date_from=self.date_from,
            date_to=self.date_to,
            formula=formula,
            defaults={
                'plan': plan,
                'fact': fact,
                'percent': percent,
                'score': score,
                'calc_details': calc_details,
                'calculated_by': self.user,
            },
        )
        return result

    # ------------------------------------------------------------------
    # Private: план и вспомогательные запросы
    # ------------------------------------------------------------------

    def _calc_plan_assessment(self, region: Region) -> Decimal | None:
        """KPI 1 plan = kbk_share_pct / 100 * SUM(prev_year_plans) * 1.20"""
        kbk = self._get_kbk_share(region)
        total = self._prev_year_plan_total('assessment')
        if not kbk or not total:
            return None
        return (kbk / _ONE_HUNDRED * total * _D('1.20')).quantize(_FOUR, ROUND_HALF_UP)

    def _calc_plan_collection(self, region: Region) -> Decimal | None:
        """KPI 2 plan = kbk_share_pct / 100 * SUM(prev_year_collection_plans) * 1.20"""
        kbk = self._get_kbk_share(region)
        total = self._prev_year_plan_total('collection')
        if not kbk or not total:
            return None
        return (kbk / _ONE_HUNDRED * total * _D('1.20')).quantize(_FOUR, ROUND_HALF_UP)

    def _kpi3_plan(self) -> Decimal | None:
        """
        Единый порог KPI 3 для всех ДГД = среднее по всем 20 ДГД за прошлый год * 1.20.
        Вычисляется один раз и кэшируется.
        """
        if self._kpi3_plan_value is not _UNSET:
            return self._kpi3_plan_value  # type: ignore[return-value]

        qs = CompletedInspection.objects.filter(
            management='УНА',
            completed_date__year=self._prev_year,
            region__is_summary=False,
        )

        total_sum = _to_decimal(qs.aggregate(s=Sum('amount_assessed'))['s'])
        total_count = qs.count()

        if total_count > 0:
            prev_avg = total_sum / _D(str(total_count))
            self._kpi3_plan_value = (prev_avg * _D('1.20')).quantize(_FOUR, ROUND_HALF_UP)
        else:
            self._kpi3_plan_value = None

        return self._kpi3_plan_value

    def _prev_year_plan_total(self, kpi_type: str) -> Decimal | None:
        """
        SUM(план всех ДГД за прошлый год) для KPI 1 или KPI 2.
        Берётся из сохранённых KPIResult предыдущего года.
        """
        total = KPIResult.objects.filter(
            kpi_type=kpi_type,
            date_from__year=self._prev_year,
            region__is_summary=False,
        ).aggregate(s=Sum('plan'))['s']
        return _to_decimal(total) if total else None

    def _get_kbk_share(self, region: Region) -> Decimal | None:
        """Возвращает kbk_share_pct из ManualInput для текущего года."""
        manual = self._get_manual(region)
        return _to_decimal(manual.kbk_share_pct) if manual and manual.kbk_share_pct else None

    def _get_manual(self, region: Region) -> ManualInput | None:
        """ManualInput для данного региона и года начала периода."""
        return ManualInput.objects.filter(region=region, year=self.date_from.year).first()

    def _count_months(self) -> int:
        """
        Количество полных календарных месяцев в периоде (накопленный итог).
        Пример: 01.01–31.03 = 3, 01.01–30.06 = 6.
        """
        months = (
            (self.date_to.year - self.date_from.year) * 12
            + self.date_to.month
            - self.date_from.month
            + 1
        )
        return max(months, 1)

    def _load_formulas(self) -> None:
        """Загружает все активные формулы один раз перед расчётом."""
        if self._formulas:
            return
        for kpi_type, _ in KPIFormula.KPI_TYPES:
            try:
                self._formulas[kpi_type] = KPIFormula.get_active(kpi_type)
            except KPIFormula.DoesNotExist:
                raise RuntimeError(
                    f'Нет активной формулы для {kpi_type}. '
                    f'Запустите: python manage.py init_formulas'
                )

    def _get_formula(self, kpi_type: str) -> KPIFormula:
        """Возвращает формулу из кэша или загружает напрямую (для одиночных вызовов)."""
        if kpi_type not in self._formulas:
            self._formulas[kpi_type] = KPIFormula.get_active(kpi_type)
        return self._formulas[kpi_type]


# Sentinel для ленивого кэша
_UNSET = object()

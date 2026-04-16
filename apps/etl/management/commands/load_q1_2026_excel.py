"""
Загрузка тестовых ETL-данных за 1-й квартал 2026 из Excel
«Статистика КЭР РК на 01.04.2026.xlsx».

Период расчёта KPI: 01.01.2026 — 31.03.2026 (включительно).
Для KPIEngine нужны данные за 2025 год (проверки + KPIResult 2025).

Пример:
    python manage.py load_q1_2026_excel
    python manage.py load_q1_2026_excel --path data/excel/Статистика\\ КЭР\\ РК\\ на\\ 01.04.2026.xlsx
    python manage.py load_q1_2026_excel --clear --calculate
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import random
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.regions.models import Region
from apps.etl.models import (
    CompletedInspection,
    ActiveInspection,
    AppealDecision,
    ManualInput,
    ImportJob,
)
from apps.etl.excel_q1_2026 import parse_statistika_ker_2026_04
from apps.kpi.models import KPIResult, KPIFormula, KPISummary
from apps.kpi.services.engine import KPIEngine


class Command(BaseCommand):
    help = (
        "Загружает тестовые данные из Excel на 01.04.2026 (Q1 2026). "
        "Требуются регионы (loaddata regions.json)."
    )

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        default_xlsx = root / "data" / "excel" / "Статистика КЭР РК на 01.04.2026.xlsx"
        parser.add_argument(
            "--path",
            type=str,
            default=str(default_xlsx),
            help="Путь к xlsx",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Очистить ETL и KPI за 2025–2026 перед загрузкой",
        )
        parser.add_argument(
            "--calculate",
            action="store_true",
            help="Запустить KPIEngine(2026-01-01 … 2026-03-31) после загрузки",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только распарсить Excel и вывести число регионов",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            self.stdout.write(self.style.ERROR(f"Файл не найден: {path}"))
            return

        parsed = parse_statistika_ker_2026_04(path)
        n = len(parsed.regions)
        self.stdout.write(self.style.SUCCESS(f"Распознано регионов в Excel: {n}"))

        if options["dry_run"]:
            for code in sorted(parsed.regions.keys())[:5]:
                self.stdout.write(f"  {code}: {parsed.regions[code].kpi_fact_01_04_2026}")
            return

        if options["clear"]:
            self.stdout.write("Очистка ETL и KPI (2025+)…")
            CompletedInspection.objects.all().delete()
            ActiveInspection.objects.all().delete()
            AppealDecision.objects.all().delete()
            ManualInput.objects.all().delete()
            KPIResult.objects.filter(date_from__year__gte=2025).delete()
            KPISummary.objects.filter(date_from__year__gte=2025).delete()
            self.stdout.write(self.style.SUCCESS("Очищено."))

        regions = {r.code: r for r in Region.objects.filter(is_summary=False)}
        if not regions:
            self.stdout.write(
                self.style.ERROR(
                    "Регионы не найдены. Сначала: python manage.py loaddata apps/regions/fixtures/regions.json"
                )
            )
            return

        report_date = date(2026, 4, 1)
        y2025_start = date(2025, 1, 1)
        q1_start = date(2026, 1, 1)
        q1_end = date(2026, 3, 31)

        import_job, _ = ImportJob.objects.get_or_create(
            source="inis",
            status="done",
            defaults={
                "records_total": 8000,
                "records_imported": 8000,
                "params": {"test": True, "source": "excel_q1_2026_04"},
            },
        )

        # ── ManualInput 2026: доля КБК и штат ─────────────────────────────
        self.stdout.write("ManualInput 2026 (КБК, штат)…")
        mi_n = 0
        for code, row in parsed.regions.items():
            reg = regions.get(code)
            if not reg:
                continue
            kbk = row.kbk_share_pct if row.kbk_share_pct is not None else KBK_FALLBACK.get(code)
            staff = row.staff_count or KPI4_DEFAULT_STAFF.get(code, 10)
            if kbk is None:
                continue
            ManualInput.objects.update_or_create(
                region=reg,
                year=2026,
                defaults={
                    "kbk_share_pct": kbk,
                    "staff_count": staff,
                },
            )
            mi_n += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ ManualInput: {mi_n}"))

        # ── CompletedInspection 2025 (для KPI 3: prev_year = 2025) ──────────
        self.stdout.write("CompletedInspection 2025…")
        c25 = 0
        for code, row in parsed.regions.items():
            reg = regions.get(code)
            if not reg:
                continue
            amt_mln = row.donach_01_04_2025_mln
            if amt_mln is None or amt_mln <= 0:
                continue
            count = max(row.check_count, 1)
            total_tg = int(amt_mln * 1_000_000)
            k2_mln = row.vzyscano_01_01_2026 or 0
            collected_tg = int(float(k2_mln) * 1_000_000 * 0.25)
            per_a = total_tg // count
            per_c = collected_tg // count if collected_tg else 0
            batch = []
            for i in range(count):
                days_offset = int((i / count) * 365)
                completed_dt = y2025_start + timedelta(days=min(days_offset, 364))
                src = "isna" if completed_dt >= date(2025, 7, 9) else "inis"
                batch.append(
                    CompletedInspection(
                        source=src,
                        source_id=f"Q1-P25-{code}-{i+1:04d}",
                        region=reg,
                        management="УНА",
                        form_type="Тематическая проверка",
                        completed_date=completed_dt,
                        amount_assessed=per_a,
                        amount_collected=per_c,
                        is_counted=True,
                        is_accepted=True,
                        is_anomaly=False,
                        import_job=import_job,
                        raw_data={"test": True, "period": "2025", "excel_q1": True},
                    )
                )
            CompletedInspection.objects.bulk_create(batch, ignore_conflicts=True)
            c25 += count
        self.stdout.write(self.style.SUCCESS(f"  ✓ 2025: {c25}"))

        # ── CompletedInspection 2026 Q1 (факт I / взыскание I) ─────────────
        self.stdout.write("CompletedInspection 2026 Q1…")
        c26 = 0
        for code, row in parsed.regions.items():
            reg = regions.get(code)
            if not reg:
                continue
            fact_mln = row.kpi_fact_01_04_2026
            k2_mln = row.k2_fact_01_04_2026
            if fact_mln is None and k2_mln is None:
                continue
            fact_mln = fact_mln or 0
            k2_mln = k2_mln or 0
            count = max(row.check_count, 1)
            count = min(count, 90)
            total_a = int(fact_mln * 1_000_000)
            total_c = int(k2_mln * 1_000_000)
            per_a = total_a // count if count else 0
            per_c = total_c // count if count else 0
            batch = []
            for i in range(count):
                days_offset = int((i / count) * 89)
                completed_dt = q1_start + timedelta(days=days_offset)
                if completed_dt > q1_end:
                    completed_dt = q1_end
                batch.append(
                    CompletedInspection(
                        source="inis",
                        source_id=f"Q1-26-{code}-{i+1:04d}",
                        region=reg,
                        management="УНА",
                        form_type="Тематическая проверка",
                        completed_date=completed_dt,
                        amount_assessed=per_a,
                        amount_collected=per_c,
                        is_counted=True,
                        is_accepted=True,
                        is_anomaly=False,
                        import_job=import_job,
                        raw_data={"test": True, "period": "2026-Q1", "excel_q1": True},
                    )
                )
            CompletedInspection.objects.bulk_create(batch, ignore_conflicts=True)
            c26 += count
        self.stdout.write(self.style.SUCCESS(f"  ✓ 2026 Q1: {c26}"))

        # ── ActiveInspection (на дату отчёта 01.04.2026) ───────────────────
        self.stdout.write("ActiveInspection…")
        active_n = _load_active(parsed, regions, report_date, import_job)
        self.stdout.write(self.style.SUCCESS(f"  ✓ ActiveInspection: {active_n}"))

        # ── AppealDecision ───────────────────────────────────────────────────
        self.stdout.write("AppealDecision…")
        app_n = _load_appeals(parsed, regions, import_job)
        self.stdout.write(self.style.SUCCESS(f"  ✓ AppealDecision: {app_n}"))

        # ── KPIResult 2025 (суммы планов всех ДГД для Engine) ──────────────
        self.stdout.write("KPIResult 2025 (assessment + collection)…")
        fa = KPIFormula.get_active("assessment")
        fc = KPIFormula.get_active("collection")
        d0, d1 = date(2025, 1, 1), date(2025, 12, 31)
        kr = 0
        for code, row in parsed.regions.items():
            reg = regions.get(code)
            if not reg:
                continue
            if row.donachisleno_01_01_2026 is not None:
                fact = Decimal(str(row.donachisleno_01_01_2026)) * Decimal("1000000")
                KPIResult.objects.update_or_create(
                    region=reg,
                    kpi_type="assessment",
                    date_from=d0,
                    date_to=d1,
                    formula=fa,
                    defaults={
                        "plan": fact,
                        "fact": fact,
                        "percent": Decimal("100"),
                        "score": 10,
                        "status": "approved",
                    },
                )
                kr += 1
            if row.vzyscano_01_01_2026 is not None:
                fact = Decimal(str(row.vzyscano_01_01_2026)) * Decimal("1000000")
                KPIResult.objects.update_or_create(
                    region=reg,
                    kpi_type="collection",
                    date_from=d0,
                    date_to=d1,
                    formula=fc,
                    defaults={
                        "plan": fact,
                        "fact": fact,
                        "percent": Decimal("100"),
                        "score": 40,
                        "status": "approved",
                    },
                )
                kr += 1
        self.stdout.write(self.style.SUCCESS(f"  ✓ KPIResult 2025: {kr} строк (assessment + collection)"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Готово. Период KPI: 2026-01-01 — 2026-03-31"))
        self.stdout.write(f"Источник: {path.name}")

        if options["calculate"]:
            self.stdout.write("Расчёт KPI…")
            engine = KPIEngine(q1_start, q1_end, user=None)
            summaries = engine.calculate_all()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ KPISummary: {len(summaries)} (GET /api/v1/kpi/summary/?date_from=2026-01-01&date_to=2026-03-31)")
            )


def _load_active(parsed, regions, report_date, import_job) -> int:
    n = 0
    batch = []
    for code, row in parsed.regions.items():
        reg = regions.get(code)
        if not reg:
            continue
        total = row.active_total
        long_count = row.active_long
        normal_count = max(total - long_count, 0)
        for i in range(normal_count):
            days_ago = random.randint(30, 170)
            batch.append(
                ActiveInspection(
                    source="isna",
                    source_id=f"Q1-ACT-{code}-N-{i+1:04d}",
                    region=reg,
                    management="УНА",
                    case_type="Тематическая проверка",
                    prescription_date=report_date - timedelta(days=days_ago),
                    is_counted=True,
                    import_job=import_job,
                    raw_data={"test": True},
                )
            )
            n += 1
        for i in range(long_count):
            days_ago = random.randint(181, 400)
            batch.append(
                ActiveInspection(
                    source="inis",
                    source_id=f"Q1-ACT-{code}-L-{i+1:04d}",
                    region=reg,
                    management="УНА",
                    case_type="Тематическая проверка",
                    prescription_date=report_date - timedelta(days=days_ago),
                    is_counted=True,
                    import_job=import_job,
                    raw_data={"test": True},
                )
            )
            n += 1
    ActiveInspection.objects.bulk_create(batch, ignore_conflicts=True)
    return n


def _load_appeals(parsed, regions, import_job) -> int:
    n = 0
    batch = []
    for code, row in parsed.regions.items():
        reg = regions.get(code)
        if not reg:
            continue
        cancelled_mln = row.cancelled_mln
        if cancelled_mln is None:
            continue
        cancelled_tg = int(cancelled_mln * 1_000_000)
        if cancelled_tg == 0:
            batch.append(
                AppealDecision(
                    source_id=f"Q1-APP-{code}-0001",
                    region=reg,
                    amount_cancelled=0,
                    is_counted=True,
                    completion_date=date(2025, 6, 1),
                    decision_date=date(2026, 3, 1),
                    import_job=import_job,
                    raw_data={"test": True},
                )
            )
            n += 1
            continue
        num = random.randint(1, 3)
        per = cancelled_tg // num
        for i in range(num):
            completion_dt = date(2025, random.randint(1, 12), 1)
            decision_dt = completion_dt + timedelta(days=random.randint(30, 400))
            amt = per if i < num - 1 else (cancelled_tg - per * (num - 1))
            batch.append(
                AppealDecision(
                    source_id=f"Q1-APP-{code}-{i+1:04d}",
                    region=reg,
                    amount_cancelled=amt,
                    is_counted=True,
                    completion_date=completion_dt,
                    decision_date=decision_dt,
                    import_job=import_job,
                    raw_data={"test": True},
                )
            )
            n += 1
    AppealDecision.objects.bulk_create(batch, ignore_conflicts=True)
    return n


# Доля КБК из прошлого тестового набора, если в Excel нет строки по региону
KBK_FALLBACK = {
    "03xx": 1.5307,
    "06xx": 3.0100,
    "09xx": 3.8936,
    "15xx": 5.2504,
    "18xx": 2.5176,
    "21xx": 2.2009,
    "27xx": 2.0262,
    "30xx": 4.4708,
    "33xx": 1.9099,
    "39xx": 1.9255,
    "43xx": 3.0562,
    "45xx": 2.9847,
    "48xx": 0.9801,
    "58xx": 1.5619,
    "59xx": 3.3730,
    "60xx": 37.7631,
    "62xx": 19.0974,
    "70xx": 0.8457,
    "71xx": 1.0092,
    "72xx": 0.5931,
}

# Штат, если лист «Занятость» пустой по региону
KPI4_DEFAULT_STAFF = {
    "03xx": 11,
    "06xx": 18,
    "09xx": 15,
    "15xx": 8,
    "18xx": 20,
    "21xx": 15,
    "27xx": 11,
    "30xx": 22,
    "33xx": 16,
    "39xx": 12,
    "43xx": 13,
    "45xx": 10,
    "48xx": 12,
    "58xx": 13,
    "59xx": 13,
    "60xx": 59,
    "62xx": 36,
    "70xx": 6,
    "71xx": 8,
    "72xx": 8,
}

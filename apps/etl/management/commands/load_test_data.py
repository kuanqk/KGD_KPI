"""
Management command: load_test_data
Загружает тестовые данные на основе реального Excel-файла
Статистика_КЭР_РК_на_01_01_2026.xlsx

Использование:
    python manage.py load_test_data
    python manage.py load_test_data --clear  # очистить перед загрузкой
    python manage.py load_test_data --clear --calculate  # + расчёт сводок для дашборда
"""

from django.core.management.base import BaseCommand
from datetime import date, timedelta
import random

from decimal import Decimal

from apps.regions.models import Region
from apps.etl.models import (
    CompletedInspection, ActiveInspection, AppealDecision, ManualInput, ImportJob
)
from apps.kpi.models import KPIResult, KPIFormula


# ── Реальные данные из Excel Статистика_КЭР_РК_на_01_01_2026.xlsx ──────────

# KPI 1 — Доначисление: план и факт (млн тг)
KPI1_DATA = {
    '03xx': {'plan': 1586.38,  'fact': 1659.84},
    '06xx': {'plan': 3119.47,  'fact': 11448.07},
    '09xx': {'plan': 4035.24,  'fact': 12007.00},
    '15xx': {'plan': 5441.38,  'fact': 6315.99},
    '18xx': {'plan': 2609.17,  'fact': 2538.06},
    '21xx': {'plan': 2280.91,  'fact': 2764.18},
    '27xx': {'plan': 2099.90,  'fact': 2326.88},
    '30xx': {'plan': 4633.39,  'fact': 4695.17},
    '33xx': {'plan': 1979.31,  'fact': 4541.96},
    '39xx': {'plan': 1995.53,  'fact': 2093.63},
    '43xx': {'plan': 3167.33,  'fact': 4907.96},
    '45xx': {'plan': 3093.22,  'fact': 4518.60},
    '48xx': {'plan': 1015.75,  'fact': 1116.02},
    '58xx': {'plan': 1618.69,  'fact': 7752.95},
    '59xx': {'plan': 3495.67,  'fact': 7812.37},
    '60xx': {'plan': 39136.46, 'fact': 39277.38},
    '62xx': {'plan': 19791.96, 'fact': 23269.38},
    '70xx': {'plan': 876.44,   'fact': 3866.58},
    '71xx': {'plan': 1045.90,  'fact': 2720.64},
    '72xx': {'plan': 614.69,   'fact': 830.56},
}

# KPI 2 — Взыскание: план и факт (млн тг)
KPI2_DATA = {
    '03xx': {'plan': 799.37,   'fact': 789.07},
    '06xx': {'plan': 1571.88,  'fact': 1837.30},
    '09xx': {'plan': 2033.33,  'fact': 2999.96},
    '15xx': {'plan': 2741.88,  'fact': 3303.74},
    '18xx': {'plan': 1314.74,  'fact': 1737.91},
    '21xx': {'plan': 1149.34,  'fact': 2619.54},
    '27xx': {'plan': 1058.13,  'fact': 1279.95},
    '30xx': {'plan': 2334.74,  'fact': 2804.04},
    '33xx': {'plan': 997.36,   'fact': 2471.08},
    '39xx': {'plan': 1005.53,  'fact': 1106.13},
    '43xx': {'plan': 1596.00,  'fact': 2262.26},
    '45xx': {'plan': 1558.65,  'fact': 1354.14},
    '48xx': {'plan': 511.83,   'fact': 669.60},
    '58xx': {'plan': 815.65,   'fact': 903.24},
    '59xx': {'plan': 1761.45,  'fact': 2050.26},
    '60xx': {'plan': 19720.62, 'fact': 17830.63},
    '62xx': {'plan': 9973.05,  'fact': 9013.72},
    '70xx': {'plan': 441.63,   'fact': 496.49},
    '71xx': {'plan': 527.02,   'fact': 765.33},
    '72xx': {'plan': 309.74,   'fact': 483.92},
}

# KPI 3 — Среднее доначисление: кол-во проверок и сумма (млн тг, без ДФНО)
KPI3_DATA = {
    '03xx': {'count': 50,  'amount': 1459.40},
    '06xx': {'count': 93,  'amount': 11380.09},
    '09xx': {'count': 100, 'amount': 11241.54},
    '15xx': {'count': 96,  'amount': 4793.15},
    '18xx': {'count': 50,  'amount': 2538.06},
    '21xx': {'count': 38,  'amount': 2764.18},
    '27xx': {'count': 77,  'amount': 1897.73},
    '30xx': {'count': 150, 'amount': 3725.82},
    '33xx': {'count': 85,  'amount': 4377.49},
    '39xx': {'count': 80,  'amount': 2093.63},
    '43xx': {'count': 114, 'amount': 4938.50},
    '45xx': {'count': 63,  'amount': 4407.44},
    '48xx': {'count': 40,  'amount': 1005.47},
    '58xx': {'count': 66,  'amount': 7792.71},
    '59xx': {'count': 85,  'amount': 7944.76},
    '60xx': {'count': 617, 'amount': 36934.21},
    '62xx': {'count': 360, 'amount': 18868.84},
    '70xx': {'count': 37,  'amount': 3860.36},
    '71xx': {'count': 38,  'amount': 2857.98},
    '72xx': {'count': 14,  'amount': 830.56},
}

# KPI 4 — Занятость: кол-во сотрудников
KPI4_STAFF = {
    '03xx': 11, '06xx': 18, '09xx': 15, '15xx': 8,  '18xx': 20,
    '21xx': 15, '27xx': 11, '30xx': 22, '33xx': 16, '39xx': 12,
    '43xx': 13, '45xx': 10, '48xx': 12, '58xx': 13, '59xx': 13,
    '60xx': 59, '62xx': 36, '70xx': 6,  '71xx': 8,  '72xx': 8,
}

# KPI 5 — Проводимые: всего и долгих (>180 дней)
KPI5_DATA = {
    '03xx': {'total': 9,   'long': 0},
    '06xx': {'total': 24,  'long': 2},
    '09xx': {'total': 14,  'long': 1},
    '15xx': {'total': 21,  'long': 0},
    '18xx': {'total': 10,  'long': 0},
    '21xx': {'total': 6,   'long': 0},
    '27xx': {'total': 9,   'long': 1},
    '30xx': {'total': 50,  'long': 4},
    '33xx': {'total': 22,  'long': 0},
    '39xx': {'total': 8,   'long': 1},
    '43xx': {'total': 14,  'long': 2},
    '45xx': {'total': 12,  'long': 0},
    '48xx': {'total': 6,   'long': 0},
    '58xx': {'total': 17,  'long': 0},
    '59xx': {'total': 26,  'long': 5},
    '60xx': {'total': 156, 'long': 7},
    '62xx': {'total': 54,  'long': 5},
    '70xx': {'total': 6,   'long': 2},
    '71xx': {'total': 5,   'long': 0},
    '72xx': {'total': 2,   'long': 0},
}

# KPI 6 — Отмененные суммы (тыс тг → конвертируем в тг для BigIntegerField)
KPI6_DATA = {
    '03xx': {'assessed': 1659.84, 'cancelled': 152.81},
    '06xx': {'assessed': 11448.07, 'cancelled': 0},
    '09xx': {'assessed': 12007.00, 'cancelled': 19.27},
    '15xx': {'assessed': 6315.99, 'cancelled': 0},
    '18xx': {'assessed': 2538.06, 'cancelled': 0.06},
    '21xx': {'assessed': 2764.18, 'cancelled': 0},
    '27xx': {'assessed': 2326.88, 'cancelled': 24.59},
    '30xx': {'assessed': 4695.17, 'cancelled': 0},
    '33xx': {'assessed': 4541.96, 'cancelled': 0},
    '39xx': {'assessed': 2093.63, 'cancelled': 57.28},
    '43xx': {'assessed': 4907.96, 'cancelled': 72.88},
    '45xx': {'assessed': 4518.60, 'cancelled': 292.04},
    '48xx': {'assessed': 1116.02, 'cancelled': 0},
    '58xx': {'assessed': 7752.95, 'cancelled': 34.05},
    '59xx': {'assessed': 7812.37, 'cancelled': 129.28},
    '60xx': {'assessed': 39277.38, 'cancelled': 25.80},
    '62xx': {'assessed': 23269.38, 'cancelled': 85.23},
    '70xx': {'assessed': 3866.58, 'cancelled': 23.94},
    '71xx': {'assessed': 2720.64, 'cancelled': 76.43},
    '72xx': {'assessed': 830.56,  'cancelled': 0},
}

PREV_YEAR_ASSESSED = {
    '03xx': 3006.967928,   '06xx': 2190.963571,   '09xx': 2676.011897,
    '15xx': 3955.44487133, '18xx': 2364.20836475,  '21xx': 1983.00823866,
    '27xx': 1813.227539,   '30xx': 5929.786161919998, '33xx': 2332.9595042900005,
    '39xx': 1596.83022723, '43xx': 4238.92128565,  '45xx': 2911.8495821799993,
    '48xx': 2185.8098180499996, '58xx': 2702.019207360001, '59xx': 7837.666042839999,
    '60xx': 24801.47262629, '62xx': 11065.043190709996, '70xx': 1842.61529008,
    '71xx': 631.04461513,  '72xx': 298.13341255,
}

PREV_YEAR_COLLECTED = {
    '03xx': 531.480025,    '06xx': 2317.36745,    '09xx': 924.9639531700001,
    '15xx': 1825.00009233, '18xx': 1319.1521292900006, '21xx': 1009.35742768,
    '27xx': 796.4463183400001, '30xx': 1993.16156383, '33xx': 1374.1329595900004,
    '39xx': 666.4967650699999, '43xx': 1705.21291926, '45xx': 997.08504663,
    '48xx': 1039.6937494,  '58xx': 1472.9639424000004, '59xx': 5179.624376400002,
    '60xx': 17031.01556737001, '62xx': 1837.5531358399999, '70xx': 813.231139,
    '71xx': 659.28480699,  '72xx': 25.066308,
}

# Доли по 4 КБК (из Excel, столбец D листа Доначисление)
KBK_SHARES = {
    '03xx': 1.5307, '06xx': 3.0100, '09xx': 3.8936, '15xx': 5.2504,
    '18xx': 2.5176, '21xx': 2.2009, '27xx': 2.0262, '30xx': 4.4708,
    '33xx': 1.9099, '39xx': 1.9255, '43xx': 3.0562, '45xx': 2.9847,
    '48xx': 0.9801, '58xx': 1.5619, '59xx': 3.3730, '60xx': 37.7631,
    '62xx': 19.0974, '70xx': 0.8457, '71xx': 1.0092, '72xx': 0.5931,
}


class Command(BaseCommand):
    help = 'Загружает тестовые данные из Excel Статистика_КЭР_РК_на_01_01_2026.xlsx'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие тестовые данные перед загрузкой',
        )
        parser.add_argument(
            '--calculate',
            action='store_true',
            help='После загрузки выполнить расчёт KPI (KPISummary для дашборда)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Очищаем тестовые данные...')
            CompletedInspection.objects.all().delete()
            ActiveInspection.objects.all().delete()
            AppealDecision.objects.all().delete()
            ManualInput.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Очищено.'))

        regions = {r.code: r for r in Region.objects.filter(is_summary=False)}

        if not regions:
            self.stdout.write(self.style.ERROR(
                'Регионы не найдены. Сначала запустите: python manage.py loaddata apps/regions/fixtures/regions.json'
            ))
            return

        report_date = date(2026, 1, 1)
        year_start = date(2025, 1, 1)

        import_job, _ = ImportJob.objects.get_or_create(
            source='inis',
            status='done',
            defaults={
                'records_total': 5000,
                'records_imported': 5000,
                'params': {'test': True},
            }
        )

        # ── ManualInput: доли КБК и штат ────────────────────────────────────
        self.stdout.write('Загружаем ManualInput (доли КБК и штат)...')
        for code, share in KBK_SHARES.items():
            region = regions.get(code)
            if not region:
                continue
            ManualInput.objects.update_or_create(
                region=region,
                year=2025,
                defaults={
                    'kbk_share_pct': share,
                    'staff_count': KPI4_STAFF.get(code, 10),
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  ✓ ManualInput: {len(KBK_SHARES)} записей'))

        # ── CompletedInspection: завершённые проверки ────────────────────────
        self.stdout.write('Загружаем CompletedInspection...')
        completed_count = 0

        for code, kpi3 in KPI3_DATA.items():
            region = regions.get(code)
            if not region:
                continue

            count = kpi3['count']
            total_amount_tg = int(kpi3['amount'] * 1_000_000)  # млн → тг
            total_collected_tg = int(KPI2_DATA[code]['fact'] * 1_000_000)

            # Распределяем суммы равномерно по проверкам
            per_check_assessed = total_amount_tg // count if count else 0
            per_check_collected = total_collected_tg // count if count else 0

            inspections = []
            for i in range(count):
                # Дата завершения — равномерно по 2025 году
                days_offset = int((i / count) * 365)
                completed_dt = year_start + timedelta(days=days_offset)

                inspections.append(CompletedInspection(
                    source='isna' if completed_dt >= date(2025, 7, 9) else 'inis',
                    source_id=f'TEST-{code}-{i+1:04d}',
                    region=region,
                    management='УНА',
                    form_type='Тематическая проверка',
                    completed_date=completed_dt,
                    amount_assessed=per_check_assessed,
                    amount_collected=per_check_collected,
                    is_counted=True,
                    is_accepted=True,
                    is_anomaly=False,
                    import_job=import_job,
                    raw_data={'test': True, 'source': 'excel_2026_01_01'},
                ))
                completed_count += 1

            CompletedInspection.objects.bulk_create(
                inspections, ignore_conflicts=True
            )

        self.stdout.write(self.style.SUCCESS(f'  ✓ CompletedInspection: {completed_count} записей'))

        # ── CompletedInspection: прошлогодние данные 2024 (нужны для расчёта плана KPI 1,2) ──
        self.stdout.write('Загружаем данные за 2024 год (для расчёта плана)...')
        prev_year_start = date(2024, 1, 1)
        prev_batch = []
        prev_count = 0

        for code, amount_mln in PREV_YEAR_ASSESSED.items():
            region = regions.get(code)
            if not region:
                continue
            collected_mln = PREV_YEAR_COLLECTED.get(code, 0)
            count = KPI3_DATA.get(code, {}).get('count', 50)
            amount_tg = int(amount_mln * 1_000_000)
            collected_tg = int(collected_mln * 1_000_000)
            per_assessed = amount_tg // count
            per_collected = collected_tg // count

            for i in range(count):
                days_offset = int((i / count) * 365)
                completed_dt = prev_year_start + timedelta(days=days_offset)
                prev_batch.append(CompletedInspection(
                    source='inis',
                    source_id=f'PREV-{code}-{i+1:04d}',
                    import_job=import_job,
                    region=region,
                    management='УНА',
                    form_type='Тематическая проверка',
                    completed_date=completed_dt,
                    amount_assessed=per_assessed,
                    amount_collected=per_collected,
                    is_counted=True,
                    is_accepted=True,
                    is_anomaly=False,
                    raw_data={'test': True, 'year': 2024},
                ))
                prev_count += 1

        CompletedInspection.objects.bulk_create(prev_batch, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Данные 2024: {prev_count} записей'))

        # ── ActiveInspection: проводимые проверки ───────────────────────────
        self.stdout.write('Загружаем ActiveInspection...')
        active_count = 0
        active_batch = []

        for code, kpi5 in KPI5_DATA.items():
            region = regions.get(code)
            if not region:
                continue

            total = kpi5['total']
            long_count = kpi5['long']
            normal_count = total - long_count

            # Нормальные проверки (< 180 дней)
            for i in range(normal_count):
                days_ago = random.randint(30, 170)
                prescription_dt = report_date - timedelta(days=days_ago)
                active_batch.append(ActiveInspection(
                    source='isna',
                    source_id=f'ACT-{code}-N-{i+1:04d}',
                    region=region,
                    management='УНА',
                    case_type='Тематическая проверка',
                    prescription_date=prescription_dt,
                    is_counted=True,
                    import_job=import_job,
                    raw_data={'test': True},
                ))
                active_count += 1

            # Долгие проверки (> 180 дней)
            for i in range(long_count):
                days_ago = random.randint(181, 400)
                prescription_dt = report_date - timedelta(days=days_ago)
                active_batch.append(ActiveInspection(
                    source='inis',
                    source_id=f'ACT-{code}-L-{i+1:04d}',
                    region=region,
                    management='УНА',
                    case_type='Тематическая проверка',
                    prescription_date=prescription_dt,
                    is_counted=True,
                    import_job=import_job,
                    raw_data={'test': True},
                ))
                active_count += 1

        ActiveInspection.objects.bulk_create(active_batch, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f'  ✓ ActiveInspection: {active_count} записей'))

        # ── AppealDecision: отменённые акты ─────────────────────────────────
        self.stdout.write('Загружаем AppealDecision...')
        appeal_count = 0
        appeal_batch = []

        for code, kpi6 in KPI6_DATA.items():
            region = regions.get(code)
            if not region:
                continue

            cancelled_tg = int(kpi6['cancelled'] * 1_000_000)
            if cancelled_tg == 0:
                # Создаём одну запись с нулевой суммой (регион без отмен)
                appeal_batch.append(AppealDecision(
                    source_id=f'APP-{code}-0001',
                    region=region,
                    amount_cancelled=0,
                    is_counted=True,
                    completion_date=date(2024, 6, 1),
                    decision_date=date(2025, 6, 1),
                    import_job=import_job,
                    raw_data={'test': True},
                ))
                appeal_count += 1
                continue

            # Разбиваем на 1-3 решения
            num_decisions = random.randint(1, 3)
            per_decision = cancelled_tg // num_decisions

            for i in range(num_decisions):
                completion_dt = date(2024, random.randint(1, 12), 1)
                # Решение в пределах 2 лет от завершения
                decision_dt = completion_dt + timedelta(days=random.randint(30, 600))

                amount = per_decision if i < num_decisions - 1 else (
                    cancelled_tg - per_decision * (num_decisions - 1)
                )

                appeal_batch.append(AppealDecision(
                    source_id=f'APP-{code}-{i+1:04d}',
                    region=region,
                    amount_cancelled=amount,
                    is_counted=True,
                    completion_date=completion_dt,
                    decision_date=decision_dt,
                    import_job=import_job,
                    raw_data={'test': True},
                ))
                appeal_count += 1

        AppealDecision.objects.bulk_create(appeal_batch, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f'  ✓ AppealDecision: {appeal_count} записей'))

        # ── KPIResult за 2024 год (нужны Engine для расчёта плана) ─────────
        self.stdout.write('Создаём KPIResult за 2024 год (база для плана)...')
        formula_assessment = KPIFormula.get_active('assessment')
        formula_collection = KPIFormula.get_active('collection')
        d_from = date(2024, 1, 1)
        d_to = date(2024, 12, 31)

        for code, fact_mln in PREV_YEAR_ASSESSED.items():
            region = regions.get(code)
            if not region:
                continue
            fact = Decimal(str(fact_mln)) * 1_000_000
            KPIResult.objects.update_or_create(
                region=region, kpi_type='assessment',
                date_from=d_from, date_to=d_to, formula=formula_assessment,
                defaults={'plan': fact, 'fact': fact, 'percent': Decimal('100'),
                          'score': 10, 'status': 'approved'}
            )

        for code, fact_mln in PREV_YEAR_COLLECTED.items():
            region = regions.get(code)
            if not region:
                continue
            fact = Decimal(str(fact_mln)) * 1_000_000
            KPIResult.objects.update_or_create(
                region=region, kpi_type='collection',
                date_from=d_from, date_to=d_to, formula=formula_collection,
                defaults={'plan': fact, 'fact': fact, 'percent': Decimal('100'),
                          'score': 40, 'status': 'approved'}
            )

        self.stdout.write(self.style.SUCCESS('  ✓ KPIResult 2024: 40 записей (20 assessment + 20 collection)'))

        # ── Итог ────────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Тестовые данные загружены успешно!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write('Данные соответствуют Excel: Статистика_КЭР_РК_на_01_01_2026.xlsx')
        self.stdout.write('Период: 01.01.2025 — 01.01.2026')
        self.stdout.write('')
        self.stdout.write('Следующий шаг — запустить расчёт KPI:')
        self.stdout.write('  python manage.py shell')
        self.stdout.write('  >>> from apps.kpi.services.engine import KPIEngine')
        self.stdout.write('  >>> from datetime import date')
        self.stdout.write('  >>> engine = KPIEngine(date(2025,1,1), date(2026,1,1), user=None)')
        self.stdout.write('  >>> results = engine.calculate_all()')
        self.stdout.write('')
        self.stdout.write('Эталон дашборда (скрин old/260423/correct2025.png) после apply:')
        self.stdout.write('  🥇 Место 1: Алматинская, Атырауская (100) — см. apply_excel_kpi_2025 --snapshot dashboard_2025_260423')
        self.stdout.write('Сверка расхождений по K1…K6: old/260423/KPI ошибки 2025/2026.docx')
        self.stdout.write('  python manage.py apply_excel_kpi_2025 --snapshot dashboard_2025_260423')
        self.stdout.write('  python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423')

        if options.get('calculate'):
            self.stdout.write('')
            self.stdout.write('Запуск расчёта KPI (01.01.2025 — 01.01.2026)…')
            from apps.kpi.services.engine import KPIEngine
            engine = KPIEngine(date(2025, 1, 1), date(2026, 1, 1), user=None)
            summaries = engine.calculate_all()
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Сводки KPISummary: {len(summaries)} (дашборд /api/v1/kpi/summary/)')
            )

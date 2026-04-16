"""
Management command: python manage.py init_formulas

Создаёт начальные версии KPIFormula (v1) для всех 6 KPI
с порогами баллов из claude.md.

Идемпотентна: повторный запуск не дублирует записи.
"""
from django.core.management.base import BaseCommand

from apps.kpi.models import KPIFormula

# ---------------------------------------------------------------------------
# Конфигурация порогов из claude.md
#
# Формат config для каждого KPI:
#   thresholds — список правил, применяются сверху вниз (первое совпадение wins).
#   Для KPI 1/2/3: сравнение percent (Факт/План * 100).
#   Для KPI 4:      сравнение coefficient (Проверок / Сотрудников / Месяцев).
#   Для KPI 5:      сравнение share_pct (Долгие / Все * 100).
#   Для KPI 6:      сравнение share_pct (Отменено / Доначислено * 100).
# ---------------------------------------------------------------------------

INITIAL_FORMULAS = [
    {
        'kpi_type': 'assessment',
        'notes': 'KPI 1 — Доначисление. Макс. 10 баллов.',
        'config': {
            'max_score': 10,
            'metric': 'percent',          # Факт / KPI_план * 100
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 10},
                {'condition': 'gte', 'value': 90,  'score': 5},
                {'condition': 'lt',  'value': 90,  'score': 0},
            ],
            'plan_formula': 'kbk_share_pct / 100 * prev_year_total_plan * 1.20',
        },
    },
    {
        'kpi_type': 'collection',
        'notes': 'KPI 2 — Взыскание. Макс. 40 баллов.',
        'config': {
            'max_score': 40,
            'metric': 'percent',          # Факт / KPI_план * 100
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 40},
                {'condition': 'gte', 'value': 90,  'score': 20},
                {'condition': 'gte', 'value': 80,  'score': 10},
                {'condition': 'lt',  'value': 80,  'score': 0},
            ],
            'plan_formula': 'kbk_share_pct / 100 * prev_year_total_plan_collection * 1.20',
        },
    },
    {
        'kpi_type': 'avg_assessment',
        'notes': (
            'KPI 3 — Среднее доначисление на 1 проверку. Макс. 10 баллов. '
            'Важно: диапазон 80–89% даёт 0 (не 5). Набор проверок = как KPI 1 (Олжас 2026).'
        ),
        'config': {
            'max_score': 10,
            'metric': 'percent',          # Среднее_факт / KPI_план * 100
            'thresholds': [
                {'condition': 'gte', 'value': 100, 'score': 10},
                {'condition': 'gte', 'value': 90,  'score': 5},
                {'condition': 'lt',  'value': 90,  'score': 0},   # 80–89% тоже 0!
            ],
            'plan_formula': 'avg_all_dgd_prev_year * 1.20',       # единый порог
        },
    },
    {
        'kpi_type': 'workload',
        'notes': 'KPI 4 — Коэффициент занятости. Макс. 15 баллов.',
        'config': {
            'max_score': 15,
            'metric': 'coefficient',      # Проверок / Сотрудников / Месяцев
            'thresholds': [
                {'condition': 'gte', 'value': 0.5, 'score': 15},
                {'condition': 'gte', 'value': 0.4, 'score': 5},
                {'condition': 'lt',  'value': 0.4, 'score': 0},
            ],
        },
    },
    {
        'kpi_type': 'long_inspections',
        'notes': (
            'KPI 5 — Доля проверок > 6 месяцев. Макс. 10 баллов. '
            'Исключить: уголовные дела, запросы правоохранительных органов.'
        ),
        'config': {
            'max_score': 10,
            'metric': 'share_pct',        # Долгие / Все * 100
            'long_threshold_days': 180,
            'thresholds': [
                {'condition': 'lt',  'value': 20, 'score': 10},
                {'condition': 'gte', 'value': 20, 'score': 0},
            ],
            'exclude_case_types': ['уголовное дело', 'правоохранительные органы'],
        },
    },
    {
        'kpi_type': 'cancelled',
        'notes': (
            'KPI 6 — Удельный вес отменённых сумм. Макс. 15 баллов. '
            'Числитель: отменённые (is_counted); знаменатель: факт KPI 1. Без исключения по сроку до АК (Олжас 2026).'
        ),
        'config': {
            'max_score': 15,
            'metric': 'share_pct',        # Отменено / Доначислено * 100
            'thresholds': [
                {'condition': 'lte', 'value': 1, 'score': 15},
                {'condition': 'lte', 'value': 2, 'score': 5},
                {'condition': 'gt',  'value': 2, 'score': 0},
            ],
            'management_filter': 'УНА',
        },
    },
]


class Command(BaseCommand):
    help = 'Создаёт начальные версии формул KPI (v1) для всех 6 KPI.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перезаписать существующие v1 формулы (деактивирует старые, создаёт новые).',
        )

    def handle(self, *args, **options):
        force = options['force']
        created_count = 0
        skipped_count = 0

        for spec in INITIAL_FORMULAS:
            kpi_type = spec['kpi_type']
            exists = KPIFormula.objects.filter(kpi_type=kpi_type, version=1).exists()

            if exists and not force:
                self.stdout.write(
                    self.style.WARNING(f'  Пропущено: {kpi_type} v1 уже существует.')
                )
                skipped_count += 1
                continue

            if exists and force:
                KPIFormula.objects.filter(kpi_type=kpi_type, version=1).delete()
                self.stdout.write(f'  Удалена старая запись: {kpi_type} v1')

            formula = KPIFormula.objects.create(
                kpi_type=kpi_type,
                version=1,
                config=spec['config'],
                is_active=True,
                notes=spec['notes'],
            )
            self.stdout.write(
                self.style.SUCCESS(f'  Создана: {formula}')
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nГотово: создано {created_count}, пропущено {skipped_count}.'
            )
        )

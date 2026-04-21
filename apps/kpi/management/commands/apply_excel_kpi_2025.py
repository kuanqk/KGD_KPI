"""
Проставляет баллы KPISummary из эталона Excel «Статистика КЭР РК на 01.01.2026», лист KPI,
для периода 01.01.2025 — 01.01.2026 и пересчитывает ранги.

Использование:
  python manage.py apply_excel_kpi_2025

Нужно, когда расчёт движка от тестовых сырых данных расходится с официальной таблицей КГД,
а цель — показать на дашборде те же баллы, что в Excel.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.kpi.models import KPISummary
from apps.kpi.reference_excel_20250101 import (
    EXCEL_KGD_SCORES_2025,
    EXCEL_KPI_SCORES_2025,
    tuple_total,
)
from apps.regions.models import Region


def _assign_ranks(summaries: list[KPISummary]) -> None:
    rankable = [s for s in summaries if not s.region.is_summary]
    rankable.sort(key=lambda s: -s.score_total)
    current_rank = 1
    for i, summary in enumerate(rankable):
        if i > 0 and rankable[i].score_total < rankable[i - 1].score_total:
            current_rank = i + 1
        summary.rank = current_rank
        summary.save(update_fields=['rank'])


class Command(BaseCommand):
    help = (
        'Записывает баллы KPI из эталона Excel (01.01.2026, лист KPI) '
        'за период 2025-01-01 — 2026-01-01 и назначает ранги.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        d0 = date(2025, 1, 1)
        d1 = date(2026, 1, 1)

        updated = 0
        summaries: list[KPISummary] = []

        for code, scores in EXCEL_KPI_SCORES_2025.items():
            region = Region.objects.filter(code=code, is_summary=False).first()
            if not region:
                self.stdout.write(self.style.WARNING(f'Пропуск неизвестного кода: {code}'))
                continue
            total = tuple_total(scores)
            s, _ = KPISummary.objects.update_or_create(
                region=region,
                date_from=d0,
                date_to=d1,
                defaults={
                    'score_assessment': scores[0],
                    'score_collection': scores[1],
                    'score_avg_assessment': scores[2],
                    'score_workload': scores[3],
                    'score_long_inspections': scores[4],
                    'score_cancelled': scores[5],
                    'score_total': total,
                    'rank': None,
                    'status': 'approved',
                },
            )
            summaries.append(s)
            updated += 1

        kgd = Region.objects.filter(code='00xx', is_summary=True).first()
        if kgd:
            g = EXCEL_KGD_SCORES_2025
            t = tuple_total(g)
            s, _ = KPISummary.objects.update_or_create(
                region=kgd,
                date_from=d0,
                date_to=d1,
                defaults={
                    'score_assessment': g[0],
                    'score_collection': g[1],
                    'score_avg_assessment': g[2],
                    'score_workload': g[3],
                    'score_long_inspections': g[4],
                    'score_cancelled': g[5],
                    'score_total': t,
                    'rank': None,
                    'status': 'approved',
                },
            )
            summaries.append(s)
            updated += 1

        _assign_ranks(summaries)

        self.stdout.write(self.style.SUCCESS(f'Готово: обновлено {updated} сводок KPISummary; ранги пересчитаны.'))

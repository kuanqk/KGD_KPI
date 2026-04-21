"""
Проставляет баллы KPISummary из эталонов Excel (лист KPI или KPI-20 ДГД) и пересчитывает ранги.

Примеры:
  python manage.py apply_excel_kpi_2025
  python manage.py apply_excel_kpi_2025 --snapshot kpi20_dgd_20260401

Docker (см. docker-compose, сервис web):
  docker compose exec web python manage.py apply_excel_kpi_2025 --snapshot kpi20_dgd_20260401
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.kpi.models import KPISummary
from apps.kpi.reference_excel_20250101 import (
    EXCEL_KGD_KPI20_20260401,
    EXCEL_KGD_SCORES_2025,
    EXCEL_KPI20_DGD_20260401,
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


SNAPSHOTS = {
    'kpi_20250101': {
        'label': '…01.01.2026, лист KPI',
        'regions': EXCEL_KPI_SCORES_2025,
        'kgd': EXCEL_KGD_SCORES_2025,
        'date_from': date(2025, 1, 1),
        'date_to': date(2026, 1, 1),
    },
    'kpi20_dgd_20260401': {
        'label': '…01.04.2026, вкладка KPI-20 ДГД (баллы на 01.04.2026)',
        'regions': EXCEL_KPI20_DGD_20260401,
        'kgd': EXCEL_KGD_KPI20_20260401,
        'date_from': date(2026, 1, 1),
        'date_to': date(2027, 1, 1),
    },
}


class Command(BaseCommand):
    help = (
        'Записывает баллы KPI из эталона Excel в KPISummary и назначает ранги. '
        'Снимок kpi20_dgd_20260401 соответствует дашборду «2026 (→ 2027)».'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--snapshot',
            choices=list(SNAPSHOTS.keys()),
            default='kpi_20250101',
            help='Эталон: kpi_20250101 (период 2025→2026) или kpi20_dgd_20260401 (2026→2027, лист KPI-20 ДГД)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        name = options['snapshot']
        cfg = SNAPSHOTS[name]
        d0, d1 = cfg['date_from'], cfg['date_to']
        scores_map = cfg['regions']
        kgd_tuple = cfg['kgd']

        self.stdout.write(f'Снимок: {name} — {cfg["label"]}')
        self.stdout.write(f'Период KPISummary: {d0} — {d1}')

        updated = 0
        summaries: list[KPISummary] = []

        for code, scores in scores_map.items():
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
            t = tuple_total(kgd_tuple)
            s, _ = KPISummary.objects.update_or_create(
                region=kgd,
                date_from=d0,
                date_to=d1,
                defaults={
                    'score_assessment': kgd_tuple[0],
                    'score_collection': kgd_tuple[1],
                    'score_avg_assessment': kgd_tuple[2],
                    'score_workload': kgd_tuple[3],
                    'score_long_inspections': kgd_tuple[4],
                    'score_cancelled': kgd_tuple[5],
                    'score_total': t,
                    'rank': None,
                    'status': 'approved',
                },
            )
            summaries.append(s)
            updated += 1

        _assign_ranks(summaries)

        self.stdout.write(
            self.style.SUCCESS(f'Готово: обновлено {updated} сводок KPISummary; ранги пересчитаны.')
        )

"""
Проставляет баллы KPISummary из эталонов (скриншоты / Excel) и пересчитывает ранги.

Эталон **old/260423** (скрины correct2025 / correct2026, Word «KPI ошибки»):
  python manage.py apply_excel_kpi_2025 --snapshot dashboard_2025_260423
  python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423

Docker:
  docker compose exec web python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.kpi.models import KPISummary
from apps.kpi.reference_excel_20250101 import (
    REF_DASHBOARD_2025_260423,
    REF_DASHBOARD_2026_260423,
    REF_KGD_2025_260423,
    REF_KGD_2026_260423,
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


def _cfg(label: str, regions, kgd, d0, d1):
    return {
        'label': label,
        'regions': regions,
        'kgd': kgd,
        'date_from': d0,
        'date_to': d1,
    }


SNAPSHOTS = {
    'dashboard_2025_260423': _cfg(
        'old/260423/correct2025.png — дашборд «2025 (→ 2026)»',
        REF_DASHBOARD_2025_260423,
        REF_KGD_2025_260423,
        date(2025, 1, 1),
        date(2026, 1, 1),
    ),
    'dashboard_2026_260423': _cfg(
        'old/260423/correct2026.png — дашборд «2026 (→ 2027)»',
        REF_DASHBOARD_2026_260423,
        REF_KGD_2026_260423,
        date(2026, 1, 1),
        date(2027, 1, 1),
    ),
}
SNAPSHOTS['kpi_20250101'] = SNAPSHOTS['dashboard_2025_260423']
SNAPSHOTS['kpi20_dgd_20260401'] = SNAPSHOTS['dashboard_2026_260423']


class Command(BaseCommand):
    help = (
        'Записывает баллы KPI из эталона в KPISummary и назначает ранги. '
        'См. old/260423 и apps/kpi/reference_excel_20250101.py.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--snapshot',
            choices=list(SNAPSHOTS.keys()),
            default='dashboard_2025_260423',
            help='Эталон: dashboard_2025_260423 | dashboard_2026_260423 (алиасы: kpi_20250101, kpi20_dgd_20260401)',
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

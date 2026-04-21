"""
Удаляет лишние строки KPISummary с одинаковой тройкой (region, date_from, date_to).

Оставляет запись с наибольшим id (последняя по времени создания). Нужна, если в БД
обошлась уникальность или данные грузили в обход ORM.

Использование:
  python manage.py dedupe_kpi_summary
  python manage.py dedupe_kpi_summary --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.kpi.models import KPISummary


class Command(BaseCommand):
    help = 'Удаляет дубликаты KPISummary по (region, date_from, date_to), оставляет max(id)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, сколько строк удалили бы',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']

        dupes = (
            KPISummary.objects.values('region_id', 'date_from', 'date_to')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
        )

        total_delete = 0
        groups = list(dupes)
        if not groups:
            self.stdout.write(self.style.SUCCESS('Дубликатов не найдено.'))
            return

        self.stdout.write(f'Найдено групп с дубликатами: {len(groups)}')

        with transaction.atomic():
            for g in groups:
                rid, df, dt = g['region_id'], g['date_from'], g['date_to']
                qs = KPISummary.objects.filter(
                    region_id=rid, date_from=df, date_to=dt
                ).order_by('-id')
                keep = qs.first()
                to_delete = qs.exclude(pk=keep.pk)
                n = to_delete.count()
                total_delete += n
                self.stdout.write(
                    f'  region_id={rid} {df}…{dt}: оставляем id={keep.pk}, удаляем {n}'
                )
                if not dry:
                    to_delete.delete()

        if dry:
            self.stdout.write(self.style.WARNING(f'[dry-run] было бы удалено строк: {total_delete}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Удалено дубликатов: {total_delete}'))

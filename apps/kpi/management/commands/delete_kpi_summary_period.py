"""
Удаляет все строки KPISummary за заданный отчётный период (для сброса дублей / перезаливки).

Пример (2026→2027):
  python manage.py delete_kpi_summary_period --date-from 2026-01-01 --date-to 2027-01-01
  python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423

Docker:
  docker compose exec web python manage.py delete_kpi_summary_period --date-from 2026-01-01 --date-to 2027-01-01
"""

from datetime import datetime

from django.core.management.base import BaseCommand

from apps.kpi.models import KPISummary


class Command(BaseCommand):
    help = 'Удаляет KPISummary за период date_from–date_to (все регионы + КГД).'

    def add_arguments(self, parser):
        parser.add_argument('--date-from', required=True, help='YYYY-MM-DD')
        parser.add_argument('--date-to', required=True, help='YYYY-MM-DD')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, сколько строк удалили бы',
        )

    def handle(self, *args, **options):
        d0 = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
        d1 = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
        qs = KPISummary.objects.filter(date_from=d0, date_to=d1)
        n = qs.count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'[dry-run] Удалило бы строк: {n} за {d0} — {d1}'))
            return
        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f'Удалено записей KPISummary: {deleted} (период {d0} — {d1}).')
        )
        self.stdout.write('Далее: python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423')

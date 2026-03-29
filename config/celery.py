import os

from celery import Celery
from celery.schedules import crontab
from decouple import config

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('kgd_kpi')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# Celery Beat — расписание периодических задач
# ---------------------------------------------------------------------------

# Час запуска ежедневного расчёта KPI (UTC).
# Переопределяется через переменную окружения CELERY_BEAT_HOUR.
_beat_hour = config('CELERY_BEAT_HOUR', default=6, cast=int)

app.conf.beat_schedule = {
    # Ежедневный автоматический расчёт KPI в _beat_hour:00 UTC
    'daily-kpi-calculation': {
        'task': 'apps.kpi.tasks.scheduled_kpi_calculation',
        'schedule': crontab(hour=_beat_hour, minute=0),
        'options': {'expires': 3600},   # задача отмирает, если не забрана за 1 час
    },
}

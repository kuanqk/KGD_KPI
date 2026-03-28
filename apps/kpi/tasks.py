import logging
from datetime import date

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from apps.core.models import AuditLog

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def calculate_kpi(
    self,
    date_from: str,
    date_to: str,
    region_ids: list[int] | None = None,
    user_id: int | None = None,
) -> dict:
    """
    Celery-задача: запускает KPIEngine для указанного периода и регионов.

    Аргументы:
        date_from   — начало периода (ISO-строка, например '2025-01-01')
        date_to     — конец периода  (ISO-строка, например '2025-06-30')
        region_ids  — список PK регионов; None → все ДГД (is_summary=False)
        user_id     — PK пользователя-инициатора; None → системный запуск

    Повторные попытки (max_retries=3) с экспоненциальным backoff:
      попытка 1 → 60 сек
      попытка 2 → 120 сек
      попытка 3 → 240 сек

    Возвращает словарь с итогом:
      {'status': 'done', 'summaries': [...pk...], 'regions': [...pk...]}
    """
    # Импорты внутри задачи, чтобы избежать циклических зависимостей при старте Celery
    from apps.core.models import User
    from apps.kpi.services.engine import KPIEngine
    from apps.regions.models import Region

    df = date.fromisoformat(date_from)
    dt = date.fromisoformat(date_to)

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning('calculate_kpi: User #%d not found, running as system', user_id)

    regions = None
    if region_ids is not None:
        regions = list(Region.objects.filter(pk__in=region_ids))
        if len(regions) != len(region_ids):
            found_ids = {r.pk for r in regions}
            missing = [rid for rid in region_ids if rid not in found_ids]
            logger.warning('calculate_kpi: unknown region_ids=%s, skipping', missing)

    try:
        engine = KPIEngine(date_from=df, date_to=dt, user=user)
        summaries = engine.calculate_all(regions=regions)

        result = {
            'status': 'done',
            'date_from': date_from,
            'date_to': date_to,
            'summaries': [s.pk for s in summaries],
            'regions': [s.region_id for s in summaries],
        }
        logger.info(
            'calculate_kpi done: period=%s–%s, %d summaries',
            date_from, date_to, len(summaries),
        )
        return result

    except Exception as exc:
        retry_number = self.request.retries
        max_retries = self.max_retries
        countdown = 60 * (2 ** retry_number)   # экспоненциальный backoff

        logger.warning(
            'calculate_kpi failed (attempt %d/%d): %s',
            retry_number + 1, max_retries + 1, exc,
        )

        try:
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error('calculate_kpi: all retries exhausted. Final error: %s', exc)
            AuditLog.log(
                event='kpi_calc',
                user=user,
                details={
                    'status': 'error',
                    'date_from': date_from,
                    'date_to': date_to,
                    'error': str(exc),
                    'retries': max_retries,
                },
            )
            return {
                'status': 'error',
                'date_from': date_from,
                'date_to': date_to,
                'error': str(exc),
            }

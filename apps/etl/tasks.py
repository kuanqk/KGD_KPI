import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from apps.core.models import AuditLog

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_import_job(self, job_id: int) -> dict:
    """
    Celery-задача: запускает KGDImporter для указанного ImportJob.

    Повторные попытки (max_retries=3) с экспоненциальным backoff:
      попытка 1 → 60 сек
      попытка 2 → 120 сек
      попытка 3 → 240 сек

    Возвращает словарь с итогом для мониторинга:
      {'job_id': ..., 'status': 'done'/'error', 'records_imported': ...}
    """
    # Импорт здесь, чтобы избежать циклических зависимостей при старте Celery
    from apps.etl.models import ImportJob
    from apps.etl.services.importer import KGDImporter

    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        logger.error('run_import_job: ImportJob #%d not found', job_id)
        return {'job_id': job_id, 'status': 'error', 'error': 'ImportJob not found'}

    try:
        importer = KGDImporter(job)
        importer.run()
        return {
            'job_id': job_id,
            'status': 'done',
            'records_imported': job.records_imported,
        }

    except Exception as exc:
        retry_number = self.request.retries
        max_retries = self.max_retries
        countdown = 60 * (2 ** retry_number)   # экспоненциальный backoff

        logger.warning(
            'run_import_job #%d failed (attempt %d/%d): %s',
            job_id, retry_number + 1, max_retries + 1, exc,
        )

        try:
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(
                'run_import_job #%d: all retries exhausted. Final error: %s',
                job_id, exc,
            )
            AuditLog.log(
                event='import',
                details={
                    'job_id': job_id,
                    'status': 'error',
                    'error': str(exc),
                    'retries': max_retries,
                },
            )
            return {'job_id': job_id, 'status': 'error', 'error': str(exc)}

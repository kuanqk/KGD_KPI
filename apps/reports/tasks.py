"""
Celery-задачи для экспорта отчётов.

Используются для фоновой/пакетной генерации файлов.
Для синхронной отдачи файла через HTTP — вызывайте экспортёры напрямую из views.
"""
import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from apps.core.models import AuditLog

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def export_to_xlsx(self, summary_id: int, user_id: int | None = None) -> dict:
    """
    Фоновая генерация XLSX для KPISummary.

    Логирует start/success/error в AuditLog.
    Повторные попытки: max 3, экспоненциальный backoff.
    """
    from apps.core.models import User
    from apps.kpi.models import KPISummary
    from apps.reports.services.xlsx_exporter import XLSXExporter

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning('export_to_xlsx: User #%d not found', user_id)

    AuditLog.log(
        event='export',
        user=user,
        details={'format': 'xlsx', 'summary_id': summary_id, 'status': 'start'},
    )

    try:
        summary = KPISummary.objects.select_related('region').get(pk=summary_id)
        buf = XLSXExporter(summary).generate()
        size = buf.getbuffer().nbytes

        AuditLog.log(
            event='export',
            user=user,
            details={
                'format': 'xlsx',
                'summary_id': summary_id,
                'status': 'success',
                'size_bytes': size,
                'region': str(summary.region),
                'period': f'{summary.date_from} — {summary.date_to}',
            },
        )
        logger.info('export_to_xlsx: summary_id=%d, %d bytes', summary_id, size)
        return {'status': 'success', 'summary_id': summary_id, 'size_bytes': size}

    except Exception as exc:
        retry_number = self.request.retries
        countdown = 30 * (2 ** retry_number)
        logger.warning(
            'export_to_xlsx failed (attempt %d/%d): %s',
            retry_number + 1, self.max_retries + 1, exc,
        )
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error('export_to_xlsx: all retries exhausted. Error: %s', exc)
            AuditLog.log(
                event='export',
                user=user,
                details={
                    'format': 'xlsx',
                    'summary_id': summary_id,
                    'status': 'error',
                    'error': str(exc),
                    'retries': self.max_retries,
                },
            )
            return {'status': 'error', 'summary_id': summary_id, 'error': str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def export_to_pdf(self, summary_id: int, user_id: int | None = None) -> dict:
    """
    Фоновая генерация PDF для KPISummary (WeasyPrint).

    Логирует start/success/error в AuditLog.
    Повторные попытки: max 3, экспоненциальный backoff.
    """
    from apps.core.models import User
    from apps.kpi.models import KPISummary
    from apps.reports.services.pdf_exporter import PDFExporter

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning('export_to_pdf: User #%d not found', user_id)

    AuditLog.log(
        event='export',
        user=user,
        details={'format': 'pdf', 'summary_id': summary_id, 'status': 'start'},
    )

    try:
        summary = KPISummary.objects.select_related('region').get(pk=summary_id)
        buf = PDFExporter(summary).generate()
        size = buf.getbuffer().nbytes

        AuditLog.log(
            event='export',
            user=user,
            details={
                'format': 'pdf',
                'summary_id': summary_id,
                'status': 'success',
                'size_bytes': size,
                'region': str(summary.region),
                'period': f'{summary.date_from} — {summary.date_to}',
            },
        )
        logger.info('export_to_pdf: summary_id=%d, %d bytes', summary_id, size)
        return {'status': 'success', 'summary_id': summary_id, 'size_bytes': size}

    except Exception as exc:
        retry_number = self.request.retries
        countdown = 30 * (2 ** retry_number)
        logger.warning(
            'export_to_pdf failed (attempt %d/%d): %s',
            retry_number + 1, self.max_retries + 1, exc,
        )
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error('export_to_pdf: all retries exhausted. Error: %s', exc)
            AuditLog.log(
                event='export',
                user=user,
                details={
                    'format': 'pdf',
                    'summary_id': summary_id,
                    'status': 'error',
                    'error': str(exc),
                    'retries': self.max_retries,
                },
            )
            return {'status': 'error', 'summary_id': summary_id, 'error': str(exc)}

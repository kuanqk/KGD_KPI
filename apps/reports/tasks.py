"""
Celery-задачи для экспорта отчётов.

Заглушки — реальная генерация файлов реализуется в Спринте 14
(openpyxl для XLSX, WeasyPrint для PDF).
"""
import logging

from celery import shared_task

from apps.core.models import AuditLog

logger = logging.getLogger(__name__)


@shared_task
def export_to_xlsx(summary_id: int, user_id: int | None = None) -> dict:
    """
    Экспорт KPISummary в XLSX.

    Реализация — Спринт 14 (openpyxl).
    Сейчас: логирует событие и возвращает заглушку.
    """
    from apps.core.models import User

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning('export_to_xlsx: User #%d not found', user_id)

    AuditLog.log(
        event='export',
        user=user,
        details={
            'format': 'xlsx',
            'summary_id': summary_id,
            'status': 'stub',
            'note': 'Реализуется в Спринте 14',
        },
    )
    logger.info('export_to_xlsx: summary_id=%d (stub)', summary_id)

    return {
        'status': 'stub',
        'format': 'xlsx',
        'summary_id': summary_id,
    }


@shared_task
def export_to_pdf(summary_id: int, user_id: int | None = None) -> dict:
    """
    Экспорт KPISummary в PDF.

    Реализация — Спринт 14 (WeasyPrint).
    Сейчас: логирует событие и возвращает заглушку.
    """
    from apps.core.models import User

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning('export_to_pdf: User #%d not found', user_id)

    AuditLog.log(
        event='export',
        user=user,
        details={
            'format': 'pdf',
            'summary_id': summary_id,
            'status': 'stub',
            'note': 'Реализуется в Спринте 14',
        },
    )
    logger.info('export_to_pdf: summary_id=%d (stub)', summary_id)

    return {
        'status': 'stub',
        'format': 'pdf',
        'summary_id': summary_id,
    }

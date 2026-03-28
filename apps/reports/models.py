from django.db import models
from django.utils.translation import gettext_lazy as _


class ReportApproval(models.Model):
    """Workflow утверждения/отклонения отчёта KPISummary."""

    ACTIONS = [
        ('submit',  _('Отправлено на утверждение')),
        ('approve', _('Утверждено')),
        ('reject',  _('Возвращено на доработку')),
        ('recalc',  _('Запрос пересчёта')),
    ]

    summary = models.ForeignKey(
        'kpi.KPISummary',
        on_delete=models.CASCADE,
        verbose_name=_('итог KPI'),
        related_name='approvals',
    )
    action = models.CharField(_('действие'), max_length=20, choices=ACTIONS)
    actor = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('автор действия'),
        related_name='report_approvals',
    )
    comment = models.TextField(_('комментарий'), blank=True)
    created_at = models.DateTimeField(_('дата действия'), auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = _('действие по отчёту')
        verbose_name_plural = _('история утверждений')

    def __str__(self):
        return f'{self.get_action_display()} — {self.summary} — {self.actor}'

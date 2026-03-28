from django.db import models
from django.utils.translation import gettext_lazy as _


class KPIFormula(models.Model):
    """Версионированные конфигурации формул KPI."""

    KPI_TYPES = [
        ('assessment',       'KPI 1 — Доначисление'),
        ('collection',       'KPI 2 — Взыскание'),
        ('avg_assessment',   'KPI 3 — Среднее доначисление'),
        ('workload',         'KPI 4 — Занятость'),
        ('long_inspections', 'KPI 5 — Проверки > 6 мес.'),
        ('cancelled',        'KPI 6 — Отменённые суммы'),
    ]

    kpi_type = models.CharField(
        _('тип KPI'), max_length=30, choices=KPI_TYPES,
    )
    version = models.PositiveSmallIntegerField(_('версия'))
    config = models.JSONField(
        _('конфигурация'),
        help_text=_('Пороги баллов и параметры расчёта'),
    )
    is_active = models.BooleanField(_('активна'), default=True)
    created_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('создал'),
        related_name='kpi_formulas',
    )
    created_at = models.DateTimeField(_('создана'), auto_now_add=True)
    notes = models.TextField(_('примечания'), blank=True)

    class Meta:
        unique_together = ('kpi_type', 'version')
        ordering = ['kpi_type', '-version']
        verbose_name = _('формула KPI')
        verbose_name_plural = _('формулы KPI')

    def __str__(self):
        return f'{self.get_kpi_type_display()} v{self.version}'

    @classmethod
    def get_active(cls, kpi_type: str) -> 'KPIFormula':
        """Вернуть актуальную версию формулы для указанного типа KPI."""
        return cls.objects.filter(kpi_type=kpi_type, is_active=True).latest('version')


class KPIResult(models.Model):
    """Результат расчёта одного KPI для одного ДГД за один период."""

    STATUSES = [
        ('draft',     _('Черновик')),
        ('submitted', _('На утверждении')),
        ('approved',  _('Утверждён')),
        ('rejected',  _('Возвращён')),
    ]

    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.PROTECT,
        verbose_name=_('регион'),
        related_name='kpi_results',
    )
    kpi_type = models.CharField(
        _('тип KPI'), max_length=30, choices=KPIFormula.KPI_TYPES,
    )
    formula = models.ForeignKey(
        KPIFormula,
        on_delete=models.PROTECT,
        verbose_name=_('формула'),
        related_name='results',
    )

    # Период
    date_from = models.DateField(_('период с'))
    date_to = models.DateField(_('период по'))

    # Результаты
    plan = models.DecimalField(
        _('план'), max_digits=20, decimal_places=4, null=True, blank=True,
    )
    fact = models.DecimalField(
        _('факт'), max_digits=20, decimal_places=4, null=True, blank=True,
    )
    percent = models.DecimalField(
        _('исполнение (%)'), max_digits=8, decimal_places=4, null=True, blank=True,
    )
    score = models.PositiveSmallIntegerField(_('баллы'), default=0)

    # Детали расчёта — для аудита и отладки
    calc_details = models.JSONField(_('детали расчёта'), default=dict, blank=True)

    status = models.CharField(
        _('статус'), max_length=20, choices=STATUSES, default='draft',
    )
    calculated_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('рассчитал'),
        related_name='calculated_kpis',
    )
    calculated_at = models.DateTimeField(_('дата расчёта'), auto_now_add=True)

    class Meta:
        unique_together = ('region', 'kpi_type', 'date_from', 'date_to', 'formula')
        indexes = [
            models.Index(
                fields=['region', 'date_from', 'date_to'],
                name='kr_region_period_idx',
            ),
            models.Index(
                fields=['status'],
                name='kr_status_idx',
            ),
        ]
        ordering = ['region__order', 'kpi_type']
        verbose_name = _('результат KPI')
        verbose_name_plural = _('результаты KPI')

    def __str__(self):
        return (
            f'{self.region} | {self.get_kpi_type_display()} | '
            f'{self.date_from}–{self.date_to} | {self.score} б.'
        )


class KPISummary(models.Model):
    """Итоговые баллы и рейтинг по всем 6 KPI для ДГД за период."""

    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.PROTECT,
        verbose_name=_('регион'),
        related_name='kpi_summaries',
    )
    date_from = models.DateField(_('период с'))
    date_to = models.DateField(_('период по'))

    # Баллы по каждому KPI
    score_assessment       = models.PositiveSmallIntegerField(_('KPI 1 баллы'), default=0)
    score_collection       = models.PositiveSmallIntegerField(_('KPI 2 баллы'), default=0)
    score_avg_assessment   = models.PositiveSmallIntegerField(_('KPI 3 баллы'), default=0)
    score_workload         = models.PositiveSmallIntegerField(_('KPI 4 баллы'), default=0)
    score_long_inspections = models.PositiveSmallIntegerField(_('KPI 5 баллы'), default=0)
    score_cancelled        = models.PositiveSmallIntegerField(_('KPI 6 баллы'), default=0)
    score_total            = models.PositiveSmallIntegerField(_('итого баллов'), default=0)

    # Позиция в рейтинге (NULL для КГД-итого — is_summary=True)
    rank = models.PositiveSmallIntegerField(_('позиция'), null=True, blank=True)

    status = models.CharField(
        _('статус'), max_length=20, choices=KPIResult.STATUSES, default='draft',
    )
    calculated_at = models.DateTimeField(_('дата расчёта'), auto_now_add=True)

    class Meta:
        unique_together = ('region', 'date_from', 'date_to')
        ordering = ['rank', 'region__order']
        verbose_name = _('итог KPI')
        verbose_name_plural = _('итоги KPI')

    def __str__(self):
        rank_str = f'#{self.rank}' if self.rank else 'КГД'
        return (
            f'{rank_str} {self.region} | '
            f'{self.date_from}–{self.date_to} | {self.score_total}/100'
        )

    def recalculate_total(self):
        """Пересчитать итоговый балл из составляющих."""
        self.score_total = (
            self.score_assessment
            + self.score_collection
            + self.score_avg_assessment
            + self.score_workload
            + self.score_long_inspections
            + self.score_cancelled
        )

from django.db import models
from django.utils.translation import gettext_lazy as _


class ImportJob(models.Model):
    SOURCES = [
        ('inis', 'ИНИС'),
        ('isna', 'ИСНА'),
        ('dgd', 'Данные ДГД'),
        ('appeals', 'Обжалования'),
    ]
    STATUSES = [
        ('pending', _('Ожидание')),
        ('running', _('Выполняется')),
        ('done', _('Завершено')),
        ('error', _('Ошибка')),
    ]

    source = models.CharField(_('источник'), max_length=20, choices=SOURCES)
    status = models.CharField(
        _('статус'), max_length=20, choices=STATUSES, default='pending'
    )
    started_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('запустил'),
        related_name='import_jobs',
    )
    started_at = models.DateTimeField(_('начало'), null=True, blank=True)
    finished_at = models.DateTimeField(_('завершение'), null=True, blank=True)
    records_total = models.IntegerField(_('записей всего'), default=0)
    records_imported = models.IntegerField(_('записей импортировано'), default=0)
    error_message = models.TextField(_('сообщение об ошибке'), blank=True)
    params = models.JSONField(_('параметры'), default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = _('задача импорта')
        verbose_name_plural = _('задачи импорта')

    def __str__(self):
        return f'ImportJob #{self.pk} [{self.get_source_display()}] — {self.get_status_display()}'

    @property
    def is_running(self):
        return self.status == 'running'

    @property
    def is_done(self):
        return self.status == 'done'

    @property
    def has_error(self):
        return self.status == 'error'


class CompletedInspection(models.Model):
    """Нормализованная таблица завершённых проверок (ИНИС + ИСНА)."""

    SOURCES = [('inis', 'ИНИС'), ('isna', 'ИСНА')]

    # Источник
    source = models.CharField(_('источник'), max_length=10, choices=SOURCES)
    source_id = models.CharField(_('ID в источнике'), max_length=100)
    import_job = models.ForeignKey(
        ImportJob,
        on_delete=models.CASCADE,
        verbose_name=_('задача импорта'),
        related_name='completed_inspections',
    )

    # Ключевые поля (условные имена — заменить после получения schema от Олжаса)
    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.PROTECT,
        verbose_name=_('регион'),
        related_name='completed_inspections',
    )
    management = models.CharField(
        _('управление'), max_length=20,
        help_text=_('УНА / УКН / УНН / УДМ / УАКН / ...')
    )
    form_type = models.CharField(
        _('тип проверки'), max_length=50,
        help_text=_('ДФНО / обычная / ...')
    )
    completed_date = models.DateField(_('дата завершения'))

    # Суммы в тенге (целые числа для точности)
    amount_assessed = models.BigIntegerField(_('доначислено (тенге)'), default=0)
    amount_collected = models.BigIntegerField(_('взыскано (тенге)'), default=0)

    # Флаги учёта
    is_counted = models.BooleanField(_('учитывается (KPI 3)'), default=False)
    is_accepted = models.BooleanField(_('принято (KPI 1, 2)'), default=False)
    is_anomaly = models.BooleanField(_('аномалия'), default=False)

    # Метаданные
    raw_data = models.JSONField(_('исходные данные'), default=dict, blank=True)
    created_at = models.DateTimeField(_('создана'), auto_now_add=True)

    class Meta:
        unique_together = ('source', 'source_id')
        indexes = [
            models.Index(
                fields=['region', 'management', 'completed_date'],
                name='ci_region_mgmt_date_idx',
            ),
            models.Index(
                fields=['is_counted', 'is_accepted'],
                name='ci_flags_idx',
            ),
        ]
        verbose_name = _('завершённая проверка')
        verbose_name_plural = _('завершённые проверки')

    def __str__(self):
        return (
            f'[{self.source.upper()}] {self.source_id} | '
            f'{self.region} | {self.completed_date}'
        )


class ActiveInspection(models.Model):
    """Проводимые (текущие) проверки."""

    source = models.CharField(_('источник'), max_length=10)
    source_id = models.CharField(_('ID в источнике'), max_length=100)
    import_job = models.ForeignKey(
        ImportJob,
        on_delete=models.CASCADE,
        verbose_name=_('задача импорта'),
        related_name='active_inspections',
    )

    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.PROTECT,
        verbose_name=_('регион'),
        related_name='active_inspections',
    )
    management = models.CharField(_('управление'), max_length=20)
    case_type = models.CharField(
        _('тип дела'), max_length=50,
        help_text=_('Исключить: уголовные дела, запросы правоохранит. органов')
    )
    prescription_date = models.DateField(_('дата вручения предписания'))
    is_counted = models.BooleanField(_('учитывается'), default=False)

    raw_data = models.JSONField(_('исходные данные'), default=dict, blank=True)

    class Meta:
        unique_together = ('source', 'source_id')
        indexes = [
            models.Index(
                fields=['region', 'prescription_date'],
                name='ai_region_date_idx',
            ),
            models.Index(
                fields=['is_counted'],
                name='ai_counted_idx',
            ),
        ]
        verbose_name = _('проводимая проверка')
        verbose_name_plural = _('проводимые проверки')

    def __str__(self):
        return (
            f'[{self.source.upper()}] {self.source_id} | '
            f'{self.region} | с {self.prescription_date}'
        )


class AppealDecision(models.Model):
    """Отменённые акты (обжалования)."""

    source_id = models.CharField(_('ID в источнике'), max_length=100, unique=True)
    import_job = models.ForeignKey(
        ImportJob,
        on_delete=models.CASCADE,
        verbose_name=_('задача импорта'),
        related_name='appeal_decisions',
    )

    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.PROTECT,
        verbose_name=_('регион'),
        related_name='appeal_decisions',
    )
    amount_cancelled = models.BigIntegerField(_('отменённая сумма (тенге)'), default=0)
    is_counted = models.BooleanField(_('учитывается'), default=False)
    completion_date = models.DateField(_('дата завершения акта'))
    decision_date = models.DateField(_('дата решения Апелляционной комиссии'))

    raw_data = models.JSONField(_('исходные данные'), default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['region', 'decision_date'],
                name='ad_region_decision_idx',
            ),
            models.Index(
                fields=['is_counted'],
                name='ad_counted_idx',
            ),
        ]
        verbose_name = _('решение по обжалованию')
        verbose_name_plural = _('решения по обжалованиям')

    def __str__(self):
        return f'Обжалование {self.source_id} | {self.region} | {self.decision_date}'


class ManualInput(models.Model):
    """Ручные вводы оператора (доля КБК и штат)."""

    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.PROTECT,
        verbose_name=_('регион'),
        related_name='manual_inputs',
    )
    year = models.PositiveSmallIntegerField(_('год'))
    kbk_share_pct = models.DecimalField(
        _('доля по КБК (%)'),
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_('Используется для KPI 1 и KPI 2'),
    )
    staff_count = models.PositiveSmallIntegerField(
        _('кол-во сотрудников'),
        null=True,
        blank=True,
        help_text=_('Используется для KPI 4'),
    )
    entered_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('внёс'),
        related_name='manual_inputs',
    )
    entered_at = models.DateTimeField(_('дата ввода'), auto_now_add=True)
    notes = models.TextField(_('примечания'), blank=True)

    class Meta:
        unique_together = ('region', 'year')
        ordering = ['-year', 'region__order']
        verbose_name = _('ручной ввод')
        verbose_name_plural = _('ручные вводы')

    def __str__(self):
        return f'{self.region} / {self.year}'

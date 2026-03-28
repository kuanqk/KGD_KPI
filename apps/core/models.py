from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    ROLES = [
        ('admin', _('Администратор')),
        ('operator', _('Оператор')),
        ('reviewer', _('Проверяющий')),
        ('viewer', _('Наблюдатель')),
    ]

    role = models.CharField(
        _('роль'),
        max_length=20,
        choices=ROLES,
        default='viewer',
    )
    mac_address = models.CharField(
        _('MAC-адрес'),
        max_length=17,
        blank=True,
        help_text=_('Привязка для аутентификации по MAC-адресу'),
    )
    regions = models.ManyToManyField(
        'regions.Region',
        through='UserRegion',
        blank=True,
        verbose_name=_('регионы'),
        related_name='users',
    )

    class Meta:
        verbose_name = _('пользователь')
        verbose_name_plural = _('пользователи')

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_operator(self):
        return self.role == 'operator'

    @property
    def is_reviewer(self):
        return self.role == 'reviewer'

    @property
    def is_viewer(self):
        return self.role == 'viewer'


class UserRegion(models.Model):
    """Привязка наблюдателей к регионам (RLS)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_('пользователь'),
    )
    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.CASCADE,
        verbose_name=_('регион'),
    )

    class Meta:
        unique_together = ('user', 'region')
        verbose_name = _('привязка пользователя к региону')
        verbose_name_plural = _('привязки пользователей к регионам')

    def __str__(self):
        return f'{self.user} → {self.region}'


class AuditLog(models.Model):
    EVENTS = [
        ('import', _('Импорт данных')),
        ('formula_change', _('Изменение формулы')),
        ('kpi_calc', _('Расчёт KPI')),
        ('login', _('Вход')),
        ('logout', _('Выход')),
        ('export', _('Экспорт')),
        ('manual_input', _('Ручной ввод')),
        ('correction', _('Корректировка')),
        ('user_mgmt', _('Управление учёткой')),
        ('approval', _('Утверждение отчёта')),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('пользователь'),
    )
    event = models.CharField(
        _('событие'),
        max_length=30,
        choices=EVENTS,
    )
    details = models.JSONField(
        _('детали'),
        default=dict,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(
        _('IP-адрес'),
        null=True,
        blank=True,
    )
    mac_address = models.CharField(
        _('MAC-адрес'),
        max_length=17,
        blank=True,
    )
    created_at = models.DateTimeField(
        _('создан'),
        auto_now_add=True,
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('запись аудит-лога')
        verbose_name_plural = _('аудит-лог')

    def __str__(self):
        return f'[{self.created_at:%Y-%m-%d %H:%M}] {self.get_event_display()} — {self.user}'

    @classmethod
    def log(cls, event, user=None, details=None, ip_address=None, mac_address=''):
        """Удобный метод для записи событий из сервисов."""
        return cls.objects.create(
            event=event,
            user=user,
            details=details or {},
            ip_address=ip_address,
            mac_address=mac_address,
        )

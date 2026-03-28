from django.db import models
from django.utils.translation import gettext_lazy as _


class Region(models.Model):
    code = models.CharField(
        _('код'),
        max_length=4,
        unique=True,
        help_text=_('Код ДГД, например: 06xx, 62xx'),
    )
    name_ru = models.CharField(_('название (рус.)'), max_length=100)
    name_kz = models.CharField(_('атауы (қаз.)'), max_length=100)
    name_en = models.CharField(_('name (eng.)'), max_length=100)
    is_summary = models.BooleanField(
        _('сводный'),
        default=False,
        help_text=_('True для КГД (итого по РК) — не участвует в рейтинге'),
    )
    order = models.PositiveSmallIntegerField(_('порядок сортировки'), default=0)

    class Meta:
        ordering = ['order']
        verbose_name = _('регион / ДГД')
        verbose_name_plural = _('регионы / ДГД')

    def __str__(self):
        return self.name_ru

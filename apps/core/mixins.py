from django.db import models


class RegionScopedQuerySet(models.QuerySet):
    """
    QuerySet с поддержкой Row-Level Security по регионам.

    Использование:
        class MyManager(models.Manager):
            def get_queryset(self):
                return RegionScopedQuerySet(self.model, using=self._db)

    Требует наличия поля `region` (ForeignKey на regions.Region) в модели.
    """

    def for_user(self, user):
        if user.role in ('admin', 'operator', 'reviewer'):
            return self
        # viewer — только регионы, к которым привязан
        return self.filter(region__in=user.regions.all())


class RegionScopedMixin:
    """
    Миксин для DRF ViewSet/APIView — автоматически применяет RLS по роли.

    Подключается к View, у которых queryset использует RegionScopedQuerySet.
    """

    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)

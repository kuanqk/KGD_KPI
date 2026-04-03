# apps/core — Пользователи, роли, безопасность

> Минимальный контекст для работы с этим app.
> Модели: [architecture/database.md](../architecture/database.md#appscore)

---

## Что делает этот app

- Кастомная модель `User` с 4 ролями
- RLS (Row-Level Security) для роли `viewer`
- `AuditLog` — логирование всех действий
- `MACAddressMiddleware` — привязка к устройству
- JWT аутентификация + rate limiting

---

## Роли

| Роль | Код | Доступ |
|------|-----|--------|
| Администратор | `admin` | CRUD пользователей, все логи, мониторинг ETL |
| Оператор | `operator` | Импорт, формулы, расчёт, ручной ввод |
| Проверяющий | `reviewer` | Утверждение отчётов |
| Наблюдатель | `viewer` | Только чтение, только свои регионы |

---

## RLS — RegionScopedQuerySet

```python
# core/mixins.py
class RegionScopedQuerySet(models.QuerySet):
    def for_user(self, user):
        if user.role in ('admin', 'operator', 'reviewer'):
            return self          # видят всё
        return self.filter(region__in=user.regions.all())  # viewer — только свои

class RegionScopedMixin:
    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)
```

**Применяется во всех ViewSet** где есть поле `region`:
- `KPIResultViewSet`
- `KPISummaryViewSet`
- `PendingReportsView`

---

## AuditLog

Логировать через метод `AuditLog.log()`:

```python
AuditLog.log(
    user=request.user,
    event='kpi_calc',        # тип события
    details={'period': '...', 'regions': [...]},
    request=request          # IP и MAC берутся автоматически
)
```

**Типы событий:** `import`, `formula_change`, `kpi_calc`, `login`, `logout`, `export`, `manual_input`, `correction`, `user_mgmt`, `approval`

---

## MACAddressMiddleware

- Перехватывает только `POST /api/v1/auth/login/`
- Читает `X-MAC-Address` из заголовка
- Если `User.mac_address` пустой → пропускает (не блокирует)
- Если не совпадает → 403 + AuditLog

---

## Permissions (DRF)

```python
from apps.core.permissions import IsAdmin, IsOperator, IsReviewer, IsOperatorOrAdmin

class MyView(APIView):
    permission_classes = [IsAuthenticated, IsOperator]
```

---

## Файлы app

```
apps/core/
├── models.py          # User, UserRegion, AuditLog
├── mixins.py          # RegionScopedQuerySet, RegionScopedMixin
├── middleware.py      # MACAddressMiddleware
├── permissions.py     # IsAdmin, IsOperator, IsReviewer, IsViewer, IsOperatorOrAdmin
├── serializers.py     # UserSerializer, AuditLogSerializer
├── views.py           # LoginView, LogoutView, UserViewSet, AuditLogViewSet
├── urls.py            # /api/v1/auth/, /api/v1/admin/users/, /api/v1/admin/audit-logs/
├── admin_urls.py      # Отдельный роутер для admin эндпоинтов
└── admin.py           # Django Admin: UserAdmin (inline UserRegion), AuditLogAdmin
```

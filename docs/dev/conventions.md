# Соглашения по коду

---

## Структура каждого Django app

```
apps/{app_name}/
├── models.py          # Только модели, никакой бизнес-логики
├── serializers.py     # DRF сериализаторы
├── views.py           # Только роутинг и сериализация
├── urls.py
├── permissions.py     # Кастомные DRF permissions (если нужны)
├── filters.py         # django-filter классы
├── services/          # ВСЯ бизнес-логика здесь
│   └── engine.py      # Пример для kpi/
├── tasks.py           # Celery задачи
├── admin.py
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_api.py
└── migrations/
```

---

## Ключевые правила

### Бизнес-логика
- **Только в `services/`** — не в views, не в models, не в tasks
- Views только читают из сервиса и возвращают HTTP ответ
- Tasks только вызывают сервис и логируют результат

### Суммы и деньги
- **Хранить в тенге** — `BigIntegerField`, целые числа
- **Конвертировать в млн** только для отображения: `amount / 1_000_000`
- **Никогда** не использовать `float` для денег

### Логирование
- **Каждый публичный метод сервиса** логировать в `AuditLog`
- Использовать `AuditLog.log(user=..., event=..., details=...)`

### QuerySet
- Всегда использовать `select_related` / `prefetch_related`
- Не допускать N+1 запросов
- Для viewer — всегда через `RegionScopedMixin`

### i18n
- Все строки интерфейса через `django.utils.translation`
- `_('текст')` в Python, `$t('key')` во Vue

---

## Permissions

```python
from apps.core.permissions import (
    IsAdmin, IsOperator, IsReviewer, IsViewer, IsOperatorOrAdmin
)

class MyView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]
```

---

## Celery задачи

```python
@shared_task(bind=True, max_retries=3)
def my_task(self, param):
    try:
        # логика
        AuditLog.log(event='...', details={'status': 'success'})
    except Exception as exc:
        AuditLog.log(event='...', details={'status': 'error', 'error': str(exc)})
        raise self.retry(exc=exc, countdown=60 * 2 ** self.request.retries)
```

---

## Git коммиты

Формат: `Sprint N: короткое описание`

```
Sprint 5: KPI Engine
Sprint 14: PDF + XLSX export
Fix: nginx port conflict
```

Язык коммитов — **английский**.

---

## Переменные окружения

- Не хардкодить credentials в коде
- Все настройки через `.env` + `python-decouple`
- `config('VAR_NAME', default='значение')`

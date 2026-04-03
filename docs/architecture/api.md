# REST API

- Базовый URL: `/api/v1/`
- Аутентификация: JWT (Bearer token)
- Формат: JSON
- Пагинация: cursor-based для больших списков

---

## Аутентификация

```
POST /api/v1/auth/login/          # → access + refresh токены
POST /api/v1/auth/logout/
POST /api/v1/auth/token/refresh/
```

**JWT:** access 15 мин, refresh 7 дней.
**MAC-адрес:** проверяется при логине через `X-MAC-Address` заголовок.
**Rate limiting:** 5 запросов/мин по IP на `/api/v1/auth/login/`.

---

## Регионы

```
GET /api/v1/regions/    # Все 21 регион (20 ДГД + КГД), без пагинации
```
Доступно всем ролям.

---

## ETL / Импорт

```
GET  /api/v1/etl/jobs/             # Список задач импорта
POST /api/v1/etl/jobs/             # Запустить импорт → Celery task
GET  /api/v1/etl/jobs/{id}/        # Статус задачи

GET   /api/v1/etl/inspections/completed/      # Нормализованные данные
PATCH /api/v1/etl/inspections/completed/{id}/ # Флаги: is_counted, is_accepted, is_anomaly

GET /api/v1/etl/manual-inputs/     # Ручные вводы
POST /api/v1/etl/manual-inputs/    # Создать
PUT  /api/v1/etl/manual-inputs/{id}/
```

Доступно: **Оператор**.

---

## KPI

```
GET  /api/v1/kpi/formulas/         # Версии формул
POST /api/v1/kpi/formulas/         # Новая версия (деактивирует предыдущую)
GET  /api/v1/kpi/formulas/{id}/

POST /api/v1/kpi/calculate/        # Запустить расчёт → 202 + task_id
                                   # Body: {date_from, date_to, region_ids}

GET /api/v1/kpi/results/           # Результаты по KPI (RLS для viewer)
GET /api/v1/kpi/results/{id}/

GET /api/v1/kpi/summary/           # Сводный рейтинг (RLS для viewer)
GET /api/v1/kpi/summary/{id}/
```

**Фильтры для results и summary:** `?region=&date_from=&date_to=&kpi_type=&status=`

Доступно: все роли (RLS для viewer). Формулы и расчёт — только **Оператор**.

---

## Отчёты

```
GET  /api/v1/reports/pending/          # Ожидают утверждения (Проверяющий)
POST /api/v1/reports/{id}/approve/     # Утвердить
POST /api/v1/reports/{id}/reject/      # Вернуть (comment обязателен)
POST /api/v1/reports/{id}/recalculate/ # Запросить пересчёт → Celery task

GET /api/v1/reports/{id}/export/xlsx/  # Скачать XLSX
GET /api/v1/reports/{id}/export/pdf/   # Скачать PDF
```

---

## Администрирование

```
GET    /api/v1/admin/users/         # Список пользователей
POST   /api/v1/admin/users/         # Создать
PUT    /api/v1/admin/users/{id}/
PATCH  /api/v1/admin/users/{id}/    # Деактивировать

GET /api/v1/admin/audit-logs/       # Лог (cursor pagination)
                                    # Фильтры: ?event=&user=&created_after=
GET /api/v1/admin/etl-monitor/      # Статус импортов
```

Доступно: **Администратор**.

---

## Права доступа по ролям

| Эндпоинт | admin | operator | reviewer | viewer |
|----------|-------|----------|----------|--------|
| regions | ✅ | ✅ | ✅ | ✅ |
| kpi/summary, results | ✅ | ✅ | ✅ | ✅ (RLS) |
| etl/* | ✅ | ✅ | ❌ | ❌ |
| kpi/calculate, formulas | ✅ | ✅ | ❌ | ❌ |
| reports/pending, approve | ✅ | ❌ | ✅ | ❌ |
| reports/export | ✅ | ✅ | ✅ | ✅ (RLS) |
| admin/* | ✅ | ❌ | ❌ | ❌ |

**RLS (viewer):** видит данные только по своим регионам (`UserRegion`).

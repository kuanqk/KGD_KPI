# Архитектура проекта

## Стек

| Слой | Технология |
|------|-----------|
| Backend | Python 3.12, Django 5.x, Django REST Framework |
| Frontend | Vue 3 (SPA), Pinia, Vue Router, Axios |
| БД | PostgreSQL 16 |
| Очереди | Celery + Redis 7 |
| Карта | Leaflet.js + GeoJSON |
| Графики | Chart.js |
| Экспорт | openpyxl (XLSX), WeasyPrint (PDF) |
| Сборка | Vite |
| Инфраструктура | Docker Compose, Nginx |
| CI/CD | GitHub Actions |

---

## Структура проекта

```
kgd_kpi/
├── config/                  # Django настройки
│   ├── settings/
│   │   ├── base.py          # Общие
│   │   ├── dev.py           # DEBUG=True
│   │   ├── prod.py          # HTTPS, HSTS
│   │   ├── test.py          # SQLite, fast hasher
│   │   └── ci.py            # CI: PostgreSQL, eager Celery
│   ├── urls.py              # /api/v1/
│   ├── celery.py            # Celery app + Beat schedule
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── core/                # User, роли, RLS, AuditLog
│   ├── regions/             # Справочник 20 ДГД
│   ├── etl/                 # Импорт, нормализация
│   ├── kpi/                 # KPI Engine
│   └── reports/             # Утверждение, экспорт
│
├── frontend/                # Vue 3 SPA
│   ├── src/
│   │   ├── views/
│   │   ├── components/
│   │   ├── stores/
│   │   ├── api/
│   │   └── router/
│   ├── Dockerfile
│   └── vite.config.js
│
├── docker/
│   └── nginx.conf
├── templates/
│   └── reports/kpi_report.html
├── docs/                    # Эта документация
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── .github/workflows/ci.yml
```

---

## Инфраструктура Docker Compose

| Сервис | Технология | Порт | Назначение |
|--------|-----------|------|-----------|
| web | Django + Gunicorn | 8000 | Основное приложение |
| frontend | Vue 3 + Nginx | 80 | SPA |
| db | PostgreSQL 16 | 5432 | База данных |
| redis | Redis 7 | 6379 | Брокер очередей |
| worker | Celery | — | Фоновые задачи |
| beat | Celery Beat | — | Расписание |
| nginx | Nginx | 8080→80 | Reverse proxy |

**Routing nginx:**
- `/api/` → `web:8000` (Django)
- `/admin/` → `web:8000` (Django Admin)
- `/static/` → статика Django
- `/` → `frontend:80` (Vue SPA)

---

## Поток данных

```
БД КГД (readonly)
    ↓
ETL (KGDImporter + DataNormalizer)
    ↓
PostgreSQL (CompletedInspection, ActiveInspection, AppealDecision)
    ↓
KPI Engine (calculate_all)
    ↓
KPIResult + KPISummary
    ↓
REST API (DRF)
    ↓
Vue 3 Frontend
```

---

## Настройки по окружению

| Переменная | dev | prod |
|-----------|-----|------|
| `DJANGO_DEBUG` | True | False |
| `DJANGO_ALLOWED_HOSTS` | * | домен КГД |
| `SECURE_SSL_REDIRECT` | False | True |
| `SESSION_COOKIE_SECURE` | False | True |

# Docker и инфраструктура

---

## Сервисы Docker Compose

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| web | kgd_kpi-web (Python 3.12) | 8000 | Django + Gunicorn |
| frontend | kgd_kpi-frontend (Node 20 + Nginx) | 80 | Vue 3 SPA |
| db | postgres:16-alpine | 5432 | PostgreSQL |
| redis | redis:7-alpine | 6379 | Брокер Celery |
| worker | kgd_kpi-worker | — | Celery worker |
| beat | kgd_kpi-beat | — | Celery Beat (расписание) |
| nginx | nginx:alpine | **8080**→80 | Reverse proxy |

---

## Nginx routing

```nginx
/api/    → web:8000    # Django REST API
/admin/  → web:8000    # Django Admin
/static/ → /static/   # Статика Django
/        → frontend:80 # Vue SPA
```

---

## Переменные окружения (.env)

```env
# Django
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL (локальная)
POSTGRES_DB=kgd_kpi
POSTGRES_USER=kgd_user
POSTGRES_PASSWORD=
DB_HOST=db
DB_PORT=5432
DB_NAME=kgd_kpi
DB_USER=kgd_user
DB_PASSWORD=

# Redis
REDIS_URL=redis://redis:6379/0

# Celery Beat
CELERY_BEAT_HOUR=6     # час автоматического расчёта KPI (UTC)

# БД КГД (заполнить при получении доступа — Спринт 18)
KGD_DB_HOST=
KGD_DB_PORT=5432
KGD_DB_NAME=
KGD_DB_USER=
KGD_DB_PASSWORD=

# CORS (домен Vue фронта)
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

---

## Makefile команды

```bash
make build      # Сборка всех контейнеров
make up         # Запуск
make down       # Остановка
make migrate    # Применить миграции
make seed       # Загрузить регионы + инициализировать формулы
make superuser  # Создать суперпользователя
make test       # Запустить все тесты
make shell      # Django shell
make logs       # Логи всех контейнеров (follow)
make restart    # Перезапустить все сервисы
```

---

## Первый запуск

```bash
cp .env.example .env
# отредактировать .env

make build
make up
make migrate
make seed
make superuser
# открыть http://localhost:8080
```

---

## Пересборка после изменений

```bash
# Только backend
docker compose build web worker beat
docker compose up -d web worker beat

# Только frontend
docker compose build frontend
docker compose up -d frontend

# Всё
make build && make up
```

---

## Healthchecks

- **db**: `pg_isready` каждые 10с
- **redis**: `redis-cli ping` каждые 10с
- **web**: `GET /api/v1/health/` каждые 30с
- **nginx**: зависит от `web` (ждёт healthy)

---

## Volumes

```yaml
postgres_data   # данные PostgreSQL
static_volume   # статика Django (/static/)
media_volume    # медиафайлы (/media/)
```

Не удалять `postgres_data` без необходимости — потеря данных.
При `docker compose down -v` удаляются все volumes!

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

## Переменные окружения (`.env`)

Сервисы `db`, `web`, `worker`, `beat` читают **`env_file: .env`**. Шаблон — **`.env.example`** (скопируйте в `.env`).

```env
# Django
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
DB_HOST=db
DB_PORT=5432
DB_NAME=kgd_kpi
DB_USER=kgd_user
DB_PASSWORD=           # ← обязательно заполнить

# Redis
REDIS_URL=redis://redis:6379/0

# CORS (домен Vue фронта)
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080

# Celery Beat
CELERY_BEAT_HOUR=6     # час автоматического расчёта KPI (UTC)

# БД КГД / витрины (заполнить при доступе; см. docs/sprints/etl_kgd_gold_vitrines.md)
KGD_DB_HOST=
KGD_DB_PORT=5432
KGD_DB_NAME=
KGD_DB_USER=
KGD_DB_PASSWORD=
```

`DB_PASSWORD` одновременно используется как `POSTGRES_PASSWORD` для контейнера `db` (подстановка `${DB_PASSWORD}` в `docker-compose.yml`).

Без Docker: `DB_HOST=localhost`, `REDIS_URL=redis://127.0.0.1:6379/0`.

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
# задать DB_PASSWORD и при необходимости DJANGO_SECRET_KEY

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
- **web**: опрос `GET /api/v1/health/` на `127.0.0.1:8000` (через `urllib` внутри контейнера). Заголовок `X-Forwarded-Proto: https` нужен, иначе при `SECURE_SSL_REDIRECT` Django ответит редиректом, а не 200.
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

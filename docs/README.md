# KGD KPI Monitor — Документация

## Навигация

### Бизнес-логика
| Файл | Содержание |
|------|-----------|
| [business/kpi_formulas.md](business/kpi_formulas.md) | 6 KPI: формулы, шкалы баллов, пороги |
| [business/data_sources.md](business/data_sources.md) | ИНИС/ИСНА, фильтры, флаги учёта, ДФНО |
| [business/business_regions.md](business/business_regions.md) | Справочник 20 ДГД |

### Архитектура
| Файл | Содержание |
|------|-----------|
| [architecture/overview.md](architecture/overview.md) | Стек, структура проекта, инфраструктура |
| [architecture/database.md](architecture/database.md) | Все модели, связи, индексы |
| [architecture/api.md](architecture/api.md) | REST API эндпоинты, аутентификация |

### Приложения (минимальный контекст для Claude Code)
| Файл | Содержание |
|------|-----------|
| [apps/core.md](apps/core.md) | User, роли, RLS, AuditLog, MAC middleware |
| [apps/etl.md](apps/etl.md) | Импорт, нормализация, ManualInput, тестовые данные |
| [apps/kpi.md](apps/kpi.md) | KPI Engine, формулы, KPIResult, KPISummary |
| [apps/reports.md](apps/reports.md) | Утверждение, экспорт PDF/XLSX |
| [apps/apps_regions.md](apps/apps_regions.md) | Справочник регионов, фикстура |

### Фронтенд
| Файл | Содержание |
|------|-----------|
| [frontend/frontend_overview.md](frontend/frontend_overview.md) | Vue 3, роуты, stores, компоненты, карта |

### Инфраструктура
| Файл | Содержание |
|------|-----------|
| [infrastructure/docker.md](infrastructure/docker.md) | Docker Compose, сервисы, переменные окружения |
| [infrastructure/deployment.md](infrastructure/deployment.md) | On-premise, требования к серверу |
| [infrastructure/ci.md](infrastructure/ci.md) | GitHub Actions, тесты, lint |

### Разработка
| Файл | Содержание |
|------|-----------|
| [dev/onboarding.md](dev/onboarding.md) | Быстрый старт для нового разработчика |
| [dev/conventions.md](dev/conventions.md) | Соглашения по коду, структура app |
| [dev/claude_code_guide.md](dev/claude_code_guide.md) | Как работать с Claude Code, экономия токенов |
| [dev/kgd_materials_and_history.md](dev/kgd_materials_and_history.md) | Локальная папка `old/`: выгрузки КГД, хронология, что где лежит |

### Спринты
| Файл | Содержание |
|------|-----------|
| [sprints/completed.md](sprints/completed.md) | Архив спринтов 0–17 |
| [sprints/sprint_18.md](sprints/sprint_18.md) | Спринт 18 — замена условных полей на реальные |

---

## Быстрый старт

```bash
cp .env.example .env   # заполните DB_PASSWORD
make build
make up
make migrate
make seed
make superuser
```

Открыть: `http://localhost:8080`

---

## Статус проекта

| Компонент | Статус |
|-----------|--------|
| Django backend (5 apps) | ✅ |
| KPI Engine (6 KPI) | ✅ Протестирован на реальных данных |
| REST API (DRF + JWT) | ✅ |
| Vue 3 frontend | ✅ |
| Celery + Redis | ✅ |
| Docker Compose | ✅ |
| Экспорт PDF + XLSX | ✅ |
| Безопасность (MAC, RLS, JWT) | ✅ |
| CI/CD (GitHub Actions) | ✅ |
| Тестовые данные из Excel | ✅ |
| Реальная БД КГД | ⏳ Спринт 18 — ждёт schema от Алихана |

---

## Команда
- **Тимур** — лид
- **Куаныш** — разработка
- **Алихан** — разработка (ГПХ), анализ БД КГД
- **Олжас** — контакт КГД, бизнес-логика

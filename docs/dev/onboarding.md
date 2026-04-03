# Онбординг нового разработчика

---

## За 15 минут

```bash
# 1. Клонировать
git clone https://github.com/kuanqk/KGD_KPI.git
cd KGD_KPI

# 2. Настроить окружение
cp .env.example .env
# Заполнить POSTGRES_PASSWORD и DB_PASSWORD (любой пароль для локалки)

# 3. Поднять проект
make build && make up && make migrate && make seed && make superuser

# 4. Открыть
# http://localhost:8080        — Vue фронт (логин)
# http://localhost:8080/admin/ — Django Admin
```

---

## Что читать

1. **`docs/README.md`** — навигация по документации
2. **`docs/business/kpi_formulas.md`** — бизнес-логика KPI (обязательно!)
3. **`docs/business/data_sources.md`** — источники данных, фильтры
4. **`docs/architecture/overview.md`** — архитектура проекта
5. **`docs/apps/[нужный app].md`** — контекст конкретного модуля

---

## Тестовые данные и расчёт

```bash
# Загрузить данные из Excel (01.01.2026)
docker compose exec web python manage.py load_test_data

# Запустить расчёт KPI
docker compose exec web python manage.py shell
```

```python
from apps.kpi.services.engine import KPIEngine
from datetime import date
engine = KPIEngine(date(2025,1,1), date(2026,1,1), user=None)
results = engine.calculate_all()
for s in sorted(results, key=lambda x: x.rank or 99):
    print(f"{s.rank or 'КГД'}. {s.region.name_ru} — {s.score_total} баллов")
```

**Ожидаемый результат:**
- Место 1: Алматинская (100 баллов)
- Место 20: Акмолинская (~35–45 баллов)

---

## Роли для тестирования

Создай 4 пользователя через Django Admin (`/admin/`):

| Роль | Что проверить |
|------|--------------|
| admin | Управление пользователями, логи |
| operator | Импорт, расчёт, ручной ввод |
| reviewer | Утверждение отчётов |
| viewer | RLS — только свои регионы (привязать 2–3 региона) |

---

## Как устроен проект

```
Данные из БД КГД
    → ETL (apps/etl) нормализует и сохраняет в PostgreSQL
    → KPI Engine (apps/kpi/services/engine.py) считает 6 KPI
    → REST API (DRF) отдаёт данные
    → Vue 3 фронт отображает
```

---

## Команда

- **Тимур** — лид, архитектурные решения
- **Куаныш** — разработка, Claude Code
- **Алихан** — разработка (ГПХ), анализ БД КГД
- **Олжас** — контакт КГД, бизнес-логика, валидация расчётов

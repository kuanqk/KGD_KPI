# apps/kpi — KPI Engine

> Минимальный контекст для работы с этим app.
> Формулы: [business/kpi_formulas.md](../business/kpi_formulas.md)
> Модели: [architecture/database.md](../architecture/database.md#appskpi)

---

## Что делает этот app

- Расчёт всех 6 KPI для 20 ДГД
- Версионирование формул
- Хранение результатов (KPIResult, KPISummary)
- Celery задача для фонового расчёта

---

## KPI Engine (`services/engine.py`)

```python
from apps.kpi.services.engine import KPIEngine
from datetime import date

engine = KPIEngine(
    date_from=date(2025, 1, 1),
    date_to=date(2026, 1, 1),
    user=None  # или request.user
)

# Рассчитать все 6 KPI для всех 20 ДГД
summaries = engine.calculate_all()

# Или для конкретных регионов
from apps.regions.models import Region
regions = Region.objects.filter(code__in=['06xx', '62xx'])
summaries = engine.calculate_all(regions=regions)
```

**Методы:**
```python
engine.calc_assessment(region)        # KPI 1 — Доначисление
engine.calc_collection(region)        # KPI 2 — Взыскание
engine.calc_avg_assessment(region)    # KPI 3 — Среднее доначисление
engine.calc_workload(region)          # KPI 4 — Занятость
engine.calc_long_inspections(region)  # KPI 5 — Проверки > 6 мес.
engine.calc_cancelled(region)         # KPI 6 — Отменённые суммы
```

Каждый метод возвращает `KPIResult` и сохраняет в БД.
`calculate_all()` дополнительно создаёт `KPISummary` и назначает ранги.

---

## Версионирование формул

```python
# Получить активную формулу
formula = KPIFormula.get_active('assessment')

# Пороги хранятся в formula.config['thresholds']:
# [{"min": 100, "score": 10}, {"min": 90, "score": 5}, {"min": 0, "score": 0}]
```

При создании новой версии — предыдущая автоматически деактивируется.
Старые `KPIResult` привязаны к своей версии формулы и не пересчитываются.

---

## Инициализация формул

```bash
python manage.py init_formulas          # создать v1 для всех 6 KPI
python manage.py init_formulas --force  # перезаписать
```

---

## Celery задача

```python
from apps.kpi.tasks import calculate_kpi

# Запустить расчёт в фоне
calculate_kpi.delay(
    date_from='2025-01-01',
    date_to='2026-01-01',
    region_ids=None,  # None = все регионы
    user_id=request.user.id
)

# Автоматически каждый день в 06:00 UTC:
# scheduled_kpi_calculation() — через Celery Beat
```

---

## Критичные особенности формул

1. **KPI 3:** диапазон 80–89% → **0 баллов** (не 5). Ранее было 5, сейчас нет.
2. **KPI 3:** ДФНО исключается и из суммы, и из кол-ва проверок.
3. **KPI 3:** целевой KPI = единый порог для всех ДГД = среднее КГД × 120%.
4. **KPI 6:** акты старше 2 лет до решения Апелл. комиссии исключаются.
5. **КГД** (`is_summary=True`) — не ранжируется, `rank=None`.

---

## Файлы app

```
apps/kpi/
├── models.py              # KPIFormula, KPIResult, KPISummary
├── services/
│   └── engine.py          # KPIEngine — центральный расчётный движок
├── tasks.py               # calculate_kpi, scheduled_kpi_calculation
├── filters.py             # KPIResultFilter, KPISummaryFilter
├── serializers.py
├── views.py               # KPIFormulaViewSet, KPIResultViewSet,
│                          # KPISummaryViewSet, CalculateView
├── urls.py
├── admin.py
├── management/commands/
│   └── init_formulas.py   # Инициализация формул v1
└── tests/
    ├── test_engine.py     # 60+ тестов с реальными данными из Excel
    ├── test_models.py
    └── test_init_formulas.py
```

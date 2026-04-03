# apps/etl — Импорт и нормализация данных

> Минимальный контекст для работы с этим app.
> Модели: [architecture/database.md](../architecture/database.md#appsetl)
> Источники данных: [business/data_sources.md](../business/data_sources.md)

---

## Что делает этот app

- Импорт данных из БД КГД (ИНИС/ИСНА) в локальную PostgreSQL
- Нормализация: условные поля → единая схема
- Ручные вводы оператора (КБК, штат)
- Тестовые данные из Excel

---

## Сервисный слой

### DataNormalizer (`services/normalizer.py`)

```python
normalizer = DataNormalizer()

# Маршрутизация по дате: < 09.07.2025 → inis, иначе → isna
insp = normalizer.normalize_completed_inspection(raw_row)
active = normalizer.normalize_active_inspection(raw_row)
appeal = normalizer.normalize_appeal(raw_row)
```

**Все условные поля помечены комментарием `# Заменить в Спринте 18`.**

### KGDImporter (`services/importer.py`)

```python
job = ImportJob.objects.create(source='inis', ...)
importer = KGDImporter(job)
importer.run()
# → pending → running → done/error
# → записи в CompletedInspection / ActiveInspection / AppealDecision
```

**`_fetch_from_kgd_db()`** — сейчас заглушка с тестовыми данными.
В Спринте 18 заменить на реальное подключение через `psycopg2`:
```python
# KGD_DB_HOST, KGD_DB_PORT, KGD_DB_NAME, KGD_DB_USER, KGD_DB_PASSWORD из .env
```

---

## Celery задача

```python
from apps.etl.tasks import run_import_job
run_import_job.delay(job_id)
# max_retries=3, exponential backoff: 60 * 2^retry сек
```

---

## Тестовые данные

```bash
python manage.py load_test_data          # загрузить
python manage.py load_test_data --clear  # очистить и загрузить заново
```

**Что загружается:**
- `ManualInput`: доли КБК и штат для 20 ДГД (из Excel 01.01.2026)
- `CompletedInspection`: 2253 записи за 2025 год + 2253 за 2024 год
- `ActiveInspection`: 471 запись
- `AppealDecision`: 36 записей
- `KPIResult`: 40 записей за 2024 год (база для расчёта плана)

**После загрузки запустить расчёт:**
```python
from apps.kpi.services.engine import KPIEngine
from datetime import date
engine = KPIEngine(date(2025,1,1), date(2026,1,1), user=None)
results = engine.calculate_all()
```

---

## Спринт 18 — что менять здесь

1. `services/normalizer.py` — обновить маппинг полей
2. `services/importer.py` — убрать заглушку в `_fetch_from_kgd_db()`, подключить реальную БД КГД
3. Обновить таблицу условных полей в `business/data_sources.md`

---

## Файлы app

```
apps/etl/
├── models.py              # ImportJob, CompletedInspection, ActiveInspection,
│                          # AppealDecision, ManualInput
├── services/
│   ├── normalizer.py      # DataNormalizer — маппинг полей
│   └── importer.py        # KGDImporter — подключение к БД КГД
├── tasks.py               # run_import_job (Celery)
├── serializers.py
├── views.py               # ImportJobViewSet, CompletedInspectionViewSet, ManualInputViewSet
├── urls.py
├── admin.py
└── management/commands/
    └── load_test_data.py  # Тестовые данные из Excel
```

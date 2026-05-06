# ETL из витрин КГД (`audit_kpi_data_gold`)

Исторически в плане спринтов это был **спринт 18** («замена условных полей на реальные»); документ назван по сути задачи — загрузка из gold-слоя ИСНА в KPI Monitor.

**Статус: ✅ SQL реализован, ожидается тест на реальных данных**

---

## Контекст

Алихан (06.05.2026) предоставил готовые витрины в схеме `audit_kpi_data_gold` БД `isna_audit`.
Витрины уже содержат предобработку: только УНА, без уголовных/прокурорских, нормализованные суммы и даты.

Локальные выгрузки и переписки: `old/260506-2/` (XML-примеры витрин + `msg12.txt`).

---

## Что реализовано (06.05.2026)

### `apps/etl/services/importer.py`

- `_fetch_completed_acts()` — SQL к `audit_kpi_data_gold.completed_acts` + JOIN с `act_collected_amount`
- `_fetch_ongoing_acts()` — SQL к `audit_kpi_data_gold.ongoing_acts`
- При наличии `KGD_DB_HOST` в окружении → реальный запрос; без него → заглушки (CI/dev)

### `apps/etl/services/normalizer.py`

- `_normalize_region_code()` — пробелы, суффикс `XX` → `xx`, кириллическое «х» → латинское `x` (совпадение со справочником `Region`)
- `_json_safe_raw()` — для поля `raw_data`: `date`/`datetime`/`Decimal` из PostgreSQL → строки/JSON-совместимые типы (иначе ошибка при `bulk_create`)
- `_parse_amount()` — безопасный парсинг сумм (числа / строки с пробелами / запятые)
- `normalize_completed_inspection()` — принимает витринные поля: `source_id=act_number`, `region_code`, `management='УНА'`, `amount_assessed`, `amount_collected`
- `normalize_active_inspection()` — принимает `prescription_date=case_notif_delivery_date`, `is_counted=True` по умолчанию

---

## Маппинг полей витрин → модели

### CompletedInspection ← `completed_acts` + `act_collected_amount`

| Django-поле | SQL | Примечание |
|---|---|---|
| `source_id` | `act_number` | GROUP BY на акт |
| `region` | `LEFT(code_nk,2)\|\|'xx'` | e.g. `'0601'→'06xx'` |
| `management` | `'УНА'` hardcoded | витрина уже фильтрована |
| `completed_date` | `completion_date` | |
| `amount_assessed` | `SUM(accrued+penalty+koap_fine+zan_fine−reduced)` | подтверждено Алиханом 06.05.2026 |
| `amount_collected` | `SUM(collected_amount)` JOIN `act_collected_amount` | методы 1+2; ДФНО исключён витриной |
| `is_counted` | — | False, вручную оператором |
| `is_accepted` | — | False, вручную оператором |

### ActiveInspection ← `ongoing_acts`

| Django-поле | SQL | Примечание |
|---|---|---|
| `source_id` | `act_number` | |
| `region` | `LEFT(code_nk,2)\|\|'xx'` | |
| `prescription_date` | `case_notif_delivery_date` | может быть NULL |
| `is_counted` | `True` | уголовные исключены витриной |

---

## Следующие шаги

### 1. Запустить импорт на реальных данных

```bash
docker compose exec web python manage.py shell
```

```python
from apps.etl.models import ImportJob
from apps.etl.services.importer import KGDImporter
from django.contrib.auth import get_user_model

User = get_user_model()
admin = User.objects.get(username='admin')

# Завершённые проверки за 2025 год
job = ImportJob.objects.create(
    source='isna',
    started_by=admin,
    params={'date_from': '2025-01-01', 'date_to': '2026-01-01'},
)
KGDImporter(job).run()
print(f'Импортировано: {job.records_imported} из {job.records_total}')
```

### 2. Валидация результатов

```python
from apps.kpi.services.engine import KPIEngine
from datetime import date

engine = KPIEngine(date(2025, 1, 1), date(2026, 1, 1), user=None)
results = engine.calculate_all()

# Сравнить с Excel Статистика_КЭР_РК_на_01_01_2026.xlsx:
# Алматинская → 100 баллов (место 1)
# Акмолинская → 45 баллов (место 20)
```

**Зафиксировать расхождения** и согласовать с Олжасом.

### Типичная ошибка: «Регион с кодом … не найден»

1. **В приложении не загружен справочник ДГД.** Должно быть **21** строка в `regions_region` (20 областей/городов с кодами `03xx` … `71xx` и сводная `00xx`). Загрузка:

   ```bash
   docker compose exec web python manage.py loaddata apps/regions/fixtures/regions.json
   ```

   Либо полный сид из Makefile проекта (`make seed`), если он включает этот fixture.

2. **Код региона с кириллическими «х»** (`27хх`) вместо латинских (`27xx`) — нормализатор приводит к виду справочника; если ошибка остаётся, проверьте пункт 1.

3. **`TypeError: Object of type date is not JSON serializable`** при `bulk_create` — в `raw_data` попадали типы psycopg2 (`date`, `Decimal`). Исправлено: `normalizer._json_safe_raw()` перед сохранением; обновите `apps/etl/services/normalizer.py` на сервере и перезапустите `web`/`worker`.

### 3. AppealDecision (KPI 6)

⏳ Алихан выяснит доступность данных обжалований с МинФин (зашифрованные суммы).
До решения KPI 6 считается по ручным вводам.

---

## Промпт для следующего сеанса (если нужны правки после валидации)

```
Прочитай docs/apps/etl.md, docs/business/data_sources.md и docs/sprints/etl_kgd_gold_vitrines.md.

ETL на витринах реализован. После первого запуска на реальных данных обнаружены расхождения:
[вставить расхождения с Excel]

Задачи:
1. Уточни формулу amount_assessed если нужно
2. Проверь маппинг region_code — все 20 регионов должны матчиться
3. Зафиксируй изменения в data_sources.md
```

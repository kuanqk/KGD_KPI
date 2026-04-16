# Спринт 18 — Замена условных полей на реальные

**Статус: ⏳ Ждёт schema БД от Алихана**

---

## Контекст

Весь проект использует **условные названия полей** в моделях ETL и KPI Engine.
Все условные поля помечены комментарием `# Заменить в Спринте 18`.

После того как Алихан предоставит реальную структуру таблиц БД КГД — выполнить этот спринт.

---

Структура локальных выгрузок и переписок (папка `old/`, не в Git): [dev/kgd_materials_and_history.md](../dev/kgd_materials_and_history.md).

## Текущий статус анализа БД КГД (апрель 2026)

**Алихан (разработчик ГПХ) ведёт анализ:**
- ✅ Найдены три вьюхи: предписания + периоды, акт предписания, акт налоговой проверки
- ✅ Суммы доначислений найдены примерно
- ✅ `re_user.department_id` → путь к определению УНА
- ⏳ Корректные даты — расходятся в разных таблицах
- ⏳ Устойчивая связка: предписание → акт → суммы → даты → управление
- ⏳ CSV с полями — ожидается

**Цепочка связей (искомая):**
```
предписание → акт предписания → акт налоговой проверки → суммы → даты → department_id
```

**Ключевые вопросы для Алихана:**
1. Как определить УНА через `department_id`? Какие значения?
2. Какая дата является основной для KPI (вручения, подписания, регистрации)?
3. Как кодируется ДФНО в поле типа проверки?
4. Есть ли `region_code` в таблице обжалований?
5. Как формируется `is_accepted` — есть ли готовый флаг или вычисляется по правилам?

---

## Что делать при получении schema

### 1. Обновить таблицу маппинга в `docs/business/data_sources.md`

Заменить `⏳ уточнить` на реальные названия полей.

### 2. Обновить `DataNormalizer` (`apps/etl/services/normalizer.py`)

```python
# Найти все комментарии "# Заменить в Спринте 18"
# и обновить маппинг полей:

def normalize_completed_inspection(self, raw_row: dict):
    return CompletedInspection(
        region=self._get_region(raw_row['РЕАЛЬНОЕ_ПОЛЕ_КОД_ДГД']),
        management=raw_row['РЕАЛЬНОЕ_ПОЛЕ_УПРАВЛЕНИЕ'],  # или через JOIN с re_user
        form_type=raw_row['РЕАЛЬНОЕ_ПОЛЕ_ТИП_ПРОВЕРКИ'],
        amount_assessed=raw_row['РЕАЛЬНОЕ_ПОЛЕ_ДОНАЧИСЛЕНО'],
        amount_collected=raw_row['РЕАЛЬНОЕ_ПОЛЕ_ВЗЫСКАНО'],
        completed_date=raw_row['РЕАЛЬНОЕ_ПОЛЕ_ДАТА'],
        ...
    )
```

### 3. Реализовать `_fetch_from_kgd_db()` в `KGDImporter`

```python
# apps/etl/services/importer.py
def _fetch_from_kgd_db(self):
    import psycopg2
    conn = psycopg2.connect(
        host=config('KGD_DB_HOST'),
        port=config('KGD_DB_PORT'),
        dbname=config('KGD_DB_NAME'),
        user=config('KGD_DB_USER'),
        password=config('KGD_DB_PASSWORD'),
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            -- реальные поля
        FROM реальная_таблица
        WHERE условия
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows
```

### 4. Проверить KPI Engine

Убедиться что все ORM запросы в `engine.py` используют правильные поля:
- `management='УНА'` — совпадает с реальными значениями
- `form_type != 'ДФНО'` — совпадает с реальным кодом ДФНО
- Фильтр `is_counted` / `is_accepted` — соответствует бизнес-правилам

### 5. Валидация

```bash
# Загрузить реальные данные за период 01.01.2025 - 01.01.2026
docker compose exec web python manage.py shell
```

```python
from apps.kpi.services.engine import KPIEngine
from datetime import date
engine = KPIEngine(date(2025,1,1), date(2026,1,1), user=None)
results = engine.calculate_all()

# Сравнить с Excel Статистика_КЭР_РК_на_01_01_2026.xlsx:
# Алматинская → 100 баллов (место 1)
# Акмолинская → 45 баллов (место 20)
```

**Зафиксировать расхождения** и согласовать с Олжасом.

---

## Промпт для Claude Code (выполнить после получения schema)

```
Прочитай docs/apps/etl.md и docs/business/data_sources.md.

Получена реальная schema БД КГД. Таблица маппинга:
[вставить таблицу реальных полей]

Задачи:
1. Обнови apps/etl/services/normalizer.py — замени условные поля на реальные
2. Реализуй _fetch_from_kgd_db() в apps/etl/services/importer.py
   SQL запрос для получения завершённых проверок за период
3. Обнови docs/business/data_sources.md — таблицу условных полей

Не запускай команды. Только создай/измени файлы.
```

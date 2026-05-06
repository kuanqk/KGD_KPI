# sprints.md — План спринтов: KGD KPI Monitor

> Каждый спринт = одна задача для Claude Code.
> Перед каждой задачей Claude Code читает `claude.md` (бизнес-логика) и `docs/DEV.md` (архитектура).
> Поля нормализованной модели ETL описаны в `docs/claude.md` и `docs/business/data_sources.md`; импорт из боевой ИСНА для KPI 1–5 — через витрины `audit_kpi_data_gold` ([etl_kgd_gold_vitrines.md](etl_kgd_gold_vitrines.md)).
> **Правило:** не запускать команды в промптах — миграции и тесты разработчик выполняет локально.

---

## Статус спринтов

| # | Спринт | Статус |
|---|--------|--------|
| 0 | Инициализация проекта | ✅ Выполнен |
| 1 | Модели: core + regions | ✅ Выполнен |
| 2 | Модели: etl | ✅ Выполнен |
| 3 | Модели: kpi + reports | ✅ Выполнен |
| 4 | ETL: импорт и нормализация | ✅ Выполнен |
| 5 | KPI Engine: расчёт всех 6 KPI | ✅ Выполнен |
| 6 | REST API: core + regions + etl | ✅ Выполнен |
| 7 | REST API: kpi + reports | ✅ Выполнен |
| 8 | Celery: задачи и расписание | ✅ Выполнен |
| 9 | Vue: Auth + Dashboard + карта | ✅ Выполнен |
| 10 | Vue: KPI детали + сравнение | ✅ Выполнен |
| 11 | Vue: Оператор (импорт, формулы, расчёт) | ✅ Выполнен |
| 12 | Vue: Проверяющий + история | ✅ Выполнен |
| 13 | Vue: Администратор | ✅ Выполнен |
| 14 | Экспорт PDF + XLSX | ✅ Выполнен |
| 15 | Безопасность: MAC, RLS, JWT | ✅ Выполнен |
| 16 | Тесты KPI Engine | ✅ Выполнен |
| 17 | Docker Compose + CI | ✅ Выполнен |
| 18 | ETL из витрин КГД (`audit_kpi_data_gold`) | ✅ SQL в коде; валидация на проде — см. [etl_kgd_gold_vitrines.md](etl_kgd_gold_vitrines.md) |

---

## Контрольные точки для локального запуска

| После спринта | Что проверяем |
|---|---|
| **3** | `docker compose up`, Django Admin, миграции |
| **7** | API через Postman, JWT, роли |
| **9** | Браузер, карта, дашборд |
| **17** | Полный прогон, все фичи |

---

## Спринт 0 — Инициализация проекта ✅

Выполнен. Создана структура проекта, Docker Compose, settings, requirements.txt.

---

## Спринт 1 — Модели: core + regions ✅

Выполнен. 29/29 тестов OK.
- User, UserRegion, AuditLog, RegionScopedQuerySet/Mixin
- Region, фикстура 20 ДГД + КГД

---

## Спринт 2 — Модели: etl ✅

Выполнен. 32/32 тестов OK.
- ImportJob, CompletedInspection, ActiveInspection, AppealDecision, ManualInput

---

## Спринт 3 — Модели: kpi + reports

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 2.4 и 2.5).

Реализуй Спринт 3: модели kpi + reports.

apps/kpi/models.py:
- KPIFormula с методом get_active(kpi_type)
- KPIResult
- KPISummary

apps/reports/models.py:
- ReportApproval

apps/kpi/admin.py — KPIFormula, KPIResult, KPISummary
apps/reports/admin.py — ReportApproval

Создай миграции.

management command: apps/kpi/management/commands/init_formulas.py
— создаёт KPIFormula версия 1 для всех 6 KPI
с конфигурацией порогов из claude.md.

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 4 — ETL: импорт и нормализация

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 2.3, сервисный слой).

Реализуй Спринт 4: ETL сервисный слой.

apps/etl/services/normalizer.py:
- Класс DataNormalizer
- normalize_completed_inspection(raw_row: dict) → CompletedInspection
  Маршрутизация: дата < 09.07.2025 → source='inis', иначе source='isna'
  Маппинг условных полей согласно таблице в claude.md раздел "Условные поля БД"
- normalize_active_inspection(raw_row: dict) → ActiveInspection
- normalize_appeal(raw_row: dict) → AppealDecision

apps/etl/services/importer.py:
- Класс KGDImporter
- __init__(self, job: ImportJob)
- run() → запускает импорт, обновляет ImportJob.status
- _fetch_from_kgd_db() → заглушка, возвращает тестовые данные
  (реальное подключение к витринам — см. docs/sprints/etl_kgd_gold_vitrines.md)
- _bulk_create(records) → batch insert с обработкой дубликатов (ignore_conflicts)

apps/etl/tasks.py:
- run_import_job(job_id) — Celery задача, вызывает KGDImporter, max_retries=3

Не запускай команды. Только создай/izmeni файлы.
```

---

## Спринт 5 — KPI Engine: расчёт всех 6 KPI

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 2.4, KPI Engine). Это центральный спринт.

Реализуй apps/kpi/services/engine.py — класс KPIEngine.

Строго следуй формулам из claude.md:

calc_assessment(region) → KPIResult  [KPI 1]
  - Факт: SUM(amount_assessed) из CompletedInspection
    WHERE region=region, management='УНА', completed_date IN [date_from, date_to]
  - KPI_план: ManualInput.kbk_share_pct * общий план * 1.20
  - Баллы: >=100%->10, >=90%->5, <90%->0

calc_collection(region) → KPIResult  [KPI 2]
  - Факт: SUM(amount_collected) WHERE management='УНА', is_accepted=True
  - KPI_план: ManualInput.kbk_share_pct * общий план взысканий * 1.20
  - Баллы: >=100%->40, >=90%->20, >=80%->10, <80%->0

calc_avg_assessment(region) → KPIResult  [KPI 3]
  - Сумма и кол-во: WHERE management='УНА', is_counted=True, form_type != 'ДФНО'
  - KPI_план: единый порог = среднее по всем 20 ДГД за прошлый год * 1.20
  - Баллы: >=100%->10, >=90%->5, <90%->0  (80-89% тоже 0, не 5!)

calc_workload(region) → KPIResult  [KPI 4]
  - Кол-во: COUNT завершённых WHERE management='УНА', is_counted=True
  - staff: ManualInput.staff_count
  - months: кол-во полных месяцев между date_from и date_to
  - Баллы: >=0.5->15, >=0.4->5, <0.4->0

calc_long_inspections(region) → KPIResult  [KPI 5]
  - Все: COUNT(ActiveInspection) WHERE is_counted=True, region=region
  - Долгие: WHERE (date_to - prescription_date).days > 180
  - Баллы: <20%->10, >=20%->0

calc_cancelled(region) → KPIResult  [KPI 6]
  - Отменено: SUM(AppealDecision.amount_cancelled) WHERE is_counted=True
  - Доначислено: берётся из уже рассчитанного KPI 1 (Факт)
  - Баллы: <=1%->15, <=2%->5, >2%->0

calculate_all(regions=None) → list[KPISummary]
  - Рассчитать все 6 KPI для всех регионов (или переданных)
  - Сохранить KPIResult для каждого KPI каждого региона
  - Сохранить KPISummary (сумма баллов по 6 KPI)
  - Назначить ранги по убыванию score_total
  - КГД (is_summary=True) ранг не получает (rank=None)
  - Всё логировать в AuditLog

apps/kpi/tasks.py:
- calculate_kpi(date_from, date_to, region_ids, user_id) — Celery задача

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 6 — REST API: core + regions + etl

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 3).

Реализуй Спринт 6: REST API для apps/core, apps/regions, apps/etl.

apps/core/:
- serializers.py: UserSerializer, AuditLogSerializer
- views.py: LoginView (JWT), LogoutView, UserViewSet, AuditLogViewSet
- permissions.py: IsAdmin, IsOperator, IsReviewer, IsViewer, IsOperatorOrAdmin
- urls.py

apps/regions/:
- serializers.py: RegionSerializer
- views.py: RegionListView (GET only, все роли)
- urls.py

apps/etl/:
- serializers.py: ImportJobSerializer, CompletedInspectionSerializer,
                  ActiveInspectionSerializer, ManualInputSerializer
- views.py:
  - ImportJobViewSet (list, create, retrieve) — только Оператор
  - CompletedInspectionViewSet (list, partial_update) — Оператор
  - ManualInputViewSet (list, create, update) — Оператор
- urls.py

config/urls.py — подключить все роутеры под /api/v1/

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 7 — REST API: kpi + reports

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 3).

Реализуй Спринт 7: REST API для apps/kpi и apps/reports.

apps/kpi/:
- serializers.py: KPIFormulaSerializer, KPIResultSerializer, KPISummarySerializer
- views.py:
  - KPIFormulaViewSet (list, create) — Оператор
  - KPIResultViewSet (list, retrieve) — все роли (RLS через RegionScopedMixin)
  - KPISummaryViewSet (list, retrieve) — все роли (RLS)
  - CalculateView (POST) — Оператор, запускает Celery задачу calculate_kpi
- filters.py — django-filter: по region, date_from, date_to, kpi_type
- urls.py

apps/reports/:
- serializers.py: ReportApprovalSerializer
- views.py:
  - PendingReportsView (GET) — Проверяющий
  - ApproveView, RejectView, RecalculateView (POST) — Проверяющий
  - ExportXLSXView, ExportPDFView (GET) — все роли
- urls.py

Все ViewSet с данными регионов использовать RegionScopedMixin из apps/core/mixins.py.

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 8 — Celery: задачи и расписание

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 4).

Реализуй Спринт 8: все Celery задачи.

apps/etl/tasks.py:
- run_import_job(job_id) — max_retries=3, exponential backoff
  Обновляет ImportJob.status, логирует в AuditLog

apps/kpi/tasks.py:
- calculate_kpi(date_from, date_to, region_ids, user_id)
- scheduled_kpi_calculation() — для Celery Beat (ежедневно в 06:00)

apps/reports/tasks.py:
- export_to_xlsx(summary_id, user_id)
- export_to_pdf(summary_id, user_id)

Каждая задача:
- Логирует start/success/error в AuditLog
- При ошибке: retry с backoff, затем status='error' + error_message

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 9 — Vue: Auth + Dashboard + карта

**Промпт для Claude Code:**
```
Прочитай claude.md.

Инициализируй Vue 3 проект в папке frontend/ (Vite + Vue 3 + Pinia + Vue Router + Axios).

Реализуй:

1. frontend/src/api/client.js
   — Axios с JWT interceptors (auto-refresh при 401)

2. frontend/src/stores/auth.js
   — Pinia: login, logout, текущий пользователь, роль

3. frontend/src/router/index.js
   — все маршруты из DEV.md раздел 6
   — route guards: проверка роли перед входом

4. frontend/src/views/LoginView.vue
   — форма логина (email + password)

5. frontend/src/views/DashboardView.vue
   — SVG карта Казахстана 20 регионов (Leaflet.js + GeoJSON)
   — цветовая индикация: зелёный >=80б, жёлтый 50-79б, красный <50б
   — таблица рейтинга: позиция, регион, баллы итого, каждый KPI отдельно
   — клик по региону — переход на /kpi/:regionCode
   — RLS: viewer видит только свои регионы

6. frontend/src/components/KPIScoreCard.vue
   — карточка KPI: название, балл, факт, план, %

Стили: цвет акцента #1F4E79 (синий КГД), минималистично.

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 10 — Vue: KPI детали + сравнение

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй Спринт 10: страницы детального просмотра KPI.

frontend/src/views/KPIDetailView.vue:
- Фильтры: период (date_from/date_to), регион, тип KPI
- Таблица результатов по всем ДГД
- График динамики (Chart.js, линейный)
- Кнопки экспорта XLSX и PDF

frontend/src/views/CompareView.vue:
- Выбор двух периодов
- Side-by-side таблица: период А vs период Б
- Дельта баллов по каждому KPI и итого

frontend/src/components/KPITable.vue — переиспользуемая таблица результатов
frontend/src/components/KPIChart.vue — Chart.js обёртка

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 11 — Vue: Оператор

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй Спринт 11: страницы для роли Оператор.

frontend/src/views/ImportView.vue:
- Кнопка "Запустить импорт из БД КГД"
- Список ImportJob: статус, кол-во записей, время
- Polling каждые 3 сек для статуса running

frontend/src/views/DataEditorView.vue:
- Таблица CompletedInspection с фильтрами (регион, дата, тип)
- Inline-редактирование флагов is_counted, is_accepted
- Кнопка "Пометить аномалию"

frontend/src/views/FormulasView.vue:
- Список версий KPIFormula по каждому KPI
- Форма создания новой версии с редактором порогов

frontend/src/views/CalculateView.vue:
- Выбор периода (date_from/date_to)
- Выбор регионов (мультиселект или "все")
- Запуск расчёта, polling статуса Celery задачи
- Кнопка "Отправить на утверждение"

frontend/src/views/ManualInputView.vue:
- Таблица: для каждого ДГД поля kbk_share_pct и staff_count
- Выбор года из дропдауна

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 12 — Vue: Проверяющий + история

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй Спринт 12: страницы для роли Проверяющий.

frontend/src/views/ApprovalView.vue:
- Список отчётов со статусом submitted
- Для каждого: регион, период, баллы итого, 6 KPI по отдельности
- Кнопки: "Утвердить" / "Вернуть" (с комментарием) / "Запросить пересчёт"

frontend/src/views/HistoryView.vue:
- Архив утверждённых отчётов
- Фильтры: период, регион, статус
- Кнопки экспорта PDF/XLSX для каждого отчёта

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 13 — Vue: Администратор

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй Спринт 13: страницы для роли Администратор.

frontend/src/views/UsersView.vue:
- Таблица пользователей с CRUD
- Поля: имя, email, роль (дропдаун), MAC-адрес
- Для роли viewer — мультиселект привязки регионов

frontend/src/views/AuditLogsView.vue:
- Таблица AuditLog с cursor-based пагинацией
- Фильтры: пользователь, тип события, дата

frontend/src/views/ETLMonitorView.vue:
- Список всех ImportJob с статусами
- Ошибки последних импортов
- Статус Celery workers

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 14 — Экспорт PDF + XLSX

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй Спринт 14: экспорт отчётов.

apps/reports/services/xlsx_exporter.py:
- Класс XLSXExporter(summary: KPISummary)
- generate() -> BytesIO
- Лист 1: сводный рейтинг (20 ДГД, позиции, баллы, все 6 KPI)
- Листы 2-7: детали по каждому KPI
- Форматирование: заморозка первой строки,
  цвет ячеек баллов (зелёный/жёлтый/красный)
- Шапка: название отчёта, период, дата генерации, версия формулы

apps/reports/services/pdf_exporter.py:
- Класс PDFExporter(summary: KPISummary)
- generate() -> BytesIO (WeasyPrint)
- HTML-шаблон: templates/reports/kpi_report.html
- Шапка: период, дата генерации, версия формулы

Оба экспортёра логируют в AuditLog событие 'export'.

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 15 — Безопасность

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 7).

Реализуй Спринт 15: безопасность.

1. apps/core/middleware.py — MACAddressMiddleware:
   - При логине проверять mac_address из запроса с User.mac_address
   - Если не совпадает — 403
   - Логировать попытки в AuditLog

2. apps/core/permissions.py:
   IsAdmin, IsOperator, IsReviewer, IsViewer, IsOperatorOrAdmin

3. Проверить что все ViewSet с данными используют RegionScopedMixin
   (viewer не должен видеть данные чужих регионов)

4. config/settings/prod.py:
   SECURE_HSTS_SECONDS = 31536000
   SESSION_COOKIE_SECURE = True
   CSRF_COOKIE_SECURE = True
   SECURE_SSL_REDIRECT = True

5. Rate limiting на /api/v1/auth/login/ — 5 запросов/мин (django-ratelimit)

6. CORS: разрешить только домен из env CORS_ALLOWED_ORIGINS

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 16 — Тесты KPI Engine

**Промпт для Claude Code:**
```
Прочитай claude.md. Этот спринт — валидация бизнес-логики KPI Engine.

Реализуй полный набор тестов в apps/kpi/tests/test_engine.py.

Для каждого из 6 KPI:

1. Нормальный случай — конкретные числа на входе, ожидаемые баллы на выходе

2. Граничные случаи:
   - Ровно 100% — максимум баллов
   - 99.9% — на одну ступень меньше
   - 0 данных — баллы = 0, не ошибка деления на ноль
   - NULL / пустые данные — баллы = 0

3. KPI 3 специфика:
   - Диапазон 80-89% — 0 баллов (не 5!)
   - Записи с form_type='ДФНО' исключены из суммы и кол-ва

4. KPI 4: расчёт месяцев корректен для разных периодов

5. KPI 6: акты старше 2 лет до решения комиссии исключены

6. Рейтинг:
   - КГД (is_summary=True) не получает ранг (rank=None)
   - 20 ДГД получают уникальные ранги 1-20

Цель: результаты должны совпасть с ручным расчётом Олжаса.

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 17 — Docker Compose + CI

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md (раздел 1, инфраструктура).

Реализуй Спринт 17: финальная инфраструктура.

1. Доработай docker-compose.yml:
   - Сервисы: web, db, redis, worker, beat, frontend, nginx
   - Healthcheck для db и redis
   - Volume для PostgreSQL данных
   - env_file: .env

2. docker/nginx.conf:
   - /api/ — Django (web:8000)
   - / — Vue (frontend:80)
   - Самоподписанный сертификат для dev

3. Dockerfile (backend) — многоэтапная сборка Python 3.12-slim
4. frontend/Dockerfile — Vue build + nginx

5. Makefile:
   make build    — сборка контейнеров
   make up       — запуск
   make down     — остановка
   make migrate  — миграции
   make seed     — loaddata regions + init_formulas
   make test     — запуск всех тестов
   make shell    — Django shell

6. .github/workflows/ci.yml:
   - При push: запуск тестов
   - При merge в main: сборка Docker образов

Не запускай команды. Только создай/измени файлы.
```

---

## Спринт 18 — ETL из витрин КГД (актуальный документ)

Историческое название спринта — «замена условных полей на реальные». **Актуальное описание, SQL и чеклист:** [etl_kgd_gold_vitrines.md](etl_kgd_gold_vitrines.md).

Ниже — исходный промпт из этого файла (частично устарел: импорт реализован через витрины).

---

## Спринт 18 — архив промпта (legacy)

> ⚠️ Выполнять ТОЛЬКО после получения реальной schema БД КГД от Олжаса.

**Промпт для Claude Code:**
```
Прочитай claude.md (раздел "Условные поля БД").

Получена реальная schema БД КГД. Выполни замену условных полей:

1. Обнови таблицу условных полей в claude.md — реальные названия
2. apps/etl/services/normalizer.py:
   - Обнови маппинг в normalize_*() методах
   - Реализуй реальное подключение в _fetch_from_kgd_db() (убери заглушку)
3. apps/kpi/services/engine.py:
   - Проверь все ORM-запросы на соответствие реальным полям
4. Запусти расчёт за период 01.01.2025-01.01.2026
   и сравни с файлом Статистика_КЭР_РК_на_01_01_2026.xlsx
5. Зафиксируй расхождения в docs/validation_report.md

Не запускай команды. Только создай/измени файлы.
```

---

## Правила для Claude Code

- **Всегда читать `claude.md` первым** — там вся бизнес-логика и формулы
- **Не запускать команды** — только создавать и изменять файлы
- **Условные поля:** после первоначального импорта из витрин см. [etl_kgd_gold_vitrines.md](etl_kgd_gold_vitrines.md); обжалования (KPI 6) — отдельный источник
- **Суммы** — BigIntegerField (тенге), в миллионах только для отображения
- **RLS** — RegionScopedMixin во всех ViewSet с данными регионов
- **AuditLog** — логировать в каждом сервисном методе
- **Тесты** — только в Спринте 16

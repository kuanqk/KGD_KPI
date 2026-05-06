# Архив выполненных спринтов (0–17)

---

## Спринт 0 — Инициализация проекта ✅

**Что создано:**
- Django проект в `config/` (settings/base, dev, prod, test, ci)
- 5 apps: core, regions, etl, kpi, reports
- Docker Compose: web, db, redis, worker, beat, frontend, nginx
- requirements.txt, Makefile, .env.example, .gitignore

---

## Спринт 1 — Модели: core + regions ✅

**Тесты: 29/29 OK**

**Что создано:**
- `User` (AbstractUser + role + mac_address)
- `UserRegion` (M2M RLS-привязка)
- `AuditLog` (10 типов событий + метод `.log()`)
- `RegionScopedQuerySet` / `RegionScopedMixin`
- `Region` (code, name_ru/kz/en, is_summary, order)
- Фикстура: 20 ДГД + КГД

---

## Спринт 2 — Модели: etl ✅

**Тесты: 32/32 OK**

**Что создано:**
- `ImportJob` (4 источника, 4 статуса)
- `CompletedInspection` (с индексами, BigIntegerField для сумм)
- `ActiveInspection`
- `AppealDecision`
- `ManualInput` (unique по region+year)

---

## Спринт 3 — Модели: kpi + reports ✅

**Что создано:**
- `KPIFormula` (версионирование, `get_active()`)
- `KPIResult` (plan, fact, percent, score, calc_details)
- `KPISummary` (6 KPI баллов + rank)
- `ReportApproval` (workflow)
- Management command `init_formulas` (создаёт v1 для 6 KPI)

---

## Спринт 4 — ETL: импорт и нормализация ✅

**Тесты: 31/31 OK**

**Что создано:**
- `DataNormalizer` — маппинг полей, маршрутизация ИНИС/ИСНА по дате 09.07.2025
- `KGDImporter` — run(), bulk_create (batch 500); `_fetch_from_kgd_db()` — SQL к витринам `audit_kpi_data_gold` при `KGD_DB_HOST`, иначе заглушки для CI/dev (см. [etl_kgd_gold_vitrines.md](etl_kgd_gold_vitrines.md))
- Celery task `run_import_job` (max_retries=3, exponential backoff)

---

## Спринт 5 — KPI Engine ✅

**Тесты: 60/60 OK**

**Что создано:**
- `KPIEngine` со всеми 6 методами расчёта
- `calculate_all()` с ранжированием (КГД rank=None)
- Helper utils: `safe_div`, `to_decimal`, `apply_score`, `count_months`
- Celery task `calculate_kpi`

**Проверено на реальных данных Excel 01.01.2026.**

---

## Спринт 6 — REST API: core + regions + etl ✅

**Что создано:**
- JWT `LoginView` / `LogoutView` с AuditLog
- `UserViewSet` (CRUD), `AuditLogViewSet` (read-only, cursor pagination)
- Permissions: IsAdmin, IsOperator, IsReviewer, IsViewer, IsOperatorOrAdmin
- `RegionListView` (без пагинации, 21 запись)
- `ImportJobViewSet`: create → `run_import_job.delay()`
- `CompletedInspectionViewSet`: partial_update флагов
- `ManualInputViewSet`: валидация kbk_share_pct

---

## Спринт 7 — REST API: kpi + reports ✅

**Что создано:**
- `KPIFormulaViewSet`: атомарное версионирование
- `KPIResultViewSet` / `KPISummaryViewSet`: RLS через RegionScopedMixin
- `CalculateView`: POST → 202 + task_id
- Фильтры: region, date_from, date_to, kpi_type, status
- `PendingReportsView`, `ApproveView`, `RejectView`, `RecalculateView`
- `ExportXLSXView` / `ExportPDFView`

---

## Спринт 8 — Celery: задачи и расписание ✅

*(Был реализован параллельно в Спринте 5)*

**Что есть:**
- `scheduled_kpi_calculation()` — Celery Beat, ежедневно в 06:00 UTC
- `export_to_xlsx` / `export_to_pdf` tasks
- `CELERY_BEAT_SCHEDULE` с настраиваемым `CELERY_BEAT_HOUR`

---

## Спринт 9 — Vue: Auth + Dashboard + карта ✅

**Что создано:**
- Vue 3 + Vite + Pinia + Vue Router + Axios
- JWT auth store с auto-refresh
- Route guards по роли
- Leaflet карта: 20 регионов, цветовые маркеры
- Таблица рейтинга с ранговыми бейджами
- `KPIScoreCard` компонент
- GeoJSON центроиды для 20 регионов

---

## Спринты 10–12 — Vue: KPI детали, Оператор, Проверяющий ✅

**Что создано:**
- `KPIDetailView`: 6 карточек + таблица + Chart.js
- `CompareView`: два периода, дельта
- `KPITable` / `KPIChart` компоненты
- `ImportView`: ETL + 3с polling
- `DataEditorView`: inline флаги, аномалии
- `FormulasView`: версии формул
- `CalculateView`: запуск расчёта + polling
- `ManualInputView`: КБК + штат, валидация суммы = 100%
- `ApprovalView`: утвердить/вернуть/пересчитать
- `HistoryView`: архив отчётов

---

## Спринт 13 — Vue: Администратор ✅

**Что создано:**
- `UsersView`: CRUD, роли, MAC, viewer → регионы
- `AuditLogsView`: 10 типов событий с иконками, cursor pagination
- `ETLMonitorView`: stat cards, progress bars, авто-обновление 10с

---

## Спринт 14 — Экспорт PDF + XLSX ✅

**Что создано:**
- `XLSXExporter`: 7 листов (рейтинг + 6 KPI), цветовая кодировка
- `PDFExporter`: WeasyPrint + HTML шаблон A4 landscape
- `templates/reports/kpi_report.html`

---

## Спринт 15 — Безопасность ✅

**Что создано:**
- `MACAddressMiddleware`: блокировка при несовпадении MAC
- Rate limiting: 5 req/мин на login
- prod.py: HSTS, SSL redirect, secure cookies
- Проверен RLS во всех ViewSet

---

## Спринт 16 — Тесты KPI Engine ✅

**7 тест-классов, ~270 строк:**
- KPI1–6 с реальными числами из Excel 01.01.2026
- KPI3: 80–89% → 0 баллов (не 5!)
- KPI3: ДФНО исключён из суммы и кол-ва
- KPI6: акты >2 лет исключены
- Рейтинг: КГД rank=None, 20 ДГД уникальные ранги

---

## Спринт 17 — Docker Compose + CI ✅

**Что создано/обновлено:**
- `Makefile`: logs, restart, superuser
- `docker-compose.yml`: healthchecks, restart policies
- `config/settings/ci.py`: CI настройки
- `.github/workflows/ci.yml`: test + lint jobs

---

## Загрузка тестовых данных (вне спринтов)

**`load_test_data` management command:**
- Данные из Excel `Статистика_КЭР_РК_на_01_01_2026.xlsx`
- ManualInput: 20 ДГД (КБК + штат)
- CompletedInspection: 2025 год (2253 записи) + 2024 год (2253 записи)
- ActiveInspection: 471 запись
- AppealDecision: 36 записей
- KPIResult 2024: 40 записей (база для расчёта плана)

**Результат расчёта на тестовых данных:**
- Место 1: Алматинская (~100 баллов)
- Место 20: Акмолинская (~35 баллов)
- K4, K5, K6 совпадают с Excel точно
- K1, K2, K3 близко (небольшие отклонения из-за синтетического распределения)

# sprints.md — План спринтов: KGD KPI Monitor

> Каждый спринт = одна задача для Claude Code.
> Перед каждой задачей Claude Code читает `claude.md` (бизнес-логика) и `docs/DEV.md` (архитектура).
> Поля БД пока условные — заменить после получения schema от Олжаса.

---

## Статус спринтов

| # | Спринт | Статус |
|---|--------|--------|
| 0 | Инициализация проекта | ✅ Выполнен |
| 1 | Модели: core + regions | ✅ Выполнен |
| 2 | Модели: etl | ⬜ Не начат |
| 3 | Модели: kpi + reports | ⬜ Не начат |
| 4 | ETL: импорт и нормализация | ⬜ Не начат |
| 5 | KPI Engine: расчёт всех 6 KPI | ⬜ Не начат |
| 6 | REST API: core + regions + etl | ⬜ Не начат |
| 7 | REST API: kpi + reports | ⬜ Не начат |
| 8 | Celery: задачи и расписание | ⬜ Не начат |
| 9 | Vue: Auth + Dashboard + карта | ⬜ Не начат |
| 10 | Vue: KPI детали + сравнение | ⬜ Не начат |
| 11 | Vue: Оператор (импорт, формулы, расчёт) | ⬜ Не начат |
| 12 | Vue: Проверяющий + история | ⬜ Не начат |
| 13 | Vue: Администратор | ⬜ Не начат |
| 14 | Экспорт PDF + XLSX | ⬜ Не начат |
| 15 | Безопасность: MAC, RLS, JWT | ⬜ Не начат |
| 16 | Тесты KPI Engine | ⬜ Не начат |
| 17 | Docker Compose + CI | ⬜ Не начат |
| 18 | Замена условных полей на реальные | ⬜ Ждёт schema БД |

---

## Спринт 0 — Инициализация проекта

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Инициализируй Django-проект kgd_kpi со следующей структурой:

1. Django-проект в папке config/ (не в корне)
2. Создай apps: core, regions, etl, kpi, reports — каждый через startapp
3. Настрой config/settings/base.py:
   - INSTALLED_APPS со всеми apps
   - Кастомная модель пользователя: AUTH_USER_MODEL = 'core.User'
   - REST_FRAMEWORK настройки (JWT аутентификация, pagination)
   - CELERY_BROKER_URL из env
   - LANGUAGE_CODE = 'ru-ru', поддержка i18n (ru, kk, en)
   - CORS настройки для Vue фронта
4. config/settings/dev.py — DEBUG=True, PostgreSQL из env
5. config/settings/prod.py — DEBUG=False, HTTPS, HSTS
6. config/celery.py — Celery app
7. requirements.txt:
   django>=5.0, djangorestframework, djangorestframework-simplejwt,
   django-cors-headers, celery, redis, psycopg2-binary,
   openpyxl, weasyprint, django-filter, django-ratelimit, Pillow
8. docker-compose.yml: web, db, redis, worker, beat, nginx
9. Dockerfile для Django
10. .env.example с переменными из DEV.md раздел 5
11. manage.py в корне
12. .gitignore

Структура папок должна точно совпадать с docs/DEV.md раздел 1.
```

---

## Спринт 1 — Модели: core + regions

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй модели для apps/core и apps/regions строго по docs/DEV.md раздел 2.1 и 2.2.

apps/core/models.py:
- User (AbstractUser) с полем role и mac_address
- UserRegion (M2M связь User ↔ Region)
- AuditLog со всеми типами событий из DEV.md

apps/core/mixins.py:
- RegionScopedQuerySet
- RegionScopedMixin

apps/regions/models.py:
- Region с полями: code, name_ru, name_kz, name_en, is_summary, order

apps/regions/fixtures/regions.json:
- Все 20 ДГД + КГД из справочника в claude.md
- is_summary=True только для КГД

apps/core/admin.py — зарегистрировать User, AuditLog
apps/regions/admin.py — зарегистрировать Region

Создай и примени миграции.
Напиши тесты в apps/core/tests/ и apps/regions/tests/.
```

---

## Спринт 2 — Модели: etl

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй модели для apps/etl строго по docs/DEV.md раздел 2.3.

Модели:
- ImportJob
- CompletedInspection (с индексами)
- ActiveInspection
- AppealDecision
- ManualInput

Важно:
- Все суммы хранить в BigIntegerField (тенге, целые)
- Индексы как в DEV.md
- unique_together ('source', 'source_id') для исходных данных

apps/etl/admin.py — зарегистрировать все модели с list_display
Создай и примени миграции.
Напиши базовые тесты в apps/etl/tests/test_models.py.
```

---

## Спринт 3 — Модели: kpi + reports

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй модели для apps/kpi и apps/reports строго по docs/DEV.md раздел 2.4 и 2.5.

apps/kpi/models.py:
- KPIFormula с методом get_active(kpi_type)
- KPIResult
- KPISummary

apps/reports/models.py:
- ReportApproval

apps/kpi/admin.py — KPIFormula, KPIResult, KPISummary
apps/reports/admin.py — ReportApproval

Создай и примени миграции.
Напиши тесты в apps/kpi/tests/test_models.py.

Добавь management command: python manage.py init_formulas
— создаёт начальные KPIFormula (версия 1) для всех 6 KPI
с конфигурацией порогов из claude.md.
```

---

## Спринт 4 — ETL: импорт и нормализация

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй ETL-сервисный слой в apps/etl/services/.

apps/etl/services/normalizer.py:
- Класс DataNormalizer
- Метод normalize_completed_inspection(raw_row: dict) → CompletedInspection
  Логика маршрутизации: если запись.дата < 09.07.2025 → source='inis', иначе source='isna'
  Условные поля маппить согласно таблице в claude.md раздел "Условные поля БД"
- Метод normalize_active_inspection(raw_row: dict) → ActiveInspection
- Метод normalize_appeal(raw_row: dict) → AppealDecision

apps/etl/services/importer.py:
- Класс KGDImporter
- __init__(self, job: ImportJob)
- run() → запускает импорт, обновляет ImportJob.status
- _fetch_from_kgd_db() → подключение к внешней БД КГД через env KGD_DB_*
  (пока: заглушка, возвращает тестовые данные)
- _bulk_create(records) → batch insert с обработкой дубликатов

apps/etl/tasks.py:
- run_import_job(job_id) — Celery задача, вызывает KGDImporter

Напиши тесты в apps/etl/tests/test_services.py с mock данными.
```

---

## Спринт 5 — KPI Engine: расчёт всех 6 KPI

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md. Это центральный спринт — KPI Engine.

Реализуй apps/kpi/services/engine.py — класс KPIEngine.

Строго следуй формулам из claude.md:

calc_assessment(region) → KPIResult  [KPI 1]
  - Факт: SUM(amount_assessed) из CompletedInspection
    WHERE region=region, management='УНА', completed_date IN [date_from, date_to]
  - KPI_план: ManualInput.kbk_share_pct * общий план * 1.20
  - Баллы: ≥100%→10, ≥90%→5, <90%→0

calc_collection(region) → KPIResult  [KPI 2]
  - Факт: SUM(amount_collected) WHERE + is_accepted=True
  - Баллы: ≥100%→40, ≥90%→20, ≥80%→10, <80%→0

calc_avg_assessment(region) → KPIResult  [KPI 3]
  - Сумма и кол-во: WHERE management='УНА', is_counted=True, form_type != 'ДФНО'
  - KPI_план: единый порог = среднее по всем 20 ДГД за прошлый год * 1.20
  - Баллы: ≥100%→10, ≥90%→5, <90%→0  (80-89% тоже 0!)

calc_workload(region) → KPIResult  [KPI 4]
  - Кол-во: COUNT завершённых, management='УНА', is_counted=True
  - staff: ManualInput.staff_count
  - months: кол-во полных месяцев в периоде
  - Баллы: ≥0.5→15, ≥0.4→5, <0.4→0

calc_long_inspections(region) → KPIResult  [KPI 5]
  - Все: COUNT(ActiveInspection) WHERE is_counted=True, region=region
  - Долгие: COUNT WHERE (date_to - prescription_date) > 180
  - Баллы: <20%→10, ≥20%→0

calc_cancelled(region) → KPIResult  [KPI 6]
  - Отменено: SUM(AppealDecision.amount_cancelled) WHERE is_counted=True
  - Доначислено: Факт из KPI 1
  - Баллы: ≤1%→15, ≤2%→5, >2%→0

calculate_all(regions) → list[KPISummary]
  - Рассчитать все 6 KPI для всех регионов
  - Сохранить KPIResult для каждого
  - Сохранить KPISummary (сумма баллов)
  - Назначить ранги (КГД — is_summary=True — не ранжируется)
  - Всё логировать в AuditLog

apps/kpi/tasks.py:
- calculate_kpi(date_from, date_to, region_ids, user_id) — Celery задача

ОБЯЗАТЕЛЬНО: тесты в apps/kpi/tests/test_engine.py
- Тест каждого из 6 KPI с известными входными данными
- Тест граничных случаев (NULL, деление на 0, нет данных)
- Тест итогового ранжирования
```

---

## Спринт 6 — REST API: core + regions + etl

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй REST API для apps/core, apps/regions, apps/etl.
Все эндпоинты из docs/DEV.md раздел 3.

apps/core/:
- serializers.py: UserSerializer, AuditLogSerializer
- views.py: LoginView (JWT), LogoutView, UserViewSet, AuditLogViewSet
- permissions.py: IsAdmin, IsOperator, IsReviewer, IsViewer, IsOperatorOrAdmin
- urls.py

apps/regions/:
- serializers.py: RegionSerializer
- views.py: RegionListView (только чтение, все роли)
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

Напиши тесты в tests/test_api.py — проверить права доступа для каждой роли.
```

---

## Спринт 7 — REST API: kpi + reports

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй REST API для apps/kpi и apps/reports.

apps/kpi/:
- serializers.py: KPIFormulaSerializer, KPIResultSerializer, KPISummarySerializer
- views.py:
  - KPIFormulaViewSet (list, create) — Оператор
  - KPIResultViewSet (list, retrieve) — все роли (RLS через RegionScopedMixin)
  - KPISummaryViewSet (list, retrieve) — все роли (RLS)
  - CalculateView (POST) — Оператор, запускает Celery задачу
- filters.py — фильтры по региону, периоду, типу KPI
- urls.py

apps/reports/:
- serializers.py: ReportApprovalSerializer
- views.py:
  - PendingReportsView — Проверяющий
  - ApproveView, RejectView, RecalculateView — Проверяющий
  - ExportXLSXView, ExportPDFView — все роли
- urls.py

Все View с RLS использовать RegionScopedMixin из apps/core/mixins.py.
Напиши тесты прав доступа для каждой роли.
```

---

## Спринт 8 — Celery: задачи и расписание

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md.

Реализуй все Celery задачи из docs/DEV.md раздел 4.

apps/etl/tasks.py:
- run_import_job(job_id) — запуск импорта, max_retries=3, exponential backoff

apps/kpi/tasks.py:
- calculate_kpi(date_from, date_to, region_ids, user_id)
- scheduled_kpi_calculation() — для Celery Beat

apps/reports/tasks.py:
- export_to_xlsx(summary_id, user_id)
- export_to_pdf(summary_id, user_id)

config/celery.py:
- Настроить CELERY_BEAT_SCHEDULE: автоматический расчёт раз в сутки (настраиваемый)

Каждая задача:
- Обновляет статус в ImportJob / KPIResult
- Логирует в AuditLog (start, success, error)
- При ошибке: retry с backoff, затем status='error' + error_message

Напиши тесты с mock для всех задач.
```

---

## Спринт 9 — Vue: Auth + Dashboard + карта

**Промпт для Claude Code:**
```
Прочитай claude.md.

Инициализируй Vue 3 проект в папке frontend/ (Vite + Vue 3 + Pinia + Vue Router).

Реализуй:

1. frontend/src/api/client.js — Axios с JWT interceptors (auto-refresh)

2. frontend/src/stores/auth.js — Pinia store: login, logout, роль пользователя

3. frontend/src/router/index.js — все маршруты из DEV.md раздел 6
   - Route guards: проверка роли перед входом на страницу

4. frontend/src/views/LoginView.vue — форма логина

5. frontend/src/views/DashboardView.vue:
   - SVG/Leaflet карта Казахстана с 20 регионами
   - Цветовая индикация по баллам: зелёный (≥80), жёлтый (50–79), красный (<50)
   - Таблица рейтинга ДГД (позиция, регион, баллы итого, каждый KPI)
   - Клик по региону → переход на /kpi/:region
   - RLS: наблюдатель видит только свои регионы подсвеченными

6. frontend/src/components/KPIScoreCard.vue — карточка одного KPI (балл, факт, план, %)

Стили: минималистичные, цвета КГД (синий #1F4E79 как акцент).
```

---

## Спринт 10 — Vue: KPI детали + сравнение

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй страницы детального просмотра KPI.

frontend/src/views/KPIDetailView.vue:
- Фильтры: период (date_from / date_to), регион, управление
- Таблица результатов по всем ДГД
- График динамики (Chart.js — линейный)
- Для каждого KPI — своя логика отображения (баллы, факт, план, %)
- Экспорт кнопки (XLSX, PDF) — вызов API

frontend/src/views/CompareView.vue:
- Выбор двух периодов
- Side-by-side таблица: период А vs период Б
- Дельта баллов по каждому KPI

frontend/src/components/KPITable.vue — переиспользуемая таблица
frontend/src/components/KPIChart.vue — Chart.js обёртка
```

---

## Спринт 11 — Vue: Оператор

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй страницы для роли Оператор.

frontend/src/views/ImportView.vue:
- Кнопка "Запустить импорт из БД КГД"
- Список ImportJob с статусом (pending/running/done/error)
- Прогресс в реальном времени (polling каждые 3 сек)

frontend/src/views/DataEditorView.vue:
- Таблица CompletedInspection с фильтрами
- Inline-редактирование флагов is_counted, is_accepted
- Кнопка "Пометить аномалию"

frontend/src/views/FormulasView.vue:
- Список версий KPIFormula
- Форма создания новой версии (JSON-редактор порогов)

frontend/src/views/CalculateView.vue:
- Выбор периода (date_from / date_to)
- Выбор регионов (или "все")
- Кнопка "Рассчитать" → Celery задача → polling статуса
- Кнопка "Отправить на утверждение"

frontend/src/views/ManualInputView.vue:
- Форма ввода kbk_share_pct и staff_count для каждого ДГД
- Год выбирается из дропдауна
```

---

## Спринт 12 — Vue: Проверяющий + история

**Промпт для Claude Code:**
```
Прочитай claude.md.

frontend/src/views/ApprovalView.vue:
- Список отчётов со статусом "submitted"
- Для каждого: регион, период, баллы итого, все 6 KPI
- Кнопки: "Утвердить" / "Вернуть" (с полем комментария) / "Запросить пересчёт"

frontend/src/views/HistoryView.vue:
- Архив утверждённых отчётов
- Фильтры: период, регион, статус
- Ссылки на экспорт PDF/XLSX
```

---

## Спринт 13 — Vue: Администратор

**Промпт для Claude Code:**
```
Прочитай claude.md.

frontend/src/views/UsersView.vue:
- CRUD пользователей
- Назначение роли из дропдауна
- Для роли viewer — привязка регионов (мультиселект)
- MAC-адрес пользователя

frontend/src/views/AuditLogsView.vue:
- Таблица AuditLog с фильтрами (пользователь, тип события, дата)
- Без пагинации — cursor-based

frontend/src/views/ETLMonitorView.vue:
- Статус всех ImportJob
- Ошибки последних импортов
- Статус Celery workers (ping)
```

---

## Спринт 14 — Экспорт PDF + XLSX

**Промпт для Claude Code:**
```
Прочитай claude.md.

Реализуй экспорт отчётов.

apps/reports/services/xlsx_exporter.py:
- Класс XLSXExporter(summary: KPISummary)
- generate() → BytesIO
- Лист 1: Сводный рейтинг (20 ДГД, все KPI, баллы, позиции)
- Лист 2–7: детали по каждому KPI
- Форматирование: заморозка строк, цветовые маркеры (зелёный/жёлтый/красный)
- Логотип КГД в шапке, дата, версия расчёта

apps/reports/services/pdf_exporter.py:
- Класс PDFExporter(summary: KPISummary)
- generate() → BytesIO (WeasyPrint)
- HTML-шаблон: templates/reports/kpi_report.html
- В шапке: герб КГД, период, дата генерации, версия формулы

Оба экспортёра логируют в AuditLog.
Тесты: проверить что файлы генерируются без ошибок.
```

---

## Спринт 15 — Безопасность

**Промпт для Claude Code:**
```
Прочитай claude.md и docs/DEV.md раздел 7.

Реализуй:

1. apps/core/middleware.py — MACAddressMiddleware
   - При логине: проверить mac_address из запроса с User.mac_address
   - Если не совпадает → 403
   - Логировать попытки в AuditLog

2. apps/core/permissions.py — все DRF Permission-классы из DEV.md

3. Проверить RLS во всех ViewSet:
   - Для роли viewer: все QuerySet должны проходить через RegionScopedMixin
   - Написать тест: viewer не может получить данные чужого региона

4. config/settings/prod.py:
   - SECURE_HSTS_SECONDS = 31536000
   - SESSION_COOKIE_SECURE = True
   - CSRF_COOKIE_SECURE = True
   - SECURE_SSL_REDIRECT = True

5. Rate limiting на /api/v1/auth/login/ — django-ratelimit: 5 запросов/мин

6. CORS настройки — разрешить только домен Vue фронта
```

---

## Спринт 16 — Тесты KPI Engine

**Промпт для Claude Code:**
```
Прочитай claude.md. Этот спринт — валидация бизнес-логики.

Реализуй полный набор тестов в apps/kpi/tests/test_engine.py.

Для каждого из 6 KPI напиши тесты:

1. Нормальный случай — входные данные → ожидаемые баллы
   Используй конкретные числа из claude.md (формулы)

2. Граничные случаи:
   - Ровно 100% → должно дать максимум баллов
   - 99.9% → на балл меньше
   - 0 проверок → баллы = 0, не ошибка
   - NULL суммы → баллы = 0

3. KPI 3 специфика:
   - Диапазон 80–89% → 0 баллов (не 5!)
   - ДФНО исключён из суммы и кол-ва

4. KPI 4: проверить расчёт Месяцев для разных периодов

5. KPI 6: проверить исключение актов >2 лет

6. Итоговый ранжирование:
   - КГД (is_summary=True) не получает ранг
   - 20 ДГД получают ранги 1–20 без дублей

Цель: результаты должны совпасть с ручным расчётом Олжаса.
```

---

## Спринт 17 — Docker Compose + CI

**Промпт для Claude Code:**
```
Прочитай claude.md.

1. Доработай docker-compose.yml:
   - Все 7 сервисов из DEV.md раздел 1
   - Healthcheck для db и redis
   - Volumes для PostgreSQL данных
   - .env файл через env_file

2. docker/nginx.conf:
   - /api/ → Django (web:8000)
   - / → Vue (frontend:80)
   - TLS заглушка (самоподписанный сертификат для dev)

3. Dockerfile.backend — многоэтапная сборка Django
4. Dockerfile.frontend — Vue build + nginx

5. Makefile с командами:
   make build    — сборка контейнеров
   make up       — запуск
   make down     — остановка
   make migrate  — миграции
   make seed     — загрузка фикстур (регионы + начальные формулы)
   make test     — запуск всех тестов
   make shell    — Django shell

6. GitHub Actions (или GitLab CI) .yml:
   - При push: запуск тестов
   - При merge в main: сборка Docker образов
```

---

## Спринт 18 — Замена условных полей на реальные

> ⚠️ Этот спринт выполнять ТОЛЬКО после получения schema БД КГД от Олжаса.

**Промпт для Claude Code:**
```
Прочитай claude.md (таблица "Условные поля БД").

Получена реальная schema БД КГД. Нужно:

1. Обновить таблицу условных полей в claude.md — заменить на реальные названия

2. apps/etl/services/normalizer.py:
   - Обновить маппинг полей в normalize_*() методах
   - Реализовать реальное подключение к БД КГД в _fetch_from_kgd_db()
     (убрать заглушку из Спринта 4)

3. apps/kpi/services/engine.py:
   - Проверить все ORM-запросы — поля должны совпадать с реальными
   - Запустить тесты из Спринта 16

4. Провести сверку: запустить расчёт за 01.01.2026,
   сравнить результаты с файлом Статистика_КЭР_РК_на_01_01_2026.xlsx

5. Зафиксировать расхождения и согласовать с Олжасом.
```

---

## Примечания для Claude Code

- **Всегда читать `claude.md` первым** — там вся бизнес-логика
- **Условные поля** — не менять до Спринта 18, использовать как есть
- **Суммы** — хранить в тенге (целые BigInteger), в миллионах только для отображения
- **RLS** — не забывать RegionScopedMixin во всех view
- **AuditLog** — логировать в каждом сервисном методе
- **Тесты** — писать в каждом спринте, не откладывать

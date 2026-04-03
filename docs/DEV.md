> ⚠️ Этот файл устарел. Актуальная документация находится в папке docs/
> Оставлен для исторической справки.

# DEV.md — Техническое задание: KGD KPI Monitor

> Читать вместе с `claude.md` — там вся бизнес-логика KPI и формулы.
> Этот документ описывает архитектуру, модели, API и соглашения по коду.

---

## 1. Архитектура

### Backend (Django)
```
config/                     # Настройки проекта
├── settings/base.py        # Общие настройки
├── settings/dev.py         # DEV: DEBUG=True, SQLite опционально
├── settings/prod.py        # PROD: PostgreSQL, HTTPS, HSTS
├── urls.py                 # Корневой роутер → /api/v1/
└── celery.py               # Celery app

apps/
├── core/                   # Пользователи, роли, RLS, аудит
├── regions/                # Справочник ДГД
├── etl/                    # ETL: импорт, нормализация
├── kpi/                    # KPI Engine
└── reports/                # Утверждение, экспорт
```

### Frontend (Vue 3)
```
frontend/
├── src/
│   ├── views/              # Страницы (Dashboard, KPI Detail, Reports...)
│   ├── components/         # Переиспользуемые компоненты
│   ├── stores/             # Pinia stores
│   ├── api/                # Axios-клиент + endpoints
│   └── router/             # Vue Router
└── vite.config.js
```

### Инфраструктура (Docker Compose)
| Сервис | Технология | Порт |
|--------|-----------|------|
| web | Django + Gunicorn | 8000 |
| frontend | Vue 3 + Nginx | 3000 |
| db | PostgreSQL 16 | 5432 |
| redis | Redis 7 | 6379 |
| worker | Celery | — |
| beat | Celery Beat | — |
| nginx | Nginx (reverse proxy) | 80/443 |

---

## 2. Django-приложения и модели

### 2.1 `apps/core` — Пользователи и безопасность

```python
# models.py

class User(AbstractUser):
    ROLES = [
        ('admin', 'Администратор'),
        ('operator', 'Оператор'),
        ('reviewer', 'Проверяющий'),
        ('viewer', 'Наблюдатель'),
    ]
    role = models.CharField(max_length=20, choices=ROLES)
    mac_address = models.CharField(max_length=17, blank=True)  # MAC-привязка
    regions = models.ManyToManyField('regions.Region', through='UserRegion', blank=True)

class UserRegion(models.Model):
    """Привязка наблюдателей к регионам (RLS)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'region')

class AuditLog(models.Model):
    EVENTS = [
        ('import', 'Импорт данных'),
        ('formula_change', 'Изменение формулы'),
        ('kpi_calc', 'Расчёт KPI'),
        ('login', 'Вход'),
        ('logout', 'Выход'),
        ('export', 'Экспорт'),
        ('manual_input', 'Ручной ввод'),
        ('correction', 'Корректировка'),
        ('user_mgmt', 'Управление учёткой'),
        ('approval', 'Утверждение отчёта'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    event = models.CharField(max_length=30, choices=EVENTS)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    mac_address = models.CharField(max_length=17, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

**RLS — RegionScopedQuerySet:**
```python
# core/mixins.py
class RegionScopedQuerySet(models.QuerySet):
    def for_user(self, user):
        if user.role in ('admin', 'operator', 'reviewer'):
            return self
        # viewer — только свои регионы
        return self.filter(region__in=user.regions.all())

class RegionScopedMixin:
    """Миксин для всех View — автоматически фильтрует по роли"""
    def get_queryset(self):
        return super().get_queryset().for_user(self.request.user)
```

---

### 2.2 `apps/regions` — Справочник ДГД

```python
class Region(models.Model):
    code = models.CharField(max_length=4, unique=True)  # '06xx', '62xx'
    name_ru = models.CharField(max_length=100)
    name_kz = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    is_summary = models.BooleanField(default=False)  # True для КГД (итого)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name_ru
```

**Фикстура:** все 20 ДГД + КГД загружаются через `regions/fixtures/regions.json`.

---

### 2.3 `apps/etl` — Импорт и нормализация

```python
class ImportJob(models.Model):
    SOURCES = [('inis', 'ИНИС'), ('isna', 'ИСНА'), ('dgd', 'Данные ДГД'), ('appeals', 'Обжалования')]
    STATUSES = [('pending', 'Ожидание'), ('running', 'Выполняется'), ('done', 'Завершено'), ('error', 'Ошибка')]

    source = models.CharField(max_length=20, choices=SOURCES)
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    started_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    records_total = models.IntegerField(default=0)
    records_imported = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    params = models.JSONField(default=dict)  # date_from, date_to и др.

class CompletedInspection(models.Model):
    """Нормализованная таблица завершённых проверок (ИНИС + ИСНА)"""
    # Источник
    source = models.CharField(max_length=10, choices=[('inis', 'ИНИС'), ('isna', 'ИСНА')])
    source_id = models.CharField(max_length=100)  # ID записи в источнике
    import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE)

    # Ключевые поля (условные имена — заменить после получения schema)
    region = models.ForeignKey('regions.Region', on_delete=models.PROTECT)
    management = models.CharField(max_length=20)         # УНА / УКН / УНН / ...
    form_type = models.CharField(max_length=50)          # ДФНО / обычная / ...
    completed_date = models.DateField()

    # Суммы (в тенге, целые числа для точности)
    amount_assessed = models.BigIntegerField(default=0)  # Доначислено
    amount_collected = models.BigIntegerField(default=0) # Взыскано

    # Флаги учёта (проставляются оператором)
    is_counted = models.BooleanField(default=False)      # Для KPI 3
    is_accepted = models.BooleanField(default=False)     # Для KPI 1, 2
    is_anomaly = models.BooleanField(default=False)      # Помечено оператором

    # Метаданные
    raw_data = models.JSONField(default=dict)            # Исходная запись
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('source', 'source_id')
        indexes = [
            models.Index(fields=['region', 'management', 'completed_date']),
            models.Index(fields=['is_counted', 'is_accepted']),
        ]

class ActiveInspection(models.Model):
    """Проводимые (текущие) проверки"""
    source = models.CharField(max_length=10)
    source_id = models.CharField(max_length=100)
    import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE)

    region = models.ForeignKey('regions.Region', on_delete=models.PROTECT)
    management = models.CharField(max_length=20)
    case_type = models.CharField(max_length=50)           # Тип дела
    prescription_date = models.DateField()                # Дата вручения предписания
    is_counted = models.BooleanField(default=False)

    raw_data = models.JSONField(default=dict)

    class Meta:
        unique_together = ('source', 'source_id')

class AppealDecision(models.Model):
    """Отменённые акты (обжалования)"""
    source_id = models.CharField(max_length=100, unique=True)
    import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE)

    region = models.ForeignKey('regions.Region', on_delete=models.PROTECT)
    amount_cancelled = models.BigIntegerField(default=0)  # Отменённая сумма
    is_counted = models.BooleanField(default=False)
    completion_date = models.DateField()                   # Дата завершения акта
    decision_date = models.DateField()                     # Дата решения Апелл. комиссии

    raw_data = models.JSONField(default=dict)

class ManualInput(models.Model):
    """Ручные вводы оператора"""
    region = models.ForeignKey('regions.Region', on_delete=models.PROTECT)
    year = models.PositiveSmallIntegerField()
    kbk_share_pct = models.DecimalField(max_digits=8, decimal_places=4, null=True)  # Доля по 4 КБК
    staff_count = models.PositiveSmallIntegerField(null=True)                         # Кол-во сотрудников
    entered_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('region', 'year')
```

---

### 2.4 `apps/kpi` — KPI Engine

```python
class KPIFormula(models.Model):
    """Версионированные конфигурации формул"""
    KPI_TYPES = [
        ('assessment', 'KPI 1 — Доначисление'),
        ('collection', 'KPI 2 — Взыскание'),
        ('avg_assessment', 'KPI 3 — Среднее доначисление'),
        ('workload', 'KPI 4 — Занятость'),
        ('long_inspections', 'KPI 5 — Проверки > 6 мес.'),
        ('cancelled', 'KPI 6 — Отменённые суммы'),
    ]
    kpi_type = models.CharField(max_length=30, choices=KPI_TYPES)
    version = models.PositiveSmallIntegerField()
    config = models.JSONField()        # Пороги баллов, параметры
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('kpi_type', 'version')

    @classmethod
    def get_active(cls, kpi_type):
        return cls.objects.filter(kpi_type=kpi_type, is_active=True).latest('version')


class KPIResult(models.Model):
    """Результат расчёта одного KPI для одного ДГД за один период"""
    STATUSES = [('draft', 'Черновик'), ('submitted', 'На утверждении'), ('approved', 'Утверждён'), ('rejected', 'Возвращён')]

    region = models.ForeignKey('regions.Region', on_delete=models.PROTECT)
    kpi_type = models.CharField(max_length=30, choices=KPIFormula.KPI_TYPES)
    formula = models.ForeignKey(KPIFormula, on_delete=models.PROTECT)

    # Период
    date_from = models.DateField()
    date_to = models.DateField()

    # Результаты
    plan = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    fact = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    percent = models.DecimalField(max_digits=8, decimal_places=4, null=True)
    score = models.PositiveSmallIntegerField(default=0)

    # Детали расчёта (для аудита и отладки)
    calc_details = models.JSONField(default=dict)

    status = models.CharField(max_length=20, choices=STATUSES, default='draft')
    calculated_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, related_name='calculated_kpis')
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('region', 'kpi_type', 'date_from', 'date_to', 'formula')
        indexes = [
            models.Index(fields=['region', 'date_from', 'date_to']),
            models.Index(fields=['status']),
        ]


class KPISummary(models.Model):
    """Итоговые баллы и рейтинг по всем 6 KPI для ДГД за период"""
    region = models.ForeignKey('regions.Region', on_delete=models.PROTECT)
    date_from = models.DateField()
    date_to = models.DateField()

    score_assessment = models.PositiveSmallIntegerField(default=0)      # KPI 1
    score_collection = models.PositiveSmallIntegerField(default=0)       # KPI 2
    score_avg_assessment = models.PositiveSmallIntegerField(default=0)   # KPI 3
    score_workload = models.PositiveSmallIntegerField(default=0)         # KPI 4
    score_long_inspections = models.PositiveSmallIntegerField(default=0) # KPI 5
    score_cancelled = models.PositiveSmallIntegerField(default=0)        # KPI 6
    score_total = models.PositiveSmallIntegerField(default=0)            # Сумма

    rank = models.PositiveSmallIntegerField(null=True)  # Позиция среди 20 ДГД

    status = models.CharField(max_length=20, choices=KPIResult.STATUSES, default='draft')
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('region', 'date_from', 'date_to')
```

**KPI Engine — сервисный слой:**
```python
# kpi/services/engine.py

class KPIEngine:
    """
    Основной расчётный движок.
    Использует: нормализованные данные из ETL + ManualInput + активные формулы.
    """
    def __init__(self, date_from: date, date_to: date, user):
        self.date_from = date_from
        self.date_to = date_to
        self.user = user
        self.months = self._count_months()

    def calculate_all(self, regions=None):
        """Рассчитать все 6 KPI для всех (или указанных) регионов"""
        if regions is None:
            regions = Region.objects.filter(is_summary=False)
        results = []
        for region in regions:
            summary = self._calculate_region(region)
            results.append(summary)
        self._assign_ranks(results)
        return results

    def _calculate_region(self, region) -> KPISummary:
        kpi1 = self.calc_assessment(region)
        kpi2 = self.calc_collection(region)
        kpi3 = self.calc_avg_assessment(region)
        kpi4 = self.calc_workload(region)
        kpi5 = self.calc_long_inspections(region)
        kpi6 = self.calc_cancelled(region)
        # Сохранить KPIResult для каждого + KPISummary
        ...

    def calc_assessment(self, region) -> KPIResult:
        """KPI 1 — Доначисление"""
        ...

    # ... остальные методы
```

---

### 2.5 `apps/reports` — Утверждение и экспорт

```python
class ReportApproval(models.Model):
    """Workflow утверждения отчёта"""
    ACTIONS = [('submit', 'Отправлено'), ('approve', 'Утверждено'), ('reject', 'Возвращено'), ('recalc', 'Запрос пересчёта')]

    summary = models.ForeignKey('kpi.KPISummary', on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTIONS)
    actor = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
```

---

## 3. REST API (Django REST Framework)

### Соглашения
- Базовый URL: `/api/v1/`
- Аутентификация: JWT (djangorestframework-simplejwt)
- Формат: JSON
- Пагинация: cursor-based для больших списков

### Основные эндпоинты

```
# Аутентификация
POST   /api/v1/auth/login/
POST   /api/v1/auth/logout/
POST   /api/v1/auth/token/refresh/

# Регионы
GET    /api/v1/regions/

# ETL / Импорт
GET    /api/v1/etl/jobs/
POST   /api/v1/etl/jobs/                    # Запустить импорт
GET    /api/v1/etl/jobs/{id}/
GET    /api/v1/etl/inspections/completed/   # Просмотр нормализованных данных
PATCH  /api/v1/etl/inspections/completed/{id}/  # Пометить аномалию / флаг

# Ручной ввод
GET    /api/v1/etl/manual-inputs/
POST   /api/v1/etl/manual-inputs/
PUT    /api/v1/etl/manual-inputs/{id}/

# Формулы KPI
GET    /api/v1/kpi/formulas/
POST   /api/v1/kpi/formulas/               # Новая версия формулы
GET    /api/v1/kpi/formulas/{id}/

# Расчёт KPI
POST   /api/v1/kpi/calculate/              # Запустить расчёт (Celery task)
GET    /api/v1/kpi/results/                # Список результатов
GET    /api/v1/kpi/results/{id}/
GET    /api/v1/kpi/summary/                # Сводный рейтинг (с фильтрами)

# Утверждение
GET    /api/v1/reports/pending/            # Ожидают утверждения
POST   /api/v1/reports/{id}/approve/
POST   /api/v1/reports/{id}/reject/
POST   /api/v1/reports/{id}/recalculate/

# Экспорт
GET    /api/v1/reports/{id}/export/xlsx/
GET    /api/v1/reports/{id}/export/pdf/

# Администрирование
GET    /api/v1/admin/users/
POST   /api/v1/admin/users/
PUT    /api/v1/admin/users/{id}/
GET    /api/v1/admin/audit-logs/
# Мониторинг импорта: GET /api/v1/etl/jobs/ (см. docs/architecture/api.md)
```

---

## 4. Celery-задачи

```python
# etl/tasks.py
@shared_task(bind=True, max_retries=3)
def run_import_job(self, job_id: int): ...

# kpi/tasks.py
@shared_task(bind=True)
def calculate_kpi(self, date_from: str, date_to: str, region_ids: list, user_id: int): ...

@shared_task
def scheduled_kpi_calculation(): ...   # Celery Beat — по расписанию

# reports/tasks.py
@shared_task
def export_to_xlsx(summary_id: int, user_id: int): ...

@shared_task
def export_to_pdf(summary_id: int, user_id: int): ...
```

---

## 5. Соглашения по коду

### Структура каждого app
```
apps/{app_name}/
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── permissions.py      # Кастомные DRF permissions
├── services/           # Бизнес-логика (не в views, не в models)
│   └── engine.py       # для kpi/
├── tasks.py            # Celery задачи
├── admin.py
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_api.py
└── migrations/
```

### Правила
- **Бизнес-логика — только в `services/`**, не в views и не в models
- **Views — только роутинг и сериализация**, никакой логики расчётов
- **Все суммы хранить в целых числах (тенге)**, конвертировать в млн только для отображения
- **Каждый публичный метод сервиса — логировать в AuditLog**
- **Тесты обязательны** для всех методов KPI Engine
- Использовать `select_related` / `prefetch_related` — не допускать N+1
- Все строки интерфейса через `django.utils.translation` (i18n)

### Permissions (DRF)
```python
# core/permissions.py
class IsAdmin(BasePermission): ...
class IsOperator(BasePermission): ...
class IsReviewer(BasePermission): ...
class IsViewer(BasePermission): ...
class IsOperatorOrAdmin(BasePermission): ...
```

### Переменные окружения (.env)
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=

DB_HOST=db
DB_PORT=5432
DB_NAME=kgd_kpi
DB_USER=
DB_PASSWORD=

REDIS_URL=redis://redis:6379/0

KGD_DB_HOST=          # Хост БД КГД (заполнить при получении доступа)
KGD_DB_PORT=
KGD_DB_NAME=
KGD_DB_USER=
KGD_DB_PASSWORD=
```

---

## 6. Фронтенд (Vue 3)

### Стек
- Vue 3 + Composition API
- Pinia (state management)
- Vue Router
- Axios (HTTP-клиент)
- Vite (сборка)
- Leaflet.js (карта Казахстана)
- Chart.js (графики KPI)

### Страницы
| Путь | Компонент | Роли |
|------|-----------|------|
| `/login` | LoginView | Все |
| `/dashboard` | DashboardView | Все (RLS) |
| `/kpi/:type` | KPIDetailView | Все (RLS) |
| `/compare` | CompareView | Все (RLS) |
| `/import` | ImportView | Оператор |
| `/data` | DataEditorView | Оператор |
| `/formulas` | FormulasView | Оператор |
| `/calculate` | CalculateView | Оператор |
| `/approve` | ApprovalView | Проверяющий |
| `/history` | HistoryView | Оператор, Проверяющий, Наблюдатель |
| `/manual-input` | ManualInputView | Оператор |
| `/admin/users` | UsersView | Администратор |
| `/admin/logs` | AuditLogsView | Администратор |
| `/admin/etl` | ETLMonitorView | Администратор |

---

## 7. Безопасность

- **JWT** — access token 15 мин, refresh 7 дней
- **MAC-адрес** — проверка при логине (middleware)
- **RLS** — `RegionScopedQuerySet` во всех view для роли `viewer`
- **HTTPS** — обязательно в prod (Nginx + сертификат)
- **CORS** — только разрешённые origins (Vue фронт)
- **Rate limiting** — django-ratelimit на `/api/v1/auth/`
- **ЭЦП** — заглушка в архитектуре, реализовать в следующей версии

---

## 8. Тестирование

```
tests/
├── test_kpi_engine.py      # Юнит-тесты расчёта всех 6 KPI
├── test_etl.py             # Тесты нормализации данных
├── test_permissions.py     # Тесты ролей и RLS
└── test_api.py             # Интеграционные тесты API
```

**Обязательно:** тест-кейс — воспроизвести расчёт из Excel-файла `Статистика_КЭР_РК_на_01_01_2026.xlsx` и сверить результаты с ручным расчётом Олжаса.

---

## 9. Открытые вопросы (заполнить при получении доступа к БД КГД)

- [ ] Точные названия таблиц и полей в БД КГД
- [ ] Маппинг условных полей (`amount_assessed`, `management`, `form_type`) на реальные
- [ ] Формат кодирования ДФНО в БД
- [ ] Наличие кода ДГД в таблице обжалований (Олжас добавит)
- [ ] Credentials для подключения к БД КГД
- [ ] Правила автоматического vs ручного проставления флагов

# CI/CD — GitHub Actions

---

## Файл: `.github/workflows/ci.yml`

### Job: test
Запускается при `push` и `pull_request` на `main`.

```yaml
services:
  postgres:16

steps:
  - pip install -r requirements.txt
  - python manage.py migrate --settings=config.settings.ci
  - python manage.py test apps/ --settings=config.settings.ci
```

### Job: lint
```yaml
steps:
  - flake8 apps/ --max-line-length=120
```

---

## Настройки для CI (`config/settings/ci.py`)

- PostgreSQL с хардкодными кредами (для GitHub Actions service)
- `SECURE_SSL_REDIRECT=False`
- `PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']` — быстрее
- `CELERY_TASK_ALWAYS_EAGER=True` — задачи выполняются синхронно (без Redis)

---

## Запуск тестов локально

```bash
# Через Docker
make test

# Или напрямую (нужен PostgreSQL)
python manage.py test apps/ --settings=config.settings.test
```

---

## Тесты по приложениям

| App | Файлы тестов | Что покрывает |
|-----|-------------|--------------|
| core | test_models.py, test_mixins.py | User, роли, RLS для 4 ролей |
| regions | test_models.py | Фикстура, 20 ДГД + КГД |
| etl | test_models.py, test_services.py | Нормализация, маршрутизация ИНИС/ИСНА |
| kpi | test_engine.py, test_models.py, test_init_formulas.py | 60+ тестов Engine с реальными данными |
| reports | test_models.py | Workflow утверждения |

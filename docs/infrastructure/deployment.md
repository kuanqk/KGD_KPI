# Развёртывание on-premise

---

## Требования к серверу

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| CPU | 4 ядра | 8 ядер |
| RAM | 8 GB | 16 GB |
| Диск (SSD) | 100 GB | 500 GB |
| ОС | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Сеть | 100 Мбит | 1 Гбит (внутренняя сеть КГД) |

**Дополнительно:**
- Статический IP внутри сети КГД
- SSL сертификат (внутренний или самоподписанный)
- Readonly подключение к БД КГД
- Резервный сервер или снапшоты

---

## Установка на сервер

```bash
# 1. Установить Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Клонировать репозиторий
git clone https://github.com/kuanqk/KGD_KPI.git
cd KGD_KPI

# 3. Настроить окружение
cp .env.example .env
nano .env   # заполнить все переменные

# 4. Запустить
make build
make up
make migrate
make seed
make superuser
```

---

## Обновление

```bash
git pull origin main
make build
make up
make migrate
```

---

## Резервное копирование PostgreSQL

```bash
# Создать бэкап
docker compose exec db pg_dump -U kgd_user kgd_kpi > backup_$(date +%Y%m%d).sql

# Восстановить
docker compose exec -T db psql -U kgd_user kgd_kpi < backup.sql
```

Рекомендуется настроить cron для ежедневного бэкапа.

---

## Текущее состояние (dev)

- Nginx слушает порт **8080** (порт 80 занят на машине разработчика)
- В production nginx должен слушать 80 и 443
- HTTPS: раскомментировать HTTPS блок в `docker/nginx.conf` и добавить сертификат
- `SECURE_SSL_REDIRECT=True` в `prod.py` уже включён

---

## Мониторинг

- Django Admin: `http://server/admin/`
- ETL Monitor (UI): `http://server/admin/etl`
- Celery: через UI в разделе ETL Monitor
- Логи: `make logs` или `docker compose logs -f [service]`

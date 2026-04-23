# Excel для тестовой загрузки

Файл **`Статистика КЭР РК на 01.04.2026.xlsx`** лежит в репозитории (копия из локального `old/local_docs/`, который в `.gitignore`).

Команда: `python manage.py load_q1_2026_excel` — путь по умолчанию: `data/excel/Статистика КЭР РК на 01.04.2026.xlsx`.

- `--clear` — удалить только строки этой команды (`Q1-*`), не весь ETL.
- `--full-excel-2025` — дополнительно залить проверки 2025 из Excel (`Q1-P25-`); без флага оставляется уже загруженный ETL за 2025 (например `load_test_data`).
- `--wipe-all-etl` — полная очистка как раньше (осторожно).

При обновлении эталона замените файл здесь и при необходимости задеплойте на сервер.

## Рейтинг на дашборде = лист «KPI» (01.01.2026)

Полный файл **`Статистика КЭР РК на 01.01.2026.xlsx`** часто только в `old/local_docs/` (вне git). Эталонные баллы по регионам за период **01.01.2025 — 01.01.2026** зафиксированы в коде: `apps/kpi/reference_excel_20250101.py`.

После загрузки тестовых данных, если расчёт движка не совпал с Excel:

- Период **2025 → 2026** — эталон дашборда: **`old/260423/correct2025.png`** (и Word `KPI ошибки 2025.docx` для сверки K1…K6):  
  `python manage.py apply_excel_kpi_2025`  
  или `--snapshot dashboard_2025_260423` (алиас: `kpi_20250101`).

- Период **2026 → 2027** — **`old/260423/correct2026.png`**, `KPI ошибки 2026.docx`:  
  `python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423` (алиас: `kpi20_dgd_20260401`).

Словарь баллов в коде: `apps/kpi/reference_excel_20250101.py` (`REF_DASHBOARD_2025_260423`, `REF_DASHBOARD_2026_260423`).

**Docker** (из каталога с `docker-compose.yml`, сервис `web`):

```bash
docker compose exec web python manage.py apply_excel_kpi_2025 --snapshot dashboard_2025_260423
docker compose exec web python manage.py apply_excel_kpi_2025 --snapshot dashboard_2026_260423
```

Старый синтаксис `docker-compose` (v1): `docker-compose exec web ...`

Если в БД оказались **две строки KPISummary** на один регион и период (дашборд дублирует строки):

```bash
docker compose exec web python manage.py dedupe_kpi_summary --dry-run
docker compose exec web python manage.py dedupe_kpi_summary
```

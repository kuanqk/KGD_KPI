# apps/regions — Справочник регионов

> Минимальный контекст для работы с этим app.
> Справочник ДГД: [business/business_regions.md](../business/business_regions.md)

---

## Что делает этот app

Справочник 20 ДГД + КГД. Редко меняется.

---

## Загрузка данных

```bash
python manage.py loaddata apps/regions/fixtures/regions.json
```

---

## API

```
GET /api/v1/regions/    # Все 21 запись, без пагинации, все роли
```

---

## Файлы app

```
apps/regions/
├── models.py              # Region (code, name_ru/kz/en, is_summary, order)
├── fixtures/
│   └── regions.json       # 20 ДГД + КГД
├── serializers.py         # RegionSerializer
├── views.py               # RegionListView
├── urls.py
└── admin.py
```

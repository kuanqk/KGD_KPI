# apps/reports — Утверждение и экспорт

> Минимальный контекст для работы с этим app.

---

## Что делает этот app

- Workflow утверждения отчётов (submit → approve/reject)
- Экспорт в XLSX (openpyxl)
- Экспорт в PDF (WeasyPrint)

---

## Workflow утверждения

```
Оператор запускает расчёт → KPISummary.status = 'draft'
    ↓
Оператор отправляет на утверждение → status = 'submitted'
    ↓
Проверяющий утверждает → status = 'approved'
    или
Проверяющий возвращает → status = 'rejected' (comment обязателен)
    или
Проверяющий запрашивает пересчёт → status = 'draft' + новый расчёт
```

Каждое действие создаёт `ReportApproval` запись.

---

## Экспорт XLSX

```python
from apps.reports.services.xlsx_exporter import XLSXExporter

summary = KPISummary.objects.get(id=...)
exporter = XLSXExporter(summary)
buffer = exporter.generate()  # → BytesIO

# В view:
response = HttpResponse(buffer.getvalue(),
    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
response['Content-Disposition'] = 'attachment; filename="kpi_report.xlsx"'
```

**Структура XLSX:**
- Лист 1 «Рейтинг»: 20 ДГД, позиция, все 6 KPI баллы, итого
- Листы 2–7: детали по каждому KPI (план, факт, %, баллы)
- Цветовая кодировка: зелёный ≥80б, жёлтый 50–79б, красный <50б

---

## Экспорт PDF

```python
from apps.reports.services.pdf_exporter import PDFExporter

exporter = PDFExporter(summary)
buffer = exporter.generate()  # → BytesIO (WeasyPrint)
```

**Шаблон:** `templates/reports/kpi_report.html` (A4 landscape)

---

## Celery задачи

```python
from apps.reports.tasks import export_to_xlsx, export_to_pdf

export_to_xlsx.delay(summary_id=..., user_id=...)
export_to_pdf.delay(summary_id=..., user_id=...)
```

---

## Файлы app

```
apps/reports/
├── models.py              # ReportApproval
├── services/
│   ├── xlsx_exporter.py   # XLSXExporter
│   └── pdf_exporter.py    # PDFExporter
├── tasks.py               # export_to_xlsx, export_to_pdf
├── serializers.py
├── views.py               # PendingReportsView, ApproveView, RejectView,
│                          # RecalculateView, ExportXLSXView, ExportPDFView
├── urls.py
└── admin.py

templates/reports/
└── kpi_report.html        # PDF шаблон
```

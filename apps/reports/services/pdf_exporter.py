"""
PDF-экспорт KPI-отчёта (WeasyPrint).

Использует шаблон templates/reports/kpi_report.html.
"""
import io
from datetime import datetime

from django.template.loader import render_to_string
from weasyprint import HTML

from apps.kpi.models import KPIResult, KPISummary

_KPI_TYPES_ORDER = [
    'assessment',
    'collection',
    'avg_assessment',
    'workload',
    'long_inspections',
    'cancelled',
]

_KPI_LABELS = {
    'assessment':       ('KPI 1 — Доначисление',        10),
    'collection':       ('KPI 2 — Взыскание',            40),
    'avg_assessment':   ('KPI 3 — Среднее доначисление', 10),
    'workload':         ('KPI 4 — Коэф. занятости',      15),
    'long_inspections': ('KPI 5 — Долгие проверки',      10),
    'cancelled':        ('KPI 6 — Отменённые суммы',     15),
}

_SCORE_FIELDS = [
    'score_assessment',
    'score_collection',
    'score_avg_assessment',
    'score_workload',
    'score_long_inspections',
    'score_cancelled',
]


class PDFExporter:
    def __init__(self, summary: KPISummary):
        self.summary = summary
        self.date_from = summary.date_from
        self.date_to = summary.date_to
        self.generated_at = datetime.now()

    # ── Публичный метод ────────────────────────────────────────────────────

    def generate(self) -> io.BytesIO:
        context = self._build_context()
        html_string = render_to_string('reports/kpi_report.html', context)
        pdf_bytes = HTML(string=html_string).write_pdf()
        buf = io.BytesIO(pdf_bytes)
        buf.seek(0)
        return buf

    # ── Приватные методы ───────────────────────────────────────────────────

    def _build_context(self) -> dict:
        all_summaries = list(
            KPISummary.objects
            .filter(date_from=self.date_from, date_to=self.date_to)
            .select_related('region')
            .order_by('rank', 'region__order')
        )
        dgd_summaries = [
            self._enrich(s) for s in all_summaries if not s.region.is_summary
        ]
        kgd_summaries = [
            self._enrich(s) for s in all_summaries if s.region.is_summary
        ]

        kpi_sections = []
        formula_version = None
        for kpi_type in _KPI_TYPES_ORDER:
            label, max_score = _KPI_LABELS[kpi_type]
            results = list(
                KPIResult.objects
                .filter(kpi_type=kpi_type, date_from=self.date_from, date_to=self.date_to)
                .select_related('region', 'formula')
                .exclude(region__is_summary=True)
                .order_by('region__order')
            )
            if formula_version is None and results:
                formula_version = results[0].formula
            kpi_sections.append({
                'kpi_type': kpi_type,
                'label': label,
                'max_score': max_score,
                'results': results,
            })

        return {
            'summary': self.summary,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'generated_at': self.generated_at,
            'dgd_summaries': dgd_summaries,
            'kgd_summaries': kgd_summaries,
            'kpi_sections': kpi_sections,
            'formula_version': formula_version,
        }

    @staticmethod
    def _enrich(s: KPISummary) -> dict:
        """Преобразовать summary в dict с предвычисленным списком баллов."""
        return {
            'obj': s,
            'region': s.region,
            'rank': s.rank,
            'score_total': s.score_total,
            'scores': [
                s.score_assessment,
                s.score_collection,
                s.score_avg_assessment,
                s.score_workload,
                s.score_long_inspections,
                s.score_cancelled,
            ],
        }

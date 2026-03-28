from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import KPIFormula, KPIResult, KPISummary


@admin.register(KPIFormula)
class KPIFormulaAdmin(admin.ModelAdmin):
    list_display = ('kpi_type', 'version', 'is_active', 'created_by', 'created_at')
    list_filter = ('kpi_type', 'is_active')
    search_fields = ('kpi_type', 'notes')
    readonly_fields = ('created_at',)
    ordering = ('kpi_type', '-version')


@admin.register(KPIResult)
class KPIResultAdmin(admin.ModelAdmin):
    list_display = (
        'region', 'kpi_type', 'date_from', 'date_to',
        'plan', 'fact', 'percent', 'score', 'status',
    )
    list_filter = ('kpi_type', 'status', 'region')
    search_fields = ('region__name_ru',)
    date_hierarchy = 'date_from'
    readonly_fields = ('calculated_at',)
    raw_id_fields = ('region', 'formula', 'calculated_by')

    fieldsets = (
        (_('Расчётный период'), {'fields': ('region', 'kpi_type', 'formula', 'date_from', 'date_to')}),
        (_('Результаты'),       {'fields': ('plan', 'fact', 'percent', 'score')}),
        (_('Статус'),           {'fields': ('status', 'calculated_by', 'calculated_at')}),
        (_('Детали'),           {'fields': ('calc_details',), 'classes': ('collapse',)}),
    )


@admin.register(KPISummary)
class KPISummaryAdmin(admin.ModelAdmin):
    list_display = (
        'rank', 'region', 'date_from', 'date_to',
        'score_assessment', 'score_collection', 'score_avg_assessment',
        'score_workload', 'score_long_inspections', 'score_cancelled',
        'score_total', 'status',
    )
    list_filter = ('status', 'region')
    search_fields = ('region__name_ru',)
    date_hierarchy = 'date_from'
    readonly_fields = ('calculated_at',)
    raw_id_fields = ('region',)
    ordering = ('rank',)

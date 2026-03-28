from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    ActiveInspection,
    AppealDecision,
    CompletedInspection,
    ImportJob,
    ManualInput,
)


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'source', 'status', 'started_by',
        'started_at', 'finished_at', 'records_total', 'records_imported',
    )
    list_filter = ('source', 'status')
    search_fields = ('started_by__username', 'error_message')
    readonly_fields = ('started_at', 'finished_at', 'records_total', 'records_imported', 'error_message')
    date_hierarchy = 'started_at'


@admin.register(CompletedInspection)
class CompletedInspectionAdmin(admin.ModelAdmin):
    list_display = (
        'source_id', 'source', 'region', 'management', 'form_type',
        'completed_date', 'amount_assessed', 'amount_collected',
        'is_counted', 'is_accepted', 'is_anomaly',
    )
    list_filter = ('source', 'management', 'form_type', 'is_counted', 'is_accepted', 'is_anomaly')
    search_fields = ('source_id', 'region__name_ru', 'management')
    date_hierarchy = 'completed_date'
    raw_id_fields = ('import_job', 'region')

    fieldsets = (
        (_('Источник'), {'fields': ('source', 'source_id', 'import_job')}),
        (_('Проверка'), {'fields': ('region', 'management', 'form_type', 'completed_date')}),
        (_('Суммы'), {'fields': ('amount_assessed', 'amount_collected')}),
        (_('Флаги'), {'fields': ('is_counted', 'is_accepted', 'is_anomaly')}),
        (_('Метаданные'), {'fields': ('raw_data', 'created_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)


@admin.register(ActiveInspection)
class ActiveInspectionAdmin(admin.ModelAdmin):
    list_display = (
        'source_id', 'source', 'region', 'management',
        'case_type', 'prescription_date', 'is_counted',
    )
    list_filter = ('source', 'management', 'case_type', 'is_counted')
    search_fields = ('source_id', 'region__name_ru', 'management')
    date_hierarchy = 'prescription_date'
    raw_id_fields = ('import_job', 'region')


@admin.register(AppealDecision)
class AppealDecisionAdmin(admin.ModelAdmin):
    list_display = (
        'source_id', 'region', 'amount_cancelled',
        'is_counted', 'completion_date', 'decision_date',
    )
    list_filter = ('is_counted', 'region')
    search_fields = ('source_id', 'region__name_ru')
    date_hierarchy = 'decision_date'
    raw_id_fields = ('import_job', 'region')


@admin.register(ManualInput)
class ManualInputAdmin(admin.ModelAdmin):
    list_display = (
        'region', 'year', 'kbk_share_pct', 'staff_count',
        'entered_by', 'entered_at',
    )
    list_filter = ('year', 'region')
    search_fields = ('region__name_ru', 'entered_by__username')
    readonly_fields = ('entered_at',)

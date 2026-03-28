from django.contrib import admin

from .models import ReportApproval


@admin.register(ReportApproval)
class ReportApprovalAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'summary', 'actor', 'comment')
    list_filter = ('action',)
    search_fields = ('actor__username', 'summary__region__name_ru', 'comment')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    raw_id_fields = ('summary', 'actor')

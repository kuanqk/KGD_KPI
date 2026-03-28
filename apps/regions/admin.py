from django.contrib import admin

from .models import Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_ru', 'name_kz', 'name_en', 'is_summary', 'order')
    list_filter = ('is_summary',)
    search_fields = ('code', 'name_ru', 'name_kz', 'name_en')
    ordering = ('order',)

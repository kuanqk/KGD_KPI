from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import AuditLog, User, UserRegion


class UserRegionInline(admin.TabularInline):
    model = UserRegion
    extra = 1
    autocomplete_fields = ['region']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (_('Роль и доступ'), {'fields': ('role', 'mac_address')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_('Роль и доступ'), {'fields': ('role', 'mac_address')}),
    )
    list_display = ('username', 'email', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'mac_address')
    inlines = [UserRegionInline]


@admin.register(UserRegion)
class UserRegionAdmin(admin.ModelAdmin):
    list_display = ('user', 'region')
    list_filter = ('region',)
    search_fields = ('user__username', 'region__name_ru')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event', 'user', 'ip_address', 'mac_address')
    list_filter = ('event',)
    search_fields = ('user__username', 'ip_address', 'mac_address')
    readonly_fields = ('user', 'event', 'details', 'ip_address', 'mac_address', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

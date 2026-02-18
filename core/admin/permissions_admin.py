from django.contrib import admin
from core.models import (
    Journal,
    JournalColumn,
    RolePermission,
    UserPermissionOverride,
    PermissionsLog,
)

class JournalColumnInline(admin.TabularInline):
    model   = JournalColumn
    extra   = 1
    ordering = ['display_order']

@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active']
    inlines      = [JournalColumnInline]


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'journal', 'column', 'access_level']
    list_filter  = ['role', 'journal', 'access_level']


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ['user', 'journal', 'column', 'access_level', 'is_active', 'valid_until']
    list_filter  = ['is_active', 'journal']


@admin.register(PermissionsLog)
class PermissionsLogAdmin(admin.ModelAdmin):
    list_display = ['changed_at', 'changed_by', 'target_user', 'journal', 'old_access_level', 'new_access_level', 'permission_type']
    list_filter  = ['permission_type', 'journal']
    ordering     = ['-changed_at']
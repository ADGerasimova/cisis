"""
Система управления правами доступа:
- Journal (Журналы)
- JournalColumn (Столбцы журналов)
- RolePermission (Групповые права по ролям)
- UserPermissionOverride (Индивидуальные переопределения)
- PermissionsLog (История изменений прав)
"""

from django.db import models


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================================================

class AccessLevel(models.TextChoices):
    NONE = 'NONE', 'Нет доступа'
    VIEW = 'VIEW', 'Просмотр'
    EDIT = 'EDIT', 'Редактирование'


class PermissionType(models.TextChoices):
    GROUP      = 'GROUP',      'Групповое'
    INDIVIDUAL = 'INDIVIDUAL', 'Индивидуальное'


# =============================================================================
# СПРАВОЧНИК ЖУРНАЛОВ
# =============================================================================

class Journal(models.Model):
    code      = models.CharField(max_length=50, unique=True)
    name      = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'journals'
        managed  = False
        ordering = ['code']
        verbose_name        = 'Журнал'
        verbose_name_plural = 'Журналы'

    def __str__(self):
        return f'{self.code} — {self.name}'


# =============================================================================
# СПРАВОЧНИК СТОЛБЦОВ ЖУРНАЛА
# =============================================================================

class JournalColumn(models.Model):
    journal       = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='columns')
    code          = models.CharField(max_length=100)
    name          = models.CharField(max_length=200)
    is_active     = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table        = 'journal_columns'
        managed         = False
        unique_together = [('journal', 'code')]
        ordering        = ['display_order']
        verbose_name        = 'Столбец журнала'
        verbose_name_plural = 'Столбцы журнала'

    def __str__(self):
        return f'{self.journal.code}.{self.code} — {self.name}'


# =============================================================================
# ГРУППОВЫЕ ПРАВА (ПО РОЛИ)
# =============================================================================

class RolePermission(models.Model):
    role         = models.CharField(max_length=20)  # Выбор из UserRole
    journal      = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='role_permissions')
    column       = models.ForeignKey(JournalColumn, on_delete=models.CASCADE, null=True, blank=True, related_name='role_permissions')
    access_level = models.CharField(max_length=10, default=AccessLevel.NONE, choices=AccessLevel.choices)

    class Meta:
        db_table        = 'role_permissions'
        managed         = False
        unique_together = [('role', 'journal', 'column')]
        verbose_name        = 'Групповое право'
        verbose_name_plural = 'Групповые права'

    def __str__(self):
        col = self.column.code if self.column else '*'
        return f'{self.role} → {self.journal.code}.{col} = {self.access_level}'


# =============================================================================
# ИНДИВИДУАЛЬНЫЕ ПЕРЕОПРЕДЕЛЕНИЯ
# =============================================================================

class UserPermissionOverride(models.Model):
    user         = models.ForeignKey('User', on_delete=models.CASCADE, related_name='permission_overrides')
    journal      = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='user_overrides')
    column       = models.ForeignKey(JournalColumn, on_delete=models.CASCADE, null=True, blank=True, related_name='user_overrides')
    access_level = models.CharField(max_length=10, default=AccessLevel.NONE, choices=AccessLevel.choices)
    reason       = models.TextField()
    granted_by   = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='granted_overrides', db_column='granted_by_id')
    granted_at   = models.DateTimeField(auto_now_add=True)
    valid_until  = models.DateField(null=True, blank=True)  # NULL = бессрочно
    is_active    = models.BooleanField(default=True)

    class Meta:
        db_table        = 'user_permissions_override'
        managed         = False
        unique_together = [('user', 'journal', 'column')]
        verbose_name        = 'Переопределение прав'
        verbose_name_plural = 'Переопределения прав'

    def __str__(self):
        col = self.column.code if self.column else '*'
        return f'{self.user.username} → {self.journal.code}.{col} = {self.access_level}'


# =============================================================================
# ЛОГ ИЗМЕНЕНИЙ ПРАВ
# =============================================================================

class PermissionsLog(models.Model):
    changed_at       = models.DateTimeField(auto_now_add=True)
    changed_by       = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='permission_changes', db_column='changed_by_id')
    target_user      = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='permission_change_targets', db_column='target_user_id')
    role             = models.CharField(max_length=20, default='', blank=True)
    journal          = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='permission_logs')
    column           = models.ForeignKey(JournalColumn, on_delete=models.CASCADE, null=True, blank=True, related_name='permission_logs')
    old_access_level = models.CharField(max_length=10)
    new_access_level = models.CharField(max_length=10)
    reason           = models.TextField(default='', blank=True)
    permission_type  = models.CharField(max_length=20, choices=PermissionType.choices)

    class Meta:
        db_table = 'permissions_log'
        managed  = False
        ordering = ['-changed_at']
        verbose_name        = 'Запись лога прав'
        verbose_name_plural = 'Лог прав доступа'

    def __str__(self):
        col = self.column.code if self.column else '*'
        return f'{self.changed_at:%Y-%m-%d} {self.journal.code}.{col}: {self.old_access_level} → {self.new_access_level}'

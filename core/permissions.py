from datetime import date
from core.models import RolePermission, UserPermissionOverride


class PermissionChecker:
    """Класс для проверки прав доступа на основе БД"""

    PERMISSION_LEVELS = {
        'NONE': 0,
        'VIEW': 1,
        'EDIT': 2,
    }

    @classmethod
    def get_user_permission(cls, user, journal_code, column_code):
        """
        Получает уровень доступа пользователя к конкретному столбцу журнала.
        Приоритет: user_permissions_override > role_permissions
        """
        # 1. Проверяем индивидуальное переопределение
        override = UserPermissionOverride.objects.filter(
            user=user,
            journal__code=journal_code,
            column__code=column_code,
            is_active=True
        ).first()

        if override:
            # Проверяем срок действия
            if override.valid_until is None or override.valid_until >= date.today():
                return override.access_level

        # 2. Берём из роли
        role_perm = RolePermission.objects.filter(
            role=user.role,
            journal__code=journal_code,
            column__code=column_code
        ).first()

        if role_perm:
            return role_perm.access_level

        # 3. По умолчанию NONE
        return 'NONE'

    @classmethod
    def can_view(cls, user, journal_code, column_code):
        """Может ли пользователь видеть поле"""
        level = cls.get_user_permission(user, journal_code, column_code)
        return cls.PERMISSION_LEVELS.get(level, 0) >= cls.PERMISSION_LEVELS['VIEW']

    @classmethod
    def can_edit(cls, user, journal_code, column_code):
        """Может ли пользователь редактировать поле"""
        level = cls.get_user_permission(user, journal_code, column_code)
        return cls.PERMISSION_LEVELS.get(level, 0) >= cls.PERMISSION_LEVELS['EDIT']

    @classmethod
    def has_journal_access(cls, user, journal_code):
        """Есть ли у пользователя доступ к журналу вообще (хотя бы VIEW к одному полю)"""
        # Проверяем переопределения
        if UserPermissionOverride.objects.filter(
                user=user,
                journal__code=journal_code,
                access_level__in=['VIEW', 'EDIT'],
                is_active=True
        ).exists():
            return True

        # Проверяем права роли
        if RolePermission.objects.filter(
                role=user.role,
                journal__code=journal_code,
                access_level__in=['VIEW', 'EDIT']
        ).exists():
            return True

        return False
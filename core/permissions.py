"""
CISIS v3.17.0 — PermissionChecker

Файл: core/permissions.py
Действие: ПОЛНАЯ ЗАМЕНА

Изменения v3.17.0:
- Добавлен метод get_visible_laboratory_ids()
- Добавлена константа CAN_SEE_PENDING_VERIFICATION
"""

from datetime import date
from core.models import RolePermission, UserPermissionOverride, RoleLaboratoryAccess


# Роли, которые видят образцы со статусом PENDING_VERIFICATION
CAN_SEE_PENDING_VERIFICATION = frozenset({
    'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'SYSADMIN',
    'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST', 'CTO', 'CEO', 'LAB_HEAD',
})


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

    # ─────────────────────────────────────────────────────────
    # v3.17.0: Видимость лабораторий
    # ─────────────────────────────────────────────────────────

    @classmethod
    def get_visible_laboratory_ids(cls, user, journal_code):
        """
        Возвращает множество ID лабораторий, доступных пользователю для журнала.

        Возвращает:
            None  — все лаборатории (без фильтра по laboratory)
            set() — пустой набор (нет доступа)
            {1,3} — конкретные лаборатории

        Логика:
            1. Есть запись с laboratory_id IS NULL → все лаборатории
            2. Есть записи с конкретными laboratory_id → эти лаборатории
            3. Нет записей → fallback: user.laboratory + additional_laboratories
        """
        role_labs = RoleLaboratoryAccess.objects.filter(
            role=user.role,
            journal__code=journal_code
        )

        if not role_labs.exists():
            # Нет настроек → fallback на лаборатории пользователя
            lab_ids = set()
            if user.laboratory_id:
                lab_ids.add(user.laboratory_id)
            if hasattr(user, 'additional_laboratories'):
                lab_ids.update(
                    user.additional_laboratories.values_list('id', flat=True)
                )
            return lab_ids if lab_ids else set()

        # Есть запись с NULL → все лаборатории
        if role_labs.filter(laboratory_id__isnull=True).exists():
            return None

        # Конкретные лаборатории
        return set(role_labs.values_list('laboratory_id', flat=True))

    @classmethod
    def get_role_laboratory_access(cls, role, journal_code):
        """
        Возвращает настройки видимости лабораторий для роли.

        Возвращает:
            ('all', [])       — все лаборатории
            ('specific', ids) — конкретные лаборатории
            ('default', [])   — нет настроек (fallback)
        """
        role_labs = RoleLaboratoryAccess.objects.filter(
            role=role,
            journal__code=journal_code
        )

        if not role_labs.exists():
            return ('default', [])

        if role_labs.filter(laboratory_id__isnull=True).exists():
            return ('all', [])

        lab_ids = list(role_labs.values_list('laboratory_id', flat=True))
        return ('specific', lab_ids)
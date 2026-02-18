"""
CISIS — Логика заморозки/разморозки блоков полей образца.

Содержит:
- _can_unfreeze_block: проверка прав на разморозку блока
- _is_field_frozen: проверка заморозки конкретного поля
"""

from .constants import (
    QMS_ROLES, WORKSHOP_ROLES, WORKSHOP_FIELDS,
    REGISTRATION_FIELDS, TESTER_FIELDS, TESTER_FROZEN_STATUSES,
)


def _can_unfreeze_block(user, sample, block):
    """
    Проверяет, может ли пользователь редактировать замороженный блок.

    Правила:
    - SYSADMIN может всё всегда
    - QMS_HEAD / QMS_ADMIN могут размораживать любой блок
    - LAB_HEAD своей лаборатории может размораживать регистрацию и испытателя
    - WORKSHOP_HEAD может размораживать мастерскую
    - CLIENT_MANAGER / CLIENT_DEPT_HEAD могут размораживать регистрацию
    """
    if user.role == 'SYSADMIN':
        return True

    if user.role in QMS_ROLES:
        return True

    if block == 'registration':
        if user.role == 'LAB_HEAD' and user.laboratory:
            return user.has_laboratory(sample.laboratory)
        if user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'):
            return True

    if block == 'tester':
        if user.role == 'LAB_HEAD' and user.laboratory:
            return user.has_laboratory(sample.laboratory)

    if user.role == 'WORKSHOP_HEAD' and block == 'workshop':
        return True

    return False


def _is_field_frozen(field_code, user, sample, request=None):
    """
    Проверяет, заморожено ли конкретное поле для данного пользователя и образца.

    Возвращает (is_frozen: bool, reason: str или None).

    Правила заморозки:
    1) Регистрация: readonly после подтверждения (status != PENDING_VERIFICATION)
    2) Мастерская: readonly после workshop_status == COMPLETED
    3) Испытатель: readonly начиная с DRAFT_READY и далее
    4) WORKSHOP_HEAD / WORKSHOP для НЕ-мастерских полей — ВСЕГДА readonly
    5) Поле «status» — завлаб может менять только для образцов СВОЕЙ лаборатории
    6) Регистраторы размораживают ТОЛЬКО через кнопку (сессионный флаг)
    """
    # Правило 4: Роли мастерской видят только поля мастерской
    if user.role in WORKSHOP_ROLES:
        if field_code not in WORKSHOP_FIELDS:
            return True, 'Мастерская может редактировать только поля мастерской'

    # Правило 1: Регистрация заморожена после подтверждения
    if field_code in REGISTRATION_FIELDS:
        if sample.status != 'PENDING_VERIFICATION':
            # Регистраторы — только через сессионный флаг (кнопку)
            if user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'):
                if request:
                    unfrozen_key = f'unfrozen_registration_{sample.id}'
                    if request.session.get(unfrozen_key, False):
                        return False, None
                return True, 'Регистрация подтверждена — поля заблокированы'

            # Остальные роли — через _can_unfreeze_block (SYSADMIN, QMS, LAB_HEAD)
            if not _can_unfreeze_block(user, sample, 'registration'):
                return True, 'Регистрация подтверждена — поля заблокированы'

    # Правило 2: Мастерская заморожена после завершения изготовления
    if field_code in WORKSHOP_FIELDS:
        if sample.workshop_status == 'COMPLETED':
            if not _can_unfreeze_block(user, sample, 'workshop'):
                return True, 'Изготовление завершено — поля мастерской заблокированы'

    # Правило 3: Испытатель заморожен начиная с DRAFT_READY
    if field_code in TESTER_FIELDS:
        if sample.status in TESTER_FROZEN_STATUSES:
            if not _can_unfreeze_block(user, sample, 'tester'):
                return True, 'Черновик готов / результаты выложены — поля испытателя заблокированы'

    # Правило 5: Поле «status» — завлаб может менять только для образцов СВОЕЙ лаборатории
    if field_code == 'status':
        if (user.role == 'LAB_HEAD'
                and user.laboratory
                and not user.has_laboratory(sample.laboratory)):
            return True, 'Завлаб может менять статус только для образцов своей лаборатории'

    # Правило 6: Регистраторы — статус заморожен, кроме разморозки через кнопку
    if field_code == 'status' and user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'):
        if sample.status != 'PENDING_VERIFICATION':
            if request:
                unfrozen_key = f'unfrozen_registration_{sample.id}'
                if request.session.get(unfrozen_key, False):
                    return False, None
            return True, 'Статус заблокирован — используйте разморозку блока регистрации'

    return False, None

"""
CISIS v3.17.0 — Views для управления правами доступа.

Файл: core/views/permissions_views.py
Действие: ПОЛНАЯ ЗАМЕНА

Изменения v3.17.0:
- Блок «Видимость лабораторий» для ролей (role_laboratory_access)
- Сохранение/загрузка настроек лабораторий
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from core.models import (
    User, Journal, JournalColumn, RolePermission,
    UserPermissionOverride, PermissionsLog, UserRole, AccessLevel,
    Laboratory, RoleLaboratoryAccess,
)
from core.permissions import PermissionChecker


# ═══════════════════════════════════════════════════════════════════
# УПРАВЛЕНИЕ ПРАВАМИ ДОСТУПА
# ═══════════════════════════════════════════════════════════════════

@login_required
def manage_permissions(request):
    """
    Страница управления правами доступа.

    Параметры GET:
        target_type: 'role' или 'user'
        target_id: ID роли (код роли как строка) или ID пользователя
        journal_id: ID журнала
    """

    # Проверяем права текущего пользователя
    if request.user.role not in ['SYSADMIN', 'QMS_HEAD', 'LAB_HEAD']:
        messages.error(request, 'У вас нет прав для управления доступом')
        return redirect('admin:index')

    # Получаем параметры из GET
    target_type = request.GET.get('target_type', 'role')
    target_id = request.GET.get('target_id')
    journal_id = request.GET.get('journal_id')

    # Списки для выпадающих списков
    journals = Journal.objects.filter(is_active=True).order_by('name')
    roles = UserRole.choices
    users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')

    # Если LAB_HEAD — может управлять только пользователями своей лаборатории
    if request.user.role == 'LAB_HEAD':
        users = users.filter(laboratory=request.user.laboratory)

    context = {
        'target_type': target_type,
        'target_id': target_id,
        'journal_id': journal_id,
        'journals': journals,
        'roles': roles,
        'users': users,
        'permissions': None,
        'target_name': None,
        'journal_name': None,
        # v3.17.0: лаборатории
        'laboratories': None,
        'lab_access_mode': None,
        'lab_access_ids': [],
        'show_lab_access': False,
    }

    # Если выбраны параметры — загружаем права
    if target_id and journal_id:
        try:
            journal = get_object_or_404(Journal, id=journal_id)
            context['journal_name'] = journal.name

            # ─── v3.17.0: Видимость лабораторий (только для ролей) ───
            if target_type == 'role':
                context['show_lab_access'] = True
                context['laboratories'] = Laboratory.objects.filter(
                    is_active=True,
                    department_type__in=['LAB', 'WORKSHOP'],
                ).order_by('department_type', 'code_display')

                mode, lab_ids = PermissionChecker.get_role_laboratory_access(
                    target_id, journal.code
                )
                context['lab_access_mode'] = mode
                context['lab_access_ids'] = lab_ids

            # ─── Столбцы журнала ───
            columns = JournalColumn.objects.filter(
                journal=journal,
                is_active=True
            ).order_by('display_order')

            permissions = []

            if target_type == 'role':
                role_code = target_id
                context['target_name'] = f'Роль: {dict(roles).get(role_code, role_code)}'

                for column in columns:
                    try:
                        perm = RolePermission.objects.get(
                            role=role_code,
                            journal=journal,
                            column=column
                        )
                        access_level = perm.access_level
                    except RolePermission.DoesNotExist:
                        access_level = 'NONE'

                    permissions.append({
                        'column': column,
                        'access_level': access_level,
                    })

            else:  # target_type == 'user'
                user = get_object_or_404(User, id=target_id)
                context['target_name'] = f'Пользователь: {user.full_name} ({user.username})'

                if request.user.role == 'LAB_HEAD':
                    if user.laboratory != request.user.laboratory:
                        messages.error(request, 'Вы можете управлять правами только сотрудников своей лаборатории')
                        return redirect('admin:index')

                for column in columns:
                    override = None
                    try:
                        override = UserPermissionOverride.objects.get(
                            user=user,
                            journal=journal,
                            column=column,
                            is_active=True
                        )
                        if override.valid_until and override.valid_until < timezone.now().date():
                            override.is_active = False
                            override.save()
                            override = None
                    except UserPermissionOverride.DoesNotExist:
                        pass

                    if override:
                        access_level = override.access_level
                        is_override = True
                    else:
                        try:
                            perm = RolePermission.objects.get(
                                role=user.role,
                                journal=journal,
                                column=column
                            )
                            access_level = perm.access_level
                        except RolePermission.DoesNotExist:
                            access_level = 'NONE'
                        is_override = False

                    permissions.append({
                        'column': column,
                        'access_level': access_level,
                        'is_override': is_override,
                    })

            context['permissions'] = permissions

        except Exception as e:
            messages.error(request, f'Ошибка при загрузке прав: {e}')

    # ═══════════════════════════════════════════════════════════
    # POST — сохранение прав
    # ═══════════════════════════════════════════════════════════

    if request.method == 'POST':
        try:
            journal = get_object_or_404(Journal, id=journal_id)
            columns = JournalColumn.objects.filter(journal=journal, is_active=True)

            if target_type == 'role':
                role_code = target_id

                # ─── v3.17.0: Сохранение видимости лабораторий ───
                _save_role_laboratory_access(request, role_code, journal)

                # ─── Сохранение прав столбцов ───
                for column in columns:
                    new_level = request.POST.get(f'perm_{column.id}')
                    if new_level not in ['NONE', 'VIEW', 'EDIT']:
                        continue

                    perm, created = RolePermission.objects.get_or_create(
                        role=role_code,
                        journal=journal,
                        column=column,
                        defaults={'access_level': new_level}
                    )

                    if not created and perm.access_level != new_level:
                        PermissionsLog.objects.create(
                            changed_by=request.user,
                            role=role_code,
                            journal=journal,
                            column=column,
                            old_access_level=perm.access_level,
                            new_access_level=new_level,
                            reason=request.POST.get('reason', 'Изменение через интерфейс'),
                            permission_type='GROUP'
                        )
                        perm.access_level = new_level
                        perm.save()

                messages.success(request, f'Права для роли {dict(roles).get(role_code)} сохранены')

            else:  # target_type == 'user'
                user = get_object_or_404(User, id=target_id)
                reason = request.POST.get('reason', '').strip()

                if not reason:
                    messages.error(request, 'Необходимо указать причину изменения прав')
                    return redirect(f'/permissions/?target_type=user&target_id={target_id}&journal_id={journal_id}')

                valid_until_str = request.POST.get('valid_until', '').strip()
                valid_until = None
                if valid_until_str:
                    from datetime import datetime as dt
                    valid_until = dt.strptime(valid_until_str, '%Y-%m-%d').date()

                for column in columns:
                    new_level = request.POST.get(f'perm_{column.id}')
                    if new_level not in ['NONE', 'VIEW', 'EDIT']:
                        continue

                    try:
                        role_perm = RolePermission.objects.get(
                            role=user.role,
                            journal=journal,
                            column=column
                        )
                        base_level = role_perm.access_level
                    except RolePermission.DoesNotExist:
                        base_level = 'NONE'

                    if new_level == base_level:
                        try:
                            override = UserPermissionOverride.objects.get(
                                user=user,
                                journal=journal,
                                column=column
                            )
                            PermissionsLog.objects.create(
                                changed_by=request.user,
                                target_user=user,
                                journal=journal,
                                column=column,
                                old_access_level=override.access_level,
                                new_access_level=new_level,
                                reason=f'Возврат к групповым правам: {reason}',
                                permission_type='INDIVIDUAL'
                            )
                            override.delete()
                        except UserPermissionOverride.DoesNotExist:
                            pass
                    else:
                        override, created = UserPermissionOverride.objects.get_or_create(
                            user=user,
                            journal=journal,
                            column=column,
                            defaults={
                                'access_level': new_level,
                                'reason': reason,
                                'granted_by': request.user,
                                'valid_until': valid_until,
                                'is_active': True
                            }
                        )

                        if not created:
                            PermissionsLog.objects.create(
                                changed_by=request.user,
                                target_user=user,
                                journal=journal,
                                column=column,
                                old_access_level=override.access_level,
                                new_access_level=new_level,
                                reason=reason,
                                permission_type='INDIVIDUAL'
                            )
                            override.access_level = new_level
                            override.reason = reason
                            override.granted_by = request.user
                            override.valid_until = valid_until
                            override.is_active = True
                            override.save()

                messages.success(request, f'Права для пользователя {user.full_name} сохранены')

            return redirect(f'/permissions/?target_type={target_type}&target_id={target_id}&journal_id={journal_id}')

        except Exception as e:
            messages.error(request, f'Ошибка при сохранении прав: {e}')

    return render(request, 'core/manage_permissions.html', context)


def _save_role_laboratory_access(request, role_code, journal):
    """
    v3.17.0: Сохраняет настройки видимости лабораторий из POST.

    POST-параметры:
        lab_access_mode: 'default' | 'all' | 'specific'
        lab_ids: список ID лабораторий (для mode=specific)
    """
    mode = request.POST.get('lab_access_mode', 'default')

    # Удаляем старые записи
    RoleLaboratoryAccess.objects.filter(
        role=role_code,
        journal=journal,
    ).delete()

    if mode == 'all':
        # Одна запись с laboratory_id = NULL
        RoleLaboratoryAccess.objects.create(
            role=role_code,
            journal=journal,
            laboratory=None,
        )
    elif mode == 'specific':
        lab_ids = request.POST.getlist('lab_ids')
        for lab_id in lab_ids:
            try:
                lab = Laboratory.objects.get(id=int(lab_id))
                RoleLaboratoryAccess.objects.create(
                    role=role_code,
                    journal=journal,
                    laboratory=lab,
                )
            except (Laboratory.DoesNotExist, ValueError):
                continue
    # mode == 'default' → нет записей = fallback на user.laboratory
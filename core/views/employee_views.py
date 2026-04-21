"""
employee_views.py — Справочник сотрудников
v3.74.0 (матрица ответственности удалена, редактирование областей
в карточке сотрудника)

Расположение: core/views/employee_views.py

Маршруты в core/urls.py:
    path('workspace/employees/<int:user_id>/save-areas/', employee_views.employee_save_areas, name='employee_save_areas'),
"""

import json
import re
import secrets
import string
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django.views.decorators.http import require_POST

from core.permissions import PermissionChecker
from core.models import User, Laboratory, UserRole
from core.models.base import AccreditationArea
import os, uuid
from django.conf import settings
from django.views.decorators.http import require_GET

EMPLOYEES_PER_PAGE = 50

# ─────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────

PHONE_RE = re.compile(r'^[\+]?[\d\s\-\(\)]{7,20}$')

MANAGER_ROLES = frozenset({'CEO', 'CTO', 'SYSADMIN'})


def _can_manage_employee(editor, target):
    """
    Может ли editor редактировать target.
    CEO/CTO/SYSADMIN → всех.
    LAB_HEAD → сотрудников своей лаборатории (основная + доп.).
    """
    if not PermissionChecker.can_edit(editor, 'EMPLOYEES', 'access'):
        return False

    if editor.role in MANAGER_ROLES:
        return True

    if editor.role == 'LAB_HEAD':
        editor_lab_ids = editor.all_laboratory_ids
        # Целевой пользователь принадлежит одной из лабораторий редактора?
        if target.laboratory_id and target.laboratory_id in editor_lab_ids:
            return True
        # Проверяем доп. лаборатории целевого пользователя
        target_lab_ids = target.all_laboratory_ids
        if editor_lab_ids & target_lab_ids:
            return True
        return False

    return False


def _can_manage_accreditation(user):
    """
    Может ли пользователь назначать области аккредитации сотрудникам
    в карточке сотрудника (ex-матрица ответственности, v3.74.0).

    Ключ `RESPONSIBILITY_MATRIX.access` в role_permissions сохранён как
    исторический — чтобы не делать миграцию ради косметического переименования.
    """
    return PermissionChecker.can_edit(user, 'RESPONSIBILITY_MATRIX', 'access')


def _validate_phone(phone):
    """Валидация телефона. Возвращает (cleaned, error)."""
    if not phone:
        return '', None
    phone = phone.strip()
    if not PHONE_RE.match(phone):
        return phone, 'Некорректный формат телефона'
    return phone, None


def _plural_ru(n, f1, f2, f5):
    """
    Русское склонение по числу: 1 день, 2 дня, 5 дней.
    f1 — для 1, 21, 31…; f2 — для 2-4, 22-24…; f5 — для 0, 5-20, 25-30…
    """
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 19:
        return f5
    last = n_abs % 10
    if last == 1:
        return f1
    if 2 <= last <= 4:
        return f2
    return f5


def _generate_password(length=10):
    """Генерирует случайный пароль."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _get_user_area_ids(user_id):
    """Получить ID областей аккредитации, к которым допущен сотрудник."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT accreditation_area_id FROM user_accreditation_areas WHERE user_id = %s",
            [user_id]
        )
        return [row[0] for row in cur.fetchall()]


def _get_equipment_for_user(user_id):
    """Получить оборудование, где сотрудник ответственный или замещающий."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                e.id, e.name, e.inventory_number, e.equipment_type,
                e.status, l.code_display AS lab_display,
                CASE
                    WHEN e.responsible_person_id = %s THEN 'responsible'
                    WHEN e.substitute_person_id = %s THEN 'substitute'
                END AS person_role
            FROM equipment e
            LEFT JOIN laboratories l ON l.id = e.laboratory_id
            WHERE e.responsible_person_id = %s OR e.substitute_person_id = %s
            ORDER BY
                CASE WHEN e.responsible_person_id = %s THEN 0 ELSE 1 END,
                e.equipment_type, e.name
        """, [user_id, user_id, user_id, user_id, user_id])

        columns = [col[0] for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
# Список сотрудников
# ─────────────────────────────────────────────────────────────

@login_required
def employees_list(request):
    if not PermissionChecker.can_view(request.user, 'EMPLOYEES', 'access'):
        messages.error(request, 'У вас нет доступа к справочнику сотрудников')
        return redirect('workspace_home')

    can_edit = PermissionChecker.can_edit(request.user, 'EMPLOYEES', 'access')

    # ── Фильтры ───────────────────────────────────────────────
    search       = request.GET.get('search', '').strip()
    lab_id       = request.GET.get('lab_id', '')
    role_filter  = request.GET.get('role', '')
    show_inactive = request.GET.get('show_inactive', '')

    qs = User.objects.select_related('laboratory', 'mentor')

    # По умолчанию скрываем деактивированных
    if not show_inactive:
        qs = qs.filter(is_active=True)

    if search:
        qs = qs.filter(
            Q(last_name__icontains=search) |
            Q(first_name__icontains=search) |
            Q(sur_name__icontains=search) |
            Q(username__icontains=search) |
            Q(position__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    if lab_id:
        qs = qs.filter(laboratory_id=int(lab_id))

    if role_filter:
        qs = qs.filter(role=role_filter)

    # ── Сортировка ────────────────────────────────────────────
    sort = request.GET.get('sort', 'last_name')
    allowed_sorts = {
        'last_name', '-last_name',
        'position', '-position',
        'laboratory', '-laboratory',
        'role', '-role',
    }
    if sort not in allowed_sorts:
        sort = 'last_name'

    if sort in ('laboratory', '-laboratory'):
        order_field = 'laboratory__name' if sort == 'laboratory' else '-laboratory__name'
    else:
        order_field = sort

    qs = qs.order_by(order_field, 'last_name', 'first_name')

    # ── Пагинация ─────────────────────────────────────────────
    total_count = qs.count()
    paginator = Paginator(qs, EMPLOYEES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Справочники для фильтров
    laboratories = Laboratory.objects.filter(is_active=True).order_by('name')
    roles = UserRole.choices

    # Показывать чекбокс «Деактивированные» только тем, кто может редактировать
    show_inactive_toggle = can_edit

    # Параметры фильтров для пагинации
    filter_params = {}
    if search:        filter_params['search']        = search
    if lab_id:        filter_params['lab_id']        = lab_id
    if role_filter:   filter_params['role']          = role_filter
    if show_inactive: filter_params['show_inactive'] = show_inactive
    if sort != 'last_name': filter_params['sort']    = sort

    context = {
        'page_obj':              page_obj,
        'employees':             page_obj.object_list,
        'total_count':           total_count,
        'laboratories':          laboratories,
        'roles':                 roles,
        'can_edit':              can_edit,
        'show_inactive_toggle':  show_inactive_toggle,
        'current_search':        search,
        'current_lab_id':        lab_id,
        'current_role':          role_filter,
        'current_show_inactive': show_inactive,
        'current_sort':          sort,
        'filter_query':          urlencode(filter_params),
        'sort_link_params':      urlencode({k: v for k, v in filter_params.items() if k != 'sort'}),
    }
    return render(request, 'core/employees.html', context)


# ─────────────────────────────────────────────────────────────
# Карточка сотрудника
# ─────────────────────────────────────────────────────────────

@login_required
def employee_detail(request, user_id):
    if not PermissionChecker.can_view(request.user, 'EMPLOYEES', 'access'):
        messages.error(request, 'У вас нет доступа к справочнику сотрудников')
        return redirect('workspace_home')

    employee = get_object_or_404(User, pk=user_id)
    can_manage = _can_manage_employee(request.user, employee)
    is_self = (request.user.pk == employee.pk)

    # Роль — красивое отображение
    role_display = dict(UserRole.choices).get(employee.role, employee.role)

    # Наставник
    mentor_name = employee.mentor.full_name if employee.mentor_id else None

    # Стажёры (если этот пользователь — наставник)
    trainees = User.objects.filter(
        mentor=employee, is_active=True
    ).order_by('last_name', 'first_name')

    # ── Оборудование ⭐ v3.28.0 ──────────────────────────────
    equipment_list = _get_equipment_for_user(employee.pk)
    equipment_responsible = [e for e in equipment_list if e['person_role'] == 'responsible']
    equipment_substitute  = [e for e in equipment_list if e['person_role'] == 'substitute']

    # ── Области аккредитации ⭐ v3.28.0 ───────────────────────
    # ⭐ v3.76.0: «Вне области» (is_default=TRUE) видна всем — фикс v3.74.0 отменён
    user_area_ids = _get_user_area_ids(employee.pk)
    all_areas = AccreditationArea.objects.filter(is_active=True).order_by('name')

    # ⭐ v3.76.0: единый breakdown стандартов сотрудника (auto/granted/revoked)
    from core.services.equipment_access import (
        get_user_standard_breakdown,
        get_user_equipment_breakdown,
        get_user_grant_equipment_candidates,
        get_user_grant_standard_candidates,
        can_manage_user_standard_access,
    )
    standard_breakdown = get_user_standard_breakdown(employee)

    # Обратно-совместимые ключи для шаблона
    allowed_standards_by_area = list(standard_breakdown['by_area'])
    if standard_breakdown['granted']:
        # Stаndарты, назначенные вручную вне областей → отдельная «группа»
        allowed_standards_by_area.append({
            'area_id': None,
            'area_name': '🔓 Назначены вручную',
            'standards': [{'id': g['id'], 'code': g['code'], 'name': g['name']}
                          for g in standard_breakdown['granted']],
        })
    # ⭐ v3.79.0: Исключения per-area — одна плашка = одна пара (std, area).
    # Разные области могут иметь разный reason/assigned_by, поэтому
    # deduplicate по sid нельзя. Читаем revoked_pairs из breakdown напрямую.
    standard_exclusions = [
        {
            'standard_id': p['standard_id'],
            'code': p['code'],
            'name': p['name'],
            'area_id': p['area_id'],
            'area_name': p['area_name'],
            'reason': p['reason'],
            'assigned_by': p['assigned_by'],
        }
        for p in standard_breakdown.get('revoked_pairs', [])
    ]

    # Можно ли редактировать области аккредитации сотруднику
    can_manage_areas = _can_manage_accreditation(request.user)
    # LAB_HEAD может редактировать только для своих сотрудников
    if not can_manage_areas and request.user.role == 'LAB_HEAD':
        can_manage_areas = _can_manage_employee(request.user, employee)

    # ⭐ v3.73.0 + v3.76.0: счётчики по breakdown
    # Один и тот же стандарт может лежать в нескольких областях —
    # считаем уникальные, чтобы счётчик не врал.
    allowed_standards_unique_ids = {
        s['id']
        for g in allowed_standards_by_area
        for s in g['standards']
    }
    allowed_standards_unique_count = len(allowed_standards_unique_ids)
    allowed_standards_areas_count = len(allowed_standards_by_area)
    _std_word = _plural_ru(
        allowed_standards_unique_count,
        'стандарт', 'стандарта', 'стандартов',
    )
    _area_word = _plural_ru(
        allowed_standards_areas_count,
        'области', 'областях', 'областях',
    )
    allowed_standards_summary = (
        f'{allowed_standards_unique_count} {_std_word}'
        f' в {allowed_standards_areas_count} {_area_word}'
    )

    # ⭐ v3.75.0: разбивка оборудования на auto/granted/revoked
    equipment_breakdown = get_user_equipment_breakdown(employee)
    equipment_breakdown_total = (
            len(equipment_breakdown['auto']) +
            len(equipment_breakdown['granted']) +
            len(equipment_breakdown['revoked'])
    )

    # ⭐ v3.75.0: Права на редактирование override'ов оборудования
    # SYSADMIN — для всех. LAB_HEAD — только для оборудования своих лаб
    # (вариант B: прикрепляем флаг can_edit_access к каждому Equipment).
    viewer_is_sysadmin = (
            request.user.is_superuser or request.user.role == 'SYSADMIN'
    )
    viewer_is_lab_head = (request.user.role == 'LAB_HEAD')
    viewer_lab_ids = set(request.user.all_laboratory_ids) if viewer_is_lab_head else set()

    # Для проверки per-equipment нужны все лабы каждого оборудования.
    # Один запрос вместо N+1:
    all_eq_ids = [
        e.id
        for bucket in (equipment_breakdown['auto'],
                       equipment_breakdown['granted'],
                       equipment_breakdown['revoked'])
        for e in bucket
    ]
    eq_labs_map = {}  # {eq_id: set(lab_ids)}
    if all_eq_ids:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT id, laboratory_id FROM equipment WHERE id = ANY(%s)
                UNION ALL
                SELECT equipment_id, laboratory_id FROM equipment_laboratories
                 WHERE equipment_id = ANY(%s)
            """, [all_eq_ids, all_eq_ids])
            for eq_id, lab_id in cur.fetchall():
                eq_labs_map.setdefault(eq_id, set()).add(lab_id)

    # Прикрепляем флаг can_edit_access к каждому оборудованию
    for bucket in (equipment_breakdown['auto'],
                   equipment_breakdown['granted'],
                   equipment_breakdown['revoked']):
        for e in bucket:
            if viewer_is_sysadmin:
                e.can_edit_access = True
            elif viewer_is_lab_head:
                e.can_edit_access = bool(viewer_lab_ids & eq_labs_map.get(e.id, set()))
            else:
                e.can_edit_access = False

    # Глобальный флаг: может ли зритель в принципе править допуски (для рендера кнопки «+ Разрешить вручную»)
    can_edit_equipment_access = viewer_is_sysadmin or viewer_is_lab_head

    # Кандидаты для dropdown «+ Разрешить вручную» — только для тех, кто может править
    if can_edit_equipment_access:
        equipment_grant_candidates = list(get_user_grant_equipment_candidates(employee))
        # Для LAB_HEAD фильтруем кандидатов по его лабам
        if viewer_is_lab_head and not viewer_is_sysadmin:
            equipment_grant_candidates = [
                e for e in equipment_grant_candidates
                if viewer_lab_ids & eq_labs_map.get(e.id, set())
                   or viewer_lab_ids & set(
                    e.all_laboratories.values_list('id', flat=True)
                )
            ]
    else:
        equipment_grant_candidates = []

    # ⭐ v3.76.0: Права на user_standard_access (GRANTED/REVOKED) этого сотрудника
    # — это независимый флаг от can_edit_equipment_access (другие правила).
    # can_edit_exclusions оставляем для обратной совместимости со старыми
    # участками шаблона, но логика теперь идёт через единый хелпер.
    can_edit_user_standards = can_manage_user_standard_access(request.user, employee)
    can_edit_exclusions = can_edit_user_standards  # ← alias для уже написанной вёрстки

    # ⭐ v3.76.0: Кандидаты для dropdown «+ Добавить стандарт» в карточке сотрудника
    if can_edit_user_standards:
        standard_grant_candidates = list(get_user_grant_standard_candidates(employee))
    else:
        standard_grant_candidates = []

    # ⭐ v3.74.0: Правильный счётчик «Ответственный за оборудование»
    equipment_total_count = len(equipment_responsible) + len(equipment_substitute)

    context = {
        'employee': employee,
        'role_display': role_display,
        'mentor_name': mentor_name,
        'trainees': trainees,
        'can_manage': can_manage,
        'is_self': is_self,
        'equipment_responsible': equipment_responsible,
        'equipment_substitute': equipment_substitute,
        'equipment_total_count': equipment_total_count,
        'user_area_ids': user_area_ids,
        'all_areas': all_areas,
        'can_manage_areas': can_manage_areas,
        'standard_exclusions': standard_exclusions,
        # ⭐ v3.73.0
        'allowed_standards_by_area': allowed_standards_by_area,
        'allowed_standards_unique_count': allowed_standards_unique_count,
        'allowed_standards_areas_count': allowed_standards_areas_count,
        'allowed_standards_summary': allowed_standards_summary,
        # ⭐ v3.75.0
        'equipment_breakdown': equipment_breakdown,
        'equipment_breakdown_total': equipment_breakdown_total,
        'equipment_grant_candidates': equipment_grant_candidates,
        'can_edit_equipment_access': can_edit_equipment_access,
        'can_edit_exclusions': can_edit_exclusions,
        # ⭐ v3.76.0
        'standard_breakdown': standard_breakdown,
        'standard_grant_candidates': standard_grant_candidates,
        'can_edit_user_standards': can_edit_user_standards,
    }
    return render(request, 'core/employee_detail.html', context)


# ─────────────────────────────────────────────────────────────
# Сохранение областей аккредитации сотрудника ⭐ v3.28.0
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def employee_save_areas(request, user_id):
    """
    Сохранить области аккредитации для сотрудника (form-submit вариант).
    v3.76.0: переведён на replace_user_areas; логика та же, что у api_employee_update_areas.
    """
    employee = get_object_or_404(User, pk=user_id)

    # Проверка прав
    can_edit_areas = _can_manage_accreditation(request.user)
    if not can_edit_areas and request.user.role == 'LAB_HEAD':
        can_edit_areas = _can_manage_employee(request.user, employee)
    if not can_edit_areas:
        return HttpResponseForbidden()

    area_ids = request.POST.getlist('area_ids')  # список строк
    area_ids_int = [int(a) for a in area_ids if a.isdigit()]

    from core.services.equipment_access import replace_user_areas
    result = replace_user_areas(
        user_id=employee.pk,
        area_ids=area_ids_int,
        actor_id=request.user.pk,
    )

    # Аудит — только если что-то реально изменилось
    if result['added'] or result['removed']:
        try:
            from core.views.audit import log_action
            areas_map = dict(AccreditationArea.objects.values_list('id', 'name'))
            # Восстанавливаем, что было добавлено/удалено (нам пришли только числа)
            new_ids = set(area_ids_int)
            old_ids = set(_get_user_area_ids_before := [])  # заглушка — данные уже потеряны
            # Для лога достаточно итоговых id — названия в areas_map,
            # сколько именно поступило в added/removed, уже известно из result.
            log_action(
                request, 'USER', employee.pk, 'EMPLOYEE_AREAS_CHANGED',
                extra_data={
                    'employee': employee.full_name,
                    'added_count': result['added'],
                    'removed_count': result['removed'],
                    'final_ids': sorted(new_ids),
                    'final_names': sorted(areas_map.get(a, str(a)) for a in new_ids),
                }
            )
        except Exception:
            pass

    messages.success(
        request,
        f'Области аккредитации для {employee.full_name} обновлены '
        f'(добавлено: {result["added"]}, удалено: {result["removed"]})'
    )
    return redirect('employee_detail', user_id=employee.pk)

# ─────────────────────────────────────────────────────────────
# Ограничения на добавление/редактирование сотрудников
# ─────────────────────────────────────────────────────────────

EMPLOYEE_MANAGEMENT_RULES = {
    'LAB_HEAD': {
        'allowed_roles': ['TESTER'],
        'same_lab_only': True,
    },
    'WORKSHOP_HEAD': {
        'allowed_roles': ['WORKSHOP'],
        'same_lab_only': True,
    },
    'CLIENT_DEPT_HEAD': {
        'allowed_roles': ['CLIENT_MANAGER'],
        'same_lab_only': True,
    },
}


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_employee_management_rule(user):
    return EMPLOYEE_MANAGEMENT_RULES.get(user.role)


def _is_lab_restricted(user):
    rule = _get_employee_management_rule(user)
    return bool(rule and rule.get('same_lab_only'))


def _get_allowed_role_values(user):
    rule = _get_employee_management_rule(user)
    if not rule:
        # Для остальных ролей — без ограничений
        return [value for value, _label in UserRole.choices]
    return rule['allowed_roles']


def _get_allowed_role_choices(user):
    allowed_values = set(_get_allowed_role_values(user))
    return [
        (value, label)
        for value, label in UserRole.choices
        if value in allowed_values
    ]


def _get_allowed_laboratories(user):
    if _is_lab_restricted(user):
        if not user.laboratory_id:
            return Laboratory.objects.none()
        return Laboratory.objects.filter(
            pk=user.laboratory_id,
            is_active=True
        ).order_by('name')

    return Laboratory.objects.filter(is_active=True).order_by('name')


def _can_assign_role(user, role):
    return role in _get_allowed_role_values(user)


def _can_assign_laboratory(user, lab_id):
    if not _is_lab_restricted(user):
        return True
    return str(user.laboratory_id or '') == str(lab_id or '')


def _can_manage_employee_by_rule(manager, employee):
    """
    Дополнительная объектная проверка:
    LAB_HEAD -> только TESTER из своей лаборатории
    WORKSHOP_HEAD -> только WORKSHOP из своей лаборатории
    CLIENT_DEPT_HEAD -> только CLIENT_MANAGER из своей лаборатории
    Остальные роли — без ограничений здесь
    """
    rule = _get_employee_management_rule(manager)
    if not rule:
        return True

    if rule.get('same_lab_only') and manager.laboratory_id != employee.laboratory_id:
        return False

    return employee.role in rule['allowed_roles']
# ─────────────────────────────────────────────────────────────
# Добавление сотрудника
# ─────────────────────────────────────────────────────────────

@login_required
def employee_add(request):
    if not PermissionChecker.can_edit(request.user, 'EMPLOYEES', 'access'):
        messages.error(request, 'У вас нет прав для добавления сотрудников')
        return redirect('employees')

    current_user = request.user
    lab_restricted = _is_lab_restricted(current_user)

    if lab_restricted and not current_user.laboratory_id:
        messages.error(request, 'У вас не указана лаборатория. Обратитесь к администратору.')
        return redirect('employees')

    laboratories = _get_allowed_laboratories(current_user)
    roles = _get_allowed_role_choices(current_user)

    mentors = User.objects.filter(
        is_active=True,
        is_trainee=False
    )

    # При желании можно ограничить наставников той же лабораторией
    if lab_restricted:
        mentors = mentors.filter(laboratory_id=current_user.laboratory_id)

    mentors = mentors.order_by('last_name', 'first_name')

    employee = None

    if request.method == 'POST':
        errors = []

        username   = request.POST.get('username', '').strip()
        password   = request.POST.get('password', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        sur_name   = request.POST.get('sur_name', '').strip()
        position   = request.POST.get('position', '').strip() or None
        lab_id     = request.POST.get('laboratory', '').strip()
        role       = request.POST.get('role', '').strip() or 'OTHER'
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        is_trainee = request.POST.get('is_trainee') == 'on'
        mentor_id  = request.POST.get('mentor', '').strip() or None

        # ── Ограничения по роли
        if not _can_assign_role(current_user, role):
            errors.append('Вы не можете создавать сотрудника с этой ролью')

        # ── Ограничения по лаборатории
        if not _can_assign_laboratory(current_user, lab_id):
            errors.append('Вы можете добавлять сотрудников только в свою лабораторию')
            lab_id = str(current_user.laboratory_id)

        # ── Валидация
        if not username:
            errors.append('Логин обязателен')
        elif User.objects.filter(username=username).exists():
            errors.append(f'Логин «{username}» уже занят')

        if not password:
            errors.append('Пароль обязателен')
        elif len(password) < 4:
            errors.append('Пароль слишком короткий (минимум 4 символа)')

        if not last_name:
            errors.append('Фамилия обязательна')
        if not first_name:
            errors.append('Имя обязательно')

        phone_clean, phone_err = _validate_phone(phone)
        if phone_err:
            errors.append(phone_err)

        if is_trainee and not mentor_id:
            errors.append('Для стажёра обязательно указать наставника')

        if errors:
            for err in errors:
                messages.error(request, err)

            employee = {
                'username': username,
                'last_name': last_name,
                'first_name': first_name,
                'sur_name': sur_name,
                'position': position,
                'laboratory_id': _safe_int(lab_id),
                'role': role,
                'email': email,
                'phone': phone,
                'is_trainee': is_trainee,
                'mentor_id': _safe_int(mentor_id),
            }
        else:
            try:
                new_user = User(
                    username=username,
                    last_name=last_name,
                    first_name=first_name,
                    sur_name=sur_name,
                    position=position,
                    laboratory_id=_safe_int(lab_id),
                    role=role,
                    email=email,
                    phone=phone_clean,
                    is_trainee=is_trainee,
                    mentor_id=_safe_int(mentor_id),
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                )
                new_user.set_password(password)
                new_user.save()

                try:
                    from core.views.audit import log_action
                    log_action(
                        request, 'USER', new_user.pk, 'EMPLOYEE_ADD',
                        extra_data={'employee': new_user.full_name}
                    )
                except Exception:
                    pass

                messages.success(request, f'Сотрудник {new_user.full_name} добавлен')
                return redirect('employee_detail', user_id=new_user.pk)

            except Exception as e:
                messages.error(request, f'Ошибка создания: {e}')

    context = {
        'employee': employee,
        'laboratories': laboratories,
        'roles': roles,
        'mentors': mentors,
        'is_new': True,
        'lab_restricted': lab_restricted,
    }
    return render(request, 'core/employee_edit.html', context)
# ─────────────────────────────────────────────────────────────
# Редактирование сотрудника
# ─────────────────────────────────────────────────────────────

@login_required
def employee_edit(request, user_id):
    employee = get_object_or_404(User, pk=user_id)
    current_user = request.user

    # Базовая проверка
    if not _can_manage_employee(current_user, employee):
        messages.error(request, 'У вас нет прав для редактирования этого сотрудника')
        return redirect('employee_detail', user_id=user_id)

    # Дополнительная проверка по нашим новым правилам
    if not _can_manage_employee_by_rule(current_user, employee):
        messages.error(
            request,
            'Вы можете редактировать только сотрудников своей лаборатории и только разрешённой роли'
        )
        return redirect('employee_detail', user_id=user_id)

    lab_restricted = _is_lab_restricted(current_user)

    if lab_restricted and not current_user.laboratory_id:
        messages.error(request, 'У вас не указана лаборатория. Обратитесь к администратору.')
        return redirect('employee_detail', user_id=user_id)

    laboratories = _get_allowed_laboratories(current_user)
    roles = _get_allowed_role_choices(current_user)

    mentors = User.objects.filter(
        is_active=True,
        is_trainee=False
    ).exclude(pk=employee.pk)

    if lab_restricted:
        mentors = mentors.filter(laboratory_id=current_user.laboratory_id)

    mentors = mentors.order_by('last_name', 'first_name')

    if request.method == 'POST':
        errors = []

        last_name  = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        sur_name   = request.POST.get('sur_name', '').strip()
        position   = request.POST.get('position', '').strip() or None
        lab_id     = request.POST.get('laboratory', '').strip()
        role       = request.POST.get('role', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        is_trainee = request.POST.get('is_trainee') == 'on'
        mentor_id  = request.POST.get('mentor', '').strip() or None

        # ── Ограничения по роли
        if not _can_assign_role(current_user, role):
            errors.append('Вы не можете назначить этому сотруднику такую роль')

        # ── Ограничения по лаборатории
        if not _can_assign_laboratory(current_user, lab_id):
            errors.append('Вы можете переводить сотрудника только в свою лабораторию')
            lab_id = str(current_user.laboratory_id)

        # ── Валидация
        if not last_name:
            errors.append('Фамилия обязательна')
        if not first_name:
            errors.append('Имя обязательно')

        phone_clean, phone_err = _validate_phone(phone)
        if phone_err:
            errors.append(phone_err)

        if is_trainee and not mentor_id:
            errors.append('Для стажёра обязательно указать наставника')

        if mentor_id and str(mentor_id) == str(employee.pk):
            errors.append('Сотрудник не может быть наставником самому себе')

        if errors:
            for err in errors:
                messages.error(request, err)

            # Чтобы форма не сбрасывалась после ошибки
            employee.last_name = last_name
            employee.first_name = first_name
            employee.sur_name = sur_name
            employee.position = position
            employee.laboratory_id = _safe_int(lab_id)
            employee.role = role
            employee.email = email
            employee.phone = phone
            employee.is_trainee = is_trainee
            employee.mentor_id = _safe_int(mentor_id)

        else:
            employee.last_name = last_name
            employee.first_name = first_name
            employee.sur_name = sur_name
            employee.position = position
            employee.laboratory_id = _safe_int(lab_id)
            employee.role = role
            employee.email = email
            employee.phone = phone_clean
            employee.is_trainee = is_trainee
            employee.mentor_id = _safe_int(mentor_id)

            try:
                employee.save()

                try:
                    from core.views.audit import log_action
                    log_action(
                        request, 'USER', employee.pk, 'EMPLOYEE_EDIT',
                        extra_data={'employee': employee.full_name}
                    )
                except Exception:
                    pass

                messages.success(request, f'Сотрудник {employee.full_name} обновлён')
                return redirect('employee_detail', user_id=employee.pk)

            except Exception as e:
                messages.error(request, f'Ошибка сохранения: {e}')

    context = {
        'employee': employee,
        'laboratories': laboratories,
        'roles': roles,
        'mentors': mentors,
        'is_new': False,
        'lab_restricted': lab_restricted,
    }
    return render(request, 'core/employee_edit.html', context)

# ─────────────────────────────────────────────────────────────
# Деактивация / активация
# ─────────────────────────────────────────────────────────────

@login_required
def employee_deactivate(request, user_id):
    if request.method != 'POST':
        return redirect('employee_detail', user_id=user_id)

    employee = get_object_or_404(User, pk=user_id)

    if not _can_manage_employee(request.user, employee):
        return HttpResponseForbidden()

    if employee.pk == request.user.pk:
        messages.error(request, 'Нельзя деактивировать самого себя')
        return redirect('employee_detail', user_id=user_id)

    employee.is_active = False
    employee.save()

    try:
        from core.views.audit import log_action
        log_action(
                request, 'USER', employee.pk, 'EMPLOYEE_DEACTIVATE',
                extra_data={'employee': employee.full_name}
        )
    except Exception:
        pass

    messages.success(request, f'Сотрудник {employee.full_name} деактивирован')
    return redirect('employee_detail', user_id=user_id)


@login_required
def employee_activate(request, user_id):
    if request.method != 'POST':
        return redirect('employee_detail', user_id=user_id)

    employee = get_object_or_404(User, pk=user_id)

    if not _can_manage_employee(request.user, employee):
        return HttpResponseForbidden()

    employee.is_active = True
    employee.save()

    try:
        from core.views.audit import log_action
        log_action(
                request, 'USER', employee.pk, 'EMPLOYEE_ACTIVATE',
                extra_data={'employee': employee.full_name}
        )
    except Exception:
        pass

    messages.success(request, f'Сотрудник {employee.full_name} активирован')
    return redirect('employee_detail', user_id=user_id)


# ─────────────────────────────────────────────────────────────
# Сброс пароля (админом)
# ─────────────────────────────────────────────────────────────

@login_required
def employee_reset_password(request, user_id):
    if request.method != 'POST':
        return redirect('employee_detail', user_id=user_id)

    employee = get_object_or_404(User, pk=user_id)

    if not _can_manage_employee(request.user, employee):
        return HttpResponseForbidden()

    new_password = _generate_password()
    employee.set_password(new_password)
    employee.save()

    try:
        from core.views.audit import log_action
        log_action(
                request, 'USER', employee.pk, 'EMPLOYEE_RESET_PASSWORD',
                extra_data={'employee': employee.full_name}
        )
    except Exception:
        pass

    messages.success(
        request,
        f'Пароль для {employee.full_name} сброшен. '
        f'Новый пароль: {new_password} — запишите его, он больше не будет показан!'
    )
    return redirect('employee_detail', user_id=user_id)


# ─────────────────────────────────────────────────────────────
# Смена своего пароля
# ─────────────────────────────────────────────────────────────

@login_required
def change_password(request):
    if request.method == 'POST':
        old_password     = request.POST.get('old_password', '')
        new_password     = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        errors = []

        if not request.user.check_password(old_password):
            errors.append('Текущий пароль указан неверно')
        if len(new_password) < 4:
            errors.append('Новый пароль слишком короткий (минимум 4 символа)')
        if new_password != confirm_password:
            errors.append('Пароли не совпадают')
        if old_password and new_password == old_password:
            errors.append('Новый пароль совпадает с текущим')

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            request.user.set_password(new_password)
            request.user.save()
            # Обновляем хеш в текущей сессии — без этого и текущая сессия слетит.
            # Все остальные сессии (телефон, другой браузер) будут инвалидированы
            # автоматически, т.к. их session auth hash не совпадёт с новым паролем.
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Пароль успешно изменён')
            return redirect('workspace_home')

    return render(request, 'core/change_password.html')


# ─────────────────────────────────────────────────────────────
# AJAX: проверка уникальности username
# ─────────────────────────────────────────────────────────────

@login_required
def api_check_username(request):
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({'available': False, 'error': 'Пустой логин'})

    exists = User.objects.filter(username=username).exists()
    return JsonResponse({'available': not exists})


# ─────────────────────────────────────────────────────────────
# Матрица ответственности — удалена в v3.74.0
# Редактирование областей аккредитации перенесено в карточку сотрудника
# (employee_save_areas выше).
# ─────────────────────────────────────────────────────────────


@login_required
@require_POST
def avatar_upload(request, user_id):
    """Загрузка аватарки сотрудника."""
    employee = get_object_or_404(User, pk=user_id)

    if request.user.pk != employee.pk and not _can_manage_employee(request.user, employee):
        return JsonResponse({'error': 'Нет прав'}, status=403)

    file = request.FILES.get('avatar')
    if not file:
        return JsonResponse({'error': 'Нет файла'}, status=400)

    if not file.content_type.startswith('image/'):
        return JsonResponse({'error': 'Только изображения'}, status=400)

    if file.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'Максимум 5 МБ'}, status=400)

    # ═══ Удаляем старую из S3 ═══
    if employee.avatar_path:
        from core.services.s3_utils import delete_file
        delete_file(employee.avatar_path)

    # ═══ Загрузка в S3 ═══
    from core.services.s3_utils import upload_file

    ext = os.path.splitext(file.name)[1].lower()
    safe_name = f'{employee.id}_{uuid.uuid4().hex[:8]}{ext}'
    s3_key = f'avatars/{safe_name}'

    result = upload_file(file, s3_key, content_type=file.content_type)
    if not result:
        return JsonResponse({'error': 'Ошибка загрузки'}, status=500)

    # Сохраняем S3-ключ в БД
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('UPDATE users SET avatar_path = %s WHERE id = %s', [s3_key, employee.id])

    return JsonResponse({
        'ok': True,
        'avatar_url': f'/api/avatar/{s3_key}',
    })


@login_required
@require_POST
def avatar_delete(request, user_id):
    """Удалить аватарку сотрудника."""
    employee = get_object_or_404(User, pk=user_id)

    if request.user.pk != employee.pk and not _can_manage_employee(request.user, employee):
        return JsonResponse({'error': 'Нет прав'}, status=403)

    # Удаляем из S3
    if employee.avatar_path:
        from core.services.s3_utils import delete_file
        delete_file(employee.avatar_path)

    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('UPDATE users SET avatar_path = NULL WHERE id = %s', [employee.id])

    return JsonResponse({'ok': True})

@require_GET
@login_required
def api_avatar(request, s3_key):
    """Отдаёт presigned URL для аватарки."""
    from core.services.s3_utils import get_presigned_url
    url = get_presigned_url(s3_key, expires_in=3600, content_type='image/jpeg')
    if not url:
        raise Http404('Аватарка не найдена')
    from django.shortcuts import redirect
    return redirect(url)


# ═══════════════════════════════════════════════════════════════════════
# ⭐ v3.76.0 — API для кросс-редактирования из карточки сотрудника
# ═══════════════════════════════════════════════════════════════════════


@login_required
@require_POST
def api_employee_toggle_standard(request, user_id):
    """
    Назначить/снять user_standard_access для сотрудника в конкретной области.

    URL:   POST /workspace/employees/<user_id>/api/toggle-standard/
    Тело:  {"standard_id": int, "area_id": int,
            "mode": "GRANTED"|"REVOKED"|null, "reason": str?}

    ⭐ v3.79.0: per-area. area_id обязателен. Override применяется к
    тройке (user, standard, area). Нажатие ✕ на бейдже стандарта в
    одной области не влияет на другие области.

    Семантика mode:
      - 'GRANTED'  — дать допуск вручную в этой области.
      - 'REVOKED'  — отозвать в этой области (исключить из автонабора).
      - null       — удалить запись, вернуть «чисто по области».

    Права: SYSADMIN + LAB_HEAD primary-лабы сотрудника
           (см. can_manage_user_standard_access).
    """
    employee = get_object_or_404(User, pk=user_id)

    from core.services.equipment_access import (
        can_manage_user_standard_access,
        toggle_user_standard_access,
    )

    if not can_manage_user_standard_access(request.user, employee):
        return JsonResponse({'error': 'Нет прав на редактирование этого сотрудника'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)

    standard_id = data.get('standard_id')
    area_id = data.get('area_id')
    mode = data.get('mode')
    reason = (data.get('reason') or '').strip() or None

    if not standard_id:
        return JsonResponse({'error': 'standard_id обязателен'}, status=400)
    if not area_id:
        return JsonResponse({'error': 'area_id обязателен'}, status=400)
    if mode not in ('GRANTED', 'REVOKED', None):
        return JsonResponse(
            {'error': "mode должен быть 'GRANTED', 'REVOKED' или null"}, status=400
        )

    from core.models import Standard
    from core.models.base import AccreditationArea
    standard = get_object_or_404(Standard, pk=standard_id)
    area = get_object_or_404(AccreditationArea, pk=area_id)

    # ⭐ v3.79.0: валидация «область принадлежит сотруднику».
    # Защита от подмены area_id в POST.
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM user_accreditation_areas "
            "WHERE user_id = %s AND accreditation_area_id = %s",
            [employee.pk, area_id],
        )
        if not cur.fetchone():
            return JsonResponse(
                {'error': 'У сотрудника нет этой области аккредитации'},
                status=400
            )

    status, prev_mode = toggle_user_standard_access(
        user_id=employee.pk,
        standard_id=standard.pk,
        area_id=area.pk,
        mode=mode,
        reason=reason,
        actor_id=request.user.pk,
    )

    # ⭐ v3.79.0: сообщения упоминают область
    area_name = area.name
    if mode == 'REVOKED':
        msg = f'{standard.code}: исключён из допуска {employee.full_name} в области «{area_name}»'
        action_name = 'user_excluded_from_standard'
    elif mode == 'GRANTED':
        msg = f'{standard.code}: {employee.full_name} допущен вручную в области «{area_name}»'
        action_name = 'user_granted_standard'
    else:  # None
        if prev_mode == 'REVOKED':
            msg = f'{standard.code}: {employee.full_name} возвращён в допуск в области «{area_name}»'
            action_name = 'user_included_to_standard'
        elif prev_mode == 'GRANTED':
            msg = f'{standard.code}: ручной допуск {employee.full_name} в области «{area_name}» снят'
            action_name = 'user_standard_grant_removed'
        else:
            msg = 'Изменений нет'
            action_name = 'user_standard_noop'

    try:
        from core.views.audit import log_action
        log_action(
            request,
            entity_type='user',
            entity_id=employee.pk,
            action=action_name,
            extra_data={
                'standard_id': standard.pk,
                'standard_code': standard.code,
                'area_id': area_id,
                'area_name': area_name,
                'mode': mode,
                'prev_mode': prev_mode,
                'status': status,
                'reason': reason,
            },
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'message': msg,
        'mode': mode,
        'prev_mode': prev_mode,
        'status': status,
        'area_id': area_id,
    })


@login_required
@require_POST
def api_employee_grant_standard_all_areas(request, user_id):
    """
    ⭐ v3.79.0 Кусок 6: «+ Добавить стандарт» из dropdown'а карточки сотрудника.
    Создаёт GRANTED-запись для пары (user, standard) во ВСЕХ областях сотрудника,
    где для этой пары ещё нет записи (A2: существующие REVOKED не трогаются).

    URL:   POST /workspace/employees/<user_id>/api/grant-standard-all/
    Тело:  {"standard_id": int, "reason": str?}

    Права: SYSADMIN + LAB_HEAD primary-лабы сотрудника.
    """
    employee = get_object_or_404(User, pk=user_id)

    from core.services.equipment_access import (
        can_manage_user_standard_access,
        grant_standard_to_all_user_areas,
    )
    if not can_manage_user_standard_access(request.user, employee):
        return JsonResponse({'error': 'Нет прав на редактирование этого сотрудника'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)

    standard_id = data.get('standard_id')
    reason = (data.get('reason') or '').strip() or None
    if not standard_id:
        return JsonResponse({'error': 'standard_id обязателен'}, status=400)

    from core.models import Standard
    standard = get_object_or_404(Standard, pk=standard_id)

    result = grant_standard_to_all_user_areas(
        user_id=employee.pk,
        standard_id=standard.pk,
        reason=reason,
        actor_id=request.user.pk,
    )

    added = result['added']
    skipped = result['skipped']
    if added == 0 and skipped > 0:
        msg = f'{standard.code}: во всех областях уже есть запись — без изменений'
    elif skipped == 0:
        msg = f'{standard.code}: {employee.full_name} допущен в {added} обл.'
    else:
        msg = f'{standard.code}: допущен в {added} обл., пропущено {skipped} (уже есть записи)'

    try:
        from core.views.audit import log_action
        log_action(
            request,
            entity_type='user',
            entity_id=employee.pk,
            action='user_granted_standard_all_areas',
            extra_data={
                'standard_id': standard.pk,
                'standard_code': standard.code,
                'added': added,
                'skipped': skipped,
                'reason': reason,
            },
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'message': msg,
        'added': added,
        'skipped': skipped,
    })


@login_required
@require_POST
def api_employee_clear_standard_grant_all_areas(request, user_id):
    """
    ⭐ v3.79.0 Кусок 6: ✕ на «🔓 Назначены вручную» плашке в карточке сотрудника.
    Удаляет GRANTED-записи пары (user, standard) во всех областях.
    REVOKED-записи не трогаются.

    URL:   POST /workspace/employees/<user_id>/api/clear-standard-grant-all/
    Тело:  {"standard_id": int}

    Права: SYSADMIN + LAB_HEAD primary-лабы сотрудника.
    """
    employee = get_object_or_404(User, pk=user_id)

    from core.services.equipment_access import (
        can_manage_user_standard_access,
        clear_standard_grant_all_user_areas,
    )
    if not can_manage_user_standard_access(request.user, employee):
        return JsonResponse({'error': 'Нет прав на редактирование этого сотрудника'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)

    standard_id = data.get('standard_id')
    if not standard_id:
        return JsonResponse({'error': 'standard_id обязателен'}, status=400)

    from core.models import Standard
    standard = get_object_or_404(Standard, pk=standard_id)

    result = clear_standard_grant_all_user_areas(
        user_id=employee.pk,
        standard_id=standard.pk,
    )
    deleted = result['deleted']

    if deleted == 0:
        msg = f'{standard.code}: ручных назначений не было'
    else:
        msg = f'{standard.code}: ручные назначения сняты ({deleted} обл.)'

    try:
        from core.views.audit import log_action
        log_action(
            request,
            entity_type='user',
            entity_id=employee.pk,
            action='user_standard_grant_all_areas_removed',
            extra_data={
                'standard_id': standard.pk,
                'standard_code': standard.code,
                'deleted': deleted,
            },
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'message': msg,
        'deleted': deleted,
    })


@login_required
@require_POST
def api_employee_update_areas(request, user_id):
    """
    AJAX-вариант сохранения областей аккредитации сотрудника.
    Отличается от employee_save_areas только форматом запроса/ответа.

    URL:   POST /workspace/employees/<user_id>/api/update-areas/
    Тело:  {"area_ids": [int, int, ...]}

    Права: как у employee_save_areas — SYSADMIN/CEO/CTO или LAB_HEAD своего сотрудника.
    """
    employee = get_object_or_404(User, pk=user_id)

    can_edit_areas = _can_manage_accreditation(request.user)
    if not can_edit_areas and request.user.role == 'LAB_HEAD':
        can_edit_areas = _can_manage_employee(request.user, employee)
    if not can_edit_areas:
        return JsonResponse({'error': 'Нет прав'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)

    raw_ids = data.get('area_ids') or []
    if not isinstance(raw_ids, list):
        return JsonResponse({'error': 'area_ids должен быть списком'}, status=400)

    try:
        area_ids_int = [int(a) for a in raw_ids]
    except (TypeError, ValueError):
        return JsonResponse({'error': 'area_ids содержит нечисловые значения'}, status=400)

    from core.services.equipment_access import replace_user_areas
    result = replace_user_areas(
        user_id=employee.pk,
        area_ids=area_ids_int,
        actor_id=request.user.pk,
    )

    if result['added'] or result['removed']:
        try:
            from core.views.audit import log_action
            areas_map = dict(AccreditationArea.objects.values_list('id', 'name'))
            log_action(
                request, 'USER', employee.pk, 'EMPLOYEE_AREAS_CHANGED',
                extra_data={
                    'employee': employee.full_name,
                    'added_count': result['added'],
                    'removed_count': result['removed'],
                    'final_ids': sorted(set(area_ids_int)),
                    'final_names': sorted(areas_map.get(a, str(a)) for a in set(area_ids_int)),
                }
            )
        except Exception:
            pass

    return JsonResponse({
        'success': True,
        'added': result['added'],
        'removed': result['removed'],
        'kept': result['kept'],
        'message': f'Области обновлены: +{result["added"]} / −{result["removed"]}',
    })
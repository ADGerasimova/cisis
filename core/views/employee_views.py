"""
employee_views.py — Справочник сотрудников
v3.27.0

Расположение: core/views/employee_views.py

Подключить в core/views/__init__.py:
    from . import employee_views

Маршруты в core/urls.py:
    path('workspace/employees/', employee_views.employees_list, name='employees'),
    path('workspace/employees/add/', employee_views.employee_add, name='employee_add'),
    path('workspace/employees/<int:user_id>/', employee_views.employee_detail, name='employee_detail'),
    path('workspace/employees/<int:user_id>/edit/', employee_views.employee_edit, name='employee_edit'),
    path('workspace/employees/<int:user_id>/deactivate/', employee_views.employee_deactivate, name='employee_deactivate'),
    path('workspace/employees/<int:user_id>/activate/', employee_views.employee_activate, name='employee_activate'),
    path('workspace/employees/<int:user_id>/reset-password/', employee_views.employee_reset_password, name='employee_reset_password'),
    path('workspace/change-password/', employee_views.change_password, name='change_password'),
    path('api/check-username/', employee_views.api_check_username, name='api_check_username'),
"""

import re
import secrets
import string
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q

from core.permissions import PermissionChecker
from core.models import User, Laboratory, UserRole

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


def _validate_phone(phone):
    """Валидация телефона. Возвращает (cleaned, error)."""
    if not phone:
        return '', None
    phone = phone.strip()
    if not PHONE_RE.match(phone):
        return phone, 'Некорректный формат телефона'
    return phone, None


def _generate_password(length=10):
    """Генерирует случайный пароль."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


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

    context = {
        'employee':     employee,
        'role_display': role_display,
        'mentor_name':  mentor_name,
        'trainees':     trainees,
        'can_manage':   can_manage,
        'is_self':      is_self,
    }
    return render(request, 'core/employee_detail.html', context)


# ─────────────────────────────────────────────────────────────
# Редактирование сотрудника
# ─────────────────────────────────────────────────────────────

@login_required
def employee_edit(request, user_id):
    employee = get_object_or_404(User, pk=user_id)

    if not _can_manage_employee(request.user, employee):
        messages.error(request, 'У вас нет прав для редактирования этого сотрудника')
        return redirect('employee_detail', user_id=user_id)

    laboratories = Laboratory.objects.filter(is_active=True).order_by('name')
    roles = UserRole.choices
    mentors = User.objects.filter(
        is_active=True, is_trainee=False
    ).exclude(pk=employee.pk).order_by('last_name', 'first_name')

    if request.method == 'POST':
        errors = []

        # Собираем данные
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

        # Валидация
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
        else:
            employee.last_name  = last_name
            employee.first_name = first_name
            employee.sur_name   = sur_name
            employee.position   = position
            employee.laboratory_id = int(lab_id) if lab_id else None
            employee.role       = role
            employee.email      = email
            employee.phone      = phone_clean
            employee.is_trainee = is_trainee
            employee.mentor_id  = int(mentor_id) if mentor_id else None

            try:
                employee.save()

                # Аудит
                try:
                    from core.views.audit import log_action
                    log_action(
                        user=request.user,
                        action='EMPLOYEE_EDIT',
                        target_type='USER',
                        target_id=employee.pk,
                        extra_data={'employee': employee.full_name}
                    )
                except Exception:
                    pass

                messages.success(request, f'Сотрудник {employee.full_name} обновлён')
                return redirect('employee_detail', user_id=employee.pk)
            except Exception as e:
                messages.error(request, f'Ошибка сохранения: {e}')

    context = {
        'employee':     employee,
        'laboratories': laboratories,
        'roles':        roles,
        'mentors':      mentors,
        'is_new':       False,
    }
    return render(request, 'core/employee_edit.html', context)


# ─────────────────────────────────────────────────────────────
# Добавление сотрудника
# ─────────────────────────────────────────────────────────────

@login_required
def employee_add(request):
    if not PermissionChecker.can_edit(request.user, 'EMPLOYEES', 'access'):
        messages.error(request, 'У вас нет прав для добавления сотрудников')
        return redirect('employees')

    laboratories = Laboratory.objects.filter(is_active=True).order_by('name')
    roles = UserRole.choices
    mentors = User.objects.filter(
        is_active=True, is_trainee=False
    ).order_by('last_name', 'first_name')

    # Пустой «сотрудник» для шаблона
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

        # Валидация
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
            # Сохраняем введённые данные для повторного заполнения
            employee = {
                'username': username, 'last_name': last_name,
                'first_name': first_name, 'sur_name': sur_name,
                'position': position, 'laboratory_id': int(lab_id) if lab_id else None,
                'role': role, 'email': email, 'phone': phone,
                'is_trainee': is_trainee, 'mentor_id': int(mentor_id) if mentor_id else None,
            }
        else:
            try:
                new_user = User(
                    username=username,
                    last_name=last_name,
                    first_name=first_name,
                    sur_name=sur_name,
                    position=position,
                    laboratory_id=int(lab_id) if lab_id else None,
                    role=role,
                    email=email,
                    phone=phone_clean,
                    is_trainee=is_trainee,
                    mentor_id=int(mentor_id) if mentor_id else None,
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                )
                new_user.set_password(password)
                new_user.save()

                # Аудит
                try:
                    from core.views.audit import log_action
                    log_action(
                        user=request.user,
                        action='EMPLOYEE_ADD',
                        target_type='USER',
                        target_id=new_user.pk,
                        extra_data={'employee': new_user.full_name}
                    )
                except Exception:
                    pass

                messages.success(request, f'Сотрудник {new_user.full_name} добавлен')
                return redirect('employee_detail', user_id=new_user.pk)
            except Exception as e:
                messages.error(request, f'Ошибка создания: {e}')

    context = {
        'employee':     employee,
        'laboratories': laboratories,
        'roles':        roles,
        'mentors':      mentors,
        'is_new':       True,
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
            user=request.user,
            action='EMPLOYEE_DEACTIVATE',
            target_type='USER',
            target_id=employee.pk,
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
            user=request.user,
            action='EMPLOYEE_ACTIVATE',
            target_type='USER',
            target_id=employee.pk,
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
            user=request.user,
            action='EMPLOYEE_RESET_PASSWORD',
            target_type='USER',
            target_id=employee.pk,
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

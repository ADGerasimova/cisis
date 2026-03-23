"""
core/views/task_views.py — Задачи
v3.39.0

- task_list: список задач (свои / лаборатории / все)
- task_create: ручное создание задачи
- task_update_status: смена статуса (AJAX)
- create_auto_task / close_auto_tasks: хелперы для автозадач
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q

from core.models.tasks import Task, TaskType, TaskStatus, TaskPriority
from core.models import User, Laboratory

logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 30

# Роли, которые видят задачи всей лаборатории
LAB_MANAGER_ROLES = ('LAB_HEAD', 'CLIENT_DEPT_HEAD', 'SYSADMIN', 'QMS_HEAD', 'CTO', 'CEO')


# ─────────────────────────────────────────────────────────────
# Список задач
# ─────────────────────────────────────────────────────────────

@login_required
def task_list(request):
    """Страница задач."""
    user = request.user
    view_mode = request.GET.get('view', 'my')  # my / lab / all

    # Базовый queryset
    qs = Task.objects.select_related('assignee', 'created_by', 'laboratory')

    # Доступ
    if user.role == 'SYSADMIN':
        if view_mode == 'my':
            qs = qs.filter(assignee=user)
        elif view_mode == 'lab' and user.laboratory_id:
            qs = qs.filter(laboratory=user.laboratory)
        # else: все
    elif user.role in LAB_MANAGER_ROLES:
        if view_mode == 'lab' and user.laboratory_id:
            qs = qs.filter(laboratory=user.laboratory)
        elif view_mode == 'all':
            # LAB_HEAD видит свою лабу + свои
            qs = qs.filter(
                Q(assignee=user) | Q(laboratory=user.laboratory)
            )
        else:
            qs = qs.filter(assignee=user)
    else:
        # TESTER, WORKSHOP и т.д. — только свои
        qs = qs.filter(assignee=user)
        view_mode = 'my'

    # Фильтры
    f_status = request.GET.get('status', '')
    f_type = request.GET.get('type', '')
    f_priority = request.GET.get('priority', '')

    if f_status:
        qs = qs.filter(status=f_status)
    else:
        # По умолчанию — только открытые
        qs = qs.filter(status__in=['OPEN', 'IN_PROGRESS'])

    if f_type:
        qs = qs.filter(task_type=f_type)
    if f_priority:
        qs = qs.filter(priority=f_priority)

    # Счётчики
    my_base = Task.objects.filter(assignee=user)
    count_open = my_base.filter(status='OPEN').count()
    count_in_progress = my_base.filter(status='IN_PROGRESS').count()
    count_overdue = my_base.filter(
        status__in=['OPEN', 'IN_PROGRESS'],
        deadline__lt=timezone.now().date(),
    ).exclude(deadline__isnull=True).count()

    # Сортировка
    sort = request.GET.get('sort', 'deadline')
    if sort == 'deadline':
        qs = qs.order_by(
            # Сначала просроченные, потом по дедлайну, потом без дедлайна
            models_nulls_last('deadline'),
        )
    elif sort == '-created_at':
        qs = qs.order_by('-created_at')
    elif sort == 'priority':
        qs = qs.order_by(
            models.Case(
                models.When(priority='HIGH', then=0),
                models.When(priority='MEDIUM', then=1),
                models.When(priority='LOW', then=2),
                output_field=models.IntegerField(),
            ),
            'deadline',
        )
    else:
        qs = qs.order_by('-created_at')

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Для ручного создания — список пользователей
    assignable_users = []
    if user.role in LAB_MANAGER_ROLES or user.role == 'SYSADMIN':
        assignable_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')

    laboratories = Laboratory.objects.filter(is_active=True).order_by('name')

    context = {
        'page_obj': page_obj,
        'items': page_obj.object_list,
        'total_count': paginator.count,
        'view_mode': view_mode,
        'f_status': f_status,
        'f_type': f_type,
        'f_priority': f_priority,
        'count_open': count_open,
        'count_in_progress': count_in_progress,
        'count_overdue': count_overdue,
        'type_choices': TaskType.choices,
        'status_choices': TaskStatus.choices,
        'priority_choices': TaskPriority.choices,
        'can_manage': user.role in LAB_MANAGER_ROLES or user.role == 'SYSADMIN',
        'assignable_users': assignable_users,
        'laboratories': laboratories,
        'user': user,
    }
    return render(request, 'core/tasks.html', context)


def models_nulls_last(field):
    """Сортировка с NULL в конце."""
    from django.db.models import F
    return F(field).asc(nulls_last=True)


# ─────────────────────────────────────────────────────────────
# Ручное создание задачи
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def task_create(request):
    """Ручное создание задачи."""
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    assignee_id = request.POST.get('assignee_id', '').strip()
    priority = request.POST.get('priority', 'MEDIUM').strip()
    deadline_str = request.POST.get('deadline', '').strip()
    laboratory_id = request.POST.get('laboratory_id', '').strip()

    if not title:
        messages.error(request, 'Укажите заголовок задачи')
        return redirect('task_list')

    if not assignee_id:
        messages.error(request, 'Укажите исполнителя')
        return redirect('task_list')

    try:
        from datetime import datetime
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        task = Task.objects.create(
            task_type='MANUAL',
            title=title,
            description=description,
            assignee_id=int(assignee_id),
            created_by=request.user,
            laboratory_id=int(laboratory_id) if laboratory_id else None,
            priority=priority,
            deadline=deadline,
        )
        messages.success(request, f'Задача «{title}» создана')

        # Аудит
        from core.views.audit import log_action
        log_action(request, 'task', task.id, 'task_created',
                   extra_data={'title': title, 'assignee_id': assignee_id})

    except Exception as e:
        logger.exception('Ошибка создания задачи')
        messages.error(request, f'Ошибка: {e}')

    return redirect('task_list')


# ─────────────────────────────────────────────────────────────
# Смена статуса задачи (AJAX)
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def task_update_status(request, task_id):
    """AJAX: смена статуса задачи."""
    task = get_object_or_404(Task, id=task_id)

    # Проверка прав: свою задачу может менять любой, чужую — только менеджеры
    if task.assignee_id != request.user.id and request.user.role not in LAB_MANAGER_ROLES and request.user.role != 'SYSADMIN':
        return JsonResponse({'error': 'Нет прав'}, status=403)

    new_status = request.POST.get('status', '').strip()
    if new_status not in dict(TaskStatus.choices):
        return JsonResponse({'error': 'Неверный статус'}, status=400)

    old_status = task.status
    task.status = new_status
    if new_status in ('DONE', 'CANCELLED'):
        task.completed_at = timezone.now()
    elif new_status in ('OPEN', 'IN_PROGRESS'):
        task.completed_at = None
    task.save()

    from core.views.audit import log_action
    log_action(request, 'task', task.id, 'task_status_changed',
               field_name='status', old_value=old_status, new_value=new_status)

    return JsonResponse({'success': True, 'status': new_status})


# ─────────────────────────────────────────────────────────────
# Хелперы для автосоздания задач
# ─────────────────────────────────────────────────────────────

def create_auto_task(task_type, sample, assignee, created_by=None):
    """
    Создаёт автозадачу по образцу.

    Вызывается из:
    - save_logic.py (при назначении оператора → TESTING)
    - sample_create (при manufacturing=True → MANUFACTURING)
    """
    from core.models import Sample

    if task_type == 'TESTING':
        title = f'Провести испытание: {sample.cipher or f"#{sample.id}"}'
    elif task_type == 'MANUFACTURING':
        title = f'Изготовить образец: {sample.cipher or f"#{sample.id}"}'
    else:
        title = f'Задача по образцу {sample.cipher or f"#{sample.id}"}'

    # Не создаём дубликат
    existing = Task.objects.filter(
        task_type=task_type,
        entity_type='sample',
        entity_id=sample.id,
        assignee=assignee,
        status__in=['OPEN', 'IN_PROGRESS'],
    ).exists()
    if existing:
        return None

    task = Task.objects.create(
        task_type=task_type,
        title=title,
        entity_type='sample',
        entity_id=sample.id,
        assignee=assignee,
        created_by=created_by,
        laboratory=sample.laboratory,
        deadline=sample.deadline if hasattr(sample, 'deadline') else None,
        priority='MEDIUM',
    )
    return task


def close_auto_tasks(task_type, entity_type, entity_id, assignee_id=None):
    """
    Закрывает автозадачи при смене статуса образца.

    Вызывается из:
    - _handle_status_change (TESTED → закрыть TESTING)
    - _handle_status_change (workshop_status=COMPLETED → закрыть MANUFACTURING)
    - handle_m2m_update (оператор удалён → закрыть TESTING для него)
    """
    qs = Task.objects.filter(
        task_type=task_type,
        entity_type=entity_type,
        entity_id=entity_id,
        status__in=['OPEN', 'IN_PROGRESS'],
    )
    if assignee_id:
        qs = qs.filter(assignee_id=assignee_id)

    count = qs.update(
        status='DONE',
        completed_at=timezone.now(),
    )
    return count
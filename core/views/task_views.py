"""
core/views/task_views.py — Задачи
v3.39.0

Задача может быть индивидуальной (1 исполнитель) или групповой (несколько).
Исполнители хранятся в M2M таблице task_assignees.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from django.db.models import Q

from core.models.tasks import Task, TaskAssignee, TaskType, TaskStatus, TaskPriority
from core.models import User, Laboratory

logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 30

MANAGER_ROLES = (
    'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD',
    'SYSADMIN', 'QMS_HEAD', 'QMS_ADMIN', 'CTO', 'CEO',
    'WORKSHOP_HEAD',
)


# ─────────────────────────────────────────────────────────────
# Список задач
# ─────────────────────────────────────────────────────────────

@login_required
def task_list(request):
    user = request.user
    view_mode = request.GET.get('view', 'my')
    can_manage = user.role in MANAGER_ROLES

    qs = Task.objects.prefetch_related('assignees__user').select_related('created_by', 'laboratory')

    if view_mode == 'created' and can_manage:
        qs = qs.filter(created_by=user)
    elif view_mode == 'lab' and can_manage and user.laboratory_id:
        qs = qs.filter(laboratory=user.laboratory)
    elif view_mode == 'all' and user.role == 'SYSADMIN':
        pass
    elif view_mode == 'all' and can_manage:
        qs = qs.filter(
            Q(assignees__user=user) | Q(created_by=user) | Q(laboratory=user.laboratory)
        ).distinct()
    else:
        qs = qs.filter(assignees__user=user)
        view_mode = 'my'

    f_status = request.GET.get('status', '')
    f_type = request.GET.get('type', '')
    f_priority = request.GET.get('priority', '')

    if f_status:
        qs = qs.filter(status=f_status)
    else:
        qs = qs.filter(status__in=['OPEN', 'IN_PROGRESS'])

    if f_type:
        qs = qs.filter(task_type=f_type)
    if f_priority:
        qs = qs.filter(priority=f_priority)

    my_tasks = Task.objects.filter(assignees__user=user)
    count_open = my_tasks.filter(status='OPEN').count()
    count_in_progress = my_tasks.filter(status='IN_PROGRESS').count()
    count_overdue = my_tasks.filter(
        status__in=['OPEN', 'IN_PROGRESS'],
        deadline__lt=timezone.now().date(),
    ).exclude(deadline__isnull=True).count()

    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Собираем имена исполнителей
    items = list(page_obj.object_list)
    for task in items:
        names = []
        for a in task.assignees.all():
            name = f'{a.user.last_name} {a.user.first_name}'.strip()
            names.append(name or a.user.username)
        task.assignee_names_list = names

    assignable_users = []
    if can_manage:
        assignable_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')

    laboratories = Laboratory.objects.filter(is_active=True).order_by('name')

    return render(request, 'core/tasks.html', {
        'page_obj': page_obj,
        'items': items,
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
        'can_manage': can_manage,
        'assignable_users': assignable_users,
        'laboratories': laboratories,
        'user': user,
    })


# ─────────────────────────────────────────────────────────────
# Ручное создание задачи
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def task_create(request):
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    assignee_ids = request.POST.getlist('assignee_ids')
    priority = request.POST.get('priority', 'MEDIUM').strip()
    deadline_str = request.POST.get('deadline', '').strip()
    laboratory_id = request.POST.get('laboratory_id', '').strip()

    if not title:
        messages.error(request, 'Укажите заголовок задачи')
        return redirect('task_list')
    if not assignee_ids:
        messages.error(request, 'Укажите хотя бы одного исполнителя')
        return redirect('task_list')

    try:
        from datetime import datetime
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        task = Task.objects.create(
            task_type='MANUAL',
            title=title,
            description=description,
            created_by=request.user,
            laboratory_id=int(laboratory_id) if laboratory_id else None,
            priority=priority,
            deadline=deadline,
        )
        for uid in assignee_ids:
            if uid and uid.isdigit():
                TaskAssignee.objects.create(task=task, user_id=int(uid))

        messages.success(request, f'Задача «{title}» создана ({len(assignee_ids)} исполнит.)')

        from core.views.audit import log_action
        log_action(request, 'task', task.id, 'task_created',
                   extra_data={'title': title, 'assignee_count': len(assignee_ids)})
    except Exception as e:
        logger.exception('Ошибка создания задачи')
        messages.error(request, f'Ошибка: {e}')

    return redirect('task_list')


# ─────────────────────────────────────────────────────────────
# Смена статуса (AJAX)
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def task_update_status(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    is_assignee = TaskAssignee.objects.filter(task=task, user=request.user).exists()
    is_manager = request.user.role in MANAGER_ROLES
    if not is_assignee and not is_manager:
        return JsonResponse({'error': 'Нет прав'}, status=403)

    new_status = request.POST.get('status', '').strip()
    if new_status not in dict(TaskStatus.choices):
        return JsonResponse({'error': 'Неверный статус'}, status=400)

    old_status = task.status
    task.status = new_status
    if new_status in ('DONE', 'CANCELLED'):
        task.completed_at = timezone.now()
    else:
        task.completed_at = None
    task.save()

    from core.views.audit import log_action
    log_action(request, 'task', task.id, 'task_status_changed',
               field_name='status', old_value=old_status, new_value=new_status)

    return JsonResponse({'success': True, 'status': new_status})


# ─────────────────────────────────────────────────────────────
# Хелперы для автозадач
# ─────────────────────────────────────────────────────────────

def create_auto_task(task_type, sample, assignee_ids, created_by=None):
    """
    Создаёт или обновляет групповую автозадачу по образцу.
    assignee_ids — список/set ID пользователей или один int.

    Если задача уже есть — синхронизирует исполнителей.
    """
    if isinstance(assignee_ids, int):
        assignee_ids = [assignee_ids]
    assignee_ids = set(int(x) for x in assignee_ids if x)
    if not assignee_ids:
        return None

    if task_type == 'TESTING':
        title = f'Провести испытание: {sample.cipher or f"#{sample.id}"}'
    elif task_type == 'MANUFACTURING':
        title = f'Изготовить образец: {sample.cipher or f"#{sample.id}"}'
    else:
        title = f'Задача по образцу {sample.cipher or f"#{sample.id}"}'

    # Ищем существующую открытую задачу
    existing = Task.objects.filter(
        task_type=task_type,
        entity_type='sample',
        entity_id=sample.id,
        status__in=['OPEN', 'IN_PROGRESS'],
    ).first()

    if existing:
        _sync_assignees(existing, assignee_ids)
        return existing

    task = Task.objects.create(
        task_type=task_type,
        title=title,
        entity_type='sample',
        entity_id=sample.id,
        created_by=created_by,
        laboratory=sample.laboratory,
        deadline=getattr(sample, 'deadline', None),
        priority='MEDIUM',
    )
    for uid in assignee_ids:
        TaskAssignee.objects.get_or_create(task=task, user_id=uid)

    return task


def _sync_assignees(task, new_user_ids):
    """Синхронизирует исполнителей задачи."""
    new_ids = set(int(x) for x in new_user_ids)
    current_ids = set(TaskAssignee.objects.filter(task=task).values_list('user_id', flat=True))

    for uid in new_ids - current_ids:
        TaskAssignee.objects.get_or_create(task=task, user_id=uid)

    to_remove = current_ids - new_ids
    if to_remove:
        TaskAssignee.objects.filter(task=task, user_id__in=to_remove).delete()

    if not TaskAssignee.objects.filter(task=task).exists():
        task.status = 'CANCELLED'
        task.completed_at = timezone.now()
        task.save()


def close_auto_tasks(task_type, entity_type, entity_id):
    """Закрывает все автозадачи по сущности."""
    return Task.objects.filter(
        task_type=task_type,
        entity_type=entity_type,
        entity_id=entity_id,
        status__in=['OPEN', 'IN_PROGRESS'],
    ).update(status='DONE', completed_at=timezone.now())
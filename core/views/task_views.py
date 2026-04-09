"""
core/views/task_views.py — Задачи
v3.52.0 — Добавлены комментарии к задачам

Задача может быть индивидуальной (1 исполнитель) или групповой (несколько).
Исполнители хранятся в M2M таблице task_assignees.
"""

import logging
import json
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from django.db.models import Q

from core.models.tasks import Task, TaskAssignee, TaskView, TaskType, TaskStatus, TaskPriority, TaskComment
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
    can_create = True  # все могут создавать задачи
    can_manage = user.role in MANAGER_ROLES  # управление — только менеджеры

    qs = Task.objects.prefetch_related('assignees__user').select_related('created_by', 'laboratory')

    if view_mode == 'created':
        qs = qs.filter(created_by=user)
    elif view_mode == 'lab' and user.laboratory_id:
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

    # Счётчики — по текущему view (до фильтров статуса/типа)
    count_open = qs.filter(status='OPEN').count()
    count_in_progress = qs.filter(status='IN_PROGRESS').count()
    count_overdue = qs.filter(
        status__in=['OPEN', 'IN_PROGRESS'],
        deadline__lt=timezone.now().date(),
    ).exclude(deadline__isnull=True).count()

    # Теперь применяем фильтры к qs
    if f_status:
        qs = qs.filter(status=f_status)
    else:
        qs = qs.filter(status__in=['OPEN', 'IN_PROGRESS'])

    if f_type:
        qs = qs.filter(task_type=f_type)
    if f_priority:
        qs = qs.filter(priority=f_priority)

    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Собираем имена исполнителей
    items = list(page_obj.object_list)

    # ── Просмотры (read receipts) ──
    task_ids = [t.id for t in items]
    if task_ids:
        # Все просмотры для задач на текущей странице
        all_views = TaskView.objects.filter(task_id__in=task_ids).select_related('user')
        views_by_task = {}
        for tv in all_views:
            views_by_task.setdefault(tv.task_id, []).append(tv)

        # Автопометка: отмечаем задачи как просмотренные для текущего пользователя
        my_viewed_task_ids = set(
            TaskView.objects.filter(task_id__in=task_ids, user=user)
            .values_list('task_id', flat=True)
        )
        tasks_to_mark = [t.id for t in items if t.id not in my_viewed_task_ids
                         and TaskAssignee.objects.filter(task_id=t.id, user=user).exists()]
        for tid in tasks_to_mark:
            TaskView.objects.get_or_create(task_id=tid, user=user)
    else:
        views_by_task = {}

    for task in items:
        names = []
        for a in task.assignees.all():
            name = f'{a.user.last_name} {a.user.first_name}'.strip()
            names.append(name or a.user.username)
        task.assignee_names_list = names

        # Данные просмотров
        assignee_ids = set(a.user_id for a in task.assignees.all())
        task_views = views_by_task.get(task.id, [])
        viewed_user_ids = set(tv.user_id for tv in task_views)
        viewed_assignee_ids = viewed_user_ids & assignee_ids

        task.total_assignees = len(assignee_ids)
        task.viewed_count = len(viewed_assignee_ids)
        task.all_viewed = task.viewed_count >= task.total_assignees and task.total_assignees > 0
        task.viewed_by_names = [
            f'{tv.user.last_name} {tv.user.first_name}'.strip() or tv.user.username
            for tv in task_views if tv.user_id in assignee_ids
        ]
        task.not_viewed_names = [
            name for a in task.assignees.all()
            if a.user_id not in viewed_assignee_ids
            for name in [f'{a.user.last_name} {a.user.first_name}'.strip() or a.user.username]
        ]

        # ⭐ v3.51.0: Прогресс индивидуального выполнения (режим ALL)
        if task.completion_mode == 'ALL':
            all_assignees_list = list(task.assignees.all())
            task.completed_assignee_count = sum(1 for a in all_assignees_list if a.completed_at)
            task.my_assignee_completed = any(
                a.user_id == user.id and a.completed_at for a in all_assignees_list
            )
            task.completed_assignee_names = [
                f'{a.user.last_name} {a.user.first_name}'.strip() or a.user.username
                for a in all_assignees_list if a.completed_at
            ]
            task.not_completed_assignee_names = [
                f'{a.user.last_name} {a.user.first_name}'.strip() or a.user.username
                for a in all_assignees_list if not a.completed_at
            ]
        else:
            task.completed_assignee_count = 0
            task.my_assignee_completed = False

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
        'can_create': can_create,
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
    completion_mode = request.POST.get('completion_mode', 'ANY').strip()  # ⭐ v3.51.0
    if completion_mode not in ('ANY', 'ALL'):
        completion_mode = 'ANY'

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
            completion_mode=completion_mode,  # ⭐ v3.51.0
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

    # ⭐ v3.51.0: Режим ALL — индивидуальное выполнение
    if task.completion_mode == 'ALL' and new_status == 'DONE' and is_assignee:
        assignee = TaskAssignee.objects.filter(task=task, user=request.user).first()
        if assignee and not assignee.completed_at:
            assignee.completed_at = timezone.now()
            assignee.save(update_fields=['completed_at'])

        # Проверяем: все ли выполнили?
        total = TaskAssignee.objects.filter(task=task).count()
        completed = TaskAssignee.objects.filter(task=task, completed_at__isnull=False).count()

        if completed >= total:
            # Все выполнили — закрываем задачу
            task.status = 'DONE'
            task.completed_at = timezone.now()
            task.save()
        else:
            # Не все — ставим IN_PROGRESS если ещё OPEN
            if task.status == 'OPEN':
                task.status = 'IN_PROGRESS'
                task.save()

        from core.views.audit import log_action
        log_action(request, 'task', task.id, 'task_assignee_completed',
                   extra_data={'user_id': request.user.id, 'completed': completed, 'total': total})

        return JsonResponse({
            'success': True,
            'status': task.status,
            'completed_count': completed,
            'total_count': total,
            'all_done': completed >= total,
        })

    # ⭐ v3.51.0: Режим ALL — возврат задачи (OPEN) сбрасывает все индивидуальные выполнения
    if task.completion_mode == 'ALL' and new_status == 'OPEN':
        TaskAssignee.objects.filter(task=task).update(completed_at=None)

    # Стандартное поведение (ANY или управление менеджером)
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
    elif task_type == 'VERIFY_REGISTRATION':
        title = f'Проверить регистрацию: {sample.cipher or f"#{sample.id}"}'
    elif task_type == 'ACCEPT_SAMPLE':
        title = f'Принять образец: {sample.cipher or f"#{sample.id}"}'
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


# ─────────────────────────────────────────────────────────────
# Просмотры задач (read receipts)
# ─────────────────────────────────────────────────────────────

@login_required
def task_view_details(request, task_id):
    """AJAX: кто просмотрел задачу — для tooltip."""
    task = get_object_or_404(Task, id=task_id)
    assignee_ids = set(TaskAssignee.objects.filter(task=task).values_list('user_id', flat=True))
    views = TaskView.objects.filter(task=task, user_id__in=assignee_ids).select_related('user')

    viewed = []
    viewed_ids = set()
    for tv in views:
        viewed.append({
            'name': f'{tv.user.last_name} {tv.user.first_name}'.strip() or tv.user.username,
            'viewed_at': tv.viewed_at.strftime('%d.%m.%Y %H:%M'),
        })
        viewed_ids.add(tv.user_id)

    not_viewed = []
    for uid in assignee_ids - viewed_ids:
        try:
            u = User.objects.get(pk=uid)
            not_viewed.append(f'{u.last_name} {u.first_name}'.strip() or u.username)
        except User.DoesNotExist:
            pass

    return JsonResponse({
        'viewed': viewed,
        'not_viewed': not_viewed,
        'total_assignees': len(assignee_ids),
    })


# ─────────────────────────────────────────────────────────────
# Уведомления о новых задачах (AJAX polling)
# ─────────────────────────────────────────────────────────────

TASK_TYPE_LABELS = {
    'TESTING': 'Испытание',
    'MANUFACTURING': 'Изготовление',
    'METROLOGY': 'МО оборудования',
    'MAINTENANCE': 'Плановое ТО',
    'VERIFY_REGISTRATION': 'Проверка регистрации',
    'ACCEPT_SAMPLE': 'Приёмка образца',
    'MANUAL': 'Задача',
}


@login_required
def task_notifications(request):
    """
    AJAX: возвращает новые задачи с момента последней проверки.
    GET ?since=ISO_TIMESTAMP
    """
    from datetime import datetime as dt

    since_str = request.GET.get('since', '')
    try:
        since = dt.fromisoformat(since_str) if since_str else None
    except (ValueError, TypeError):
        since = None

    qs = Task.objects.filter(
        assignees__user=request.user,
        status__in=['OPEN', 'IN_PROGRESS'],
    ).select_related('laboratory')

    if since:
        qs = qs.filter(created_at__gt=since)

    qs = qs.order_by('-created_at')[:10]

    tasks_data = []
    for t in qs:
        tasks_data.append({
            'id': t.id,
            'title': t.title,
            'type': t.task_type,
            'type_label': TASK_TYPE_LABELS.get(t.task_type, 'Задача'),
            'priority': t.priority,
            'entity_type': t.entity_type,
            'entity_id': t.entity_id,
            'created_at': t.created_at.isoformat(),
        })

    # Общее количество непрочитанных (открытые)
    total_open = Task.objects.filter(
        assignees__user=request.user,
        status__in=['OPEN', 'IN_PROGRESS'],
    ).count()

    return JsonResponse({
        'tasks': tasks_data,
        'total_open': total_open,
        'server_time': timezone.now().isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# ⭐ v3.52.0: Комментарии к задачам
# ─────────────────────────────────────────────────────────────

def _can_comment(user, task):
    """Проверка права на комментирование задачи."""
    # Админы могут всё
    if user.role in ('SYSADMIN', 'ADMIN'):
        return True
    # Создатель задачи
    if task.created_by_id == user.id:
        return True
    # Исполнитель
    return TaskAssignee.objects.filter(task=task, user=user).exists()


def _can_delete_comment(user, comment):
    """Проверка права на удаление комментария."""
    # Автор может удалить в течение 5 минут
    if comment.author_id == user.id:
        if timezone.now() - comment.created_at < timedelta(minutes=5):
            return True
    # Админы могут удалять всё
    if user.role in ('SYSADMIN', 'ADMIN'):
        return True
    # Создатель задачи может удалять комментарии
    if comment.task.created_by_id == user.id:
        return True
    return False


@login_required
@require_http_methods(["GET"])
def task_comments_list(request, task_id):
    """Получение списка комментариев к задаче."""
    task = get_object_or_404(Task, id=task_id)
    
    # Проверка доступа
    if not _can_comment(request.user, task):
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    
    comments = TaskComment.objects.filter(task=task).select_related('author').order_by('created_at')
    
    comments_data = []
    for c in comments:
        # Формируем инициалы
        initials = ''
        if c.author.first_name:
            initials += c.author.first_name[0]
        if c.author.last_name:
            initials += c.author.last_name[0]
        if not initials:
            initials = '??'
        
        comments_data.append({
            'id': c.id,
            'author_id': c.author_id,
            'author_name': c.author.full_name if hasattr(c.author, 'full_name') else f'{c.author.last_name} {c.author.first_name}'.strip(),
            'author_initials': initials.upper(),
            'text': c.text,
            'created_at': c.created_at.isoformat(),
            'created_at_display': c.created_at.strftime('%d.%m.%Y %H:%M'),
            'can_delete': _can_delete_comment(request.user, c),
        })
    
    return JsonResponse({
        'comments': comments_data,
        'total': len(comments_data),
        'can_comment': _can_comment(request.user, task),
    })


@login_required
@require_http_methods(["POST"])
def task_comment_create(request, task_id):
    """Создание нового комментария."""
    task = get_object_or_404(Task, id=task_id)
    
    if not _can_comment(request.user, task):
        return JsonResponse({'error': 'Нет права комментировать'}, status=403)
    
    # Парсим данные
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}
    else:
        data = request.POST
    
    text = data.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Текст комментария обязателен'}, status=400)
    
    if len(text) > 5000:
        return JsonResponse({'error': 'Слишком длинный комментарий (макс. 5000)'}, status=400)
    
    comment = TaskComment.objects.create(
        task=task,
        author=request.user,
        text=text,
    )
    
    # Формируем инициалы
    initials = ''
    if request.user.first_name:
        initials += request.user.first_name[0]
    if request.user.last_name:
        initials += request.user.last_name[0]
    if not initials:
        initials = '??'
    
    # Логируем
    try:
        from core.views.audit import log_action
        log_action(request, 'task', task.id, 'task_comment_added',
                   extra_data={'comment_id': comment.id})
    except Exception:
        pass
    
    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'author_id': comment.author_id,
            'author_name': comment.author.full_name if hasattr(comment.author, 'full_name') else f'{comment.author.last_name} {comment.author.first_name}'.strip(),
            'author_initials': initials.upper(),
            'text': comment.text,
            'created_at': comment.created_at.isoformat(),
            'created_at_display': comment.created_at.strftime('%d.%m.%Y %H:%M'),
            'can_delete': True,  # Автор всегда может удалить сразу после создания
        }
    })


@login_required
@require_http_methods(["POST", "DELETE"])
def task_comment_delete(request, comment_id):
    """Удаление комментария."""
    comment = get_object_or_404(TaskComment, id=comment_id)
    
    if not _can_delete_comment(request.user, comment):
        return JsonResponse({'error': 'Нельзя удалить этот комментарий'}, status=403)
    
    task_id = comment.task_id
    deleted_id = comment.id
    comment.delete()
    
    # Логируем
    try:
        from core.views.audit import log_action
        log_action(request, 'task', task_id, 'task_comment_deleted',
                   extra_data={'comment_id': deleted_id})
    except Exception:
        pass
    
    return JsonResponse({
        'success': True,
        'deleted_id': deleted_id,
    })
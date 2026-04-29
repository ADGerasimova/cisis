"""
core/views/task_views.py — Задачи
v3.82.0 — Автоуправляемые статусы задач TESTING / MANUFACTURING / VERIFY_REGISTRATION

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
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from django.db.models import Q

from core.models.tasks import (
    Task, TaskAssignee, TaskView, TaskType, TaskStatus, TaskPriority,
    TaskComment, TaskFile, TaskPin, AUTO_STATUS_TASK_TYPES,
)
from core.models.files import File, FileCategory, FileVisibility
from core.models import User, Laboratory

logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 30

import os
import mimetypes

ALLOWED_TASK_FILE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
}
ALLOWED_TASK_FILE_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt',
}
MAX_TASK_FILE_SIZE = 10 * 1024 * 1024   # 10 МБ
MAX_TASK_FILES_COUNT = 5

MANAGER_ROLES = (
    'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD',
    'SYSADMIN', 'QMS_HEAD', 'QMS_ADMIN', 'CTO', 'CEO',
    'WORKSHOP_HEAD',
)


# ─────────────────────────────────────────────────────────────
# Список задач
# ─────────────────────────────────────────────────────────────
def _save_task_file(uploaded_file, user):
    """Сохраняет файл задачи в S3 и создаёт запись File."""
    from core.services.s3_utils import upload_file, generate_s3_key
    from datetime import datetime

    month_dir = datetime.now().strftime('%Y-%m')
    prefix = f'tasks/{month_dir}'
    s3_key = generate_s3_key(prefix, uploaded_file.name)

    mime, _ = mimetypes.guess_type(uploaded_file.name)

    result = upload_file(uploaded_file, s3_key, content_type=mime or 'application/octet-stream')
    if not result:
        return None

    file_record = File(
        file_path=s3_key,
        original_name=uploaded_file.name,
        file_size=uploaded_file.size,
        mime_type=mime or 'application/octet-stream',
        category=FileCategory.INBOX,
        file_type='TASK_FILE',
        visibility=FileVisibility.RESTRICTED,
        uploaded_by=user,
    )
    file_record.save()
    return file_record

@login_required
def task_list(request):
    user = request.user
    view_mode = request.GET.get('view', 'my')
    can_create = True  # все могут создавать задачи
    can_manage = user.role in MANAGER_ROLES  # управление — только менеджеры

    qs = Task.objects.prefetch_related('assignees__user', 'files__file').select_related('created_by', 'laboratory')

    if view_mode == 'created':
        qs = qs.filter(created_by=user)
    elif view_mode == 'lab' and user.laboratory_id:
        qs = qs.filter(laboratory=user.laboratory)
    elif view_mode == 'all' and user.role == 'SYSADMIN':
        pass
    elif view_mode == 'pinned':
        pinned_ids = TaskPin.objects.filter(user=user).values_list('task_id', flat=True)
        qs = qs.filter(id__in=pinned_ids)
    elif view_mode == 'all' and can_manage:
        
        qs = qs.filter(
            Q(assignees__user=user) | Q(created_by=user) | Q(laboratory=user.laboratory)
        ).distinct()
    else:
        # ⭐ v3.67.0: В «Мои» не показываем задачи режима ALL,
        # где текущий пользователь уже выполнил свою часть
        my_completed_all_ids = set(
            TaskAssignee.objects.filter(
                user=user,
                completed_at__isnull=False,
                task__completion_mode='ALL',
                task__status__in=['OPEN', 'IN_PROGRESS'],
            ).values_list('task_id', flat=True)
        )
        qs = qs.filter(assignees__user=user)
        if my_completed_all_ids:
            qs = qs.exclude(id__in=my_completed_all_ids)
        view_mode = 'my'

    f_status = request.GET.get('status', '')
    f_type = request.GET.get('type', '')
    f_priority = request.GET.get('priority', '')
    f_overdue = request.GET.get('overdue')

    # Счётчики — по текущему view (до фильтров статуса/типа)
    count_open = qs.filter(status='OPEN').count()
    count_in_progress = qs.filter(status='IN_PROGRESS').count()
    count_overdue = qs.filter(
        status__in=['OPEN', 'IN_PROGRESS'],
        deadline__lt=timezone.now().date(),
    ).exclude(deadline__isnull=True).count()

# Теперь применяем фильтры к qs
    if f_overdue:
        qs = qs.filter(
            status__in=['OPEN', 'IN_PROGRESS'],
            deadline__lt=timezone.now().date(),
        ).exclude(deadline__isnull=True)
    elif f_status:
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

    # ── Шифры образцов для ссылок ──
    sample_entity_ids = [t.entity_id for t in items if t.entity_type == 'sample' and t.entity_id]
    if sample_entity_ids:
        from core.models.sample import Sample
        cipher_map = dict(
            Sample.objects.filter(id__in=sample_entity_ids).values_list('id', 'cipher')
        )
    else:
        cipher_map = {}
    for task in items:
        if task.entity_type == 'sample' and task.entity_id:
            # ⭐ v3.92.0: единый fallback — если cipher пустой (черновик
            # ещё не выпущен), показываем «Черновик #N», иначе сам cipher.
            # task_type здесь НЕ проверяем: у исторических задач
            # VERIFY_REGISTRATION (созданных до v3.92.0 на PENDING_VERIFICATION)
            # cipher есть, и его нужно показывать как обычно. Идиома `or` —
            # чтобы поймать и отсутствие ключа, и cipher = NULL/'' в БД
            # (`.get(id, default)` не сработает: ключ-то есть, значение пустое).
            cipher = cipher_map.get(task.entity_id)
            task.entity_name = cipher or f'Черновик #{task.entity_id}'
        else:
            task.entity_name = ''

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

        # ⭐ v3.67.0: Флаг автозадачи (для скрытия «Взять в работу»)
        task.is_auto = task.task_type != 'MANUAL'

        # ⭐ v3.82.0: Флаг автоуправляемого статуса (TESTING / MANUFACTURING /
        # VERIFY_REGISTRATION). У таких задач пользователь может только отменить.
        task.is_auto_status = task.task_type in AUTO_STATUS_TASK_TYPES

    assignable_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')

    laboratories = Laboratory.objects.filter(is_active=True).order_by('name')

    # ⭐ v3.58.0: Закреплённые задачи текущего пользователя
    pinned_task_ids = set(
        TaskPin.objects.filter(user=user, task_id__in=task_ids)
        .values_list('task_id', flat=True)
    )
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
        'pinned_task_ids': pinned_task_ids,
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
    completion_mode = request.POST.get('completion_mode', 'ANY').strip()
    if completion_mode not in ('ANY', 'ALL'):
        completion_mode = 'ANY'

    if not title:
        messages.error(request, 'Укажите заголовок задачи')
        return redirect('task_list')
    if not assignee_ids:
        messages.error(request, 'Укажите хотя бы одного исполнителя')
        return redirect('task_list')

    # ⭐ v3.57.0: валидация файлов
    uploaded_files = request.FILES.getlist('files')
    if len(uploaded_files) > MAX_TASK_FILES_COUNT:
        messages.error(request, f'Максимум {MAX_TASK_FILES_COUNT} файлов')
        return redirect('task_list')

    for uf in uploaded_files:
        ext = os.path.splitext(uf.name)[1].lower().lstrip('.')
        if uf.content_type not in ALLOWED_TASK_FILE_TYPES and ext not in ALLOWED_TASK_FILE_EXTENSIONS:
            messages.error(request, f'Недопустимый формат файла: {uf.name}')
            return redirect('task_list')
        if uf.size > MAX_TASK_FILE_SIZE:
            messages.error(request, f'Файл {uf.name} превышает 10 МБ')
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
            completion_mode=completion_mode,
        )
        for uid in assignee_ids:
            if uid and uid.isdigit():
                TaskAssignee.objects.create(task=task, user_id=int(uid))

        # ⭐ v3.57.0: сохраняем файлы
        for i, uf in enumerate(uploaded_files):
            file_obj = _save_task_file(uf, request.user)
            if file_obj:
                TaskFile.objects.create(task=task, file=file_obj, sort_order=i)

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
    is_creator = task.created_by_id == request.user.id  # ⭐ v3.67.0
    if not is_assignee and not is_manager and not is_creator:
        return JsonResponse({'error': 'Нет прав'}, status=403)

    new_status = request.POST.get('status', '').strip()
    if new_status not in dict(TaskStatus.choices):
        return JsonResponse({'error': 'Неверный статус'}, status=400)

    # ⭐ v3.82.0: Для автоуправляемых типов (TESTING/MANUFACTURING/VERIFY_REGISTRATION)
    # пользователь может только отменить задачу. Остальные переходы — автоматически
    # через sync_auto_task_from_sample при смене статуса образца.
    if task.task_type in AUTO_STATUS_TASK_TYPES and new_status != 'CANCELLED':
        return JsonResponse({
            'error': 'Статус этой задачи меняется автоматически по статусу образца. '
                     'Вручную можно только отменить.'
        }, status=403)

    # ⭐ v3.67.0: Создатель/менеджер может отметить выполнение за конкретного исполнителя
    assignee_user_id = request.POST.get('assignee_user_id', '').strip()
    if assignee_user_id and (is_creator or is_manager):
        if task.completion_mode == 'ALL' and new_status == 'DONE':
            assignee = TaskAssignee.objects.filter(
                task=task, user_id=int(assignee_user_id)
            ).first()
            if assignee and not assignee.completed_at:
                assignee.completed_at = timezone.now()
                if not assignee.started_at:
                    assignee.started_at = assignee.completed_at
                assignee.save(update_fields=['completed_at', 'started_at'])

            total = TaskAssignee.objects.filter(task=task).count()
            completed = TaskAssignee.objects.filter(task=task, completed_at__isnull=False).count()

            if completed >= total:
                task.status = 'DONE'
                task.completed_at = timezone.now()
                task.save()
            elif task.status == 'OPEN':
                task.status = 'IN_PROGRESS'
                task.save()

            from core.views.audit import log_action
            log_action(request, 'task', task.id, 'task_assignee_completed',
                       extra_data={'user_id': int(assignee_user_id),
                                   'marked_by': request.user.id,
                                   'completed': completed, 'total': total})

            return JsonResponse({
                'success': True,
                'status': task.status,
                'completed_count': completed,
                'total_count': total,
                'all_done': completed >= total,
            })

    old_status = task.status

    # ⭐ v3.59.0: фиксируем момент, когда задачу взяли в работу.
    # ANY (общая) — статус меняется у всех, поэтому started_at ставим всем исполнителям.
    # ALL (персональная для каждого) — только тому, кто нажал.
    if new_status == 'IN_PROGRESS':
        if task.completion_mode == 'ALL':
            if is_assignee:
                TaskAssignee.objects.filter(
                    task=task, user=request.user, started_at__isnull=True
                ).update(started_at=timezone.now())
        else:
            TaskAssignee.objects.filter(
                task=task, started_at__isnull=True
            ).update(started_at=timezone.now())

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
        TaskAssignee.objects.filter(task=task).update(completed_at=None, started_at=None)

    # Стандартное поведение (ANY или управление менеджером)
    task.status = new_status
    if new_status in ('DONE', 'CANCELLED'):
        task.completed_at = timezone.now()
    else:
        task.completed_at = None
    task.save()

    # ⭐ v3.59.0: фиксируем completed_at у исполнителей.
    # ANY — общая задача: завершение/возврат применяется ко всем исполнителям.
    # ALL — обрабатывается выше в индивидуальной ветке.
    if task.completion_mode != 'ALL':
        if new_status == 'DONE':
            TaskAssignee.objects.filter(
                task=task, completed_at__isnull=True
            ).update(completed_at=timezone.now())
        elif new_status == 'OPEN':
            # Полный возврат к началу — сбрасываем и взятие в работу, и завершение
            TaskAssignee.objects.filter(task=task).update(completed_at=None, started_at=None)
        elif new_status == 'IN_PROGRESS':
            # Снимаем только отметку завершения; started_at сохраняем
            TaskAssignee.objects.filter(task=task).update(completed_at=None)

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
        # ⭐ v3.92.0: задача создаётся, когда образец в статусе DRAFT — у него
        # ещё нет cipher (присвоится при выпуске пула). Используем фиксированную
        # формулировку «Черновик #N» вместо `or "#{id}"`, чтобы было одинаково
        # с шапкой карточки черновика (sample_detail.html, см. v3.91.0 п. 5).
        title = f'Проверить регистрацию: Черновик #{sample.id}'
    elif task_type == 'ACCEPT_SAMPLE':
        title = f'Принять образец: {sample.cipher or f"#{sample.id}"}'
    elif task_type == 'ACCEPT_FROM_UZK':
        title = f'Принять из УЗК: {sample.cipher or f"#{sample.id}"}'
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


def close_auto_tasks(task_type, entity_type, entity_id, final_status='DONE'):
    """
    Закрывает все автозадачи по сущности.

    final_status: 'DONE' (по умолчанию, задача выполнена) или 'CANCELLED'
    (задача отменена — например, при удалении черновика образца). Принимает
    только эти два значения; OPEN/IN_PROGRESS как «финальный статус» не
    имеют смысла.
    """
    # ⭐ v3.92.0: параметр final_status. Дефолт сохраняет старое поведение.
    if final_status not in ('DONE', 'CANCELLED'):
        raise ValueError(
            f"final_status должен быть 'DONE' или 'CANCELLED', получено: {final_status!r}"
        )
    return Task.objects.filter(
        task_type=task_type,
        entity_type=entity_type,
        entity_id=entity_id,
        status__in=['OPEN', 'IN_PROGRESS'],
    ).update(status=final_status, completed_at=timezone.now())


# ─────────────────────────────────────────────────────────────
# ⭐ v3.82.0: Автоматическая синхронизация статусов задач по статусу образца
# ─────────────────────────────────────────────────────────────

# Маппинг: (тип задачи, статус образца) → целевой статус задачи.
# Применяется из sample_views / verification_views после sample.save().
_AUTO_STATUS_MAPPING = {
    ('TESTING', 'IN_TESTING'): 'IN_PROGRESS',
    ('TESTING', 'DRAFT_READY'): 'DONE',
    ('TESTING', 'RESULTS_UPLOADED'): 'DONE',
    ('MANUFACTURING', 'MANUFACTURING'): 'IN_PROGRESS',
    ('MANUFACTURING', 'MANUFACTURED'): 'DONE',
    # VERIFY_REGISTRATION закрывается при любом исходе approve в verify_sample:
    # образец может попасть в UZK_TESTING / MOISTURE_CONDITIONING / MANUFACTURING
    # / REGISTERED — действие «проверил регистрацию» в любом случае выполнено.
    # ⭐ v3.92.0: DRAFT_REGISTERED — подтверждение черновика регистратором
    # (verify_draft). Задача создаётся при → DRAFT и закрывается здесь, как
    # только другой регистратор подтвердил черновик. После DRAFT_REGISTERED
    # выпуск пула переводит образец в один из рабочих статусов — на тот
    # момент задача уже DONE, повторно не трогается (защита через _STATUS_RANK).
    ('VERIFY_REGISTRATION', 'DRAFT_REGISTERED'): 'DONE',
    ('VERIFY_REGISTRATION', 'REGISTERED'): 'DONE',
    ('VERIFY_REGISTRATION', 'UZK_TESTING'): 'DONE',
    ('VERIFY_REGISTRATION', 'MOISTURE_CONDITIONING'): 'DONE',
    ('VERIFY_REGISTRATION', 'MANUFACTURING'): 'DONE',
    ('VERIFY_REGISTRATION', 'CANCELLED'): 'DONE',
}

# Порядок продвижения статуса задачи — только вперёд.
# OPEN → IN_PROGRESS → DONE. Назад (если образец откатился) не идём:
# задача, попавшая в DONE, остаётся в DONE.
_STATUS_RANK = {'OPEN': 0, 'IN_PROGRESS': 1, 'DONE': 2, 'CANCELLED': 99}


def sync_auto_task_from_sample(sample, request=None):
    """
    ⭐ v3.82.0: Синхронизирует статусы автозадач
    (TESTING / MANUFACTURING / VERIFY_REGISTRATION) по текущему статусу образца.

    Вызывается из sample_views и verification_views после sample.save(),
    изменившего status.

    Правила:
      - Переходы только вперёд: DONE не возвращается в IN_PROGRESS.
      - CANCELLED не трогаем (пользователь отменил вручную).
      - При → IN_PROGRESS: started_at проставляется всем исполнителям
        с started_at IS NULL.
      - При → DONE: completed_at проставляется задаче и всем исполнителям
        (общее завершение, как в режиме ANY).
      - Аудит-лог пишется с user'ом из request (или "Система", если request=None).

    Аргументы:
      sample   — экземпляр core.models.Sample (нужен sample.id и sample.status).
      request  — HttpRequest для аудита. Если None — лог без user_id.
    """
    now = timezone.now()

    for task_type in AUTO_STATUS_TASK_TYPES:
        target = _AUTO_STATUS_MAPPING.get((task_type, sample.status))
        if not target:
            # Для этой пары (тип задачи, статус образца) автоперехода нет.
            continue

        target_rank = _STATUS_RANK[target]

        tasks = Task.objects.filter(
            task_type=task_type,
            entity_type='sample',
            entity_id=sample.id,
            status__in=['OPEN', 'IN_PROGRESS'],
        )

        for task in tasks:
            current_rank = _STATUS_RANK.get(task.status, 0)
            if target_rank <= current_rank:
                # Задача уже в целевом или более продвинутом состоянии.
                continue

            old_status = task.status
            task.status = target
            if target == 'DONE':
                task.completed_at = now
            task.save(update_fields=['status', 'completed_at'])

            # Синхронизируем поля исполнителей (поведение режима ANY:
            # общее завершение/общий старт).
            if target == 'IN_PROGRESS':
                TaskAssignee.objects.filter(
                    task=task, started_at__isnull=True,
                ).update(started_at=now)
            elif target == 'DONE':
                TaskAssignee.objects.filter(
                    task=task, completed_at__isnull=True,
                ).update(completed_at=now)

            # Аудит — через тот же log_action, что и ручная смена.
            try:
                from core.views.audit import log_action
                if request is not None:
                    log_action(
                        request, 'task', task.id, 'task_status_changed',
                        field_name='status',
                        old_value=old_status, new_value=target,
                        extra_data={'source': 'auto', 'sample_status': sample.status},
                    )
            except Exception:
                logger.exception('Ошибка аудита авто-смены статуса задачи %s', task.id)


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
    'ACCEPT_FROM_UZK': 'Приёмка из УЗК',
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

    # Шифры образцов для ссылок
    tasks_list = list(qs)
    sample_ids = [t.entity_id for t in tasks_list if t.entity_type == 'sample' and t.entity_id]
    if sample_ids:
        from core.models.sample import Sample
        cipher_map = dict(Sample.objects.filter(id__in=sample_ids).values_list('id', 'cipher'))
    else:
        cipher_map = {}

    tasks_data = []
    for t in tasks_list:
        # ⭐ v3.92.0: тот же fallback-механизм, что в списке задач выше.
        # Если cipher пустой (DRAFT) → «Черновик #N», иначе — сам cipher.
        if t.entity_type == 'sample':
            cipher = cipher_map.get(t.entity_id)
            entity_name = cipher or f'Черновик #{t.entity_id}'
        else:
            entity_name = ''
        tasks_data.append({
            'id': t.id,
            'title': t.title,
            'type': t.task_type,
            'type_label': TASK_TYPE_LABELS.get(t.task_type, 'Задача'),
            'priority': t.priority,
            'entity_type': t.entity_type,
            'entity_id': t.entity_id,
            'entity_name': entity_name,
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

@login_required
@require_GET
def task_file_view(request, task_id, file_id):
    """Отдаёт файл задачи через presigned URL."""
    task = get_object_or_404(Task, pk=task_id)

    # Проверка доступа: исполнитель, создатель или менеджер
    is_assignee = TaskAssignee.objects.filter(task=task, user=request.user).exists()
    is_creator = task.created_by_id == request.user.id
    is_manager = request.user.role in MANAGER_ROLES

    if not (is_assignee or is_creator or is_manager):
        from django.http import Http404
        raise Http404

    tf = TaskFile.objects.filter(task=task, file_id=file_id).select_related('file').first()
    if not tf:
        from django.http import Http404
        raise Http404('Файл не найден')

    from core.services.s3_utils import get_presigned_url
    url = get_presigned_url(tf.file.file_path, expires_in=3600, content_type=tf.file.mime_type)
    if not url:
        from django.http import Http404
        raise Http404('Файл не найден')

    return redirect(url)

@login_required
@require_POST
def task_pin_toggle(request, task_id):
    """
    ⭐ v3.58.0: Закрепить / открепить задачу для текущего пользователя.
    POST /workspace/tasks/<id>/pin/
    Ответ: { "success": true, "pinned": true/false }
    """
    task = get_object_or_404(Task, id=task_id)
 
    # Проверяем, что пользователь имеет доступ к задаче
    is_assignee = TaskAssignee.objects.filter(task=task, user=request.user).exists()
    is_creator = task.created_by_id == request.user.id
    is_manager = request.user.role in MANAGER_ROLES
 
    if not (is_assignee or is_creator or is_manager):
        return JsonResponse({'error': 'Нет доступа'}, status=403)
 
    pin, created = TaskPin.objects.get_or_create(task=task, user=request.user)
    if not created:
        # Уже было закреплено — снимаем
        pin.delete()
        pinned = False
    else:
        pinned = True
 
    return JsonResponse({'success': True, 'pinned': pinned})

# ─────────────────────────────────────────────────────────────
# ⭐ v3.59.0: Активность задачи (статистика исполнителей + история)
# ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def task_activity(request, task_id):
    """Возвращает JSON со статистикой исполнителей и историей изменений."""
    task = get_object_or_404(Task, id=task_id)

    # Доступ: создатель, исполнитель, менеджер
    is_assignee = TaskAssignee.objects.filter(task=task, user=request.user).exists()
    is_manager = request.user.role in MANAGER_ROLES
    is_creator = task.created_by_id == request.user.id
    if not (is_assignee or is_manager or is_creator):
        return JsonResponse({'error': 'Нет прав'}, status=403)

    now = timezone.now()

    # ── Статистика исполнителей ──
    assignees_qs = (
        TaskAssignee.objects
        .filter(task=task)
        .select_related('user')
        .order_by('user__last_name', 'user__first_name')
    )

    def _full_name(u):
        name = f'{u.last_name} {u.first_name}'.strip()
        return name or u.username

    def _humanize_delta(start, end):
        """Возвращает строку вида '2д 5ч' или '15м'."""
        if not start or not end:
            return None
        delta = end - start
        total_sec = int(delta.total_seconds())
        if total_sec < 0:
            return None
        days = total_sec // 86400
        hours = (total_sec % 86400) // 3600
        minutes = (total_sec % 3600) // 60
        parts = []
        if days:
            parts.append(f'{days}д')
        if hours:
            parts.append(f'{hours}ч')
        if not days and minutes:
            parts.append(f'{minutes}м')
        return ' '.join(parts) or 'меньше минуты'

    assignees = []
    for a in assignees_qs:
        if a.completed_at:
            state = 'done'
        elif a.started_at:
            state = 'in_progress'
        else:
            state = 'not_started'
        assignees.append({
            'user_name': _full_name(a.user),
            'started_at': a.started_at.strftime('%d.%m.%Y %H:%M') if a.started_at else None,
            'completed_at': a.completed_at.strftime('%d.%m.%Y %H:%M') if a.completed_at else None,
            'duration': (
                _humanize_delta(a.started_at, a.completed_at) if a.completed_at
                else _humanize_delta(a.started_at, now) if a.started_at
                else None
            ),
            'state': state,
        })

    # ── История из аудита ──
    # Используем сырой SQL, т.к. модели аудита может не быть в ORM
    from django.db import connection
    history = []
    with connection.cursor() as cur:
        cur.execute("""
            SELECT al.timestamp, al.action, al.field_name,
                   al.old_value, al.new_value,
                   u.last_name, u.first_name, u.username
              FROM audit_log al
              LEFT JOIN users u ON u.id = al.user_id
             WHERE al.entity_type = 'task' AND al.entity_id = %s
             ORDER BY al.timestamp DESC
             LIMIT 200
        """, [task.id])
        rows = cur.fetchall()

    status_labels = dict(TaskStatus.choices)
    action_labels = {
        'task_created': 'создал(а) задачу',
        'task_status_changed': 'изменил(а) статус',
        'task_assignee_completed': 'отметил(а) свою часть выполненной',
        'task_comment_added': 'добавил(а) комментарий',
        'task_comment_deleted': 'удалил(а) комментарий',
    }
    for ts, action, field_name, old_value, new_value, last, first, uname in rows:
        user_name = f'{last or ""} {first or ""}'.strip() or uname or 'Система'
        label = action_labels.get(action, action)
        detail = ''
        if action == 'task_status_changed':
            old_lbl = status_labels.get(old_value, old_value or '—')
            new_lbl = status_labels.get(new_value, new_value or '—')
            detail = f'{old_lbl} → {new_lbl}'
        history.append({
            'time': ts.strftime('%d.%m.%Y %H:%M'),
            'user': user_name,
            'label': label,
            'detail': detail,
        })

    return JsonResponse({
        'assignees': assignees,
        'history': history,
    })
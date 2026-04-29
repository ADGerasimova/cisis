"""
feedback_views.py — Обратная связь от пользователей
v3.36.0 → v3.57.0

Все пользователи видят все обращения и могут комментировать.
SYSADMIN дополнительно может менять статус.

v3.57.0: Множественные файлы (до 5 шт, до 10 МБ каждый).
Файлы хранятся в S3, связи — в таблице feedback_files.
Обратная совместимость со старым полем screenshot_file.
"""

import json
import os
import mimetypes
from datetime import datetime

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_GET
from django.http import FileResponse, Http404

from core.models.feedback import Feedback, FeedbackPriority, FeedbackStatus, FeedbackFile, FeedbackComment
from core.models.files import File, FileCategory, FileVisibility

ITEMS_PER_PAGE = 30
ADMIN_ROLES = ('SYSADMIN',)

# ⭐ v3.57.0: расширенные типы файлов
ALLOWED_FILE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
}
ALLOWED_FILE_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt',
}
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 МБ
MAX_FILES_COUNT = 5


def _is_admin(user):
    return user.role in ADMIN_ROLES


def _save_feedback_file(uploaded_file, user):
    """
    Сохраняет файл обратной связи в S3 и создаёт запись File.
    Возвращает объект File или None при ошибке.
    """
    from core.services.s3_utils import upload_file, generate_s3_key

    month_dir = datetime.now().strftime('%Y-%m')
    prefix = f'feedback/{month_dir}'
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
        file_type='FEEDBACK_FILE',
        visibility=FileVisibility.RESTRICTED,
        uploaded_by=user,
    )
    file_record.save()

    return file_record


@login_required
def feedback_list(request):
    user = request.user
    is_admin = _is_admin(user)

    qs = Feedback.objects.select_related(
        'author', 'resolved_by', 'screenshot_file', 'status_changed_by'
    ).prefetch_related('files__file', 'comments__author').all()

    f_status = request.GET.get('status', '')
    if f_status:
        qs = qs.filter(status=f_status)

    f_priority = request.GET.get('priority', '')
    if f_priority:
        qs = qs.filter(priority=f_priority)

    total_count = qs.count()

    if is_admin:
        count_new         = Feedback.objects.filter(status='NEW').count()
        count_in_progress = Feedback.objects.filter(status='IN_PROGRESS').count()
        count_fixed       = Feedback.objects.filter(status='FIXED').count()
    else:
        count_new         = Feedback.objects.filter(author=user, status='NEW').count()
        count_in_progress = Feedback.objects.filter(author=user, status='IN_PROGRESS').count()
        count_fixed       = Feedback.objects.filter(author=user, status='FIXED').count()

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Помечаем карточки с непрочитанными комментариями
    # (используем уже загруженные prefetch-данные, без доп. запросов)
    for fb in page_obj.object_list:
        if is_admin:
            fb.has_unread = any(
                not c.is_read_by_admin for c in fb.comments.all()
            )
        else:
            fb.has_unread = any(
                not c.is_read_by_author for c in fb.comments.all()
            )

    context = {
        'page_obj':        page_obj,
        'items':           page_obj.object_list,
        'total_count':     total_count,
        'is_admin':        is_admin,
        'f_status':        f_status,
        'f_priority':      f_priority,
        'priority_choices': FeedbackPriority.choices,
        'status_choices':   FeedbackStatus.choices,
        'count_new':        count_new,
        'count_in_progress': count_in_progress,
        'count_fixed':      count_fixed,
    }
    return render(request, 'core/feedback.html', context)
@login_required
@require_POST
def feedback_create(request):
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    page_url = request.POST.get('page_url', '').strip()
    priority = request.POST.get('priority', 'MEDIUM').strip()

    if not title:
        messages.error(request, 'Укажите заголовок обращения')
        return redirect('feedback_list')

    # ⭐ v3.57.0: множественные файлы
    uploaded_files = request.FILES.getlist('files')
    if len(uploaded_files) > MAX_FILES_COUNT:
        messages.error(request, f'Максимум {MAX_FILES_COUNT} файлов')
        return redirect('feedback_list')

    saved_files = []
    for uf in uploaded_files:
        ext = os.path.splitext(uf.name)[1].lower().lstrip('.')
        if uf.content_type not in ALLOWED_FILE_TYPES and ext not in ALLOWED_FILE_EXTENSIONS:
            messages.error(request, f'Недопустимый формат файла: {uf.name}')
            return redirect('feedback_list')
        if uf.size > MAX_FILE_SIZE:
            messages.error(request, f'Файл {uf.name} превышает 10 МБ')
            return redirect('feedback_list')
        file_obj = _save_feedback_file(uf, request.user)
        if file_obj:
            saved_files.append(file_obj)

    fb = Feedback.objects.create(
        author=request.user,
        title=title,
        description=description,
        page_url=page_url,
        priority=priority,
        screenshot_file=saved_files[0] if saved_files else None,  # обратная совместимость
    )

    # Сохраняем связи в feedback_files
    for i, f in enumerate(saved_files):
        FeedbackFile.objects.create(feedback=fb, file=f, sort_order=i)

    messages.success(request, 'Обращение отправлено! Спасибо за помощь в улучшении системы.')
    return redirect('feedback_list')


@login_required
@require_POST
def feedback_update(request, feedback_id):
    if not _is_admin(request.user):
        messages.error(request, 'Нет прав')
        return redirect('feedback_list')

    fb = get_object_or_404(Feedback, pk=feedback_id)
    new_status = request.POST.get('status', '').strip()

    if new_status and new_status in dict(FeedbackStatus.choices) and new_status != fb.status:
        fb.status = new_status
        fb.status_changed_by = request.user
        if new_status in ('FIXED', 'CLOSED') and not fb.resolved_by_id:
            fb.resolved_by = request.user
        fb.save()
        messages.success(request, f'Обращение #{fb.pk} обновлено')

    return redirect('feedback_list')


@login_required
@require_POST
def feedback_delete(request, feedback_id):
    fb = get_object_or_404(Feedback, pk=feedback_id)
    if fb.author_id != request.user.pk and not _is_admin(request.user):
        messages.error(request, 'Нет прав')
        return redirect('feedback_list')

    from django.utils import timezone

    # Мягко удаляем файлы, прикреплённые к комментариям
    for c in fb.comments.select_related('file').all():
        if c.file_id:
            try:
                f = c.file
                f.is_deleted = True
                f.deleted_at = timezone.now()
                f.deleted_by = request.user
                f.save()
            except Exception:
                pass

    # ⭐ v3.57.0: мягко удаляем все прикреплённые файлы
    for ff in fb.files.select_related('file').all():
        try:
            f = ff.file
            f.is_deleted = True
            f.deleted_at = timezone.now()
            f.deleted_by = request.user
            f.save()
        except Exception:
            pass

    # Обратная совместимость — старый screenshot_file
    if fb.screenshot_file_id:
        try:
            f = fb.screenshot_file
            f.is_deleted = True
            f.deleted_at = timezone.now()
            f.deleted_by = request.user
            f.save()
        except Exception:
            pass

    fb.delete()
    messages.success(request, 'Обращение удалено')
    return redirect('feedback_list')


@login_required
@require_GET
def feedback_image(request, feedback_id):
    """
    Отдаёт файл обратной связи через presigned URL.
    ?file_id=N — конкретный файл из feedback_files.
    Без параметра — старый screenshot_file (обратная совместимость).
    """
    fb = get_object_or_404(Feedback, pk=feedback_id)

    file_id = request.GET.get('file_id')

    comment_id = request.GET.get('comment_id')
    if comment_id:
        comment = FeedbackComment.objects.filter(
            feedback=fb, pk=int(comment_id)
        ).select_related('file').first()
        if not comment or not comment.file_id:
            raise Http404('Файл не найден')
        file_obj = comment.file
    else:
        file_id = request.GET.get('file_id')
        if file_id:
            ff = FeedbackFile.objects.filter(
                feedback=fb, file_id=int(file_id)
            ).select_related('file').first()
            if not ff:
                raise Http404('Файл не найден')
            file_obj = ff.file
        elif fb.screenshot_file_id:
            file_obj = fb.screenshot_file
        else:
            raise Http404('Файл не прикреплён')


    from core.services.s3_utils import get_presigned_url
    url = get_presigned_url(
        file_obj.file_path,
        expires_in=3600,
        content_type=file_obj.mime_type,
    )
    if not url:
        raise Http404('Файл не найден')

    from django.shortcuts import redirect
    return redirect(url)

@login_required
@require_POST
def feedback_comment_add(request, feedback_id):
    fb = get_object_or_404(Feedback, pk=feedback_id)

    text = request.POST.get('comment_text', '').strip()
    uploaded_file = request.FILES.get('comment_file')

    if not text and not uploaded_file:
        messages.error(request, 'Комментарий не может быть пустым')
        return redirect('feedback_list')

    # ⭐ Валидация и сохранение файла (одного)
    file_obj = None
    if uploaded_file:
        ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
        if uploaded_file.content_type not in ALLOWED_FILE_TYPES and ext not in ALLOWED_FILE_EXTENSIONS:
            messages.error(request, f'Недопустимый формат файла: {uploaded_file.name}')
            return redirect('feedback_list')
        if uploaded_file.size > MAX_FILE_SIZE:
            messages.error(request, f'Файл {uploaded_file.name} превышает 10 МБ')
            return redirect('feedback_list')

        file_obj = _save_feedback_file(uploaded_file, request.user)
        if not file_obj:
            messages.error(request, 'Не удалось загрузить файл')
            return redirect('feedback_list')

    is_admin = _is_admin(request.user)

    FeedbackComment.objects.create(
        feedback=fb,
        author=request.user,
        text=text,
        file=file_obj,
        is_read_by_author=not is_admin,
        is_read_by_admin=is_admin,
    )

    # Помечаем все предыдущие комментарии прочитанными для текущей стороны
    if is_admin:
        fb.comments.filter(is_read_by_admin=False).update(is_read_by_admin=True)
    else:
        fb.comments.filter(is_read_by_author=False).update(is_read_by_author=True)

    messages.success(request, 'Комментарий добавлен')
    return redirect('feedback_list')


@login_required
@require_POST
def feedback_comments_mark_read(request, feedback_id):
    """Пометить все комментарии прочитанными (вызывается при открытии карточки)."""
    fb = get_object_or_404(Feedback, pk=feedback_id)

    if _is_admin(request.user):
        fb.comments.filter(is_read_by_admin=False).update(is_read_by_admin=True)
    else:
        fb.comments.filter(is_read_by_author=False).update(is_read_by_author=True)

    return redirect('feedback_list')
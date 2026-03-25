"""
feedback_views.py — Обратная связь от пользователей
v3.36.0

Пользователь видит только свои обращения.
SYSADMIN видит все + может менять статус и комментировать.

Скриншоты хранятся через единую файловую систему проекта (модель File),
отдаются через отдельный view feedback_image — без зависимости от DEBUG.
"""

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

from core.models.feedback import Feedback, FeedbackPriority, FeedbackStatus
from core.models.files import File, FileCategory, FileVisibility

ITEMS_PER_PAGE = 30
ADMIN_ROLES = ('SYSADMIN',)

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 МБ


def _is_admin(user):
    return user.role in ADMIN_ROLES


def _save_screenshot(uploaded_file, user):
    """
    Сохраняет скриншот на диск и создаёт запись File.
    Возвращает объект File или None при ошибке.
    """
    # Папка: media/feedback/YYYY-MM/
    month_dir = datetime.now().strftime('%Y-%m')
    relative_dir = os.path.join('feedback', month_dir)
    absolute_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)

    # Безопасное имя файла с дедупликацией
    original_name = uploaded_file.name
    ext = os.path.splitext(original_name)[1].lower() or '.png'
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = f'screenshot_{user.pk}_{ts}{ext}'
    absolute_path = os.path.join(absolute_dir, safe_name)

    # Дедупликация на случай одновременной загрузки
    counter = 1
    base_name = safe_name
    while os.path.exists(absolute_path):
        name, file_ext = os.path.splitext(base_name)
        safe_name = f'{name}_{counter}{file_ext}'
        absolute_path = os.path.join(absolute_dir, safe_name)
        counter += 1

    relative_path = os.path.join(relative_dir, safe_name)

    # Сохраняем файл на диск
    with open(absolute_path, 'wb') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    mime, _ = mimetypes.guess_type(original_name)

    # Создаём запись в таблице files
    file_record = File(
        file_path=relative_path,
        original_name=original_name,
        file_size=uploaded_file.size,
        mime_type=mime or 'image/png',
        # Используем INBOX как нейтральную категорию без привязки к сущности
        category=FileCategory.INBOX,
        file_type='FEEDBACK_SCREENSHOT',
        visibility=FileVisibility.RESTRICTED,  # скрыт от обычных пользователей в файловом менеджере
        uploaded_by=user,
    )
    file_record.save()

    return file_record


@login_required
def feedback_list(request):
    user = request.user
    is_admin = _is_admin(user)

    if is_admin:
        qs = Feedback.objects.select_related(
            'author', 'resolved_by', 'screenshot_file'
        ).all()
    else:
        qs = Feedback.objects.select_related(
            'author', 'resolved_by', 'screenshot_file'
        ).filter(author=user)

    f_status = request.GET.get('status', '')
    if f_status:
        qs = qs.filter(status=f_status)

    f_priority = request.GET.get('priority', '')
    if f_priority:
        qs = qs.filter(priority=f_priority)

    total_count = qs.count()

    if is_admin:
        count_new = Feedback.objects.filter(status='NEW').count()
        count_in_progress = Feedback.objects.filter(status='IN_PROGRESS').count()
        count_fixed = Feedback.objects.filter(status='FIXED').count()
    else:
        count_new = Feedback.objects.filter(author=user, status='NEW').count()
        count_in_progress = Feedback.objects.filter(author=user, status='IN_PROGRESS').count()
        count_fixed = Feedback.objects.filter(author=user, status='FIXED').count()

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'items': page_obj.object_list,
        'total_count': total_count,
        'is_admin': is_admin,
        'f_status': f_status,
        'f_priority': f_priority,
        'priority_choices': FeedbackPriority.choices,
        'status_choices': FeedbackStatus.choices,
        'count_new': count_new,
        'count_in_progress': count_in_progress,
        'count_fixed': count_fixed,
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

    # Обработка скриншота
    screenshot_file = None
    uploaded_image = request.FILES.get('image')
    if uploaded_image:
        # Валидация типа
        if uploaded_image.content_type not in ALLOWED_IMAGE_TYPES:
            messages.error(request, 'Допустимые форматы изображения: JPEG, PNG, GIF, WebP')
            return redirect('feedback_list')
        # Валидация размера
        if uploaded_image.size > MAX_IMAGE_SIZE:
            messages.error(request, 'Размер изображения не должен превышать 5 МБ')
            return redirect('feedback_list')

        screenshot_file = _save_screenshot(uploaded_image, request.user)

    Feedback.objects.create(
        author=request.user,
        title=title,
        description=description,
        page_url=page_url,
        priority=priority,
        screenshot_file=screenshot_file,
    )
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
    admin_comment = request.POST.get('admin_comment', '').strip()

    if new_status and new_status in dict(FeedbackStatus.choices):
        fb.status = new_status
    fb.admin_comment = admin_comment
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

    # Мягко удаляем прикреплённый файл если есть
    if fb.screenshot_file_id:
        try:
            from django.utils import timezone
            f = fb.screenshot_file
            f.is_deleted = True
            f.deleted_at = timezone.now()
            f.deleted_by = request.user
            f.save()
        except Exception:
            pass  # файл уже удалён или недоступен — не критично

    fb.delete()
    messages.success(request, 'Обращение удалено')
    return redirect('feedback_list')


@login_required
@require_GET
def feedback_image(request, feedback_id):
    """
    Отдаёт скриншот к обращению.
    Доступен автору обращения и администратору.
    Не зависит от DEBUG и прав файловой системы.
    """
    fb = get_object_or_404(Feedback, pk=feedback_id)

    # Проверка прав: только автор или админ
    if fb.author_id != request.user.pk and not _is_admin(request.user):
        raise Http404

    if not fb.screenshot_file_id:
        raise Http404('Скриншот не прикреплён')

    file_obj = fb.screenshot_file
    full_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)

    if not os.path.exists(full_path):
        raise Http404('Файл не найден на диске')

    return FileResponse(
        open(full_path, 'rb'),
        content_type=file_obj.mime_type or 'image/png',
    )
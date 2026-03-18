"""
feedback_views.py — Обратная связь от пользователей
v3.35.0

Пользователь видит только свои обращения.
SYSADMIN видит все + может менять статус и комментировать.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from core.models.feedback import Feedback, FeedbackPriority, FeedbackStatus

ITEMS_PER_PAGE = 30
ADMIN_ROLES = ('SYSADMIN',)


def _is_admin(user):
    return user.role in ADMIN_ROLES


@login_required
def feedback_list(request):
    user = request.user
    is_admin = _is_admin(user)

    if is_admin:
        qs = Feedback.objects.select_related('author', 'resolved_by').all()
    else:
        qs = Feedback.objects.select_related('author', 'resolved_by').filter(author=user)

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
    else:
        count_new = Feedback.objects.filter(author=user, status='NEW').count()
        count_in_progress = Feedback.objects.filter(author=user, status='IN_PROGRESS').count()

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

    Feedback.objects.create(
        author=request.user, title=title, description=description,
        page_url=page_url, priority=priority,
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
    fb.delete()
    messages.success(request, 'Обращение удалено')
    return redirect('feedback_list')

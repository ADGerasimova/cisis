# core/views/maintenance_notice_views.py

import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from core.models import MaintenanceNotice


def _is_sysadmin(user):
    """Проверяем, что пользователь — сисадмин."""
    role = getattr(user, 'role', None)
    if role:
        role_name = role.name if hasattr(role, 'name') else str(role)
        return role_name.lower() in ('сисадмин', 'sysadmin', 'системный администратор')
    return False


@login_required
@require_POST
def api_maintenance_notify(request):
    """
    POST /api/maintenance/notify/
    Body: {"minutes": 10, "message": "Обновление системы"}
    Только для сисадмина.
    """
    if not _is_sysadmin(request.user):
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)

    minutes = data.get('minutes')
    message = data.get('message', '')

    if not minutes or not isinstance(minutes, int) or minutes < 1 or minutes > 1440:
        return JsonResponse(
            {'error': 'Укажите количество минут (от 1 до 1440)'},
            status=400
        )

    now = timezone.now()
    scheduled_at = now + timedelta(minutes=minutes)

    # Деактивируем предыдущие активные уведомления
    MaintenanceNotice.objects.filter(is_active=True).update(is_active=False)

    # Создаём новое
    notice = MaintenanceNotice.objects.create(
        created_by=request.user,
        minutes_until=minutes,
        message=message,
        scheduled_at=scheduled_at,
        is_active=True,
    )

    # Broadcast через WebSocket всем подключённым
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'maintenance_broadcast',
        {
            'type': 'maintenance_warning',
            'minutes': minutes,
            'message': message,
            'scheduled_at': scheduled_at.isoformat(),
            'notice_id': notice.id,
        }
    )

    return JsonResponse({
        'ok': True,
        'notice_id': notice.id,
        'scheduled_at': scheduled_at.isoformat(),
    })


@login_required
@require_POST
def api_maintenance_cancel(request):
    """
    POST /api/maintenance/cancel/
    Отмена активного уведомления. Только для сисадмина.
    """
    if not _is_sysadmin(request.user):
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    notices = MaintenanceNotice.objects.filter(is_active=True)
    notice_ids = list(notices.values_list('id', flat=True))
    notices.update(is_active=False)

    # Broadcast отмену
    channel_layer = get_channel_layer()
    for nid in notice_ids:
        async_to_sync(channel_layer.group_send)(
            'maintenance_broadcast',
            {
                'type': 'maintenance_cancel',
                'notice_id': nid,
            }
        )

    return JsonResponse({'ok': True, 'cancelled': notice_ids})


@login_required
def api_maintenance_status(request):
    """
    GET /api/maintenance/status/
    Проверка: есть ли активное предупреждение (для случая если WS не подключён).
    """
    notice = MaintenanceNotice.objects.filter(
        is_active=True,
        scheduled_at__gt=timezone.now()
    ).order_by('-created_at').first()

    if notice:
        remaining = (notice.scheduled_at - timezone.now()).total_seconds()
        return JsonResponse({
            'active': True,
            'notice_id': notice.id,
            'minutes_remaining': max(0, int(remaining / 60)),
            'seconds_remaining': max(0, int(remaining)),
            'message': notice.message,
            'scheduled_at': notice.scheduled_at.isoformat(),
        })

    return JsonResponse({'active': False})
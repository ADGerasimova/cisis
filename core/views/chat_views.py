"""
Chat views (v3.40.0)

API-эндпоинты для чат-системы:
- api_chat_rooms: список комнат пользователя + непрочитанные
- api_chat_messages: сообщения в комнате (пагинация)
- api_chat_mark_read: пометить как прочитанное
- api_chat_create_group: создать групповой чат
- api_chat_create_direct: создать/найти личный чат
- api_chat_unread_count: общий бейдж непрочитанных
- api_chat_search_users: поиск пользователей для создания чата
- api_chat_leave: покинуть групповой чат
"""

import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q, Count, Max, Subquery, OuterRef, F
from django.utils import timezone

from core.models.chat import ChatRoom, ChatMember, ChatMessage, RoomType, MemberRole


def _login_required_json(view_func):
    """Декоратор: проверка авторизации для JSON API."""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'user') or not request.user or not request.user.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


@require_GET
@_login_required_json
def api_chat_rooms(request):
    """Список комнат пользователя с непрочитанными и последним сообщением."""
    user = request.user

    memberships = ChatMember.objects.filter(user=user).select_related('room', 'room__laboratory')

    rooms = []
    for m in memberships:
        room = m.room

        # Последнее сообщение
        last_msg_obj = ChatMessage.objects.filter(
            room=room, is_deleted=False
        ).select_related('sender').order_by('-created_at').first()

        # Непрочитанные
        unread_qs = ChatMessage.objects.filter(room=room, is_deleted=False)
        if m.last_read_at:
            unread_qs = unread_qs.filter(created_at__gt=m.last_read_at)
        # Не считаем свои сообщения
        unread = unread_qs.exclude(sender=user).count()

        # Название для DIRECT — имя собеседника
        if room.room_type == RoomType.DIRECT:
            other = ChatMember.objects.filter(room=room).exclude(user=user).select_related('user').first()
            display_name = other.user.full_name if other else 'Личный чат'
        elif room.is_global:
            display_name = '💬 Общий чат'
        elif room.room_type == RoomType.GENERAL and room.laboratory:
            display_name = f'🏢 {room.laboratory.name}'
        else:
            display_name = room.name or f'Чат #{room.pk}'

        # Иконка типа
        if room.is_global:
            icon = '🌐'
        elif room.room_type == RoomType.GENERAL:
            icon = '🏢'
        elif room.room_type == RoomType.DIRECT:
            icon = '👤'
        else:
            icon = '👥'

        # Сортировка: по времени последнего сообщения (или created_at)
        sort_time = last_msg_obj.created_at.isoformat() if last_msg_obj else room.created_at.isoformat()

        rooms.append({
            'id': room.id,
            'type': room.room_type,
            'name': display_name,
            'icon': icon,
            'is_global': room.is_global,
            'unread': unread,
            'last_message': {
                'text': last_msg_obj.text[:80],
                'sender': last_msg_obj.sender.full_name,
                'time': last_msg_obj.created_at.strftime('%H:%M'),
            } if last_msg_obj else None,
            'sort_time': sort_time,
        })

    # Сортируем: закреплённые (GENERAL) сверху, потом по последнему сообщению
    rooms.sort(key=lambda r: (
        0 if r['is_global'] else (1 if r['type'] == 'GENERAL' else 2),
        r['sort_time'],
    ))
    # Внутри групп — по sort_time DESC (самый свежий наверху)
    general = [r for r in rooms if r['type'] == 'GENERAL']
    others = sorted([r for r in rooms if r['type'] != 'GENERAL'], key=lambda r: r['sort_time'], reverse=True)
    rooms = general + others

    return JsonResponse({'rooms': rooms})


@require_GET
@_login_required_json
def api_chat_messages(request, room_id):
    """Сообщения в комнате. ?before=ID для пагинации, limit=50."""
    user = request.user

    # Проверяем membership
    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    before_id = request.GET.get('before')
    limit = min(int(request.GET.get('limit', 50)), 100)

    qs = ChatMessage.objects.filter(
        room_id=room_id, is_deleted=False
    ).select_related('sender').order_by('-created_at')

    if before_id:
        qs = qs.filter(id__lt=int(before_id))

    messages_raw = list(qs[:limit])
    messages_raw.reverse()  # хронологический порядок

    messages = []
    prev_sender = None
    prev_date = None
    for msg in messages_raw:
        msg_date = msg.created_at.strftime('%d.%m.%Y')
        show_date = msg_date != prev_date
        prev_date = msg_date

        messages.append({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_name': msg.sender.full_name,
            'text': msg.text,
            'time': msg.created_at.strftime('%H:%M'),
            'date': msg_date if show_date else None,
            'is_own': msg.sender_id == user.id,
            'show_sender': msg.sender_id != prev_sender,
        })
        prev_sender = msg.sender_id

    has_more = qs.filter(id__lt=messages_raw[0].id).exists() if messages_raw else False

    # Обновляем last_read_at
    ChatMember.objects.filter(room_id=room_id, user=user).update(last_read_at=timezone.now())

    return JsonResponse({
        'messages': messages,
        'has_more': has_more,
    })


@require_GET
@_login_required_json
def api_chat_unread_count(request):
    """Общее количество непрочитанных сообщений (для бейджа)."""
    user = request.user
    memberships = ChatMember.objects.filter(user=user)

    total = 0
    for m in memberships:
        qs = ChatMessage.objects.filter(room=m.room, is_deleted=False).exclude(sender=user)
        if m.last_read_at:
            qs = qs.filter(created_at__gt=m.last_read_at)
        total += qs.count()

    return JsonResponse({'unread': total})


@require_POST
@_login_required_json
def api_chat_mark_read(request, room_id):
    """Пометить все сообщения в комнате как прочитанные."""
    updated = ChatMember.objects.filter(
        room_id=room_id, user=request.user
    ).update(last_read_at=timezone.now())

    return JsonResponse({'ok': bool(updated)})


@require_POST
@_login_required_json
def api_chat_create_group(request):
    """Создать групповой чат."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    member_ids = data.get('member_ids', [])

    if not name:
        return JsonResponse({'error': 'Название обязательно'}, status=400)
    if not member_ids:
        return JsonResponse({'error': 'Добавьте хотя бы одного участника'}, status=400)

    from core.models import User

    room = ChatRoom.objects.create(
        room_type=RoomType.GROUP,
        name=name,
        created_by=request.user,
    )

    # Создатель = OWNER
    ChatMember.objects.create(room=room, user=request.user, role=MemberRole.OWNER)

    # Остальные участники
    users = User.objects.filter(id__in=member_ids, is_active=True)
    for u in users:
        if u.id != request.user.id:
            ChatMember.objects.get_or_create(room=room, user=u)

    return JsonResponse({'room_id': room.id, 'name': room.name})


@require_POST
@_login_required_json
def api_chat_create_direct(request):
    """Создать или найти личный чат с пользователем."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    other_user_id = data.get('user_id')
    if not other_user_id or other_user_id == request.user.id:
        return JsonResponse({'error': 'Неверный пользователь'}, status=400)

    from core.models import User
    try:
        other_user = User.objects.get(id=other_user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Пользователь не найден'}, status=404)

    # Ищем существующий DIRECT чат между двумя пользователями
    existing = ChatRoom.objects.filter(
        room_type=RoomType.DIRECT,
        members__user=request.user,
    ).filter(
        members__user=other_user,
    ).first()

    if existing:
        return JsonResponse({'room_id': existing.id, 'name': other_user.full_name})

    # Создаём новый
    room = ChatRoom.objects.create(
        room_type=RoomType.DIRECT,
        created_by=request.user,
    )
    ChatMember.objects.create(room=room, user=request.user, role=MemberRole.OWNER)
    ChatMember.objects.create(room=room, user=other_user)

    return JsonResponse({'room_id': room.id, 'name': other_user.full_name})


@require_GET
@_login_required_json
def api_chat_search_users(request):
    """Поиск пользователей для создания чата."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'users': []})

    from core.models import User
    users = User.objects.filter(
        is_active=True,
    ).filter(
        Q(last_name__icontains=q) | Q(first_name__icontains=q) |
        Q(sur_name__icontains=q) | Q(username__icontains=q)
    ).exclude(
        id=request.user.id
    ).select_related('laboratory')[:15]

    return JsonResponse({
        'users': [
            {
                'id': u.id,
                'name': u.full_name,
                'lab': u.laboratory.name if u.laboratory else '',
            }
            for u in users
        ]
    })


@require_POST
@_login_required_json
def api_chat_leave(request, room_id):
    """Покинуть групповой чат."""
    try:
        membership = ChatMember.objects.select_related('room').get(
            room_id=room_id, user=request.user,
        )
    except ChatMember.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    # Нельзя покинуть GENERAL чат
    if membership.room.room_type == RoomType.GENERAL:
        return JsonResponse({'error': 'Нельзя покинуть общий чат'}, status=400)

    membership.delete()
    return JsonResponse({'ok': True})


@require_GET
@_login_required_json
def api_chat_room_members(request, room_id):
    """Список участников комнаты."""
    if not ChatMember.objects.filter(room_id=room_id, user=request.user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    members = ChatMember.objects.filter(
        room_id=room_id
    ).select_related('user', 'user__laboratory').order_by('user__last_name', 'user__first_name')

    return JsonResponse({
        'members': [
            {
                'id': m.user.id,
                'name': m.user.full_name,
                'role': m.role,
                'lab': m.user.laboratory.name if m.user.laboratory else '',
            }
            for m in members
        ]
    })

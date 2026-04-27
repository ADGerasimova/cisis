"""
Chat views (v3.40.0 → v3.40.1)

API-эндпоинты для чат-системы.
v3.40.1: загрузка файлов/изображений, исправлены full_name lookups
"""

import json
import os
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings

from core.models.chat import ChatRoom, ChatMember, ChatMessage, RoomType, MemberRole, ChatMessageReaction
import os, uuid
from django.conf import settings
from django.utils import timezone as tz
from django.utils.timezone import localtime
import re

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

    # v3.60.0: is_pinned не в ORM-модели, берём raw
    from django.db import connection as _conn
    pinned_rooms = set()
    with _conn.cursor() as _cur:
        _cur.execute('SELECT room_id FROM chat_members WHERE user_id = %s AND is_pinned = TRUE', [user.id])
        pinned_rooms = {row[0] for row in _cur.fetchall()}

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
        unread = unread_qs.exclude(sender=user).count()

        # Название для DIRECT
        direct_avatar = None
        direct_online = None
        direct_last_seen = None

        if room.room_type == RoomType.DIRECT:
            other = ChatMember.objects.filter(room=room).exclude(user=user).select_related('user').first()
            display_name = other.user.full_name if other else 'Личный чат'
            direct_avatar = other.user.avatar_url if other else None
            direct_online = other.user.is_online if other else False
            direct_last_seen = other.user.last_seen_display if other else ''
        elif room.is_global:
            display_name = '💬 Общий чат'
        elif room.room_type == RoomType.GENERAL and room.laboratory:
            display_name = f'🏢 {room.laboratory.name}'
        else:
            display_name = room.name or f'Чат #{room.pk}'

        # Иконка
        if room.is_global:
            icon = '🌐'
        elif room.room_type == RoomType.GENERAL:
            icon = '🏢'
        elif room.room_type == RoomType.DIRECT:
            icon = '👤'
        else:
            icon = '👥'

        sort_time = last_msg_obj.created_at.isoformat() if last_msg_obj else room.created_at.isoformat()

        # Превью последнего сообщения
        if last_msg_obj:
            if last_msg_obj.file_name and not last_msg_obj.text:
                preview_text = f'📎 {last_msg_obj.file_name}'
            elif last_msg_obj.file_name:
                preview_text = f'📎 {last_msg_obj.text[:60]}'
            else:
                preview_text = last_msg_obj.text[:80]

                sticker_match = re.match(r'^\[sticker:(\w+)\]$', last_msg_obj.text or '')
                if sticker_match:
                    preview_text = '🎨 Стикер'
            last_message = {
                'text': preview_text,
                'sender': last_msg_obj.sender.full_name,
                'time': localtime(last_msg_obj.created_at).strftime('%H:%M'),
            }
        else:
            last_message = None

        rooms.append({
            'id': room.id,
            'type': room.room_type,
            'name': display_name,
            'icon': icon,
            'is_global': room.is_global,
            'unread': unread,
            'last_message': last_message,
            'sort_time': sort_time,
            'avatar': direct_avatar,
            'is_online': direct_online if room.room_type == RoomType.DIRECT else None,
            'last_seen': direct_last_seen if room.room_type == RoomType.DIRECT else None,
            'is_pinned': room.id in pinned_rooms,
        })

    # Сортировка: закреплённые → общие → по времени
    pinned = sorted([r for r in rooms if r['is_pinned']], key=lambda r: r['sort_time'], reverse=True)
    general = [r for r in rooms if r['type'] == 'GENERAL' and not r['is_pinned']]
    others = sorted([r for r in rooms if r['type'] != 'GENERAL' and not r['is_pinned']], key=lambda r: r['sort_time'], reverse=True)
    rooms = pinned + general + others

    return JsonResponse({'rooms': rooms})


@require_GET
@_login_required_json
def api_chat_messages(request, room_id):
    """Сообщения в комнате. ?before=ID для пагинации."""
    user = request.user

    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    before_id = request.GET.get('before')
    limit = min(int(request.GET.get('limit', 50)), 100)

    qs = ChatMessage.objects.filter(
        room_id=room_id, is_deleted=False
    ).select_related('sender', 'reply_to', 'reply_to__sender').order_by('-created_at')

    if before_id:
        qs = qs.filter(id__lt=int(before_id))

    messages_raw = list(qs[:limit])
    messages_raw.reverse()

    # v3.60.0: forwarded_from не в ORM-модели (managed=False), берём raw
    forwarded_map = {}
    if messages_raw:
        from django.db import connection as _conn
        _msg_ids = [m.id for m in messages_raw]
        with _conn.cursor() as _cur:
            _cur.execute(
                'SELECT id, forwarded_from FROM chat_messages WHERE id = ANY(%s) AND forwarded_from IS NOT NULL',
                [_msg_ids]
            )
            for _row in _cur.fetchall():
                forwarded_map[_row[0]] = _row[1]

    messages = []
    prev_sender = None
    prev_date = None
    for msg in messages_raw:
        msg_date = localtime(msg.created_at).strftime('%d.%m.%Y')
        show_date = msg_date != prev_date
        prev_date = msg_date

        msg_data = {
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_name': msg.sender.full_name,
            'text': msg.text,
            'time': localtime(msg.created_at).strftime('%H:%M'),
            'date': msg_date if show_date else None,
            'is_own': msg.sender_id == user.id,
            'show_sender': msg.sender_id != prev_sender,
            'avatar': msg.sender.avatar_url,
            'initials': msg.sender.initials,
            'edited_at': localtime(msg.edited_at).strftime('%H:%M') if msg.edited_at else None,
            'forwarded_from': forwarded_map.get(msg.id),
        }

        # ⭐ Прочитанность (только для своих сообщений)
        if msg.sender_id == user.id:
            from core.models.chat import ChatReadReceipt
            total_others = ChatMember.objects.filter(room_id=room_id).exclude(user=user).count()
            read_count = ChatReadReceipt.objects.filter(message=msg).exclude(user=user).count()
            if total_others > 0 and read_count >= total_others:
                msg_data['read_status'] = 'read'
            elif read_count > 0:
                msg_data['read_status'] = 'partial'
            else:
                msg_data['read_status'] = 'sent'
        else:
            msg_data['read_status'] = None

        # ⭐ Ответ на сообщение
        if msg.reply_to_id and msg.reply_to:
            msg_data['reply_to'] = {
                'id': msg.reply_to_id,
                'sender_name': msg.reply_to.sender.full_name,
                'text': (msg.reply_to.text or '')[:60],
            }
        else:
            msg_data['reply_to'] = None

        # Файл
        if msg.file_name:
            msg_data['file'] = {
                'name': msg.file_name,
                'path': msg.file_path,
                'size': msg.file_size_display,
                'type': msg.file_type or '',
                'is_image': msg.is_image,
                'url': f'/api/chat/file/{msg.file_path}' if msg.file_path else '',
            }
        # ⭐ v3.46.0: Реакции
        reactions_qs = ChatMessageReaction.objects.filter(
            message=msg
        ).values('emoji').annotate(
            count=Count('id')
        ).order_by('-count')
        my_reaction_emojis = set(
            ChatMessageReaction.objects.filter(
                message=msg, user=user
            ).values_list('emoji', flat=True)
        )
        msg_data['reactions'] = [
            {
                'emoji': r['emoji'],
                'count': r['count'],
                'is_mine': r['emoji'] in my_reaction_emojis,
            }
            for r in reactions_qs
        ]

        messages.append(msg_data)
        prev_sender = msg.sender_id

    has_more = qs.filter(id__lt=messages_raw[0].id).exists() if messages_raw else False

    # Обновляем last_read_at
    ChatMember.objects.filter(room_id=room_id, user=user).update(last_read_at=timezone.now())

    return JsonResponse({'messages': messages, 'has_more': has_more})


@require_GET
@_login_required_json
def api_chat_unread_count(request):
    """Общее количество непрочитанных (для бейджа)."""
    user = request.user
    # ⭐ Heartbeat: обновляем last_seen_at (не чаще раза в минуту)
    from django.utils import timezone as tz
    if not user.last_seen_at or (tz.now() - user.last_seen_at).total_seconds() > 60:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('UPDATE users SET last_seen_at = NOW() WHERE id = %s', [user.id])
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
    """Пометить как прочитанное."""
    updated = ChatMember.objects.filter(
        room_id=room_id, user=request.user
    ).update(last_read_at=timezone.now())
    # Создаём read receipts
    from core.models.chat import ChatReadReceipt
    unread_msgs = ChatMessage.objects.filter(
        room_id=room_id, is_deleted=False
    ).exclude(sender=request.user).exclude(read_receipts__user=request.user)
    for msg in unread_msgs:
        ChatReadReceipt.objects.get_or_create(message=msg, user=request.user)
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
    ChatMember.objects.create(room=room, user=request.user, role=MemberRole.OWNER)

    users = User.objects.filter(id__in=member_ids, is_active=True)
    for u in users:
        if u.id != request.user.id:
            ChatMember.objects.get_or_create(room=room, user=u)

    return JsonResponse({'room_id': room.id, 'name': room.name})


@require_POST
@_login_required_json
def api_chat_create_direct(request):
    """Создать или найти личный чат."""
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

    existing = ChatRoom.objects.filter(
        room_type=RoomType.DIRECT,
        members__user=request.user,
    ).filter(
        members__user=other_user,
    ).first()

    if existing:
        return JsonResponse({'room_id': existing.id, 'name': other_user.full_name})

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

    from core.models import User

    # q=all → вернуть всех активных
    if q == 'all':
        users = User.objects.filter(
            is_active=True,
        ).exclude(
            id=request.user.id
        ).select_related('laboratory').order_by('last_name', 'first_name')
    else:
        if len(q) < 2:
            return JsonResponse({'users': []})
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
                'avatar': u.avatar_url,
                'initials': u.initials,
                'is_online': u.is_online,
                'last_seen': u.last_seen_display,
            }
            for u in users
        ]
    })

@require_GET
@_login_required_json
def api_chat_read_status(request, room_id):
    """
    Возвращает статус прочитанности для конкретных сообщений.
    GET ?ids=1,2,3  → [{id, status: 'sent'|'partial'|'read'}, ...]
    Используется клиентом для polling галочек прочитанности.
    """
    if not ChatMember.objects.filter(room_id=room_id, user=request.user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    ids_param = request.GET.get('ids', '')
    try:
        msg_ids = [int(x) for x in ids_param.split(',') if x.strip()]
    except ValueError:
        return JsonResponse({'error': 'Invalid ids'}, status=400)

    if not msg_ids:
        return JsonResponse({'statuses': []})

    from core.models.chat import ChatReadReceipt
    total_others = ChatMember.objects.filter(room_id=room_id).exclude(user=request.user).count()

    statuses = []
    msgs = ChatMessage.objects.filter(
        id__in=msg_ids, room_id=room_id, sender=request.user, is_deleted=False
    )
    for msg in msgs:
        read_count = ChatReadReceipt.objects.filter(message=msg).exclude(user=request.user).count()
        if total_others > 0 and read_count >= total_others:
            status = 'read'
        elif read_count > 0:
            status = 'partial'
        else:
            status = 'sent'
        statuses.append({'id': msg.id, 'status': status})

    return JsonResponse({'statuses': statuses})


@require_GET
@_login_required_json
def api_chat_message_read_by(request, room_id, message_id):
    """
    Возвращает, кто из участников комнаты прочитал конкретное сообщение, а кто — нет.
    Доступ только автору сообщения.
    GET → {
        "read":   [{user_id, name, avatar, initials, read_at}, ...],
        "unread": [{user_id, name, avatar, initials, last_seen}, ...],
    }
    """
    # Доступ к комнате
    if not ChatMember.objects.filter(room_id=room_id, user=request.user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        msg = ChatMessage.objects.get(id=message_id, room_id=room_id, is_deleted=False)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    # Список «кто прочитал» виден только автору сообщения
    if msg.sender_id != request.user.id:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    from core.models.chat import ChatReadReceipt

    # Все участники комнаты, кроме автора
    members = ChatMember.objects.filter(room_id=room_id).exclude(user=request.user) \
        .select_related('user')

    # Карта user_id → read_at
    receipts = ChatReadReceipt.objects.filter(message=msg).exclude(user=request.user)
    read_map = {r.user_id: r.read_at for r in receipts}

    read_list = []
    unread_list = []
    for m in members:
        u = m.user
        base = {
            'user_id': u.id,
            'name': u.full_name,
            'avatar': u.avatar_url,
            'initials': u.initials,
        }
        if u.id in read_map:
            base['read_at'] = localtime(read_map[u.id]).strftime('%d.%m.%Y %H:%M')
            read_list.append(base)
        else:
            base['last_seen'] = u.last_seen_display
            unread_list.append(base)

    # Прочитавшие — сначала самые свежие; не прочитавшие — по имени
    read_list.sort(key=lambda x: x['read_at'], reverse=True)
    unread_list.sort(key=lambda x: x['name'])

    return JsonResponse({
        'message_id': msg.id,
        'read': read_list,
        'unread': unread_list,
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
                'avatar': m.user.avatar_url,
                'initials': m.user.initials,
                'is_online': m.user.is_online,
                'last_seen': m.user.last_seen_display,
            }
            for m in members
        ]
    })


@require_POST
@_login_required_json
def api_chat_upload_file(request, room_id):
    """Загрузить файл в чат-комнату."""
    user = request.user

    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'Нет файла'}, status=400)

    if file.size > 20 * 1024 * 1024:
        return JsonResponse({'error': 'Максимальный размер файла — 20 МБ'}, status=400)

    # ═══ S3 загрузка ═══
    from core.services.s3_utils import upload_file, generate_s3_key
    from datetime import datetime

    prefix = f'chat/{datetime.now().strftime("%Y-%m")}'
    s3_key = generate_s3_key(prefix, file.name)

    result = upload_file(file, s3_key, content_type=file.content_type)
    if not result:
        return JsonResponse({'error': 'Ошибка загрузки файла'}, status=500)

    text = request.POST.get('text', '').strip()
    reply_to_id = request.POST.get('reply_to_id') or None
    if reply_to_id:
        reply_to_id = int(reply_to_id)

    # Создаём сообщение (file_path = S3 key)
    msg = ChatMessage.objects.create(
        room_id=room_id,
        sender=user,
        text=text,
        file_path=s3_key,
        file_name=file.name,
        file_size=file.size,
        file_type=file.content_type or '',
        reply_to_id=reply_to_id,
    )

    is_image = file.content_type and file.content_type.startswith('image/')

    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_id}',
        {
            'type': 'chat_message',
            'message_id': msg.id,
            'sender_id': user.id,
            'sender_name': user.full_name,
            'text': text,
            'created_at': localtime(msg.created_at).strftime('%H:%M'),
            'file': {
                'name': file.name,
                'url': f'/api/chat/file/{s3_key}',
                'size': msg.file_size_display,
                'type': file.content_type or '',
                'is_image': is_image,
            },
            'reply_to': {
                'id': reply_to_id,
                'sender_name': ChatMessage.objects.get(id=reply_to_id).sender.full_name,
                'text': (ChatMessage.objects.get(id=reply_to_id).text or '')[:60],
            } if reply_to_id else None,
        }
    )

    return JsonResponse({
        'ok': True,
        'message_id': msg.id,
    })

@require_POST
@_login_required_json
def api_chat_add_member(request, room_id):
    """Добавить участника в групповой чат."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'user_id обязателен'}, status=400)

    # Проверяем что мы OWNER этой комнаты
    try:
        membership = ChatMember.objects.select_related('room').get(
            room_id=room_id, user=request.user,
        )
    except ChatMember.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if membership.room.room_type == RoomType.DIRECT:
        return JsonResponse({'error': 'Нельзя добавлять в личный чат'}, status=400)

    # Любой участник может добавлять людей в групповой чат

    from core.models import User
    try:
        new_user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Пользователь не найден'}, status=404)

    member, created = ChatMember.objects.get_or_create(
        room_id=room_id, user=new_user,
        defaults={'is_manual': True},
    )
    return JsonResponse({'ok': True, 'created': created, 'name': new_user.full_name})


@require_POST
@_login_required_json
def api_chat_remove_member(request, room_id):
    """Удалить участника из группового чата."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'user_id обязателен'}, status=400)

    # Проверяем что мы OWNER
    try:
        my_membership = ChatMember.objects.select_related('room').get(
            room_id=room_id, user=request.user,
        )
    except ChatMember.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if my_membership.room.room_type == RoomType.DIRECT:
        return JsonResponse({'error': 'Нельзя удалять из личного чата'}, status=400)

    if my_membership.role != MemberRole.OWNER:
        return JsonResponse({'error': 'Только создатель может удалять участников'}, status=403)

    # Нельзя удалить самого себя (владельца)
    if user_id == request.user.id:
        return JsonResponse({'error': 'Нельзя удалить себя'}, status=400)

    deleted, _ = ChatMember.objects.filter(room_id=room_id, user_id=user_id).delete()
    return JsonResponse({'ok': True, 'deleted': bool(deleted)})


@require_POST
@_login_required_json
def api_chat_delete_room(request, room_id):
    """Удалить групповой чат (только OWNER)."""
    try:
        membership = ChatMember.objects.select_related('room').get(
            room_id=room_id, user=request.user,
        )
    except ChatMember.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    room = membership.room

    if room.room_type != RoomType.GROUP:
        return JsonResponse({'error': 'Можно удалить только групповые чаты'}, status=400)

    if membership.role != MemberRole.OWNER:
        return JsonResponse({'error': 'Только создатель может удалить чат'}, status=403)

    room_name = room.name
    room.delete()  # CASCADE удалит members и messages

    return JsonResponse({'ok': True, 'name': room_name})


@require_POST
def avatar_upload(request):
    """Загрузка аватарки текущего пользователя."""
    user = request.user
    if not user or not user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    file = request.FILES.get('avatar')
    if not file:
        return JsonResponse({'error': 'Нет файла'}, status=400)

    # Только изображения
    if not file.content_type.startswith('image/'):
        return JsonResponse({'error': 'Только изображения'}, status=400)

    # Макс 5 МБ
    if file.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'Максимум 5 МБ'}, status=400)

    avatar_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)

    # Удаляем старую аватарку
    if user.avatar_path and os.path.exists(user.avatar_path):
        try:
            os.remove(user.avatar_path)
        except OSError:
            pass

    ext = os.path.splitext(file.name)[1].lower()
    safe_name = f'{user.id}_{uuid.uuid4().hex[:8]}{ext}'
    file_path = os.path.join(avatar_dir, safe_name)

    with open(file_path, 'wb+') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    # Обновляем поле в БД напрямую (managed=False)
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('UPDATE users SET avatar_path = %s WHERE id = %s', [file_path, user.id])

    return JsonResponse({
        'ok': True,
        'avatar_url': f'/media/avatars/{safe_name}',
    })


@require_POST
def avatar_delete(request):
    """Удалить аватарку текущего пользователя."""
    user = request.user
    if not user or not user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    if user.avatar_path and os.path.exists(user.avatar_path):
        try:
            os.remove(user.avatar_path)
        except OSError:
            pass

    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('UPDATE users SET avatar_path = NULL WHERE id = %s', [user.id])

    return JsonResponse({'ok': True})

def sync_user_chats(user):
    """
    Синхронизирует членство пользователя в GENERAL чатах.
    Не удаляет вручную добавленных (is_manual=True).
    Вызывать при: создании, деактивации, активации, смене подразделения.
    """
    from core.models.chat import ChatRoom, ChatMember, RoomType

    global_rooms = ChatRoom.objects.filter(room_type=RoomType.GENERAL, is_global=True)
    lab_rooms = ChatRoom.objects.filter(room_type=RoomType.GENERAL, laboratory__isnull=False)

    if not user.is_active:
        ChatMember.objects.filter(
            user=user,
            room__room_type=RoomType.GENERAL,
        ).delete()
        return

    for room in global_rooms:
        ChatMember.objects.get_or_create(room=room, user=user)

    user_lab_ids = user.all_laboratory_ids

    for room in lab_rooms:
        membership = ChatMember.objects.filter(room=room, user=user).first()
        should_be = room.laboratory_id in user_lab_ids

        if should_be and not membership:
            ChatMember.objects.create(room=room, user=user)
        elif not should_be and membership and not membership.is_manual:
            membership.delete()

@require_GET
@_login_required_json
def api_chat_file(request, s3_key):
    """Отдаёт presigned URL для скачивания файла чата."""
    msg = ChatMessage.objects.filter(file_path=s3_key, is_deleted=False).first()
    if not msg:
        return JsonResponse({'error': 'Not found'}, status=404)

    if not ChatMember.objects.filter(room_id=msg.room_id, user=request.user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    from core.services.s3_utils import _get_client, get_bucket
    from urllib.parse import quote

    s3 = _get_client()
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': get_bucket(),
                'Key': s3_key,
                'ResponseContentType': msg.file_type or 'application/octet-stream',
                'ResponseContentDisposition': f"attachment; filename*=UTF-8''{quote(msg.file_name)}",
            },
            ExpiresIn=3600,
        )
    except Exception:
        return JsonResponse({'error': 'Ошибка генерации ссылки'}, status=500)

    from django.shortcuts import redirect
    return redirect(url)

@require_POST
@_login_required_json
def api_chat_toggle_reaction(request, room_id, message_id):
    """Toggle реакции на сообщение. v3.46.0"""
    user = request.user

    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        msg = ChatMessage.objects.get(id=message_id, room_id=room_id, is_deleted=False)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    emoji = data.get('emoji', '').strip()
    if not emoji:
        return JsonResponse({'error': 'emoji обязателен'}, status=400)

    # Toggle
    existing = ChatMessageReaction.objects.filter(
        message=msg, user=user, emoji=emoji
    ).first()

    if existing:
        existing.delete()
        action = 'removed'
    else:
        ChatMessageReaction.objects.create(message=msg, user=user, emoji=emoji)
        action = 'added'

    # Собираем актуальные реакции
    reactions_qs = ChatMessageReaction.objects.filter(
        message=msg
    ).values('emoji').annotate(count=Count('id')).order_by('-count')
    my_emojis = set(
        ChatMessageReaction.objects.filter(
            message=msg, user=user
        ).values_list('emoji', flat=True)
    )
    reactions = [
        {'emoji': r['emoji'], 'count': r['count'], 'is_mine': r['emoji'] in my_emojis}
        for r in reactions_qs
    ]

    # Broadcast через WebSocket
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_id}',
        {
            'type': 'reaction_update',
            'message_id': message_id,
            'emoji': emoji,
            'action': action,
            'user_id': user.id,
            'user_name': user.full_name,
            'reactions': reactions,
        }
    )

    return JsonResponse({'ok': True, 'action': action, 'reactions': reactions})

@require_POST
@_login_required_json
def api_chat_edit_message(request, room_id, message_id):
    """Редактировать своё сообщение."""
    user = request.user

    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        msg = ChatMessage.objects.get(id=message_id, room_id=room_id, sender=user, is_deleted=False)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    new_text = data.get('text', '').strip()
    if not new_text:
        return JsonResponse({'error': 'Текст не может быть пустым'}, status=400)

    # Обновляем
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute(
            'UPDATE chat_messages SET text = %s, edited_at = NOW() WHERE id = %s',
            [new_text, msg.id]
        )

    # Broadcast
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_id}',
        {
            'type': 'message_edit',
            'message_id': message_id,
            'text': new_text,
            'edited_at': localtime(timezone.now()).strftime('%H:%M'),
        }
    )

    return JsonResponse({'ok': True})


@require_POST
@_login_required_json
def api_chat_delete_message(request, room_id, message_id):
    """Удалить своё сообщение (soft delete)."""
    user = request.user

    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        msg = ChatMessage.objects.get(id=message_id, room_id=room_id, sender=user, is_deleted=False)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)

    from django.db import connection
    with connection.cursor() as cur:
        cur.execute(
            'UPDATE chat_messages SET is_deleted = TRUE, text = %s WHERE id = %s',
            ['', msg.id]
        )

    # Broadcast
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_id}',
        {
            'type': 'message_delete',
            'message_id': message_id,
        }
    )

    return JsonResponse({'ok': True})

# ═══════════════════════════════════════════════════════
# v3.60.0: Пересылка сообщений + Поиск
# Добавить в конец chat_views.py
# ═══════════════════════════════════════════════════════


@require_POST
@_login_required_json
def api_chat_forward_message(request):
    """
    Переслать сообщения в другую комнату.
    POST { message_id: int, target_room_id: int }          — одно сообщение
    POST { message_ids: [int, ...], target_room_id: int }   — несколько сообщений
    """
    user = request.user

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    target_room_id = data.get('target_room_id')
    if not target_room_id:
        return JsonResponse({'error': 'target_room_id обязателен'}, status=400)

    # Поддержка одного или нескольких сообщений
    message_ids = data.get('message_ids') or []
    if not message_ids and data.get('message_id'):
        message_ids = [data['message_id']]
    if not message_ids:
        return JsonResponse({'error': 'message_id или message_ids обязательны'}, status=400)

    # Проверяем доступ к целевой комнате
    if not ChatMember.objects.filter(room_id=target_room_id, user=user).exists():
        return JsonResponse({'error': 'Нет доступа к целевой комнате'}, status=403)

    # Загружаем оригиналы (в порядке создания)
    originals = list(
        ChatMessage.objects.filter(id__in=message_ids, is_deleted=False)
        .select_related('sender')
        .order_by('created_at')
    )
    if not originals:
        return JsonResponse({'error': 'Сообщения не найдены'}, status=404)

    # Проверяем доступ к исходным комнатам
    source_room_ids = {m.room_id for m in originals}
    user_room_ids = set(ChatMember.objects.filter(user=user).values_list('room_id', flat=True))
    if not source_room_ids.issubset(user_room_ids):
        return JsonResponse({'error': 'Нет доступа к исходным сообщениям'}, status=403)

    from django.db import connection
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()

    new_ids = []
    for original in originals:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (room_id, sender_id, text, forwarded_from, created_at,
                                           is_deleted, file_path, file_name, file_size, file_type)
                VALUES (%s, %s, %s, %s, NOW(), FALSE, %s, %s, %s, %s)
                RETURNING id, created_at
            """, [
                target_room_id, user.id,
                original.text or '', original.sender.full_name,
                original.file_path or '', original.file_name or '',
                original.file_size or 0, original.file_type or '',
            ])
            row = cur.fetchone()

        file_data = None
        if original.file_name:
            file_data = {
                'name': original.file_name,
                'url': f'/api/chat/file/{original.file_path}' if original.file_path else '',
                'size': original.file_size_display,
                'type': original.file_type or '',
                'is_image': original.is_image,
            }

        async_to_sync(channel_layer.group_send)(
            f'chat_{target_room_id}',
            {
                'type': 'chat_message',
                'message_id': row[0],
                'sender_id': user.id,
                'sender_name': user.full_name,
                'text': original.text or '',
                'created_at': localtime(row[1]).strftime('%H:%M'),
                'file': file_data,
                'reply_to': None,
                'forwarded_from': original.sender.full_name,
            }
        )
        new_ids.append(row[0])

    return JsonResponse({'ok': True, 'message_ids': new_ids, 'count': len(new_ids)})


@require_GET
@_login_required_json
def api_chat_search_messages(request):
    """
    Поиск сообщений по тексту.
    GET /api/chat/search/?q=текст&room_id=123 (room_id опционален)
    Ищет только в комнатах, где пользователь — участник.
    """
    user = request.user
    q = request.GET.get('q', '').strip()
    room_id = request.GET.get('room_id')
    limit = min(int(request.GET.get('limit', 30)), 50)

    if len(q) < 2:
        return JsonResponse({'results': []})

    # Комнаты пользователя
    user_room_ids = list(
        ChatMember.objects.filter(user=user).values_list('room_id', flat=True)
    )
    if not user_room_ids:
        return JsonResponse({'results': []})

    from django.db import connection

    if room_id:
        # Поиск внутри конкретной комнаты
        room_id = int(room_id)
        if room_id not in user_room_ids:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        room_filter = 'AND m.room_id = %s'
        params = [f'%{q}%', room_id, limit]
    else:
        # Глобальный поиск по всем комнатам пользователя
        placeholders = ','.join(['%s'] * len(user_room_ids))
        room_filter = f'AND m.room_id IN ({placeholders})'
        params = [f'%{q}%'] + user_room_ids + [limit]

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT m.id, m.room_id, m.text, m.created_at, m.sender_id,
                   u.first_name, u.last_name, u.sur_name,
                   r.name AS room_name, r.room_type, r.is_global
            FROM chat_messages m
            JOIN users u ON u.id = m.sender_id
            JOIN chat_rooms r ON r.id = m.room_id
            WHERE m.is_deleted = FALSE
              AND m.text ILIKE %s
              {room_filter}
            ORDER BY m.created_at DESC
            LIMIT %s
        """, params)
        rows = cur.fetchall()

    # Для DIRECT-чатов — показываем имя собеседника вместо null
    direct_room_names = {}
    direct_room_ids = [row[1] for row in rows if row[9] == 'DIRECT']
    if direct_room_ids:
        for rid in set(direct_room_ids):
            other = ChatMember.objects.filter(
                room_id=rid
            ).exclude(user=user).select_related('user').first()
            if other:
                direct_room_names[rid] = other.user.full_name

    results = []
    for row in rows:
        msg_id, r_id, text, created_at, sender_id, first, last, sur, room_name, room_type, is_global = row

        sender_name = ' '.join(filter(None, [last, first, sur]))

        if room_type == 'DIRECT':
            display_room = direct_room_names.get(r_id, 'Личный чат')
        elif is_global:
            display_room = '💬 Общий чат'
        else:
            display_room = room_name or f'Чат #{r_id}'

        # Фрагмент текста с подсветкой контекста
        snippet = text or ''
        if len(snippet) > 120:
            # Находим позицию совпадения и берём окно вокруг
            pos = snippet.lower().find(q.lower())
            if pos > 40:
                snippet = '…' + snippet[pos - 30:]
            if len(snippet) > 120:
                snippet = snippet[:120] + '…'

        results.append({
            'message_id': msg_id,
            'room_id': r_id,
            'room_name': display_room,
            'room_type': room_type,
            'sender_name': sender_name,
            'text': snippet,
            'time': localtime(created_at).strftime('%d.%m %H:%M'),
        })

    return JsonResponse({'results': results, 'query': q})


@require_POST
@_login_required_json
def api_chat_toggle_pin(request, room_id):
    """Закрепить/открепить чат. v3.60.0"""
    user = request.user

    if not ChatMember.objects.filter(room_id=room_id, user=user).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    from django.db import connection
    with connection.cursor() as cur:
        cur.execute(
            'UPDATE chat_members SET is_pinned = NOT is_pinned WHERE room_id = %s AND user_id = %s RETURNING is_pinned',
            [room_id, user.id]
        )
        row = cur.fetchone()
        is_pinned = row[0] if row else False

    return JsonResponse({'ok': True, 'is_pinned': is_pinned})
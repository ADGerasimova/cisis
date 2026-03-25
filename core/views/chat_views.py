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
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

from core.models.chat import ChatRoom, ChatMember, ChatMessage, RoomType, MemberRole
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
        })

    # Сортировка
    general = [r for r in rooms if r['type'] == 'GENERAL']
    others = sorted([r for r in rooms if r['type'] != 'GENERAL'], key=lambda r: r['sort_time'], reverse=True)
    rooms = general + others

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
                'url': f'/media/chat/{os.path.basename(msg.file_path)}' if msg.file_path else '',
            }

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
                'avatar': u.avatar_url,
                'initials': u.initials,
                'is_online': u.is_online,
                'last_seen': u.last_seen_display,
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

    # Ограничение: 20 МБ
    if file.size > 20 * 1024 * 1024:
        return JsonResponse({'error': 'Максимальный размер файла — 20 МБ'}, status=400)

    # Сохраняем файл
    chat_dir = os.path.join(settings.MEDIA_ROOT, 'chat')
    os.makedirs(chat_dir, exist_ok=True)

    ext = os.path.splitext(file.name)[1].lower()
    safe_name = f'{uuid.uuid4().hex}{ext}'
    file_path = os.path.join(chat_dir, safe_name)

    with open(file_path, 'wb+') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    text = request.POST.get('text', '').strip()
    reply_to_id = request.POST.get('reply_to_id') or None
    if reply_to_id:
        reply_to_id = int(reply_to_id)

    # Создаём сообщение
    msg = ChatMessage.objects.create(
        room_id=room_id,
        sender=user,
        text=text,
        file_path=file_path,
        file_name=file.name,
        file_size=file.size,
        file_type=file.content_type or '',
        reply_to_id=reply_to_id,
    )

    is_image = file.content_type and file.content_type.startswith('image/')

    # Отправляем через channel layer
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
                'url': f'/media/chat/{safe_name}',
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
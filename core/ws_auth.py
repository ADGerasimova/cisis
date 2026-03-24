"""
Middleware для аутентификации WebSocket-соединений (v3.40.0)

Читает session cookie из scope и подставляет user.
Используется вместо стандартного AuthMiddlewareStack,
т.к. у нас кастомная модель User.
"""

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.sessions.models import Session
from django.utils import timezone


@database_sync_to_async
def get_user_from_scope(scope):
    """Достаём пользователя из session cookie в WebSocket scope."""
    from core.models import User

    cookies = {}
    for header_name, header_value in scope.get('headers', []):
        if header_name == b'cookie':
            for item in header_value.decode().split(';'):
                item = item.strip()
                if '=' in item:
                    k, v = item.split('=', 1)
                    cookies[k.strip()] = v.strip()
            break

    session_key = cookies.get('sessionid')
    if not session_key:
        return None

    try:
        session = Session.objects.get(
            session_key=session_key,
            expire_date__gt=timezone.now(),
        )
        data = session.get_decoded()
        user_id = data.get('_auth_user_id')
        if user_id:
            return User.objects.get(pk=user_id, is_active=True)
    except (Session.DoesNotExist, User.DoesNotExist, Exception):
        pass

    return None


class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope['user'] = await get_user_from_scope(scope)
        return await super().__call__(scope, receive, send)

"""
ASGI config for cisis project (v3.40.0)

HTTP + WebSocket routing через Django Channels.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cisis.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from core.ws_auth import WebSocketAuthMiddleware
from core.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': WebSocketAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
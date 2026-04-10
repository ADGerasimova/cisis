"""
WebSocket URL routing (v3.40.0)
"""

from django.urls import re_path
from core import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/maintenance/', consumers.MaintenanceConsumer.as_asgi()),
]

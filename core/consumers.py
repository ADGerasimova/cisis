"""
WebSocket consumer для чата (v3.40.0 → v3.40.1)

v3.40.1: поддержка файлов в broadcast
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        is_member = await self._check_membership()
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self._update_last_read()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type', 'message')

        if msg_type == 'message':
            text = data.get('text', '').strip()
            if not text:
                return

            message = await self._save_message(text)
            if not message:
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message['id'],
                    'sender_id': self.user.id,
                    'sender_name': self.user.full_name,
                    'text': text,
                    'created_at': message['created_at'],
                    'file': None,
                }
            )

        elif msg_type == 'mark_read':
            await self._update_last_read()

        elif msg_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'sender_id': self.user.id,
                    'sender_name': self.user.full_name,
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message_id': event['message_id'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'text': event.get('text', ''),
            'created_at': event['created_at'],
            'is_own': event['sender_id'] == self.user.id,
            'file': event.get('file'),
        }, ensure_ascii=False))

    async def user_typing(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'sender_name': event['sender_name'],
            }, ensure_ascii=False))

    @database_sync_to_async
    def _check_membership(self):
        from core.models.chat import ChatMember
        return ChatMember.objects.filter(room_id=self.room_id, user=self.user).exists()

    @database_sync_to_async
    def _save_message(self, text):
        from core.models.chat import ChatMessage
        msg = ChatMessage.objects.create(room_id=self.room_id, sender=self.user, text=text)
        return {'id': msg.id, 'created_at': msg.created_at.strftime('%H:%M')}

    @database_sync_to_async
    def _update_last_read(self):
        from core.models.chat import ChatMember
        ChatMember.objects.filter(room_id=self.room_id, user=self.user).update(last_read_at=timezone.now())
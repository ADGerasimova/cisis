"""
Модели чата сотрудников (v3.40.0)

Три типа комнат:
- GENERAL: автоматические чаты (общий + по подразделениям)
- GROUP: создаются пользователями
- DIRECT: личные сообщения (2 участника)
"""

from django.db import models


class RoomType(models.TextChoices):
    GENERAL = 'GENERAL', 'Общий'
    GROUP = 'GROUP', 'Групповой'
    DIRECT = 'DIRECT', 'Личный'


class MemberRole(models.TextChoices):
    OWNER = 'OWNER', 'Создатель'
    MEMBER = 'MEMBER', 'Участник'


class ChatRoom(models.Model):
    room_type = models.CharField(max_length=10, choices=RoomType.choices, default=RoomType.GROUP)
    name = models.CharField(max_length=200, null=True, blank=True)
    laboratory = models.ForeignKey(
        'Laboratory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chat_rooms',
    )
    is_global = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_chat_rooms',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'chat_rooms'
        ordering = ['-created_at']

    def __str__(self):
        return self.name or f'Room #{self.pk}'

    @property
    def display_name(self):
        """Название для отображения (для DIRECT — имя собеседника)."""
        if self.room_type == RoomType.DIRECT:
            return None  # определяется в контексте пользователя
        return self.name or (self.laboratory.name if self.laboratory else f'Чат #{self.pk}')


class ChatMember(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chat_memberships')
    role = models.CharField(max_length=10, choices=MemberRole.choices, default=MemberRole.MEMBER)
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'chat_members'
        unique_together = [('room', 'user')]

    def __str__(self):
        return f'{self.user} in {self.room}'


class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chat_messages')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'chat_messages'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender}: {self.text[:50]}'

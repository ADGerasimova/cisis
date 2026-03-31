"""
Модели чата сотрудников (v3.40.0 → v3.46.0)

Три типа комнат:
- GENERAL: автоматические чаты (общий + по подразделениям)
- GROUP: создаются пользователями
- DIRECT: личные сообщения (2 участника)

v3.40.1: поддержка файлов/изображений в сообщениях
v3.46.0: реакции на сообщения
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
        if self.room_type == RoomType.DIRECT:
            return None
        return self.name or (self.laboratory.name if self.laboratory else f'Чат #{self.pk}')


class ChatMember(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chat_memberships')
    role = models.CharField(max_length=10, choices=MemberRole.choices, default=MemberRole.MEMBER)
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_manual = models.BooleanField(default=False)  # ⭐ v3.41.2: ручное добавление в GENERAL

    class Meta:
        managed = False
        db_table = 'chat_members'
        unique_together = [('room', 'user')]

    def __str__(self):
        return f'{self.user} in {self.room}'


class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chat_messages')
    text = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    # ⭐ v3.40.1: файлы
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    file_type = models.CharField(max_length=50, null=True, blank=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    class Meta:
        managed = False
        db_table = 'chat_messages'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender}: {self.text[:50]}'

    @property
    def is_image(self):
        return self.file_type and self.file_type.startswith('image/')

    @property
    def file_size_display(self):
        if not self.file_size:
            return ''
        if self.file_size < 1024:
            return f'{self.file_size} Б'
        elif self.file_size < 1024 * 1024:
            return f'{self.file_size / 1024:.1f} КБ'
        else:
            return f'{self.file_size / (1024 * 1024):.1f} МБ'


class ChatReadReceipt(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='read_receipts')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chat_read_receipts')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'chat_read_receipts'
        unique_together = [('message', 'user')]


class ChatMessageReaction(models.Model):
    """Реакция (эмодзи) на сообщение чата. v3.46.0"""
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='chat_reactions')
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'chat_message_reactions'
        unique_together = [('message', 'user', 'emoji')]

    def __str__(self):
        return f'{self.user} → {self.emoji} on msg#{self.message_id}'
"""
Модель SharedLink — публичные ссылки для внешнего доступа к файлам/папкам.
Добавить импорт в core/models/__init__.py:
    from core.models.shared_links import SharedLink
"""

import secrets
from django.db import models


def _generate_token():
    return secrets.token_urlsafe(32)


class SharedLink(models.Model):
    token           = models.CharField(max_length=64, unique=True, default=_generate_token)
    file            = models.ForeignKey('File', null=True, blank=True, on_delete=models.CASCADE, related_name='shared_links')
    folder          = models.ForeignKey('PersonalFolder', null=True, blank=True, on_delete=models.CASCADE, related_name='shared_links')
    created_by      = models.ForeignKey('User', on_delete=models.CASCADE, related_name='shared_links')
    label           = models.CharField(max_length=255, blank=True, default='')
    password_hash   = models.CharField(max_length=255, blank=True, default='')
    expires_at      = models.DateTimeField(null=True, blank=True)
    max_downloads   = models.IntegerField(default=0)
    download_count  = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'shared_links'
        ordering = ['-created_at']

    def __str__(self):
        target = self.file.original_name if self.file_id else f'Папка #{self.folder_id}'
        return f'{self.token[:8]}… → {target}'

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_download_limit_reached(self):
        if self.max_downloads == 0:
            return False
        return self.download_count >= self.max_downloads

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired and not self.is_download_limit_reached

    def set_password(self, raw_password):
        import hashlib
        self.password_hash = hashlib.sha256(raw_password.encode()).hexdigest()

    def check_password(self, raw_password):
        if not self.password_hash:
            return True
        import hashlib
        return self.password_hash == hashlib.sha256(raw_password.encode()).hexdigest()

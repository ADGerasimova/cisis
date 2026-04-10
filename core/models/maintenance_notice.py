# core/models/maintenance_notice.py

from django.db import models


class MaintenanceNotice(models.Model):
    """Уведомление о предстоящих технических работах."""

    created_by = models.ForeignKey(
        'User', on_delete=models.CASCADE,
        db_column='created_by_id',
        related_name='maintenance_notices'
    )
    minutes_until = models.IntegerField()
    message = models.TextField(default='', blank=True)
    scheduled_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'maintenance_notices'
        ordering = ['-created_at']

    def __str__(self):
        return f"Техработы через {self.minutes_until} мин ({self.created_at})"
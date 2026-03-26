"""
Модель обратной связи от пользователей.
core/models/feedback.py
"""

from django.db import models


class FeedbackPriority(models.TextChoices):
    LOW      = 'LOW',      'Низкий'
    MEDIUM   = 'MEDIUM',   'Средний'
    HIGH     = 'HIGH',     'Высокий'
    CRITICAL = 'CRITICAL', 'Критический'


class FeedbackStatus(models.TextChoices):
    NEW         = 'NEW',         'Новое'
    IN_PROGRESS = 'IN_PROGRESS', 'В работе'
    FIXED       = 'FIXED',       'Исправлено'
    CLOSED      = 'CLOSED',      'Закрыто'


class Feedback(models.Model):
    author = models.ForeignKey(
        'User', on_delete=models.CASCADE,
        related_name='feedback_items',
        db_column='author_id',
        verbose_name='Автор',
    )
    title = models.CharField(max_length=300, verbose_name='Заголовок')
    description = models.TextField(default='', blank=True, verbose_name='Описание')
    page_url = models.CharField(max_length=500, default='', blank=True, verbose_name='Страница')
    priority = models.CharField(
        max_length=20, default=FeedbackPriority.MEDIUM,
        choices=FeedbackPriority.choices, verbose_name='Приоритет',
    )
    status = models.CharField(
        max_length=20, default=FeedbackStatus.NEW,
        choices=FeedbackStatus.choices, verbose_name='Статус',
    )
    admin_comment = models.TextField(default='', blank=True, verbose_name='Комментарий разработчика')
    resolved_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feedback_resolved',
        db_column='resolved_by_id',
        verbose_name='Кто исправил',
    )
    # Скриншот — хранится через единую файловую систему проекта
    screenshot_file = models.ForeignKey(
        'File', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feedback_screenshots',
        db_column='screenshot_file_id',
        verbose_name='Скриншот',
    )
    status_changed_by = models.ForeignKey( 'User',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='feedback_status_changes',
)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'feedback'
        managed = False
        ordering = ['-created_at']
        verbose_name = 'Обращение'
        verbose_name_plural = 'Обратная связь'

    def __str__(self):
        return f'#{self.pk} — {self.title}'
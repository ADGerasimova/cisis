"""
Модель обратной связи от пользователей.
core/models/feedback.py
v3.58.0: FeedbackComment — комментарии для всех участников, удалён admin_comment.
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
    # admin_comment удалён в v3.58.0 — используйте FeedbackComment
    resolved_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feedback_resolved',
        db_column='resolved_by_id',
        verbose_name='Кто исправил',
    )
    screenshot_file = models.ForeignKey(
        'File', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feedback_screenshots',
        db_column='screenshot_file_id',
        verbose_name='Скриншот',
    )
    status_changed_by = models.ForeignKey(
        'User', null=True, blank=True,
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


class FeedbackFile(models.Model):
    """Файл/скриншот, прикреплённый к обращению. v3.57.0"""
    feedback = models.ForeignKey(
        Feedback, on_delete=models.CASCADE,
        related_name='files',
        db_column='feedback_id',
    )
    file = models.ForeignKey(
        'File', on_delete=models.CASCADE,
        related_name='feedback_files',
        db_column='file_id',
    )
    sort_order = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'feedback_files'
        managed = False
        ordering = ['sort_order', 'id']
        unique_together = [('feedback', 'file')]

    def __str__(self):
        return f'FeedbackFile #{self.pk}: fb={self.feedback_id} file={self.file_id}'


class FeedbackComment(models.Model):
    """
    Комментарий к обращению. v3.58.0
    Писать может и автор обращения, и разработчик (SYSADMIN).
    Непрочитанность определяется отдельно для каждой стороны:
      - is_read_by_author  — автор обращения прочитал этот комментарий
      - is_read_by_admin   — любой SYSADMIN прочитал этот комментарий
    """
    feedback = models.ForeignKey(
        Feedback, on_delete=models.CASCADE,
        related_name='comments',
        db_column='feedback_id',
        verbose_name='Обращение',
    )
    author = models.ForeignKey(
        'User', on_delete=models.CASCADE,
        related_name='feedback_comments',
        db_column='author_id',
        verbose_name='Автор комментария',
    )
    text = models.TextField(verbose_name='Текст')
    is_read_by_author = models.BooleanField(default=False, verbose_name='Прочитано автором')
    is_read_by_admin  = models.BooleanField(default=False, verbose_name='Прочитано администратором')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'feedback_comments'
        managed = False          # таблицу создаём вручную (SQL ниже)
        ordering = ['created_at']
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'

    def __str__(self):
        return f'Comment #{self.pk} → Feedback #{self.feedback_id}'
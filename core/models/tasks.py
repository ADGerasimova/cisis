"""
core/models/tasks.py — Модель задач
v3.52.0 — Добавлены комментарии к задачам

Типы задач:
- TESTING — провести испытание (автосоздание при назначении операторов)
- MANUFACTURING — изготовить образец (автосоздание при manufacturing=True)
- MANUAL — ручная задача (создаётся пользователем)

Задача может быть:
- Индивидуальной (один исполнитель в task_assignees)
- Групповой (несколько исполнителей в task_assignees)
"""

from django.db import models


class TaskType(models.TextChoices):
    TESTING = 'TESTING', 'Провести испытание'
    MANUFACTURING = 'MANUFACTURING', 'Изготовить образец'
    METROLOGY = 'METROLOGY', 'Метрологическое обслуживание'
    MAINTENANCE = 'MAINTENANCE', 'Плановое ТО'
    VERIFY_REGISTRATION = 'VERIFY_REGISTRATION', 'Проверить регистрацию'
    ACCEPT_SAMPLE = 'ACCEPT_SAMPLE', 'Принять образец'
    MANUAL = 'MANUAL', 'Задача'


class TaskStatus(models.TextChoices):
    OPEN = 'OPEN', 'Открыта'
    IN_PROGRESS = 'IN_PROGRESS', 'В работе'
    DONE = 'DONE', 'Выполнена'
    CANCELLED = 'CANCELLED', 'Отменена'


class TaskPriority(models.TextChoices):
    LOW = 'LOW', 'Низкий'
    MEDIUM = 'MEDIUM', 'Средний'
    HIGH = 'HIGH', 'Высокий'


class CompletionMode(models.TextChoices):
    """⭐ v3.51.0: Режим выполнения групповой задачи."""
    ANY = 'ANY', 'Любой исполнитель (один за всех)'
    ALL = 'ALL', 'Каждый исполнитель (все должны выполнить)'


class Task(models.Model):
    """Задача — автоматическая или ручная, индивидуальная или групповая."""

    task_type = models.CharField(
        max_length=30, choices=TaskType.choices,
        verbose_name='Тип задачи',
    )
    title = models.CharField(max_length=500, verbose_name='Заголовок')
    description = models.TextField(blank=True, default='', verbose_name='Описание')

    # Привязка к сущности-источнику (для автозадач)
    entity_type = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Тип сущности',
    )
    entity_id = models.IntegerField(null=True, blank=True, verbose_name='ID сущности')

    # Кто создал (null = система)
    created_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_tasks', verbose_name='Создал',
    )

    # Лаборатория (для фильтрации)
    laboratory = models.ForeignKey(
        'Laboratory', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tasks', verbose_name='Лаборатория',
    )

    # Сроки и приоритет
    deadline = models.DateField(null=True, blank=True, verbose_name='Срок')
    priority = models.CharField(
        max_length=10, choices=TaskPriority.choices,
        default='MEDIUM', verbose_name='Приоритет',
    )

    # Статус
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices,
        default='OPEN', verbose_name='Статус',
    )

    # ⭐ v3.51.0: Режим выполнения
    completion_mode = models.CharField(
        max_length=10, choices=CompletionMode.choices,
        default='ANY', verbose_name='Режим выполнения',
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершена')

    class Meta:
        managed = False
        db_table = 'tasks'
        ordering = ['-created_at']
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if not self.deadline or self.status in ('DONE', 'CANCELLED'):
            return False
        from django.utils import timezone
        return self.deadline < timezone.now().date()

    @property
    def assignee_names(self):
        """Список ФИО исполнителей."""
        return list(
            TaskAssignee.objects.filter(task=self)
            .select_related('user')
            .values_list('user__last_name', 'user__first_name')
        )

    @property
    def comments_count(self):
        """Количество комментариев к задаче."""
        return self.comments.count()


class TaskAssignee(models.Model):
    """M2M: задача ↔ исполнитель."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignees')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='task_assignments')
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Выполнено исполнителем',
    )  # ⭐ v3.51.0

    class Meta:
        managed = False
        db_table = 'task_assignees'
        unique_together = ('task', 'user')
        verbose_name = 'Исполнитель задачи'
        verbose_name_plural = 'Исполнители задач'

    def __str__(self):
        return f'Task #{self.task_id} → User #{self.user_id}'


class TaskView(models.Model):
    """Просмотр задачи исполнителем (read receipt)."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='task_views')
    viewed_at = models.DateTimeField(auto_now_add=True, verbose_name='Просмотрено')

    class Meta:
        managed = False
        db_table = 'task_views'
        unique_together = ('task', 'user')
        verbose_name = 'Просмотр задачи'
        verbose_name_plural = 'Просмотры задач'

    def __str__(self):
        return f'Task #{self.task_id} viewed by User #{self.user_id}'


class TaskComment(models.Model):
    """
    ⭐ v3.52.0: Комментарий к задаче (упрощённая версия).
    
    Комментировать могут:
    - Создатель задачи
    - Все назначенные исполнители
    - Администраторы (SYSADMIN, ADMIN)
    """
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Задача',
    )
    author = models.ForeignKey(
        'User', on_delete=models.CASCADE,
        related_name='task_comments',
        verbose_name='Автор',
    )
    text = models.TextField(verbose_name='Текст комментария')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        managed = False
        db_table = 'task_comments'
        ordering = ['created_at']  # Старые сверху (хронологически)
        verbose_name = 'Комментарий к задаче'
        verbose_name_plural = 'Комментарии к задачам'

    def __str__(self):
        return f'Comment #{self.id} by {self.author_id} on Task #{self.task_id}'

    @property
    def short_text(self):
        """Обрезанный текст для превью."""
        if len(self.text) > 100:
            return self.text[:100] + '...'
        return self.text
"""
core/models/tasks.py — Модель задач
v3.39.0

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


class TaskAssignee(models.Model):
    """M2M: задача ↔ исполнитель."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignees')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='task_assignments')

    class Meta:
        managed = False
        db_table = 'task_assignees'
        unique_together = ('task', 'user')
        verbose_name = 'Исполнитель задачи'
        verbose_name_plural = 'Исполнители задач'

    def __str__(self):
        return f'Task #{self.task_id} → User #{self.user_id}'
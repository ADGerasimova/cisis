# ============================================================
# CISIS v3.14.0 — Модель AuditLog
# Файл: core/models/audit_log.py
# ============================================================

from django.db import models


class AuditLog(models.Model):
    """Единый журнал аудита всех действий в системе."""

    class EntityType(models.TextChoices):
        SAMPLE = 'sample', 'Образец'
        EQUIPMENT = 'equipment', 'Оборудование'
        MEASURING_INSTRUMENT = 'measuring_instrument', 'Средство измерения'
        STANDARD = 'standard', 'Стандарт'
        USER = 'user', 'Пользователь'
        PROTOCOL = 'protocol', 'Протокол'
        # Будущие сущности добавляются сюда:
        # CLIMATE_LOG = 'climate_log', 'Журнал климатики'

    class Action(models.TextChoices):
        CREATE = 'create', 'Создание'
        UPDATE = 'update', 'Изменение'
        STATUS_CHANGE = 'status_change', 'Смена статуса'
        DELETE = 'delete', 'Удаление'
        M2M_ADD = 'm2m_add', 'Добавление связи'
        M2M_REMOVE = 'm2m_remove', 'Удаление связи'
        VIEW = 'view', 'Просмотр'

    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='user_id',
    )
    entity_type = models.CharField(max_length=50, choices=EntityType.choices)
    entity_id = models.IntegerField()
    action = models.CharField(max_length=30, choices=Action.choices)
    field_name = models.CharField(max_length=100, null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    extra_data = models.JSONField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'audit_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.user} → {self.action} {self.entity_type}#{self.entity_id}"
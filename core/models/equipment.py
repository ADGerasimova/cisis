"""
Модели оборудования:
- Equipment (Оборудование)
- EquipmentAccreditationArea (посредник M2M)
- EquipmentMaintenance (История обслуживания)
"""

from django.db import models


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ ДЛЯ ОБОРУДОВАНИЯ
# =============================================================================

class EquipmentType(models.TextChoices):
    MEASURING  = 'MEASURING',  'Средство измерения (СИ)'
    TESTING    = 'TESTING',    'Испытательное оборудование (ИО)'
    AUXILIARY  = 'AUXILIARY',  'Вспомогательное оборудование (ВО)'


class EquipmentOwnership(models.TextChoices):
    OWN       = 'OWN',       'Своё'
    RENTED    = 'RENTED',    'Аренда'
    FREE_USE  = 'FREE_USE',  'Безвозмездное пользование'


class EquipmentStatus(models.TextChoices):
    OPERATIONAL  = 'OPERATIONAL',  'В работе'
    MAINTENANCE  = 'MAINTENANCE',  'На обслуживании'
    CALIBRATION  = 'CALIBRATION',  'На поверке / калибровке'
    RETIRED      = 'RETIRED',      'Выведено из эксплуатации'


class MaintenanceType(models.TextChoices):
    VERIFICATION = 'VERIFICATION', 'Поверка'
    ATTESTATION  = 'ATTESTATION',  'Аттестация'
    REPAIR       = 'REPAIR',       'Ремонт'


# =============================================================================
# ОБОРУДОВАНИЕ
# =============================================================================

class Equipment(models.Model):
    # Основные идентификаторы
    accounting_number   = models.CharField(max_length=50, unique=True)
    equipment_type      = models.CharField(max_length=20, choices=EquipmentType.choices)
    name                = models.CharField(max_length=200)
    inventory_number    = models.CharField(max_length=50, unique=True)

    # Принадлежность
    ownership            = models.CharField(max_length=20, default=EquipmentOwnership.OWN, choices=EquipmentOwnership.choices)
    ownership_doc_number = models.CharField(max_length=200, default='', blank=True)

    # Производитель
    manufacturer          = models.CharField(max_length=200, default='', blank=True)
    year_of_manufacture   = models.IntegerField(null=True, blank=True)
    factory_number        = models.CharField(max_length=100, default='', blank=True)
    state_registry_number = models.CharField(max_length=200, default='', blank=True)

    # Техническая документация
    technical_documentation = models.TextField(default='', blank=True)
    intended_use            = models.CharField(max_length=200, default='', blank=True)
    metrology_doc           = models.TextField(default='', blank=True)
    technical_specs         = models.TextField(default='', blank=True)
    software                = models.TextField(default='', blank=True)
    operating_conditions    = models.TextField(default='', blank=True)

    # Ввод в эксплуатацию
    commissioning_info = models.TextField(default='', blank=True)

    # Состояние и расположение
    condition_on_receipt = models.TextField(default='', blank=True)
    laboratory           = models.ForeignKey(
        'Laboratory',
        on_delete=models.RESTRICT,
        related_name='equipment'
    )
    status               = models.CharField(max_length=20, default=EquipmentStatus.OPERATIONAL, choices=EquipmentStatus.choices)

    # Периодичность МО
    metrology_interval = models.IntegerField(null=True, blank=True)

    # Модификации и примечания
    modifications = models.TextField(default='', blank=True)
    notes         = models.TextField(default='', blank=True)

    # Файлы
    files_path = models.CharField(max_length=500, default='', blank=True)

    # Ответственные (добавлены ALTER TABLE после users)
    responsible_person = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_equipment',
        db_column='responsible_person_id',
    )
    substitute_person = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='substitute_equipment',
        db_column='substitute_person_id',
    )

    # M2M с областями аккредитации
    accreditation_areas = models.ManyToManyField(
        'AccreditationArea',
        through='EquipmentAccreditationArea',
        related_name='equipment',
    )

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'equipment'
        managed  = False
        ordering = ['accounting_number']
        verbose_name        = 'Оборудование'
        verbose_name_plural = 'Оборудование'

    def __str__(self):
        return f'{self.accounting_number} — {self.name}'


# =============================================================================
# ПОСРЕДНИК: ОБОРУДОВАНИЕ ↔ ОБЛАСТЬ АККРЕДИТАЦИИ
# =============================================================================

class EquipmentAccreditationArea(models.Model):
    equipment          = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    accreditation_area = models.ForeignKey('AccreditationArea', on_delete=models.CASCADE)

    class Meta:
        db_table        = 'equipment_accreditation_areas'
        managed         = False
        unique_together = [('equipment', 'accreditation_area')]


# =============================================================================
# ИСТОРИЯ ОБСЛУЖИВАНИЯ ОБОРУДОВАНИЯ
# =============================================================================

class EquipmentMaintenance(models.Model):
    equipment        = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='maintenance_history')
    maintenance_date = models.DateField()
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceType.choices)
    document_name    = models.TextField(default='', blank=True)
    reason           = models.TextField(default='', blank=True)
    description      = models.TextField(default='', blank=True)
    performed_by     = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_performed',
        db_column='performed_by_id',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'equipment_maintenance'
        managed  = False
        ordering = ['-maintenance_date']
        verbose_name        = 'Обслуживание оборудования'
        verbose_name_plural = 'История обслуживания'

    def __str__(self):
        return f'{self.maintenance_date} — {self.get_maintenance_type_display()} — {self.equipment}'

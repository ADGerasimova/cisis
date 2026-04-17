"""
Модели оборудования:
- Room (Помещение)
- BarometerCalibration (Калибровочные таблицы барометров) ⭐ v3.61.0
- Equipment (Оборудование)
- EquipmentAccreditationArea (посредник M2M)
- EquipmentLaboratory (посредник M2M для доп. лабораторий) ⭐ v3.69.0
- EquipmentRoom (посредник M2M для доп. помещений) ⭐ v3.69.0
- EquipmentMaintenance (История обслуживания)
- EquipmentMaintenancePlan (Планы ТО) ⭐ v3.24.0
- EquipmentMaintenanceLog (Журнал ТО) ⭐ v3.24.0
"""

from django.db import models


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ ДЛЯ ОБОРУДОВАНИЯ
# =============================================================================

class EquipmentType(models.TextChoices):
    MEASURING  = 'СИ',  'СИ'
    TESTING    = 'ИО',  'ИО'
    AUXILIARY  = 'ВО',  'ВО'


class EquipmentStatus(models.TextChoices):
    OPERATIONAL  = 'OPERATIONAL',  'В работе'
    MAINTENANCE  = 'MAINTENANCE',  'На обслуживании'
    CALIBRATION  = 'CALIBRATION',  'На поверке / калибровке'
    RETIRED      = 'RETIRED',      'Выведено из эксплуатации'


class MaintenanceType(models.TextChoices):
    VERIFICATION = 'VERIFICATION', 'Поверка'
    ATTESTATION  = 'ATTESTATION',  'Аттестация'
    REPAIR       = 'REPAIR',       'Ремонт'
    MODIFICATION = 'MODIFICATION', 'Модификация'
    CALIBRATION  = 'CALIBRATION',  'Калибровка'
    CONSERVATION = 'CONSERVATION', 'Консервация'


class MaintenanceFrequencyUnit(models.TextChoices):
    DAY   = 'DAY',   'День'
    WEEK  = 'WEEK',  'Неделя'
    MONTH = 'MONTH', 'Месяц'
    YEAR  = 'YEAR',  'Год'


class MaintenanceLogStatus(models.TextChoices):
    COMPLETED = 'COMPLETED', 'Выполнено'
    SKIPPED   = 'SKIPPED',   'Пропущено'
    PARTIAL   = 'PARTIAL',   'Частично'
    OVERDUE   = 'OVERDUE',   'Просрочено'

class VerificationResult(models.TextChoices):
    SUITABLE   = 'SUITABLE',   'Пригоден'
    UNSUITABLE = 'UNSUITABLE', 'Непригоден'


# =============================================================================
# ПОМЕЩЕНИЯ
# =============================================================================

class Room(models.Model):
    number = models.CharField(max_length=50, unique=True, verbose_name='Номер помещения')
    name = models.CharField(max_length=200, default='', blank=True, verbose_name='Название')
    building = models.CharField(max_length=100, default='', blank=True, verbose_name='Корпус')
    floor = models.CharField(max_length=20, default='', blank=True, verbose_name='Этаж')
    height_above_zero = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Высота над нулевым уровнем, м',
        help_text='Для барометрической поправки давления',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rooms'
        managed = False
        ordering = ['number']
        verbose_name = 'Помещение'
        verbose_name_plural = 'Помещения'

    def __str__(self):
        if self.name:
            return f'{self.number} — {self.name}'
        return self.number


# =============================================================================
# КАЛИБРОВКА БАРОМЕТРОВ ⭐ v3.61.0
# =============================================================================

class BarometerCalibration(models.Model):
    """Калибровочная таблица барометра: показание (кПа) → поправка (кПа)."""
    equipment = models.ForeignKey(
        'Equipment', on_delete=models.CASCADE,
        related_name='barometer_calibrations',
        verbose_name='Барометр',
    )
    reading_kpa = models.DecimalField(
        max_digits=7, decimal_places=2,
        verbose_name='Показание шкалы, кПа',
    )
    correction_kpa = models.DecimalField(
        max_digits=7, decimal_places=4,
        verbose_name='Поправка, кПа',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'barometer_calibrations'
        managed = False
        ordering = ['equipment', 'reading_kpa']
        unique_together = [('equipment', 'reading_kpa')]
        verbose_name = 'Калибровка барометра'
        verbose_name_plural = 'Калибровки барометров'

    def __str__(self):
        return f'{self.equipment} | {self.reading_kpa} кПа → {self.correction_kpa:+.4f} кПа'


# =============================================================================
# ОБОРУДОВАНИЕ
# =============================================================================

class Equipment(models.Model):
    # Основные идентификаторы
    accounting_number   = models.CharField(max_length=50)
    equipment_type      = models.CharField(max_length=20, choices=EquipmentType.choices)
    name                = models.CharField(max_length=200)
    inventory_number    = models.CharField(max_length=50)

    # Принадлежность
    ownership            = models.CharField(max_length=200)
    ownership_doc_number = models.CharField(max_length=200, default='', blank=True)

    # Производитель
    manufacturer          = models.CharField(max_length=200, default='', blank=True)
    year_of_manufacture   = models.IntegerField(null=True, blank=True)
    factory_number        = models.CharField(max_length=100, default='', blank=True)
    state_registry_number = models.CharField(max_length=200, default='', blank=True)

    # Техническая документация
    technical_documentation = models.TextField(default='', blank=True)
    intended_use            = models.TextField(default='', blank=True)
    metrology_doc           = models.TextField(default='', blank=True)
    technical_specs         = models.TextField(default='', blank=True)
    software                = models.TextField(default='', blank=True)
    operating_conditions    = models.TextField(default='', blank=True)

    # Ввод в эксплуатацию
    commissioning_info = models.TextField(default='', blank=True)

    # Состояние и расположение
    condition_on_receipt = models.TextField(default='', blank=True)

    # ⭐ v3.69.0: основная лаборатория (primary). Дополнительные — через M2M ниже.
    laboratory           = models.ForeignKey(
        'Laboratory',
        on_delete=models.RESTRICT,
        related_name='equipment',
        verbose_name='Основная лаборатория',
    )

    # ⭐ v3.69.0: Дополнительные лаборатории (совместное использование)
    additional_laboratories = models.ManyToManyField(
        'Laboratory',
        through='EquipmentLaboratory',
        through_fields=('equipment', 'laboratory'),
        related_name='additional_equipment',
        blank=True,
        verbose_name='Дополнительные лаборатории',
    )

    # ⭐ v3.69.0: основное помещение (primary). Дополнительные — через M2M ниже.
    room                 = models.ForeignKey(
        'Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment',
        db_column='room_id',
        verbose_name='Основное помещение',
    )

    # ⭐ v3.69.0: Дополнительные помещения (например, при переездах или мульти-размещении)
    additional_rooms = models.ManyToManyField(
        'Room',
        through='EquipmentRoom',
        through_fields=('equipment', 'room'),
        related_name='additional_equipment',
        blank=True,
        verbose_name='Дополнительные помещения',
    )

    status               = models.CharField(max_length=20, default=EquipmentStatus.OPERATIONAL, choices=EquipmentStatus.choices)

    # Периодичность МО
    metrology_interval = models.IntegerField(null=True, blank=True)

    # ⭐ v3.35.0: Назначение СИ для журнала климата
    is_temp_humidity = models.BooleanField(default=False, verbose_name='СИ: температура и влажность')
    is_pressure      = models.BooleanField(default=False, verbose_name='СИ: атмосферное давление')

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

    # ⭐ v3.69.0: Хелперы для удобного доступа ко всем лабам/помещениям
    @property
    def all_laboratories(self):
        """
        Все лаборатории (основная + дополнительные) как QuerySet.
        Удобно для отображения в UI и для проверок «оборудование X доступно лабе Y».
        """
        from django.db.models import Q
        from core.models import Laboratory
        return Laboratory.objects.filter(
            Q(pk=self.laboratory_id) | Q(additional_equipment=self)
        ).distinct().order_by('code')

    @property
    def all_rooms(self):
        """
        Все помещения (основное + дополнительные) как QuerySet.
        Если основного нет (room_id=NULL) — возвращает только дополнительные.
        """
        from django.db.models import Q
        from core.models import Room
        if not self.room_id:
            return Room.objects.filter(additional_equipment=self).order_by('number')
        return Room.objects.filter(
            Q(pk=self.room_id) | Q(additional_equipment=self)
        ).distinct().order_by('number')


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
# ПОСРЕДНИКИ ДЛЯ ДОП. ЛАБОРАТОРИЙ И ПОМЕЩЕНИЙ ⭐ v3.69.0
# =============================================================================

class EquipmentLaboratory(models.Model):
    """Посредник M2M: Equipment ↔ Laboratory (дополнительные лаборатории)."""
    equipment  = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    laboratory = models.ForeignKey('Laboratory', on_delete=models.CASCADE)

    class Meta:
        db_table        = 'equipment_laboratories'
        managed         = False
        unique_together = [('equipment', 'laboratory')]
        verbose_name        = 'Доп. лаборатория оборудования'
        verbose_name_plural = 'Доп. лаборатории оборудования'

    def __str__(self):
        return f'{self.equipment} @ {self.laboratory}'

    def clean(self):
        """⭐ v3.69.0: Запрещаем дублировать primary laboratory в additional."""
        from django.core.exceptions import ValidationError
        if (self.equipment_id and self.laboratory_id and
                self.equipment.laboratory_id == self.laboratory_id):
            raise ValidationError({
                'laboratory': (
                    f'Эта лаборатория уже указана как основная для оборудования. '
                    f'В дополнительные добавлять её не нужно.'
                )
            })


class EquipmentRoom(models.Model):
    """Посредник M2M: Equipment ↔ Room (дополнительные помещения)."""
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    room      = models.ForeignKey(Room, on_delete=models.CASCADE)

    class Meta:
        db_table        = 'equipment_rooms'
        managed         = False
        unique_together = [('equipment', 'room')]
        verbose_name        = 'Доп. помещение оборудования'
        verbose_name_plural = 'Доп. помещения оборудования'

    def __str__(self):
        return f'{self.equipment} @ {self.room}'

    def clean(self):
        """⭐ v3.69.0: Запрещаем дублировать primary room в additional."""
        from django.core.exceptions import ValidationError
        if (self.equipment_id and self.room_id and
                self.equipment.room_id == self.room_id):
            raise ValidationError({
                'room': (
                    f'Это помещение уже указано как основное для оборудования. '
                    f'В дополнительные добавлять его не нужно.'
                )
            })


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
    certificate_number = models.CharField(max_length=200, default='', blank=True,
                                          verbose_name='Номер свидетельства')
    valid_until = models.DateField(null=True, blank=True,
                                   verbose_name='Действительно до')
    verification_organization = models.CharField(max_length=300, default='', blank=True,
                                                 verbose_name='Организация-поверитель')
    verification_result = models.CharField(max_length=20, default='', blank=True,
                                           choices=VerificationResult.choices,
                                           verbose_name='Результат')
    fgis_arshin_number = models.CharField(max_length=100, default='', blank=True,
                                          verbose_name='Номер в ФГИС Аршин')
    class Meta:
        db_table = 'equipment_maintenance'
        managed  = False
        ordering = ['-maintenance_date']
        verbose_name        = 'Обслуживание оборудования'
        verbose_name_plural = 'История обслуживания'

    def __str__(self):
        return f'{self.maintenance_date} — {self.get_maintenance_type_display()} — {self.equipment}'


# =============================================================================
# ПЛАНЫ ПЛАНОВОГО ТО ⭐ v3.24.0
# =============================================================================

class EquipmentMaintenancePlan(models.Model):
    equipment              = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='maintenance_plans')
    name                   = models.CharField(max_length=300)

    # Периодичность: календарная часть
    frequency_count        = models.IntegerField(null=True, blank=True)
    frequency_unit         = models.CharField(max_length=10, choices=MaintenanceFrequencyUnit.choices, null=True, blank=True)
    frequency_period_value = models.IntegerField(null=True, blank=True)

    # Периодичность: условие
    frequency_condition    = models.TextField(default='', blank=True)
    is_condition_based     = models.BooleanField(default=False)

    # Дополнительно
    next_due_date          = models.DateField(null=True, blank=True)
    is_active              = models.BooleanField(default=True)
    notes                  = models.TextField(default='', blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'equipment_maintenance_plans'
        managed  = False
        ordering = ['equipment', 'name']
        verbose_name        = 'План ТО'
        verbose_name_plural = 'Планы ТО'

    def __str__(self):
        return f'{self.equipment} — {self.name}'

    def frequency_display(self):
        """Человекочитаемое описание периодичности."""
        if self.is_condition_based and not self.frequency_count:
            return self.frequency_condition or 'По условию'
        parts = []
        if self.frequency_count and self.frequency_unit and self.frequency_period_value:
            count = self.frequency_count
            period = self.frequency_period_value

            # Склонение единиц измерения: (1, 2-4, 5+)
            unit_forms = {
                'DAY':   ('день', 'дня', 'дней'),
                'WEEK':  ('неделю', 'недели', 'недель'),
                'MONTH': ('месяц', 'месяца', 'месяцев'),
                'YEAR':  ('год', 'года', 'лет'),
            }
            forms = unit_forms.get(self.frequency_unit, (self.frequency_unit,) * 3)

            def _pluralize(n, form1, form2, form5):
                """Склонение: 1 день, 2 дня, 5 дней"""
                n_abs = abs(n) % 100
                if 11 <= n_abs <= 19:
                    return form5
                last = n_abs % 10
                if last == 1:
                    return form1
                if 2 <= last <= 4:
                    return form2
                return form5

            unit_word = _pluralize(period, *forms)

            raz_word = _pluralize(count, 'раз', 'раза', 'раз')

            if period == 1:
                if count == 1:
                    parts.append(f'раз в {unit_word}')
                else:
                    parts.append(f'{count} {raz_word} в {unit_word}')
            else:
                if count == 1:
                    parts.append(f'раз в {period} {unit_word}')
                else:
                    parts.append(f'{count} {raz_word} в {period} {unit_word}')

        if self.is_condition_based and self.frequency_condition:
            parts.append(f'({self.frequency_condition})')
        return ', '.join(parts) if parts else '—'


# =============================================================================
# ЖУРНАЛ ВЫПОЛНЕНИЯ ТО ⭐ v3.24.0
# =============================================================================

class EquipmentMaintenanceLog(models.Model):
    plan           = models.ForeignKey(EquipmentMaintenancePlan, on_delete=models.CASCADE, related_name='logs')
    performed_date = models.DateField()
    performed_by   = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_logs_performed',
        db_column='performed_by_id',
    )
    verified_by    = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_logs_verified',
        db_column='verified_by_id',
    )
    status         = models.CharField(max_length=20, default=MaintenanceLogStatus.COMPLETED, choices=MaintenanceLogStatus.choices)
    verified_date  = models.DateField(null=True, blank=True)
    notes          = models.TextField(default='', blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    # ⭐ v3.71.0: Отслеживание редактирования записи
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name='Отредактировано')
    edited_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_logs_edited',
        db_column='edited_by_id',
        verbose_name='Кто отредактировал',
    )

    class Meta:
        db_table = 'equipment_maintenance_logs'
        managed  = False
        ordering = ['-performed_date']
        verbose_name        = 'Запись журнала ТО'
        verbose_name_plural = 'Журнал ТО'

    def __str__(self):
        return f'{self.performed_date} — {self.plan} — {self.get_status_display()}'
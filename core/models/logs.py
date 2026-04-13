"""
Журналы логирования различных операций:
- ClimateLog (Журнал климата)
- WeightLog (Журнал взвешивания)
- WorkshopLog (Журнал мастерской)
- TimeLog (Журнал учёта времени)
"""

from django.db import models


# =============================================================================
# ЖУРНАЛ КЛИМАТА
# =============================================================================

class ClimateLog(models.Model):
    date        = models.DateField(verbose_name='Дата')
    time        = models.TimeField(verbose_name='Время')
    room        = models.ForeignKey('Room', on_delete=models.RESTRICT, related_name='climate_logs',
                                    verbose_name='Помещение')
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                      verbose_name='Температура, °C')
    humidity    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                      verbose_name='Относительная влажность, %')
    temp_humidity_equipment = models.ForeignKey(
        'Equipment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='climate_temp_logs', db_column='temp_humidity_equipment_id',
        verbose_name='СИ (температура/влажность)',
    )
    atmospheric_pressure = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True,
                                                verbose_name='Атм. давление итоговое, кПа')
    pressure_raw = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True,
                                        verbose_name='Показание барометра (сырое), кПа')
    pressure_corrected = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True,
                                              verbose_name='Давление с поправками, кПа')
    pressure_manually_edited = models.BooleanField(default=False,
                                                    verbose_name='Давление изменено вручную')
    pressure_equipment = models.ForeignKey(
        'Equipment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='climate_pressure_logs', db_column='pressure_equipment_id',
        verbose_name='СИ (давление)',
    )
    responsible = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='climate_measurements', db_column='responsible_id',
                                    verbose_name='Ответственный')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'climate_logs'
        managed  = False
        ordering = ['-date', '-time']
        verbose_name        = 'Замер климата'
        verbose_name_plural = 'Журнал климата'

    def __str__(self):
        room_str = self.room.number if self.room else '?'
        return f'{self.date} {self.time} — каб. {room_str} — {self.temperature}°C / {self.humidity}%'


# =============================================================================
# ЖУРНАЛ ВЗВЕШИВАНИЯ
# =============================================================================

class WeightLog(models.Model):
    sample      = models.ForeignKey('Sample', on_delete=models.CASCADE, related_name='weight_logs')
    measured_at = models.DateTimeField(auto_now_add=True)
    weight      = models.DecimalField(max_digits=10, decimal_places=4)
    test_type   = models.CharField(max_length=50)
    measured_by = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='weight_measurements', db_column='measured_by_id')
    equipment   = models.ForeignKey('Equipment', on_delete=models.RESTRICT, related_name='weight_logs')
    notes       = models.TextField(default='', blank=True)

    class Meta:
        db_table = 'weight_log'
        managed  = False
        ordering = ['-measured_at']
        verbose_name        = 'Замер массы'
        verbose_name_plural = 'Журнал взвешивания'

    def __str__(self):
        return f'{self.sample} — {self.weight} г — {self.measured_at:%Y-%m-%d}'


# =============================================================================
# ЖУРНАЛ МАСТЕРСКОЙ
# =============================================================================

class WorkshopLog(models.Model):
    sample         = models.ForeignKey('Sample', on_delete=models.CASCADE, related_name='workshop_logs')
    operator       = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='workshop_operations')
    operation_date = models.DateField()
    operation_type = models.CharField(max_length=200)
    equipment      = models.ForeignKey('Equipment', on_delete=models.RESTRICT, related_name='workshop_logs')
    cutting_params = models.TextField(default='', blank=True)
    quantity       = models.IntegerField(default=1)
    quality_check  = models.BooleanField(default=True)
    notes          = models.TextField(default='', blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workshop_log'
        managed  = False
        ordering = ['-operation_date']
        verbose_name        = 'Запись мастерской'
        verbose_name_plural = 'Журнал мастерской'

    def __str__(self):
        return f'{self.operation_date} — {self.sample} — {self.operation_type}'


# =============================================================================
# ЖУРНАЛ УЧЁТА ВРЕМЕНИ
# =============================================================================

class TimeLog(models.Model):
    employee   = models.ForeignKey('User', on_delete=models.CASCADE, related_name='time_logs')
    date       = models.DateField()
    start_time = models.TimeField()
    end_time   = models.TimeField()
    work_type  = models.CharField(max_length=200)
    sample     = models.ForeignKey('Sample', on_delete=models.SET_NULL, null=True, blank=True, related_name='time_logs')
    notes      = models.TextField(default='', blank=True)

    class Meta:
        db_table = 'time_log'
        managed  = False
        ordering = ['-date', 'start_time']
        verbose_name        = 'Запись времени'
        verbose_name_plural = 'Журнал времени'

    def __str__(self):
        return f'{self.date} {self.start_time}–{self.end_time} — {self.employee}'
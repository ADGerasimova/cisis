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
    laboratory  = models.ForeignKey('Laboratory', on_delete=models.RESTRICT, related_name='climate_logs')
    measured_at = models.DateTimeField()
    temperature = models.DecimalField(max_digits=5, decimal_places=1)
    humidity    = models.DecimalField(max_digits=5, decimal_places=1)
    measured_by = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='climate_measurements', db_column='measured_by_id')
    notes       = models.TextField(default='', blank=True)

    class Meta:
        db_table = 'climate_log'
        managed  = False
        ordering = ['-measured_at']
        verbose_name        = 'Замер климата'
        verbose_name_plural = 'Журнал климата'

    def __str__(self):
        return f'{self.measured_at:%Y-%m-%d %H:%M} — {self.laboratory} — {self.temperature}°C / {self.humidity}%'


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

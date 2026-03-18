from django.contrib import admin
from core.models import (
    ClimateLog,
    WeightLog,
    WorkshopLog,
    TimeLog,
)

@admin.register(ClimateLog)
class ClimateLogAdmin(admin.ModelAdmin):
    list_display = ['date', 'time', 'room', 'temperature', 'humidity',
                    'atmospheric_pressure', 'responsible']
    list_filter  = ['room', 'date']
    ordering     = ['-date', '-time']


@admin.register(WeightLog)
class WeightLogAdmin(admin.ModelAdmin):
    list_display = ['sample', 'measured_at', 'weight', 'test_type', 'measured_by']
    ordering     = ['-measured_at']


@admin.register(WorkshopLog)
class WorkshopLogAdmin(admin.ModelAdmin):
    list_display = ['sample', 'operation_date', 'operation_type', 'operator', 'equipment']
    ordering     = ['-operation_date']


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'start_time', 'end_time', 'work_type', 'sample']
    list_filter  = ['employee']
    ordering     = ['-date']
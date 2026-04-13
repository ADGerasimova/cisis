from django.contrib import admin

from core.models import (
    Laboratory,
    Client,
    ClientContact,
    Contract,
    AccreditationArea,
    Standard,
    StandardAccreditationArea,
    Holiday,
    Equipment,
    EquipmentAccreditationArea,
    EquipmentMaintenance,
    StandardLaboratory,        # ⭐ v3.11.2
)
from core.models.equipment import Room
from core.models.equipment import BarometerCalibration  # ⭐ v3.61.0
from core.models.parameters import Parameter, StandardParameter, SampleParameter
from core.models.client_hierarchy import Invoice, Specification


# ═══════════════════════════════════════════════════════════════
# ИНЛАЙНЫ
# ═══════════════════════════════════════════════════════════════

class ClientContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 1


class StandardAccreditationAreaInline(admin.TabularInline):
    model = StandardAccreditationArea
    extra = 1

class StandardLaboratoryInline(admin.TabularInline):
    model = StandardLaboratory
    extra = 1

class EquipmentAccreditationAreaInline(admin.TabularInline):
    model = EquipmentAccreditationArea
    extra = 1


class EquipmentMaintenanceInline(admin.TabularInline):
    model   = EquipmentMaintenance
    extra   = 1
    ordering = ['-maintenance_date']

class BarometerCalibrationInline(admin.TabularInline):
    """⭐ v3.61.0: Калибровочная таблица барометра (показание → поправка, кПа)."""
    model = BarometerCalibration
    extra = 3
    fields = ('reading_kpa', 'correction_kpa')
    ordering = ['reading_kpa']

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('reading_kpa')

class StandardParameterInline(admin.TabularInline):
    model = StandardParameter
    extra = 1
    fields = ('parameter', 'parameter_role', 'is_default', 'unit_override',
              'test_conditions', 'precision', 'display_order')
# ═══════════════════════════════════════════════════════════════
# МОДЕЛИ
# ═══════════════════════════════════════════════════════════════

@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'head', 'is_active']
    list_filter  = ['is_active']
    search_fields = ['name', 'code']


class InvoiceInline(admin.TabularInline):
    model = Invoice
    fk_name = 'client'
    extra = 0
    show_change_link = True
    fields = ['number', 'date', 'status', 'work_cost']
    can_delete = True

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ['name', 'inn', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['name', 'inn']
    inlines       = [ClientContactInline, ContractInline, InvoiceInline]


@admin.register(AccreditationArea)
class AccreditationAreaAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'is_default']
    list_filter  = ['is_active']

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['date', 'name', 'is_working']
    list_filter  = ['is_working']
    ordering     = ['-date']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display  = ['accounting_number', 'name', 'equipment_type', 'laboratory', 'status']
    list_filter   = ['equipment_type', 'status', 'ownership', 'laboratory']
    search_fields = ['accounting_number', 'name', 'inventory_number']
    inlines       = [EquipmentAccreditationAreaInline, EquipmentMaintenanceInline, BarometerCalibrationInline]

@admin.register(Standard)
class StandardAdmin(admin.ModelAdmin):
    list_display  = ['code', 'name', 'test_code', 'test_type', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['code', 'name', 'test_code']
    inlines       = [StandardAccreditationAreaInline, StandardLaboratoryInline]

@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'category', 'is_active', 'display_order')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'name_en')
    ordering = ('display_order', 'name')

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'building', 'floor', 'height_above_zero', 'is_active')
    list_filter = ('is_active', 'building', 'floor')
    search_fields = ('number', 'name')
    list_editable = ('height_above_zero',)
    ordering = ('number',)

class SpecificationInline(admin.TabularInline):
    model = Specification
    extra = 0
    show_change_link = True
    fields = ['spec_type', 'number', 'date', 'work_deadline', 'status']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display  = ['number', 'client', 'date', 'status']
    list_filter   = ['status', 'client']
    search_fields = ['number', 'client__name']
    inlines       = [SpecificationInline]
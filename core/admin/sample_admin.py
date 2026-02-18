from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from datetime import date

from core.models import (
    Sample,
    SampleMeasuringInstrument,
    SampleTestingEquipment,
    SampleOperator,
    JournalColumn,
)
from core.permissions import PermissionChecker

class SampleMeasuringInstrumentInline(admin.TabularInline):
    model = SampleMeasuringInstrument
    extra = 1


class SampleTestingEquipmentInline(admin.TabularInline):
    model = SampleTestingEquipment
    extra = 1


class SampleOperatorInline(admin.TabularInline):
    model = SampleOperator
    extra = 1

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ['sequence_number', 'cipher_link', 'pi_number', 'client', 'laboratory', 'status', 'registration_date']
    list_display_links = ['cipher_link']  # кликабелен только шифр
    search_fields = ['cipher', 'accompanying_doc_number', 'object_id']
    list_filter = ['laboratory', 'status', 'accreditation_area', 'registration_date']

    # Поля только для чтения (автоматические)
    readonly_fields = [
        'sequence_number',
        'cipher',
        'pi_number',
        'test_code',
        'test_type',
        'deadline',
        'created_at',
        'updated_at'
    ]

    fieldsets = (
        ('Автоматические поля (только чтение)', {
            'fields': ('sequence_number', 'cipher', 'registration_date', 'pi_number', 'deadline')
        }),
        ('Регистрация', {
            'fields': (
                'client', 'contract', 'contract_date', 'laboratory',
                'accompanying_doc_number', 'accompanying_doc_full_name',
                'accreditation_area', 'standard', 'test_code', 'test_type',
                'working_days', 'sample_received_date',
                'object_info', 'object_id', 'cutting_direction',
                'test_conditions', 'panel_id', 'material',
                'determined_parameters', 'sample_count',  # ← ДОБАВЛЕНО
                'admin_notes', 'report_type',
                'manufacturing', 'workshop_status',  # ← ИСПРАВЛЕНО
                'uzk_required', 'further_movement',
                'registered_by', 'verified_by', 'verified_at',
                'replacement_protocol_required', 'replacement_pi_number'
            )
        }),
        ('Испытатель', {
            'fields': (
                # Новые DateTime поля
                'conditioning_start_datetime',
                'conditioning_end_datetime',
                'testing_start_datetime',
                'testing_end_datetime',
                # Остальные поля
                'report_prepared_date',
                'report_prepared_by',
                'operator_notes'
            )
        }),
        ('СМК', {
            'fields': (
                'protocol_checked_by',
                'protocol_issued_date',
                'protocol_printed_date',
                'replacement_protocol_issued_date'
            )
        }),
        ('Статусы', {
            'fields': ('status',)
        }),
        ('Файлы', {
            'fields': ('files_path',)
        }),
    )

    inlines = [
        SampleMeasuringInstrumentInline,
        SampleTestingEquipmentInline,
        SampleOperatorInline,
    ]

    def response_add(self, request, obj, post_url_override=None):
        """После сохранения сохраняем данные заказчика для следующего образца"""
        if '_addanother' in request.POST:
            request.session['prefill_sample'] = {
                'registration_date': obj.registration_date.isoformat() if obj.registration_date else None,
                'client': obj.client_id,
                'contract': obj.contract_id,
                'contract_date': obj.contract_date.isoformat() if obj.contract_date else None,
                'laboratory': obj.laboratory_id,
                'accompanying_doc_number': obj.accompanying_doc_number,
                'accompanying_doc_full_name': obj.accompanying_doc_full_name,
                'accreditation_area': obj.accreditation_area_id,
                'standard': obj.standard_id,
                'test_conditions': obj.test_conditions,
                'working_days': obj.working_days,
            }
        return super().response_add(request, obj, post_url_override)

    def get_changeform_initial_data(self, request):
        """Подставляем сохранённые данные при создании нового образца"""
        from datetime import date

        initial = super().get_changeform_initial_data(request)
        prefill = request.session.get('prefill_sample')
        if prefill:
            # Преобразуем даты обратно из строк
            if prefill.get('registration_date'):
                prefill['registration_date'] = date.fromisoformat(prefill['registration_date'])
            if prefill.get('contract_date'):
                prefill['contract_date'] = date.fromisoformat(prefill['contract_date'])

            initial.update(prefill)
            del request.session['prefill_sample']
        return initial

    def has_view_permission(self, request, obj=None):
        """Проверяет право просмотра журнала образцов"""
        if request.user.is_superuser or request.user.role == 'SYSADMIN':
            return True
        return PermissionChecker.has_journal_access(request.user, 'SAMPLES')

    def has_add_permission(self, request):
        """Проверяет право добавления образцов"""
        if request.user.is_superuser or request.user.role == 'SYSADMIN':
            return True
        # Проверяем может ли редактировать хотя бы одно поле
        from core.models import JournalColumn
        columns = JournalColumn.objects.filter(journal__code='SAMPLES')
        for col in columns:
            if PermissionChecker.can_edit(request.user, 'SAMPLES', col.code):  # ← col.code
                return True
        return False

    def has_change_permission(self, request, obj=None):
        """Проверяет право редактирования образцов"""
        return self.has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Право удаления только у SYSADMIN"""
        return request.user.is_superuser or request.user.role == 'SYSADMIN'

    def cipher_link(self, obj):
        """Делаем шифр кликабельной ссылкой"""
        from django.urls import reverse
        from django.utils.html import format_html

        url = reverse('admin:core_sample_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.cipher)

    cipher_link.short_description = 'Шифр'
    cipher_link.admin_order_field = 'cipher'


from django.contrib import admin
from core.models.client_hierarchy import (
    Invoice,
    Specification,
    SpecificationLaboratory,
    ClosingDocumentBatch,
    ClosingBatchAct,
)
from core.models.acts import AcceptanceAct, AcceptanceActLaboratory


# ═══════════════════════════════════════════════════════════════
# ИНЛАЙНЫ
# ═══════════════════════════════════════════════════════════════

class AcceptanceActLaboratoryInline(admin.TabularInline):
    model = AcceptanceActLaboratory
    extra = 0
    fields = ['laboratory', 'completed_date']


class AcceptanceActInlineForSpec(admin.TabularInline):
    model = AcceptanceAct
    fk_name = 'specification'
    extra = 0
    show_change_link = True
    fields = ['doc_number', 'document_name', 'samples_received_date', 'work_status']
    readonly_fields = ['doc_number', 'document_name', 'samples_received_date', 'work_status']
    can_delete = True


class AcceptanceActInlineForInvoice(admin.TabularInline):
    model = AcceptanceAct
    fk_name = 'invoice'
    extra = 0
    show_change_link = True
    fields = ['doc_number', 'document_name', 'samples_received_date', 'work_status']
    readonly_fields = ['doc_number', 'document_name', 'samples_received_date', 'work_status']
    can_delete = True


class SpecificationLaboratoryInline(admin.TabularInline):
    model = SpecificationLaboratory
    extra = 1


class SpecificationInline(admin.TabularInline):
    model = Specification
    fk_name = 'contract'
    extra = 0
    show_change_link = True
    fields = ['spec_type', 'number', 'date', 'work_deadline', 'status']
    can_delete = True


class InvoiceInline(admin.TabularInline):
    model = Invoice
    fk_name = 'client'
    extra = 0
    show_change_link = True
    fields = ['number', 'date', 'status', 'work_cost']
    can_delete = True


class ClosingBatchActInline(admin.TabularInline):
    model = ClosingBatchAct
    extra = 1


# ═══════════════════════════════════════════════════════════════
# АКТЫ ПРИЁМА-ПЕРЕДАЧИ
# ═══════════════════════════════════════════════════════════════

@admin.register(AcceptanceAct)
class AcceptanceActAdmin(admin.ModelAdmin):
    list_display  = ['doc_number', 'document_name', 'get_client', 'get_parent',
                     'samples_received_date', 'work_deadline', 'work_status', 'closing_status']
    list_filter   = ['work_status', 'closing_status', 'has_subcontract']
    search_fields = ['doc_number', 'document_name',
                     'contract__number', 'contract__client__name',
                     'invoice__number', 'invoice__client__name']
    raw_id_fields = ['contract', 'specification', 'invoice']
    inlines       = [AcceptanceActLaboratoryInline]

    fieldsets = (
        ('Связи', {
            'fields': ('contract', 'specification', 'invoice')
        }),
        ('Входная часть', {
            'fields': ('doc_number', 'document_name', 'document_status',
                       'samples_received_date', 'work_deadline',
                       'payment_terms', 'has_subcontract', 'comment')
        }),
        ('Финансы', {
            'fields': ('services_count', 'work_cost', 'payment_invoice',
                       'advance_date', 'full_payment_date'),
            'classes': ('collapse',),
        }),
        ('Закрывающие документы', {
            'fields': ('completion_act', 'invoice_number', 'document_flow',
                       'closing_status', 'work_status', 'sending_method'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Заказчик')
    def get_client(self, obj):
        c = obj.client
        return c.name if c else '—'

    @admin.display(description='Договор / Счёт')
    def get_parent(self, obj):
        return obj.parent_label


# ═══════════════════════════════════════════════════════════════
# СПЕЦИФИКАЦИИ
# ═══════════════════════════════════════════════════════════════

@admin.register(Specification)
class SpecificationAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'spec_type', 'contract', 'work_deadline', 'status', 'work_cost']
    list_filter   = ['spec_type', 'status']
    search_fields = ['number', 'contract__number', 'contract__client__name']
    raw_id_fields = ['contract']
    inlines       = [SpecificationLaboratoryInline, AcceptanceActInlineForSpec]

    fieldsets = (
        ('Реквизиты', {
            'fields': ('contract', 'spec_type', 'number', 'date', 'work_deadline', 'status', 'notes')
        }),
        ('Финансы', {
            'fields': ('services_count', 'work_cost', 'payment_terms',
                       'payment_invoice', 'advance_date', 'full_payment_date'),
            'classes': ('collapse',),
        }),
        ('Закрывающие документы', {
            'fields': ('completion_act', 'invoice_number', 'document_flow',
                       'closing_status', 'sending_method'),
            'classes': ('collapse',),
        }),
    )


# ═══════════════════════════════════════════════════════════════
# СЧЕТА
# ═══════════════════════════════════════════════════════════════

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ['number', 'date', 'client', 'status', 'work_cost']
    list_filter   = ['status']
    search_fields = ['number', 'client__name']
    raw_id_fields = ['client']
    inlines       = [AcceptanceActInlineForInvoice]

    fieldsets = (
        ('Реквизиты', {
            'fields': ('client', 'number', 'date', 'status', 'notes')
        }),
        ('Финансы', {
            'fields': ('services_count', 'work_cost', 'payment_terms',
                       'payment_invoice', 'advance_date', 'full_payment_date'),
            'classes': ('collapse',),
        }),
        ('Закрывающие документы', {
            'fields': ('completion_act', 'invoice_number', 'document_flow',
                       'closing_status', 'sending_method'),
            'classes': ('collapse',),
        }),
    )


# ═══════════════════════════════════════════════════════════════
# БАТЧИ ЗАКРЫВАЮЩИХ ДОКУМЕНТОВ
# ═══════════════════════════════════════════════════════════════

@admin.register(ClosingDocumentBatch)
class ClosingDocumentBatchAdmin(admin.ModelAdmin):
    list_display  = ['batch_number', 'work_cost', 'closing_status', 'created_at']
    search_fields = ['batch_number', 'completion_act']
    inlines       = [ClosingBatchActInline]
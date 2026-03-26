"""
CISIS v3.37.0 — Модели расширенной иерархии заказчиков

Файл: core/models/client_hierarchy.py

Модели:
- Invoice              — счёт (работа без договора)
- Specification        — спецификация / ТЗ (к договору)
- SpecificationLaboratory — M2M спецификация ↔ лаборатория
- ClosingDocumentBatch — массовые закрывающие документы
- ClosingBatchAct      — M2M батч ↔ акт ПП
"""

from django.db import models


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================================================

class SpecificationType(models.TextChoices):
    SPEC = 'SPEC', 'Спецификация'
    TZ   = 'TZ',   'Техническое задание'


class InvoiceStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Активен'
    CLOSED = 'CLOSED', 'Закрыт'


# =============================================================================
# 1. СЧЕТА (работа без договора)
# =============================================================================

class Invoice(models.Model):
    """Счёт — верхний уровень при работе без договора."""

    client = models.ForeignKey(
        'Client', on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name='Заказчик'
    )

    # Реквизиты
    number = models.CharField(max_length=100, verbose_name='Номер счёта')
    date   = models.DateField(verbose_name='Дата')
    notes  = models.TextField(default='', blank=True, verbose_name='Примечания')

    # Финансы (наследуются актами ПП)
    services_count    = models.IntegerField(null=True, blank=True, verbose_name='Количество услуг')
    work_cost         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Стоимость работ')
    payment_terms     = models.CharField(max_length=30, default='', blank=True, verbose_name='Условия оплаты')
    payment_invoice   = models.CharField(max_length=200, default='', blank=True, verbose_name='Счёт на оплату')
    advance_date      = models.DateField(null=True, blank=True, verbose_name='Дата аванса')
    full_payment_date = models.DateField(null=True, blank=True, verbose_name='Дата полной оплаты')

    # Закрывающие документы (наследуются актами ПП)
    completion_act  = models.CharField(max_length=200, default='', blank=True, verbose_name='Акт выполненных работ')
    invoice_number  = models.CharField(max_length=200, default='', blank=True, verbose_name='Счёт-фактура')
    document_flow   = models.CharField(max_length=20, default='', blank=True, verbose_name='Документооборот')
    closing_status  = models.CharField(max_length=30, default='', blank=True, verbose_name='Статус закрывающих документов')
    sending_method  = models.CharField(max_length=30, default='', blank=True, verbose_name='Способ отправки')

    # Метаданные
    status     = models.CharField(max_length=20, default=InvoiceStatus.ACTIVE, choices=InvoiceStatus.choices, verbose_name='Статус')
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_invoices', db_column='created_by_id', verbose_name='Создал')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'invoices'
        managed         = False
        unique_together = [('client', 'number')]
        ordering        = ['-date']
        verbose_name        = 'Счёт'
        verbose_name_plural = 'Счета'

    def __str__(self):
        return f'Счёт № {self.number} ({self.client.name})'


# =============================================================================
# 2. СПЕЦИФИКАЦИИ / ТЗ
# =============================================================================

class Specification(models.Model):
    """Спецификация или ТЗ — второй уровень к договору."""

    contract = models.ForeignKey(
        'Contract', on_delete=models.CASCADE,
        related_name='specifications',
        verbose_name='Договор'
    )

    # Тип
    spec_type = models.CharField(
        max_length=20,
        default=SpecificationType.SPEC,
        choices=SpecificationType.choices,
        verbose_name='Тип'
    )

    # Реквизиты
    number        = models.CharField(max_length=100, default='', blank=True, verbose_name='Номер')
    date          = models.DateField(null=True, blank=True, verbose_name='Дата')
    work_deadline = models.DateField(null=True, blank=True, verbose_name='Срок завершения работ')
    notes         = models.TextField(default='', blank=True, verbose_name='Примечания')

    # Финансы (наследуются актами ПП)
    services_count    = models.IntegerField(null=True, blank=True, verbose_name='Количество услуг')
    work_cost         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Стоимость работ')
    payment_terms     = models.CharField(max_length=30, default='', blank=True, verbose_name='Условия оплаты')
    payment_invoice   = models.CharField(max_length=200, default='', blank=True, verbose_name='Счёт на оплату')
    advance_date      = models.DateField(null=True, blank=True, verbose_name='Дата аванса')
    full_payment_date = models.DateField(null=True, blank=True, verbose_name='Дата полной оплаты')

    # Закрывающие документы (наследуются актами ПП)
    completion_act  = models.CharField(max_length=200, default='', blank=True, verbose_name='Акт выполненных работ')
    invoice_number  = models.CharField(max_length=200, default='', blank=True, verbose_name='Счёт-фактура')
    document_flow   = models.CharField(max_length=20, default='', blank=True, verbose_name='Документооборот')
    closing_status  = models.CharField(max_length=30, default='', blank=True, verbose_name='Статус закрывающих документов')
    sending_method  = models.CharField(max_length=30, default='', blank=True, verbose_name='Способ отправки')

    # Лаборатории (M2M)
    laboratories = models.ManyToManyField(
        'Laboratory',
        through='SpecificationLaboratory',
        related_name='specifications',
        verbose_name='Лаборатории'
    )

    # Метаданные
    status     = models.CharField(max_length=20, default='ACTIVE', verbose_name='Статус')
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_specifications', db_column='created_by_id', verbose_name='Создал')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'specifications'
        managed         = False
        unique_together = [('contract', 'number')]
        ordering        = ['-date']
        verbose_name        = 'Спецификация'
        verbose_name_plural = 'Спецификации'

    def __str__(self):
        type_label = 'ТЗ' if self.spec_type == 'TZ' else 'Спец.'
        return f'{type_label} {self.number} ({self.contract.number})'


# =============================================================================
# 3. СПЕЦИФИКАЦИЯ ↔ ЛАБОРАТОРИИ (M2M)
# =============================================================================

class SpecificationLaboratory(models.Model):
    specification = models.ForeignKey(Specification, on_delete=models.CASCADE)
    laboratory    = models.ForeignKey('Laboratory', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'specification_laboratories'
        managed         = False
        unique_together = [('specification', 'laboratory')]
        verbose_name        = 'Лаборатория спецификации'
        verbose_name_plural = 'Лаборатории спецификаций'


# =============================================================================
# 4. МАССОВЫЕ ЗАКРЫВАЮЩИЕ ДОКУМЕНТЫ
# =============================================================================

class ClosingDocumentBatch(models.Model):
    """Группировка нескольких актов ПП для общих закрывающих документов."""

    batch_number   = models.CharField(max_length=200, default='', blank=True, verbose_name='Номер')
    completion_act = models.CharField(max_length=200, default='', blank=True, verbose_name='Акт выполненных работ')
    invoice_number = models.CharField(max_length=200, default='', blank=True, verbose_name='Счёт-фактура')
    document_flow  = models.CharField(max_length=20, default='', blank=True, verbose_name='Документооборот')
    closing_status = models.CharField(max_length=30, default='', blank=True, verbose_name='Статус закрывающих документов')
    sending_method = models.CharField(max_length=30, default='', blank=True, verbose_name='Способ отправки')
    notes          = models.TextField(default='', blank=True, verbose_name='Примечания')

    # Финансы
    work_cost    = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Стоимость работ')
    payment_date = models.DateField(null=True, blank=True, verbose_name='Дата оплаты')

    # M2M акты
    acts = models.ManyToManyField(
        'AcceptanceAct',
        through='ClosingBatchAct',
        related_name='closing_batches',
        verbose_name='Акты ПП'
    )

    # Метаданные
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_closing_batches', db_column='created_by_id', verbose_name='Создал')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'closing_document_batches'
        managed  = False
        ordering = ['-created_at']
        verbose_name        = 'Батч закрывающих документов'
        verbose_name_plural = 'Батчи закрывающих документов'

    def __str__(self):
        return f'Батч {self.batch_number or self.id}'


# =============================================================================
# 5. БАТЧ ↔ АКТЫ ПП (M2M)
# =============================================================================

class ClosingBatchAct(models.Model):
    batch = models.ForeignKey(ClosingDocumentBatch, on_delete=models.CASCADE)
    act   = models.ForeignKey('AcceptanceAct', on_delete=models.CASCADE)

    class Meta:
        db_table        = 'closing_batch_acts'
        managed         = False
        unique_together = [('batch', 'act')]

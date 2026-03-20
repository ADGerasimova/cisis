"""
CISIS v3.19.0 — Модели актов приёма-передачи

Добавить в core/models/base.py (или создать отдельный файл core/models/acts.py)

Модели:
- AcceptanceAct — акт приёма-передачи (входящий документ)
- AcceptanceActLaboratory — M2M: акт ↔ лаборатория (с датой завершения)
"""

from django.db import models


# =============================================================================
# АКТ ПРИЁМА-ПЕРЕДАЧИ
# =============================================================================

class AcceptanceAct(models.Model):
    """Акт приёма-передачи (входящий документ от заказчика)"""

    # --- Связи ---
    contract = models.ForeignKey(
        'Contract', on_delete=models.RESTRICT,
        related_name='acceptance_acts',
        verbose_name='Договор'
    )
    created_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_acts',
        db_column='created_by_id',
        verbose_name='Создал'
    )
    # ─────────────────────────────────────────────────────────────
    # НОВЫЕ ПОЛЯ (добавить после contract / created_by)
    # ─────────────────────────────────────────────────────────────

    # v3.37.0: Спецификация (для актов по договору)
    specification = models.ForeignKey(
        'Specification', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acceptance_acts',
        db_column='specification_id',
        verbose_name='Спецификация / ТЗ'
    )

    # v3.37.0: Счёт (альтернатива договору)
    invoice = models.ForeignKey(
        'Invoice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acceptance_acts',
        db_column='invoice_id',
        verbose_name='Счёт'
    )

    # ─────────────────────────────────────────────────────────────
    # ИЗМЕНЕНИЕ: contract становится nullable
    # ─────────────────────────────────────────────────────────────

    contract = models.ForeignKey(
        'Contract', on_delete=models.RESTRICT,
        null=True, blank=True,  # ← было: без null/blank
        related_name='acceptance_acts',
        verbose_name='Договор'
    )

    # ─────────────────────────────────────────────────────────────
    # НОВЫЕ СВОЙСТВА (добавить в класс AcceptanceAct)
    # ─────────────────────────────────────────────────────────────

    @property
    def finance_source(self):
        """
        Определяет источник финансовых данных.
        Приоритет: спецификация → счёт → сам акт.
        Возвращает объект, из которого читать финансы.
        """
        if self.specification_id:
            return self.specification
        if self.invoice_id:
            return self.invoice
        return self

    @property
    def finance_source_label(self):
        """Текстовая метка источника финансов для UI."""
        if self.specification_id:
            spec = self.specification
            type_label = 'ТЗ' if spec.spec_type == 'TZ' else 'Спецификация'
            return f'{type_label} {spec.number}'
        if self.invoice_id:
            return f'Счёт {self.invoice.number}'
        return 'Акт ПП (собственные)'

    @property
    def has_inherited_finance(self):
        """True если финансы наследуются от спецификации или счёта."""
        return bool(self.specification_id or self.invoice_id)

    @property
    def effective_work_cost(self):
        """Стоимость работ из актуального источника."""
        return self.finance_source.work_cost

    @property
    def effective_payment_terms(self):
        """Условия оплаты из актуального источника."""
        return self.finance_source.payment_terms

    @property
    def effective_closing_status(self):
        """Статус закрывающих документов из актуального источника."""
        return self.finance_source.closing_status

    @property
    def parent_label(self):
        """Метка верхнего уровня: 'Договор № X' или 'Счёт № X'."""
        if self.contract_id:
            return f'Договор № {self.contract.number}'
        if self.invoice_id:
            return f'Счёт № {self.invoice.number}'
        return '—'

    @property
    def client(self):
        """Заказчик (через договор ИЛИ через счёт)."""
        if self.contract_id:
            return self.contract.client
        if self.invoice_id:
            return self.invoice.client
        return None
    # --- Входная часть ---
    doc_number = models.CharField(
        max_length=100, default='', blank=True,
        verbose_name='Код документа (латиница)',
        help_text='Короткий код: M1092. Используется для шифра образца'
    )
    document_name = models.CharField(
        max_length=500, default='', blank=True,
        verbose_name='Наименование входящего документа',
        help_text='Например: Сопроводительное письмо № М1092 от 30.01.2026'
    )
    document_status = models.CharField(
        max_length=30, default='', blank=True,
        verbose_name='Статус входящих документов'
    )
    samples_received_date = models.DateField(
        null=True, blank=True,
        verbose_name='Дата получения образцов'
    )
    work_deadline = models.DateField(
        null=True, blank=True,
        verbose_name='Срок завершения работ'
    )
    payment_terms = models.CharField(
        max_length=30, default='', blank=True,
        verbose_name='Условия оплаты'
    )
    has_subcontract = models.BooleanField(
        default=False,
        verbose_name='Субподряд'
    )
    comment = models.TextField(
        default='', blank=True,
        verbose_name='Комментарии'
    )

    # --- Финансы ---
    services_count = models.IntegerField(
        null=True, blank=True,
        verbose_name='Количество услуг'
    )
    work_cost = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Стоимость работ'
    )
    payment_invoice = models.CharField(
        max_length=200, default='', blank=True,
        verbose_name='Счёт на оплату'
    )
    advance_date = models.DateField(
        null=True, blank=True,
        verbose_name='Дата аванса'
    )
    full_payment_date = models.DateField(
        null=True, blank=True,
        verbose_name='Дата полной оплаты'
    )

    # --- Закрывающие документы ---
    completion_act = models.CharField(
        max_length=200, default='', blank=True,
        verbose_name='Акт выполненных работ'
    )
    invoice_number = models.CharField(
        max_length=200, default='', blank=True,
        verbose_name='Счёт-фактура'
    )
    document_flow = models.CharField(
        max_length=20, default='', blank=True,
        verbose_name='Документооборот'
    )
    closing_status = models.CharField(
        max_length=30, default='', blank=True,
        verbose_name='Статус закрывающих документов'
    )
    work_status = models.CharField(
        max_length=20, default='IN_PROGRESS',
        verbose_name='Статус работ'
    )
    sending_method = models.CharField(
        max_length=30, default='', blank=True,
        verbose_name='Способ отправки'
    )

    # --- Метаданные ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- M2M лаборатории ---
    laboratories = models.ManyToManyField(
        'Laboratory',
        through='AcceptanceActLaboratory',
        related_name='acceptance_acts',
        verbose_name='Лаборатории'
    )

    class Meta:
        db_table = 'acceptance_acts'
        managed = False
        ordering = ['-created_at']
        verbose_name = 'Акт приёма-передачи'
        verbose_name_plural = 'Акты приёма-передачи'

    def __str__(self):
        client_name = self.contract.client.name if self.contract_id else '—'
        return f'{self.document_name or "Акт"} ({client_name})'

    # ─────────────────────────────────────────────────────────
    # Вычисляемые свойства
    # ─────────────────────────────────────────────────────────

    @property
    def client(self):
        """Заказчик (через договор)"""
        return self.contract.client if self.contract_id else None

    @property
    def progress(self):
        """
        Прогресс по образцам: (completed, cancelled, total)
        completed = COMPLETED + PROTOCOL_ISSUED + REPLACEMENT_PROTOCOL
        """
        from core.models.sample import Sample
        samples = Sample.objects.filter(acceptance_act_id=self.id)
        total = samples.count()
        if total == 0:
            return {'completed': 0, 'cancelled': 0, 'total': 0}

        completed = samples.filter(
            status__in=['COMPLETED', 'PROTOCOL_ISSUED', 'REPLACEMENT_PROTOCOL']
        ).count()
        cancelled = samples.filter(status='CANCELLED').count()

        return {
            'completed': completed,
            'cancelled': cancelled,
            'total': total,
        }

    @property
    def progress_display(self):
        """Строка прогресса: '7 ✅ 1 ❌ / 10'"""
        p = self.progress
        if p['total'] == 0:
            return '—'
        parts = [f"{p['completed']} ✅"]
        if p['cancelled'] > 0:
            parts.append(f"{p['cancelled']} ❌")
        parts.append(f"/ {p['total']}")
        return ' '.join(parts)

    @property
    def is_all_done(self):
        """Все образцы в финальном статусе"""
        p = self.progress
        return p['total'] > 0 and (p['completed'] + p['cancelled']) == p['total']

    @property
    def deadline_check(self):
        """
        Проверка на срок: разница между сегодня и дедлайном.
        Возвращает dict: {days: int, status: 'overdue'|'warning'|'ok'|'unknown'|'closed'}
        """
        from datetime import date

        if self.work_status in ('CLOSED', 'CANCELLED'):
            return {'days': None, 'status': 'closed'}

        if not self.work_deadline:
            return {'days': None, 'status': 'unknown'}

        delta = (self.work_deadline - date.today()).days

        if delta < 0:
            return {'days': abs(delta), 'status': 'overdue'}
        elif delta <= 7:
            return {'days': delta, 'status': 'warning'}
        else:
            return {'days': delta, 'status': 'ok'}


# =============================================================================
# M2M: АКТ ↔ ЛАБОРАТОРИЯ
# =============================================================================

class AcceptanceActLaboratory(models.Model):
    """Лаборатория, задействованная в акте (с автоматической датой завершения)"""

    act = models.ForeignKey(
        AcceptanceAct, on_delete=models.CASCADE,
        related_name='act_laboratories',
        verbose_name='Акт'
    )
    laboratory = models.ForeignKey(
        'Laboratory', on_delete=models.RESTRICT,
        related_name='act_entries',
        verbose_name='Лаборатория'
    )
    completed_date = models.DateField(
        null=True, blank=True,
        verbose_name='Дата завершения'
    )

    class Meta:
        db_table = 'acceptance_act_laboratories'
        managed = False
        unique_together = [('act', 'laboratory')]
        verbose_name = 'Лаборатория акта'
        verbose_name_plural = 'Лаборатории акта'

    def __str__(self):
        return f'{self.act_id} ↔ {self.laboratory.code_display}'

    def compute_completed_date(self):
        """
        Вычисляет дату завершения для этой лаборатории по акту.
        Возвращает дату или None если ещё не все образцы закрыты.
        """
        from core.models.sample import Sample

        FINAL_STATUSES = ['COMPLETED', 'PROTOCOL_ISSUED', 'REPLACEMENT_PROTOCOL', 'CANCELLED']
        DONE_STATUSES = ['COMPLETED', 'PROTOCOL_ISSUED', 'REPLACEMENT_PROTOCOL']

        samples = Sample.objects.filter(
            acceptance_act_id=self.act_id,
            laboratory_id=self.laboratory_id,
        )

        total = samples.count()
        if total == 0:
            return None

        final_count = samples.filter(status__in=FINAL_STATUSES).count()
        if final_count < total:
            return None  # ещё не все закрыты

        # Все закрыты — берём дату последнего протокола среди не-CANCELLED
        done_samples = samples.filter(status__in=DONE_STATUSES)
        if not done_samples.exists():
            return None  # все отменены — дату не ставим

        # Берём max(protocol_issued_date) среди завершённых
        max_date = done_samples.aggregate(
            max_date=models.Max('protocol_issued_date')
        )['max_date']

        return max_date
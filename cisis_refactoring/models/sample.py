"""
Модели для работы с образцами:
- Sample (Образец) - основная модель
- SampleMeasuringInstrument (посредник M2M)
- SampleTestingEquipment (посредник M2M)
- SampleOperator (посредник M2M)
"""

from django.db import models
from .base import validate_latin_only


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ ДЛЯ ОБРАЗЦОВ
# =============================================================================

class SampleStatus(models.TextChoices):
    # Регистрация
    PENDING_VERIFICATION = 'PENDING_VERIFICATION', 'Ждёт проверки регистрации'
    REGISTERED = 'REGISTERED', 'Зарегистрирован'
    CANCELLED = 'CANCELLED', 'Отменён'

    # Испытания
    CONDITIONING = 'CONDITIONING', 'Кондиционирование'
    READY_FOR_TEST = 'READY_FOR_TEST', 'Ждёт испытания'
    IN_TESTING = 'IN_TESTING', 'На испытании'
    TESTED = 'TESTED', 'Испытан'
    DRAFT_READY = 'DRAFT_READY', 'Черновик готов'
    RESULTS_UPLOADED = 'RESULTS_UPLOADED', 'Результаты выложены'

    # СМК
    PROTOCOL_ISSUED = 'PROTOCOL_ISSUED', 'Протокол готов'
    COMPLETED = 'COMPLETED', 'Готово'

    # Замещающий протокол (НОВЫЙ!)
    REPLACEMENT_PROTOCOL = 'REPLACEMENT_PROTOCOL', 'Замещающий протокол'


class ReportType(models.TextChoices):
    PROTOCOL = 'PROTOCOL', 'Протокол'
    REPORT   = 'REPORT',   'Отчёт'
    NONE     = 'NONE',     'Без отчётности'


class ManufacturingStatus(models.TextChoices):
    NOT_REQUIRED = 'NOT_REQUIRED', 'Не требуется'
    REQUIRED     = 'REQUIRED',     'Требуется'
    COMPLETED    = 'COMPLETED',    'Выполнено'


# =============================================================================
# ОБРАЗЕЦ (ГЛАВНАЯ МОДЕЛЬ)
# =============================================================================

class Sample(models.Model):
    # ═══════════════════════════════════════════════════════════════
    # АВТОМАТИЧЕСКИЕ ПОЛЯ
    # ═══════════════════════════════════════════════════════════════
    sequence_number   = models.IntegerField(unique=True, verbose_name='Порядковый номер')
    cipher            = models.CharField(max_length=500, unique=True, verbose_name='Шифр')
    registration_date = models.DateField(verbose_name='Дата регистрации')

    # ═══════════════════════════════════════════════════════════════
    # БЛОК «РЕГИСТРАЦИЯ»
    # ═══════════════════════════════════════════════════════════════
    client                         = models.ForeignKey('Client', on_delete=models.RESTRICT, related_name='samples', verbose_name='Заказчик')
    contract                       = models.ForeignKey('Contract', on_delete=models.RESTRICT, null=True, blank=True, related_name='samples', verbose_name='Договор')
    contract_date                  = models.DateField(null=True, blank=True, verbose_name='Дата договора')
    laboratory                     = models.ForeignKey('Laboratory', on_delete=models.RESTRICT, related_name='samples', verbose_name='Лаборатория')
    accompanying_doc_number        = models.CharField(max_length=100, verbose_name='Номер сопроводительного документа', validators=[validate_latin_only], help_text='Только латиница')
    accompanying_doc_full_name     = models.TextField(verbose_name='Полное наименование сопроводительного документа')
    accreditation_area             = models.ForeignKey('AccreditationArea', on_delete=models.RESTRICT, related_name='samples', verbose_name='Область аккредитации')
    standard                       = models.ForeignKey('Standard', on_delete=models.RESTRICT, related_name='samples', verbose_name='Стандарт')
    test_code                      = models.CharField(max_length=20, default='', blank=True, verbose_name='Код испытания')
    test_type                      = models.CharField(max_length=200, default='', blank=True, verbose_name='Вид испытания')
    working_days                   = models.IntegerField(verbose_name='Рабочие дни')
    sample_received_date           = models.DateField(verbose_name='Дата поступления образца')
    object_info                    = models.TextField(default='', blank=True, verbose_name='Информация об объекте')
    object_id                      = models.CharField(max_length=200, default='', blank=True, verbose_name='ID объекта испытаний', validators=[validate_latin_only], help_text='Только латиница')
    cutting_direction              = models.CharField(max_length=200, default='', blank=True, verbose_name='Направление вырезки')
    test_conditions                = models.CharField(max_length=100, default='', blank=True, verbose_name='Условия испытания', validators=[validate_latin_only], help_text='Только латиница (например: RTD, CTW80C). Только для МИ')
    panel_id                       = models.CharField(max_length=200, default='', blank=True, verbose_name='Идентификация панели')
    material                       = models.CharField(max_length=200, default='', blank=True, verbose_name='Материал')
    preparation_required           = models.BooleanField(default=False, verbose_name='Требуется изготовление')
    determined_parameters          = models.TextField(verbose_name='Определяемые параметры')
    admin_notes                    = models.TextField(default='', blank=True, verbose_name='Примечания администратора')
    deadline                       = models.DateField(verbose_name='Срок выполнения')
    report_type                    = models.CharField(max_length=20, default=ReportType.PROTOCOL, choices=ReportType.choices, verbose_name='Тип отчёта')
    pi_number                      = models.CharField(max_length=200, default='', blank=True, verbose_name='Номер ПИ')
    manufacturing                  = models.CharField(max_length=20, default=ManufacturingStatus.NOT_REQUIRED, choices=ManufacturingStatus.choices, verbose_name='Изготовление')
    manufacturing_date             = models.DateField(null=True, blank=True, verbose_name='Дата изготовления')
    uzk_required                   = models.BooleanField(default=False, verbose_name='Требуется УЗК')
    further_movement               = models.CharField(max_length=200, default='', blank=True, verbose_name='Дальнейшее движение')
    
    # Система двойной проверки регистрации
    registered_by                  = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='registered_samples', db_column='registered_by_id', verbose_name='Зарегистрировал (первый админ)')
    verified_by                    = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_samples', db_column='verified_by')
    verified_at                    = models.DateTimeField(null=True, blank=True, verbose_name='Дата проверки')
    
    # Система замещающих протоколов
    replacement_protocol_required  = models.BooleanField(default=False, verbose_name='Требуется протокол-заменитель')
    replacement_pi_number          = models.CharField(max_length=200, default='', blank=True, verbose_name='Номер ПИ-заменителя', editable=False)

    # ═══════════════════════════════════════════════════════════════
    # БЛОК «ИСПЫТАТЕЛЬ»
    # ═══════════════════════════════════════════════════════════════
    test_date            = models.DateField(null=True, blank=True, verbose_name='Дата испытания')
    report_prepared_date = models.DateField(null=True, blank=True, verbose_name='Дата подготовки отчёта')
    report_prepared_by   = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prepared_reports',
        db_column='report_prepared_by_id',
        verbose_name='Отчёт подготовил'
    )
    operator_notes = models.TextField(default='', blank=True, verbose_name='Примечания испытателя')

    # ═══════════════════════════════════════════════════════════════
    # БЛОК «СМК»
    # ═══════════════════════════════════════════════════════════════
    protocol_checked_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='protocol_checks',
        db_column='protocol_checked_by',
        verbose_name='Протокол проверил (СМК)'
    )
    protocol_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата проверки протокола'
    )
    replacement_count = models.IntegerField(
        default=0,
        verbose_name='Количество замещающих протоколов'
    )
    protocol_issued_date             = models.DateField(null=True, blank=True, verbose_name='Дата выдачи протокола')
    protocol_printed_date            = models.DateField(null=True, blank=True, verbose_name='Дата печати протокола')
    replacement_protocol_issued_date = models.DateField(null=True, blank=True, verbose_name='Дата выдачи протокола-заменителя')

    # ═══════════════════════════════════════════════════════════════
    # СТАТУСЫ
    # ═══════════════════════════════════════════════════════════════
    status = models.CharField(max_length=30, default=SampleStatus.PENDING_VERIFICATION, choices=SampleStatus.choices, verbose_name='Статус')

    # ═══════════════════════════════════════════════════════════════
    # ФАЙЛЫ
    # ═══════════════════════════════════════════════════════════════
    files_path = models.CharField(max_length=500, default='', blank=True, verbose_name='Путь к файлам')

    # ═══════════════════════════════════════════════════════════════
    # M2M СВЯЗИ (через посредники)
    # ═══════════════════════════════════════════════════════════════
    measuring_instruments = models.ManyToManyField(
        'Equipment',
        through='SampleMeasuringInstrument',
        related_name='used_as_measuring_instrument',
        verbose_name='Средства измерений'
    )
    testing_equipment = models.ManyToManyField(
        'Equipment',
        through='SampleTestingEquipment',
        related_name='used_as_testing_equipment',
        verbose_name='Испытательное оборудование'
    )
    operators = models.ManyToManyField(
        'User',
        through='SampleOperator',
        related_name='operated_samples',
        verbose_name='Операторы'
    )

    # ═══════════════════════════════════════════════════════════════
    # МЕТАДАННЫЕ
    # ═══════════════════════════════════════════════════════════════
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        db_table = 'samples'
        managed  = False
        ordering = ['sequence_number']
        verbose_name        = 'Образец'
        verbose_name_plural = 'Образцы'

    def __str__(self):
        return f'№ {self.sequence_number} — {self.cipher}'

    # ═══════════════════════════════════════════════════════════════
    # ГЕНЕРАЦИЯ НОМЕРОВ И ИДЕНТИФИКАТОРОВ
    # ═══════════════════════════════════════════════════════════════

    def generate_sequence_number(self):
        """Генерирует следующий порядковый номер"""
        max_num = Sample.objects.aggregate(models.Max('sequence_number'))['sequence_number__max']
        return (max_num or 0) + 1

    def generate_cipher(self):
        """Генерирует шифр образца (только латиница): ГГММДД_номер_сопр.док_ID_код_условия"""
        date_str = self.registration_date.strftime('%y%m%d')  # ГГММДД

        parts = [
            date_str,
            str(self.sequence_number),
            self.accompanying_doc_number,
            self.object_id or 'Sample',
            self.test_code,
        ]

        # Условия испытания только для лаборатории МИ (MI)
        if self.laboratory.code == 'MI' and self.test_conditions:
            parts.append(self.test_conditions)

        return '_'.join(filter(None, parts))

    def generate_pi_number(self):
        """Генерирует номер протокола испытаний: сопр.док/номер-код-лаб"""
        return f"{self.accompanying_doc_number}/{self.sequence_number}-{self.test_code}-{self.laboratory.code}"

    def generate_replacement_pi_number(self):
        """Генерирует номер замещающего протокола: основной_номер-ЗАМ"""
        if not self.pi_number:
            self.pi_number = self.generate_pi_number()
        return f"{self.pi_number}-ЗАМ"

    # ═══════════════════════════════════════════════════════════════
    # СИСТЕМА ЗАМЕЩАЮЩИХ ПРОТОКОЛОВ
    # ═══════════════════════════════════════════════════════════════

    def initiate_replacement_protocol(self):
        """
        Инициирует процесс создания замещающего протокола.
        Вызывается автоматически при установке галки replacement_protocol_required.
        """
        # Проверяем, что образец в статусе COMPLETED
        if self.status != SampleStatus.COMPLETED:
            return

        # Если образец был "без отчётности" - нельзя создать замещающий протокол
        if hasattr(self, 'report_type') and self.report_type == 'WITHOUT_REPORT':
            return  # Или raise ValueError("Нельзя создать замещающий для образца без отчётности")

        # Генерируем номер замещающего протокола
        self.replacement_pi_number = self.generate_replacement_pi_number()

        # Меняем статус на REPLACEMENT_PROTOCOL
        self.status = SampleStatus.REPLACEMENT_PROTOCOL

        # Сбрасываем данные о проверке протокола
        self.protocol_checked_by = None
        self.protocol_checked_at = None

        # Дату выпуска основного протокола НЕ трогаем
        # Дату выпуска замещающего сохраняем в replacement_protocol_issued_date
        # (это поле будет заполнено позже, когда СМК одобрит замещающий протокол)

    # ═══════════════════════════════════════════════════════════════
    # РАСЧЁТ СРОКОВ
    # ═══════════════════════════════════════════════════════════════

    def calculate_deadline(self):
        """Рассчитывает срок выполнения с учётом выходных и праздников"""
        from datetime import timedelta
        from .base import Holiday

        current_date = self.sample_received_date
        days_added = 0

        # Получаем праздники из БД
        holidays = set(Holiday.objects.values_list('date', flat=True))

        while days_added < self.working_days:
            current_date += timedelta(days=1)

            # Пропускаем выходные (суббота=5, воскресенье=6)
            if current_date.weekday() >= 5:
                continue

            # Пропускаем праздники
            if current_date in holidays:
                continue

            days_added += 1

        return current_date

    # ═══════════════════════════════════════════════════════════════
    # ПЕРЕОПРЕДЕЛЕНИЕ SAVE
    # ═══════════════════════════════════════════════════════════════

    def save(self, *args, **kwargs):
        """Переопределяем save для автоматической генерации полей"""

        # ОБРАБОТКА ЗАМЕЩАЮЩЕГО ПРОТОКОЛА
        if self.pk:
            try:
                old_instance = Sample.objects.get(pk=self.pk)

                if (self.replacement_protocol_required and
                        not old_instance.replacement_protocol_required and
                        old_instance.status == SampleStatus.COMPLETED):
                    self.initiate_replacement_protocol()
                    super().save(*args, **kwargs)
                    return

            except Sample.DoesNotExist:
                pass

        # 1. Генерируем порядковый номер если его нет
        if not self.sequence_number:
            self.sequence_number = self.generate_sequence_number()

        # 2. Копируем данные из стандарта
        if self.standard_id and not self.test_code:
            self.test_code = self.standard.test_code
            self.test_type = self.standard.test_type

        # 3. Генерируем шифр
        self.cipher = self.generate_cipher()

        # 4. Генерируем номер ПИ ТОЛЬКО если нужна отчётность
        if not self.pi_number:
            # ВАЖНО: Адаптируйте под ваше поле для типа отчётности!
            if hasattr(self, 'reporting') and self.reporting in ['WITH_PROTOCOL', 'PROTOCOL_ONLY']:
                self.pi_number = self.generate_pi_number()

        # 5. Рассчитываем deadline
        if not self.deadline and self.working_days:
            self.deadline = self.calculate_deadline()

        super().save(*args, **kwargs)

    # ═══════════════════════════════════════════════════════════════
    # МЕТОДЫ ПРОВЕРКИ ПРАВ
    # ═══════════════════════════════════════════════════════════════

    def can_be_verified_by(self, user):
        """Проверяет, может ли пользователь подтвердить регистрацию этого образца"""
        from .user import UserRole
        
        # Проверять может только другой администратор (не тот кто зарегистрировал)
        if user.role not in ['ADMIN', 'SYSADMIN']:
            return False

        if self.registered_by == user:
            return False  # Нельзя проверять свои образцы

        if self.status != SampleStatus.PENDING_VERIFICATION:
            return False  # Можно проверять только образцы ожидающие проверки

        return True

    def can_protocol_be_verified_by(self, user):
        """Проверяет, может ли пользователь проверить протокол"""
        # Проверять может только СМК
        if user.role not in ['QMS_HEAD', 'QMS']:
            return False

        # Только если статус = DRAFT_READY
        if self.status != SampleStatus.DRAFT_READY:
            return False

        return True

    def is_visible_to_testers(self):
        """Проверяет, виден ли образец испытателям"""
        # Испытатели видят только проверенные образцы
        return self.status != SampleStatus.PENDING_VERIFICATION


# =============================================================================
# ПОСРЕДНИКИ M2M ДЛЯ ОБРАЗЦОВ
# =============================================================================

class SampleMeasuringInstrument(models.Model):
    """Связь образца со средствами измерений"""
    sample    = models.ForeignKey(Sample, on_delete=models.CASCADE)
    equipment = models.ForeignKey('Equipment', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_measuring_instruments'
        managed         = False
        unique_together = [('sample', 'equipment')]


class SampleTestingEquipment(models.Model):
    """Связь образца с испытательным оборудованием"""
    sample    = models.ForeignKey(Sample, on_delete=models.CASCADE)
    equipment = models.ForeignKey('Equipment', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_testing_equipment'
        managed         = False
        unique_together = [('sample', 'equipment')]


class SampleOperator(models.Model):
    """Связь образца с операторами"""
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    user   = models.ForeignKey('User', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_operators'
        managed         = False
        unique_together = [('sample', 'user')]

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

    # Изготовление (для лаборатории)
    MANUFACTURING = 'MANUFACTURING', 'Изготавливается'
    MANUFACTURED = 'MANUFACTURED', 'Изготовлено (ожидает приёмки)'
    TRANSFERRED = 'TRANSFERRED', 'Передан в лабораторию'  # ⭐ v3.9.1
    UZK_TESTING = 'UZK_TESTING', 'На УЗК'  # ⭐ v3.64.0
    UZK_READY = 'UZK_READY', 'Готово к передаче из МИ (УЗК)'  # ⭐ v3.64.0
    MOISTURE_CONDITIONING = 'MOISTURE_CONDITIONING', 'На влагонасыщении'  # ⭐ v3.15.0
    MOISTURE_READY = 'MOISTURE_READY', 'Готово к передаче из УКИ'

    # Испытания
    ACCEPTED_IN_LAB = 'ACCEPTED_IN_LAB', 'Принят в лаборатории'  # ⭐ v3.64.0
    CONDITIONING = 'CONDITIONING', 'Кондиционирование'
    READY_FOR_TEST = 'READY_FOR_TEST', 'Ждёт испытания'
    IN_TESTING = 'IN_TESTING', 'На испытании'
    TESTED = 'TESTED', 'Испытан'
    # ⭐ v3.84.0: PENDING_MENTOR_REVIEW удалён. Система проверки отчёта
    # наставником упразднена — ответственность теперь на аттестованном сотруднике
    # в M2M-поле report_preparers (см. _validate_trainee_for_draft).
    DRAFT_READY = 'DRAFT_READY', 'Черновик готов'
    RESULTS_UPLOADED = 'RESULTS_UPLOADED', 'Результаты выложены'

    # СМК
    PROTOCOL_ISSUED = 'PROTOCOL_ISSUED', 'Протокол готов'
    COMPLETED = 'COMPLETED', 'Готово'

    # Замещающий протокол
    REPLACEMENT_PROTOCOL = 'REPLACEMENT_PROTOCOL', 'Замещающий протокол'


# ⭐ НОВОЕ: Отдельный enum для статусов мастерской
class WorkshopStatus(models.TextChoices):
    """Статусы работы мастерской с образцом"""
    IN_WORKSHOP = 'IN_WORKSHOP', 'В мастерской'
    COMPLETED = 'COMPLETED', 'Готово'
    CANCELLED = 'CANCELLED', 'Отменено'


class FurtherMovement(models.TextChoices):
    """Варианты дальнейшего движения образца после изготовления"""
    EMPTY = '', '—'
    TO_CLIENT_DEPT = 'TO_CLIENT_DEPT', 'Вернуть специалистам по регистрации'

class StorageLocation(models.TextChoices):
    EMPTY = '', '—'
    CONTAINER = 'CONTAINER', 'Контейнер'
    FRIDGE_1 = 'FRIDGE_1', 'Холодильник №1'
    FRIDGE_2 = 'FRIDGE_2', 'Холодильник №2'

class ReportType(models.TextChoices):
    PROTOCOL = 'PROTOCOL', 'Протокол'
    RESULTS_CLIENT = 'RESULTS_CLIENT', 'Результаты заказчику'
    PHOTO = 'PHOTO', 'Фото'
    GRAPHICS = 'GRAPHICS', 'Графики'
    RESULTS_SCIENCE = 'RESULTS_SCIENCE', 'Результаты наука'
    WITHOUT_REPORT = 'WITHOUT_REPORT', 'Без отчётности'




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
    invoice                        = models.ForeignKey('Invoice', on_delete=models.RESTRICT, null=True, blank=True, related_name='samples', verbose_name='Счёт')  # ⭐ v3.38.0
    laboratory                     = models.ForeignKey('Laboratory', on_delete=models.RESTRICT, related_name='samples', verbose_name='Лаборатория')
    accompanying_doc_number        = models.CharField(max_length=500, default='', blank=True, verbose_name='Номер сопроводительного документа', validators=[validate_latin_only], help_text='Автозаполняется из акта')
    accompanying_doc_full_name     = models.CharField(max_length=500, default='', blank=True, verbose_name='Полное название сопроводительного документа')
    accreditation_area             = models.ForeignKey('AccreditationArea', on_delete=models.RESTRICT, related_name='samples', verbose_name='Область аккредитации')
    standards                      = models.ManyToManyField('Standard', through='SampleStandard', related_name='samples', verbose_name='Стандарты',)
    test_code                      = models.CharField(max_length=20, default='', blank=True, verbose_name='Код испытания')
    test_type                      = models.CharField(max_length=500, default='', blank=True, verbose_name='Вид испытания')
    working_days                   = models.IntegerField(null=True, blank=True, verbose_name='Рабочие дни (устар.)')  # ⭐ deadline теперь указывается явно в форме; поле оставлено для обратной совместимости
    sample_received_date           = models.DateField(verbose_name='Дата поступления образца')
    storage_location = models.CharField(max_length=30, choices=StorageLocation.choices, default='', blank=True, verbose_name='Место хранения')
    storage_conditions             = models.CharField(max_length=500, default='', blank=True, verbose_name='Условия хранения')
    object_info                    = models.TextField(default='', blank=True, verbose_name='Информация об объекте')
    object_id                      = models.CharField(max_length=500, default='', blank=True, verbose_name='ID объекта испытаний', validators=[validate_latin_only], help_text='Только латиница, цифры и символы: - _ . /')
    cutting_direction              = models.CharField(max_length=500, default='', blank=True, verbose_name='Направление вырезки')
    test_conditions                = models.CharField(max_length=1000, default='', blank=True, verbose_name='Условия испытания', validators=[validate_latin_only], help_text='Только латиница (например: RTD, CTW80C). Только для МИ')
    panel_id                       = models.CharField(max_length=500, default='', blank=True, verbose_name='Идентификация панели')
    material                       = models.CharField(max_length=500, default='', verbose_name='Материал')
    preparation = models.TextField(default='', blank=True, verbose_name='Пробоподготовка')  # ⭐ v3.6.0
    determined_parameters          = models.TextField(max_length=1000, default='', blank=True,verbose_name='Определяемые параметры')
    sample_count                   = models.IntegerField(default=1, verbose_name='Количество образцов')
    additional_sample_count        = models.IntegerField(default=0, verbose_name='Дополнительные образцы')  # ⭐ v3.9.0
    cut_maximum                    = models.BooleanField(default=False, verbose_name='Нарезать максимум')  # ⭐ v3.64.0
    notes                          = models.TextField(default='', blank=True, verbose_name='Примечания')  # ⭐ v3.6.1
    workshop_notes                 = models.TextField(default='', blank=True, verbose_name='Примечания мастерской')  # ⭐ v3.9.0
    admin_notes                    = models.TextField(default='', blank=True, verbose_name='Комментарии')  # ⭐ v3.6.1: переименовано
    deadline                       = models.DateField(verbose_name='Срок выполнения')
    manufacturing_deadline         = models.DateField(null=True, blank=True, verbose_name='Срок изготовления')  # ⭐ v3.7.0
    report_type                    = models.CharField(max_length=200, default=ReportType.PROTOCOL, choices=ReportType.choices, verbose_name='Тип отчёта')
    pi_number                      = models.CharField(max_length=200, default='', blank=True, verbose_name='Номер ПИ')
    manufacturing                  = models.BooleanField(default=False,verbose_name='Требуется изготовление')
    workshop_status                = models.CharField(max_length=30, choices=WorkshopStatus.choices, null=True, blank=True, verbose_name='В мастерской')
    uzk_required                   = models.BooleanField(default=False, verbose_name='Требуется УЗК')
    uzk_sample                     = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependent_uzk_samples', db_column='uzk_sample_id', verbose_name='Образец УЗК (МИ)')  # ⭐ v3.64.0
    moisture_conditioning          = models.BooleanField(default=False, verbose_name='Влагонасыщение')
    moisture_sample                = models.ForeignKey('self', on_delete=models.SET_NULL,null=True, blank=True, related_name='dependent_samples',db_column='moisture_sample_id', verbose_name='Образец влагонасыщения (УКИ)',)
    cutting_standard               = models.ForeignKey('Standard', on_delete=models.SET_NULL,null=True, blank=True,related_name='cutting_samples',db_column='cutting_standard_id',verbose_name='Стандарт на нарезку',)  # ⭐ v3.15.0
    acceptance_act                 = models.ForeignKey('AcceptanceAct', on_delete=models.SET_NULL, null=True, blank=True,related_name='samples',db_column='acceptance_act_id', verbose_name='Акт приёма-передачи' )
    moisture_conditioning          = models.BooleanField(default=False, verbose_name='Требуется влагонасыщение')
    moisture_sample                = models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True,related_name='dependent_samples',db_column='moisture_sample_id',verbose_name='Образец влагонасыщения (УКИ)')
    further_movement               = models.CharField(max_length=20, choices=FurtherMovement.choices, default='', blank=True, verbose_name='Дальнейшее движение образца')

    # Система двойной проверки регистрации
    registered_by                  = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='registered_samples', db_column='registered_by_id', verbose_name='Зарегистрировал (первый админ)')
    verified_by                    = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_samples', db_column='verified_by')
    verified_at                    = models.DateTimeField(null=True, blank=True, verbose_name='Дата проверки')

    # Система замещающих протоколов
    replacement_protocol_required  = models.BooleanField(default=False, verbose_name='Требуется протокол-заменитель')
    replacement_pi_number          = models.CharField(max_length=200, default='', blank=True, verbose_name='Номер ПИ-заменителя', editable=False)

    # ═══════════════════════════════════════════════════════════════
    # БЛОК «ИЗГОТОВЛЕНИЕ» (МАСТЕРСКАЯ)
    # ═══════════════════════════════════════════════════════════════

    manufacturing_completion_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения изготовления')
    workshop_comment              = models.TextField(default='', blank=True, verbose_name='Комментарий мастерской')

    # M2M связи для изготовления (через посредники)
    manufacturing_measuring_instruments = models.ManyToManyField(
        'Equipment',
        through='SampleManufacturingMeasuringInstrument',
        related_name='used_for_manufacturing_mi',
        verbose_name='СИ для изготовления'
    )

    manufacturing_testing_equipment = models.ManyToManyField(
        'Equipment',
        through='SampleManufacturingTestingEquipment',
        related_name='used_for_manufacturing_te',
        verbose_name='ИО для изготовления'
    )

    # ⭐ v3.10.1: Вспомогательное оборудование (ВО)
    manufacturing_auxiliary_equipment = models.ManyToManyField(
        'Equipment',
        through='SampleManufacturingAuxiliaryEquipment',
        related_name='used_for_manufacturing_aux',
        verbose_name='ВО для изготовления'
    )

    manufacturing_operators = models.ManyToManyField(
        'User',
        through='SampleManufacturingOperator',
        related_name='manufacturing_samples',
        verbose_name='Операторы изготовления'
    )

    # ═══════════════════════════════════════════════════════════════
    # БЛОК «ИСПЫТАТЕЛЬ»
    # ═══════════════════════════════════════════════════════════════

    # --- КОНДИЦИОНИРОВАНИЕ (для ХА и ТА) ---
    conditioning_start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Начало кондиционирования'
    )
    conditioning_end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Окончание кондиционирования'
    )

    # --- ИСПЫТАНИЯ (для всех лабораторий) ---
    testing_start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Начало испытания'
    )
    testing_end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Окончание испытания'
    )

    # --- ПРОЧИЕ ПОЛЯ ИСПЫТАТЕЛЯ ---
    report_prepared_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время подготовки отчёта',
        help_text='Заполняется вручную испытателем перед переходом в «Черновик готов»',
    )
    # ⭐ v3.84.0: FK report_prepared_by → M2M report_preparers.
    # Поля report_verified_by / report_verified_date удалены — система проверки
    # отчёта стажёра наставником (v3.70.0) упразднена. Ответственность теперь
    # лежит на аттестованном сотруднике, включённом в M2M report_preparers.
    # См. _validate_trainee_for_draft: ≥1 не-стажёр в operators И в preparers.
    report_preparers = models.ManyToManyField(
        'User',
        through='SampleReportPreparer',
        related_name='prepared_sample_reports',
        verbose_name='Отчёт подготовили',
    )
    operator_notes = models.TextField(
        default='',
        blank=True,
        verbose_name='Примечания испытателя'
    )

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
    label_printed =                    models.BooleanField(default=False, verbose_name='Этикетка распечатана')
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
    auxiliary_equipment = models.ManyToManyField(
        'Equipment',
        through='SampleAuxiliaryEquipment',
        related_name='used_for_testing_aux',
        verbose_name='Вспомогательное оборудование'
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

    def generate_panel_id(self):
        """
        ⭐ v3.9.0: Генерирует ID панели: YYMMDD_object_id
        Только при manufacturing=True и наличии object_id.
        """
        if not self.manufacturing or not self.object_id or not self.registration_date:
            return ''
        date_str = self.registration_date.strftime('%y%m%d')
        return f"{date_str}_{self.object_id}"

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
        # ⭐ v3.32.0: report_type может быть запятая-разделённым списком
        if hasattr(self, 'report_type') and self.report_type:
            report_types = set(self.report_type.split(','))
            if not (report_types - {'WITHOUT_REPORT'}):
                return

        # Генерируем номер замещающего протокола
        self.replacement_pi_number = self.generate_replacement_pi_number()

        # Меняем статус на REPLACEMENT_PROTOCOL
        self.status = SampleStatus.REPLACEMENT_PROTOCOL

        # Сбрасываем данные о проверке протокола
        self.protocol_checked_by = None
        self.protocol_checked_at = None

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

    def calculate_manufacturing_deadline(self):
        """
        Рассчитывает срок изготовления: 60% от рабочих дней между
        sample_received_date и deadline (с округлением).

        ⭐ Переписано: раньше считалось от working_days, теперь от интервала
        received_date → deadline, т.к. deadline теперь указывается явно.
        """
        from datetime import timedelta
        from .base import Holiday

        if not self.sample_received_date or not self.deadline:
            return None

        holidays = set(Holiday.objects.values_list('date', flat=True))

        # 1. Считаем, сколько рабочих дней между received_date и deadline
        total_working_days = 0
        current_date = self.sample_received_date
        while current_date < self.deadline:
            current_date += timedelta(days=1)
            if current_date.weekday() >= 5:
                continue
            if current_date in holidays:
                continue
            total_working_days += 1

        # 2. Берём 60%, минимум 1 день
        manufacturing_days = round(total_working_days * 0.6)
        if manufacturing_days < 1:
            manufacturing_days = 1

        # 3. Отсчитываем это количество рабочих дней от received_date
        current_date = self.sample_received_date
        days_added = 0
        while days_added < manufacturing_days:
            current_date += timedelta(days=1)
            if current_date.weekday() >= 5:
                continue
            if current_date in holidays:
                continue
            days_added += 1

        return current_date

    # ═══════════════════════════════════════════════════════════════
    # ⭐ v3.9.0: ОТОБРАЖЕНИЕ КОЛИЧЕСТВА ОБРАЗЦОВ
    # ═══════════════════════════════════════════════════════════════

    @property
    def report_type_display(self):
        """⭐ v3.32.0: Отображение типов отчёта (через запятую)."""
        if not self.report_type:
            return '—'
        labels_map = dict(ReportType.choices)
        return ', '.join(labels_map.get(rt, rt) for rt in self.report_type.split(','))

    @property
    def sample_count_display(self):
        """
        Отображение количества образцов для этикетки и карточки.
        - cut_maximum=True → 'Макс.'
        - Формат: '6+1' если есть дополнительные, иначе '6'.
        """
        if self.cut_maximum:
            return 'Макс.'
        if self.additional_sample_count and self.additional_sample_count > 0:
            return f"{self.sample_count}+{self.additional_sample_count}"
        return str(self.sample_count)

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
                    # Восстанавливаем статус COMPLETED перед вызовом,
                    # т.к. save_sample_fields() мог изменить self.status
                    self.status = SampleStatus.COMPLETED
                    self.initiate_replacement_protocol()
                    super().save(*args, **kwargs)
                    return

            except Sample.DoesNotExist:
                pass

        # 1. Генерируем порядковый номер если его нет
        if not self.sequence_number:
            self.sequence_number = self.generate_sequence_number()

        # 3. Генерируем шифр
        self.cipher = self.generate_cipher()

        # 4. Генерируем номер ПИ ТОЛЬКО если нужна отчётность
        # ⭐ v3.11.1: Если установлен _use_existing_pi_number — используем его вместо автогенерации
        if getattr(self, '_use_existing_pi_number', None):
            self.pi_number = self._use_existing_pi_number
        elif not self.pi_number:
            # ⭐ v3.32.0: report_type — запятая-разделённый список
            # ПИ нужен, если есть хотя бы один тип кроме WITHOUT_REPORT
            report_types = set(self.report_type.split(',')) if self.report_type else set()
            needs_pi = 'PROTOCOL' in report_types
            if needs_pi:
                self.pi_number = self.generate_pi_number()

        # 5. Рассчитываем deadline
        # ⭐ Закомментировано: deadline теперь указывается пользователем явно в форме.
        # Оставлено для возможного отката. Если захотите вернуть авторасчёт —
        # раскомментируйте и убедитесь, что working_days заполнен.
        # if not self.deadline and self.working_days:
        #     self.deadline = self.calculate_deadline()

        # 6. Рассчитываем manufacturing_deadline
        # ⭐ Теперь считается от deadline (а не от working_days)
        if self.manufacturing and not self.manufacturing_deadline and self.deadline:
            if self.further_movement == 'TO_CLIENT_DEPT':
                # «Только нарезка» — срок изготовления = срок выполнения
                self.manufacturing_deadline = self.deadline
            else:
                # Обычное изготовление — 60% рабочих дней от интервала received → deadline
                self.manufacturing_deadline = self.calculate_manufacturing_deadline()

        # ⭐ v3.9.0: 7. Автогенерация panel_id
        if self.manufacturing:
            self.panel_id = self.generate_panel_id()
        else:
            self.panel_id = ''

        super().save(*args, **kwargs)

    # ═══════════════════════════════════════════════════════════════
    # РАСЧЁТНЫЕ СВОЙСТВА (PROPERTIES)
    # ═══════════════════════════════════════════════════════════════

    @property
    def test_date(self):
        """
        Для обратной совместимости: возвращает дату из testing_end_datetime.
        Используется в старых шаблонах и коде.
        """
        if self.testing_end_datetime:
            return self.testing_end_datetime.date()
        return None

    @property
    def conditioning_duration_hours(self):
        """
        Длительность кондиционирования в часах.
        Используется для аналитики и отчётов.
        """
        if self.conditioning_start_datetime and self.conditioning_end_datetime:
            delta = self.conditioning_end_datetime - self.conditioning_start_datetime
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def testing_duration_hours(self):
        """
        Длительность испытания в часах.
        Используется для аналитики и отчётов.
        """
        if self.testing_start_datetime and self.testing_end_datetime:
            delta = self.testing_end_datetime - self.testing_start_datetime
            return round(delta.total_seconds() / 3600, 2)
        return None

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
            return False

        if self.status != SampleStatus.PENDING_VERIFICATION:
            return False

        return True

    def can_protocol_be_verified_by(self, user):
        """Проверяет, может ли пользователь проверить протокол"""
        if user.role not in ['QMS_HEAD', 'QMS']:
            return False

        if self.status != SampleStatus.DRAFT_READY:
            return False

        return True

    def is_visible_to_testers(self):
        """Проверяет, виден ли образец испытателям"""
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


class SampleReportPreparer(models.Model):
    """
    ⭐ v3.84.0: Связь образца с подготовившими отчёт сотрудниками.
    Заменяет прежний FK Sample.report_prepared_by — теперь отчёт может
    подготовить несколько сотрудников совместно (например, стажёр + наставник).
    Валидация стажёров — в save_logic._validate_trainee_for_draft.
    """
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    user   = models.ForeignKey('User', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_report_preparers'
        managed         = False
        unique_together = [('sample', 'user')]

# =============================================================================
# ПОСРЕДНИКИ M2M ДЛЯ ИЗГОТОВЛЕНИЯ
# =============================================================================

class SampleManufacturingMeasuringInstrument(models.Model):
    """Связь образца со средствами измерений для изготовления"""
    sample    = models.ForeignKey(Sample, on_delete=models.CASCADE)
    equipment = models.ForeignKey('Equipment', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_manufacturing_measuring_instruments'
        managed         = False
        unique_together = [('sample', 'equipment')]


class SampleManufacturingTestingEquipment(models.Model):
    """Связь образца с испытательным оборудованием для изготовления"""
    sample    = models.ForeignKey(Sample, on_delete=models.CASCADE)
    equipment = models.ForeignKey('Equipment', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_manufacturing_testing_equipment'
        managed         = False
        unique_together = [('sample', 'equipment')]


class SampleManufacturingOperator(models.Model):
    """Связь образца с операторами изготовления (мастерская)"""
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    user   = models.ForeignKey('User', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_manufacturing_operators'
        managed         = False
        unique_together = [('sample', 'user')]

class SampleManufacturingAuxiliaryEquipment(models.Model):
    """Связь образца со вспомогательным оборудованием для изготовления"""
    sample    = models.ForeignKey(Sample, on_delete=models.CASCADE)
    equipment = models.ForeignKey('Equipment', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_manufacturing_auxiliary_equipment'
        managed         = False
        unique_together = [('sample', 'equipment')]

    def __str__(self):
        return f"Sample {self.sample_id} ↔ ManufAux Equipment {self.equipment_id}"


class SampleAuxiliaryEquipment(models.Model):
    """Связь образца со вспомогательным оборудованием для испытаний"""
    sample    = models.ForeignKey(Sample, on_delete=models.CASCADE)
    equipment = models.ForeignKey('Equipment', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_auxiliary_equipment'
        managed         = False
        unique_together = [('sample', 'equipment')]

    def __str__(self):
        return f"Sample {self.sample_id} ↔ Aux Equipment {self.equipment_id}"

class SampleStandard(models.Model):
    """Связь образца со стандартами (M2M)"""
    sample   = models.ForeignKey(Sample, on_delete=models.CASCADE)
    standard = models.ForeignKey('Standard', on_delete=models.RESTRICT)

    class Meta:
        db_table        = 'sample_standards'
        managed         = False
        unique_together = [('sample', 'standard')]

    def __str__(self):
        return f"Sample {self.sample_id} ↔ Standard {self.standard_id}"
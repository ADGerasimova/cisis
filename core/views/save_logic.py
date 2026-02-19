"""
CISIS — Логика сохранения полей образца.

Содержит:
- save_sample_fields: сохранение изменённых полей из POST
- handle_sample_save: обёртка с transaction + messages
- handle_m2m_update: обновление M2M-связей
- _recalculate_auto_fields: пересчёт зависимых полей
- _parse_datetime_value: парсинг datetime из формы
- _validate_trainee_for_draft: валидация стажёров
"""

import logging
from datetime import datetime

from django.db import models, transaction
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.timezone import make_aware
from django.core.exceptions import FieldDoesNotExist

from core.models import (
    Sample, JournalColumn, WorkshopStatus, User,
    SampleMeasuringInstrument, SampleTestingEquipment, SampleOperator,
    SampleManufacturingMeasuringInstrument,
    SampleManufacturingTestingEquipment,
    SampleManufacturingOperator,
    SampleManufacturingAuxiliaryEquipment,
    SampleAuxiliaryEquipment,SampleStandard,
)
from core.permissions import PermissionChecker
from .constants import (
    AUTO_FIELDS, AUTO_FIELD_DEPENDENCIES,
    LATIN_ONLY_FIELDS, LATIN_ONLY_IF_MI,
)
from .field_utils import _validate_latin_only
from .freeze_logic import _is_field_frozen

logger = logging.getLogger(__name__)


def _parse_datetime_value(form_value):
    """Парсит datetime из формы (YYYY-MM-DDTHH:MM или YYYY-MM-DD)."""
    if 'T' in form_value:
        dt = datetime.strptime(form_value, '%Y-%m-%dT%H:%M')
    else:
        dt = datetime.strptime(form_value, '%Y-%m-%d').replace(hour=12, minute=0)
    return make_aware(dt)


def _recalculate_auto_fields(sample, changed_fields):
    """
    Пересчитывает автоматические поля образца,
    зависящие от изменённых полей.

    changed_fields: set кодов полей, которые были изменены.
    Вызывается ПЕРЕД sample.save().
    """
    fields_to_recalc = set()
    for field_code in changed_fields:
        deps = AUTO_FIELD_DEPENDENCIES.get(field_code, set())
        fields_to_recalc.update(deps)

    if not fields_to_recalc:
        return

    # test_code / test_type (из стандарта)
    if 'test_code' in fields_to_recalc or 'test_type' in fields_to_recalc:
        # ⭐ v3.13.0: берём test_code/test_type из первого стандарта
        if sample.pk:
            first_standard = sample.standards.order_by('samplestandard__id').first()
            if first_standard:
                sample.test_code = first_standard.test_code
                sample.test_type = first_standard.test_type

    # cipher пересчитывается автоматически в save() — ничего не нужно

    # pi_number
    if 'pi_number' in fields_to_recalc:
        if sample.report_type and sample.report_type != 'WITHOUT_REPORT':
            old_pi = sample.pi_number
            new_pi = sample.generate_pi_number()
            if old_pi and f"/{sample.sequence_number}-" in old_pi:
                sample.pi_number = new_pi

    # deadline
    if 'deadline' in fields_to_recalc:
        if sample.working_days and sample.sample_received_date:
            sample.deadline = sample.calculate_deadline()

    # manufacturing_deadline
    if 'manufacturing_deadline' in fields_to_recalc:
        if sample.manufacturing and sample.working_days and sample.sample_received_date:
            if sample.further_movement == 'TO_CLIENT_DEPT':
                sample.manufacturing_deadline = sample.deadline
            else:
                sample.manufacturing_deadline = sample.calculate_manufacturing_deadline()
        elif not sample.manufacturing:
            sample.manufacturing_deadline = None


def save_sample_fields(request, sample):
    """
    Сохраняет изменённые поля образца из POST-данных.
    M2M-поля обрабатываются отдельно через промежуточные таблицы.
    Возвращает список названий обновлённых полей.
    """
    updated_fields = []
    changed_field_codes = set()
    m2m_updates = []

    all_columns = JournalColumn.objects.filter(
        journal__code='SAMPLES', is_active=True
    )

    for column in all_columns:
        field_code = column.code

        if not PermissionChecker.can_edit(request.user, 'SAMPLES', field_code):
            # Регистраторы могут менять status при активной разморозке
            if field_code == 'status' and request.user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'):
                unfrozen_key = f'unfrozen_registration_{sample.id}'
                if not request.session.get(unfrozen_key, False):
                    continue
            else:
                continue

        if field_code in AUTO_FIELDS:
            continue

        # Серверная защита заморозки блоков
        is_frozen, _ = _is_field_frozen(field_code, request.user, sample, request=request)
        if is_frozen:
            continue

        try:
            field_obj = Sample._meta.get_field(field_code)
        except FieldDoesNotExist:
            continue

        # M2M-поля: собираем для обработки после save()
        if isinstance(field_obj, models.ManyToManyField):
            if field_code not in request.POST:
                continue
            selected_ids = request.POST.getlist(field_code)
            m2m_updates.append((field_code, column.name, selected_ids))
            continue

        # BooleanField: unchecked чекбокс не отправляется в POST
        if isinstance(field_obj, models.BooleanField):
            new_value = request.POST.get(field_code) == 'on'
            old_value = getattr(sample, field_code)
            if old_value != new_value:
                setattr(sample, field_code, new_value)
                updated_fields.append(column.name)
                changed_field_codes.add(field_code)
            continue

        form_value = request.POST.get(field_code)
        if form_value is None:
            continue

        # Валидация «только латиница»
        needs_latin_check = False
        if field_code in LATIN_ONLY_FIELDS and form_value:
            needs_latin_check = True
        elif field_code in LATIN_ONLY_IF_MI and form_value:
            if sample.laboratory and sample.laboratory.code == 'MI':
                needs_latin_check = True

        if needs_latin_check:
            is_valid, error_msg = _validate_latin_only(field_code, form_value)
            if not is_valid:
                messages.error(request, f'Поле «{column.name}»: {error_msg}')
                continue

        old_value = getattr(sample, field_code)

        # DateTimeField (проверяем ДО DateField)
        if isinstance(field_obj, models.DateTimeField):
            if form_value:
                new_value = _parse_datetime_value(form_value)
                if old_value != new_value:
                    setattr(sample, field_code, new_value)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)
            elif old_value is not None:
                if field_obj.null:
                    setattr(sample, field_code, None)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)

        elif isinstance(field_obj, models.DateField):
            if form_value:
                new_value = datetime.strptime(form_value, '%Y-%m-%d').date()
                if old_value != new_value:
                    setattr(sample, field_code, new_value)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)
            elif old_value is not None:
                if field_obj.null:
                    setattr(sample, field_code, None)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)

        elif isinstance(field_obj, models.ForeignKey):
            old_id = getattr(sample, f'{field_code}_id')
            if form_value:
                new_id = int(form_value)
                if old_id != new_id:
                    setattr(sample, f'{field_code}_id', new_id)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)
            elif old_id is not None:
                if field_obj.null:
                    setattr(sample, f'{field_code}_id', None)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)

        elif isinstance(field_obj, models.IntegerField):
            if form_value:
                new_value = int(form_value)
                if old_value != new_value:
                    setattr(sample, field_code, new_value)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)
            else:
                if not field_obj.null:
                    default_val = field_obj.default if field_obj.has_default() else 0
                    if old_value != default_val:
                        setattr(sample, field_code, default_val)
                        updated_fields.append(column.name)
                        changed_field_codes.add(field_code)
                elif old_value is not None:
                    setattr(sample, field_code, None)
                    updated_fields.append(column.name)
                    changed_field_codes.add(field_code)

        else:
            # Текстовые поля (CharField, TextField)
            if field_obj.choices and not form_value:
                continue

            # Валидация статуса при разморозке регистраторами
            if field_code == 'status' and request.user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'):
                allowed_statuses = {'CANCELLED', 'PENDING_VERIFICATION', sample.status}
                if form_value not in allowed_statuses:
                    messages.error(request, f'Недопустимый статус: {form_value}')
                    continue

            if old_value != form_value:
                setattr(sample, field_code, form_value)
                updated_fields.append(column.name)
                changed_field_codes.add(field_code)

    # Пересчёт автополей при изменении зависимостей
    if changed_field_codes:
        _recalculate_auto_fields(sample, changed_field_codes)

    # Синхронизация: при отмене образца автоматически отменяем workshop_status
    if sample.manufacturing and sample.status == 'CANCELLED' and sample.workshop_status != 'CANCELLED':
        sample.workshop_status = WorkshopStatus.CANCELLED
        updated_fields.append('Статус в мастерской')

    sample.save()

    # Обрабатываем M2M-поля через промежуточные таблицы (после save)
    for field_code, column_name, selected_ids in m2m_updates:
        if handle_m2m_update(sample, field_code, selected_ids):
            updated_fields.append(column_name)

    return updated_fields


def handle_sample_save(request, sample):
    """Обрабатывает сохранение образца: сохраняет поля, показывает сообщение, делает redirect."""
    try:
        with transaction.atomic():
            updated_fields = save_sample_fields(request, sample)
            if updated_fields:
                messages.success(
                    request,
                    f'Образец успешно обновлён. Изменены поля: {", ".join(updated_fields)}'
                )
            else:
                messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка при сохранении образца %s', sample.id)
        messages.error(request, f'Ошибка при сохранении: {e}')

    return redirect('sample_detail', sample_id=sample.id)


def handle_m2m_update(sample, field_code, selected_ids):
    """
    Обновляет M2M связи (СИ, ИО, операторы, стандарты).
    Возвращает True если были изменения.
    """
    m2m_config = {
        'standards': (SampleStandard, 'standard_id'),  # ⭐ v3.13.0
        'measuring_instruments': (SampleMeasuringInstrument, 'equipment_id'),
        'testing_equipment': (SampleTestingEquipment, 'equipment_id'),
        'operators': (SampleOperator, 'user_id'),
        'manufacturing_measuring_instruments': (SampleManufacturingMeasuringInstrument, 'equipment_id'),
        'manufacturing_testing_equipment': (SampleManufacturingTestingEquipment, 'equipment_id'),
        'manufacturing_operators': (SampleManufacturingOperator, 'user_id'),
        'manufacturing_auxiliary_equipment': (SampleManufacturingAuxiliaryEquipment, 'equipment_id'),
        'auxiliary_equipment': (SampleAuxiliaryEquipment, 'equipment_id'),
    }

    config = m2m_config.get(field_code)
    if not config:
        return False

    through_model, id_field = config

    current_ids = set(
        through_model.objects.filter(sample=sample)
        .values_list(id_field, flat=True)
    )
    new_ids = set(int(id) for id in selected_ids if id)

    if current_ids == new_ids:
        return False

    through_model.objects.filter(sample=sample).delete()
    for obj_id in new_ids:
        through_model.objects.create(sample=sample, **{id_field: obj_id})

    # ⭐ v3.13.0: При изменении стандартов — пересчитать test_code/test_type
    if field_code == 'standards' and new_ids:
        from core.models import Standard
        first_standard = Standard.objects.filter(id__in=new_ids).order_by('id').first()
        if first_standard:
            sample.test_code = first_standard.test_code
            sample.test_type = first_standard.test_type
            sample.cipher = sample.generate_cipher()
            # Пересчёт pi_number если был автосгенерирован
            old_pi = sample.pi_number
            if old_pi and f"/{sample.sequence_number}-" in old_pi:
                sample.pi_number = sample.generate_pi_number()
            sample.save()

    return True

def _validate_trainee_for_draft(sample):
    """
    Проверяет, что среди назначенных испытателей есть хотя бы один
    не-стажёр. Вызывается при выпуске черновика протокола (draft_ready).

    Возвращает (is_valid: bool, error_message: str или None).
    """
    operator_ids = SampleOperator.objects.filter(
        sample=sample
    ).values_list('user_id', flat=True)

    if not operator_ids:
        return True, None

    operators = User.objects.filter(id__in=operator_ids, is_active=True)
    has_non_trainee = operators.filter(is_trainee=False).exists()

    if not has_non_trainee:
        return False, (
            'Невозможно выпустить черновик протокола: '
            'среди испытателей отсутствует аттестованный сотрудник. '
            'Добавьте наставника или другого аттестованного испытателя.'
        )

    return True, None

"""
CISIS — Утилиты для работы с полями образцов.

Содержит:
- get_field_info: получение информации о поле (значение, тип, choices, options)
- _get_foreignkey_options / _get_m2m_options: варианты для FK/M2M полей
- is_readonly_for_user: проверка readonly
- _validate_latin_only: валидация латиницы

⭐ v3.68.1: Фикс отображения оборудования
  - Приоритет sample.laboratory над user.laboratory при выборе лабы для фильтра
    (иначе сисадмин/QMS_ADMIN видят пустой список при просмотре чужого образца)
  - Fallback на всё оборудование лабы, если пересечение с accreditation_area пусто
    (ранее пользователь видел пустоту, когда для связки «лаба × область» не было
    записей в EquipmentAccreditationArea)
  - Для симметрии: аналогичный приоритет и в ветке User (операторы)
"""

from django.db import models
from django.utils.timezone import make_aware, localtime, is_aware
from django.core.exceptions import FieldDoesNotExist

from core.models import (
    Sample, Laboratory, Client, Contract,
    Standard, AccreditationArea, Equipment, EquipmentAccreditationArea,
    User, StandardLaboratory, StandardAccreditationArea,
)
from .constants import (
    ALLOWED_STATUSES_BY_ROLE, BASE_READONLY_FIELDS, LATIN_ONLY_REGEX,
)


# Сопоставление поля образца и типа оборудования (equipment_type в БД)
EQUIPMENT_TYPE_BY_FIELD = {
    'measuring_instruments':                'СИ',
    'manufacturing_measuring_instruments':  'СИ',
    'testing_equipment':                    'ИО',
    'manufacturing_testing_equipment':      'ИО',
    'auxiliary_equipment':                  'ВО',
    'manufacturing_auxiliary_equipment':    'ВО',
}


def get_allowed_statuses_for_role(role):
    """Возвращает список разрешённых статусов для роли."""
    return ALLOWED_STATUSES_BY_ROLE.get(role, ['CANCELLED'])


def _get_foreignkey_options(sample, field_obj, field_code, user):
    """Возвращает queryset доступных вариантов для ForeignKey-поля."""
    related_model = field_obj.related_model

    if related_model == Client:
        return Client.objects.filter(is_active=True).order_by('name')

    elif related_model == Contract:
        if sample.client:
            return Contract.objects.filter(
                client=sample.client, status='ACTIVE'
            ).order_by('-date')
        return Contract.objects.none()

    elif related_model == Laboratory:
        return Laboratory.objects.filter(
            is_active=True, department_type='LAB'
        ).order_by('name')

    elif related_model == AccreditationArea:
        return AccreditationArea.objects.filter(is_active=True).order_by('name')

    elif related_model == User:
        return User.objects.filter(
            laboratory=user.laboratory, is_active=True
        ).order_by('last_name', 'first_name')

    else:
        return related_model.objects.all()[:100]


def _get_equipment_options(sample, field_code, user):
    """
    Возвращает queryset оборудования для M2M-полей образца.

    Логика выбора лабы:
    - manufacturing_* → WORKSHOP + MI (оборудование мастерской + МИ)
    - обычные поля  → лаборатория ОБРАЗЦА (а не пользователя), иначе
                       пользователь не из этой лабы видел бы пустой список

    Фильтрация по accreditation_area с fallback:
    - если есть пересечение по области → возвращаем его
    - если пересечение пусто → возвращаем всё оборудование лабы,
      чтобы не блокировать пользователя пустым списком
    """
    is_manufacturing_field = field_code.startswith('manufacturing_')

    # --- 1. Определяем лабу для фильтра ---
    if is_manufacturing_field:
        workshop_lab = Laboratory.objects.filter(code='WORKSHOP').first()
        mi_lab = Laboratory.objects.filter(code='MI').first()
        lab_ids = [l.id for l in (workshop_lab, mi_lab) if l]
        if not lab_ids:
            return Equipment.objects.none()
        base_filter = {'laboratory_id__in': lab_ids, 'status': 'OPERATIONAL'}
    else:
        # ⭐ v3.68.1: Приоритет — лаборатория ОБРАЗЦА, не пользователя.
        # Сисадмин/QMS видят оборудование той лабы, где будет испытан образец.
        lab = sample.laboratory if sample.laboratory else user.laboratory
        if not lab:
            return Equipment.objects.none()
        base_filter = {'laboratory': lab, 'status': 'OPERATIONAL'}

    # --- 2. Фильтр по типу оборудования (СИ / ИО / ВО) ---
    equipment_type = EQUIPMENT_TYPE_BY_FIELD.get(field_code)
    if equipment_type:
        base_filter['equipment_type'] = equipment_type

    # --- 3. Пересечение с областью аккредитации (с fallback) ---
    if sample.accreditation_area and not is_manufacturing_field:
        equipment_ids = EquipmentAccreditationArea.objects.filter(
            accreditation_area=sample.accreditation_area
        ).values_list('equipment_id', flat=True)

        qs_with_area = Equipment.objects.filter(
            id__in=equipment_ids, **base_filter
        )

        # ⭐ v3.68.1: Если в связующей таблице нет записей для этой лабы и
        # области — показываем всё оборудование лабы. Иначе пользователь
        # видит пустой список при недозаполненной EquipmentAccreditationArea.
        if qs_with_area.exists():
            return qs_with_area.order_by('accounting_number')

    return Equipment.objects.filter(**base_filter).order_by('accounting_number')


def _get_operator_options(sample, field_code, user):
    """Возвращает queryset пользователей для полей операторов (M2M User)."""
    is_manufacturing_field = field_code.startswith('manufacturing_')

    if is_manufacturing_field:
        lab = Laboratory.objects.filter(code='WORKSHOP').first()
    else:
        # ⭐ v3.68.1: Приоритет — лаборатория ОБРАЗЦА (симметрично с оборудованием)
        lab = sample.laboratory if sample.laboratory else user.laboratory

    if not lab:
        return User.objects.none()

    return User.objects.filter(
        laboratory=lab, is_active=True
    ).order_by('last_name', 'first_name')


def _get_standard_options(sample):
    """Возвращает queryset стандартов с учётом лабы и области аккредитации образца."""
    qs = Standard.objects.filter(is_active=True)

    if sample.laboratory_id:
        lab_standard_ids = StandardLaboratory.objects.filter(
            laboratory_id=sample.laboratory_id
        ).values_list('standard_id', flat=True)
        qs = qs.filter(id__in=lab_standard_ids)

    if sample.accreditation_area_id:
        area_standard_ids = StandardAccreditationArea.objects.filter(
            accreditation_area_id=sample.accreditation_area_id
        ).values_list('standard_id', flat=True)
        qs = qs.filter(id__in=area_standard_ids)

    return qs.order_by('code')


def _get_m2m_options(sample, field_obj, field_code, user):
    """Возвращает queryset доступных вариантов для ManyToMany-поля."""
    related_model = field_obj.related_model

    if related_model == Equipment:
        return _get_equipment_options(sample, field_code, user)

    if related_model == User:
        return _get_operator_options(sample, field_code, user)

    # ⭐ v3.13.0: Standard теперь M2M
    if related_model == Standard:
        return _get_standard_options(sample)

    return related_model.objects.all()[:100]


def get_field_info(sample, field_code, user):
    """Получает информацию о поле: значение, тип, choices, options, help_text."""
    try:
        field_obj = Sample._meta.get_field(field_code)
    except FieldDoesNotExist:
        return {
            'value': None,
            'display_value': '—',
            'field_type': 'text',
        }

    value = getattr(sample, field_code, None)
    field_type = 'text'
    choices = None
    options = None
    display_value = value
    help_text = field_obj.help_text or None

    # --- ⭐ v3.32.0: Множественный выбор типа отчёта ---
    if field_code == 'report_type':
        field_type = 'multi_checkbox'
        choices = list(field_obj.choices)
        # value хранится как "PROTOCOL,PHOTO" (через запятую)
        selected = set(value.split(',')) if value else set()
        display_labels = [label for val, label in choices if val in selected]
        display_value = ', '.join(display_labels) if display_labels else '—'

    # --- Select (поля с choices) ---
    elif field_obj.choices:
        field_type = 'select'
        choices = list(field_obj.choices)

        if field_code == 'status':
            allowed = get_allowed_statuses_for_role(user.role)
            choices = [(k, v) for k, v in choices if k in allowed]
        elif field_code == 'workshop_status':
            choices.insert(0, ('', '—'))

        display_value = dict(field_obj.choices).get(value, value) if value else '—'

    # --- Boolean ---
    elif isinstance(field_obj, models.BooleanField):
        field_type = 'checkbox'
        display_value = 'Да' if value else 'Нет'

    # --- DateTime (проверяем ДО DateField, т.к. DateTimeField наследует DateField) ---
    elif isinstance(field_obj, models.DateTimeField):
        field_type = 'datetime'
        if value:
            if not is_aware(value):
                value = make_aware(value)
            display_value = localtime(value).strftime('%d.%m.%Y %H:%M')
        else:
            display_value = '—'

    # --- Date ---
    elif isinstance(field_obj, models.DateField):
        field_type = 'date'
        display_value = value.strftime('%d.%m.%Y') if value else '—'

    # --- ForeignKey ---
    elif isinstance(field_obj, models.ForeignKey):
        field_type = 'foreignkey'
        options = _get_foreignkey_options(sample, field_obj, field_code, user)
        display_value = str(value) if value else '—'

    # --- TextField ---
    elif isinstance(field_obj, models.TextField):
        field_type = 'textarea'
        if not value:
            display_value = '—'

    # --- ManyToMany ---
    elif isinstance(field_obj, models.ManyToManyField):
        field_type = 'manytomany'
        related_manager = getattr(sample, field_code)
        value = list(related_manager.all())
        options = _get_m2m_options(sample, field_obj, field_code, user)
        display_value = ', '.join(str(obj) for obj in value) if value else '—'

    # --- Integer ---
    elif isinstance(field_obj, models.IntegerField):
        field_type = 'number'
        if value is None:
            display_value = '—'

    # --- Остальные (CharField и т.д.) ---
    else:
        if not value:
            display_value = '—'

    return {
        'value': value,
        'display_value': display_value,
        'field_type': field_type,
        'choices': choices,
        'options': options,
        'help_text': help_text,
    }


def is_readonly_for_user(field_code, user):
    """Проверяет, является ли поле readonly для данного пользователя."""
    if field_code in BASE_READONLY_FIELDS:
        return True

    if field_code == 'workshop_status' and user.role == 'WORKSHOP':
        return True

    if field_code == 'manufacturing_completion_date':
        if user.role in ('WORKSHOP_HEAD', 'SYSADMIN'):
            return False
        return True

    return False


def _validate_latin_only(field_code, value):
    """
    Проверяет, что значение содержит только допустимые символы
    (латиница, цифры, - _ . / пробел).
    Возвращает (is_valid: bool, error_message: str или None).
    """
    if not value:
        return True, None

    if not LATIN_ONLY_REGEX.match(value):
        return False, (
            f'Поле содержит недопустимые символы (кириллица и др.). '
            f'Допустимы только латинские буквы, цифры и символы: - _ . /'
        )

    return True, None
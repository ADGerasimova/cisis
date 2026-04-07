"""
CISIS — Константы и конфигурация для модуля образцов.

Содержит:
- Разрешённые статусы по ролям
- Автополя и readonly-поля
- Конфигурация заморозки блоков
- Группы полей для «Создать + такой же»
- Зависимости автополей
- Столбцы журнала, фильтры, дефолты

⭐ v3.15.0: Добавлено влагонасыщение (MOISTURE_CONDITIONING)
"""

import re
from core.models import SampleStatus, WorkshopStatus

# ─────────────────────────────────────────────────────────────
# Regex для валидации полей «только латиница»
# ─────────────────────────────────────────────────────────────
LATIN_ONLY_REGEX = re.compile(r'^[A-Za-z0-9\-_./\s]*$')

# ─────────────────────────────────────────────────────────────
# Разрешённые статусы по ролям
# ─────────────────────────────────────────────────────────────

ALLOWED_STATUSES_BY_ROLE = {
    'CLIENT_MANAGER': [
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED', 'REPLACEMENT_PROTOCOL',
        'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
    ],
    'CLIENT_DEPT_HEAD': [
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED', 'REPLACEMENT_PROTOCOL',
        'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
    ],
    'LAB_HEAD': [
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED',
        'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
        'CONDITIONING', 'READY_FOR_TEST', 'IN_TESTING', 'TESTED',
        'DRAFT_READY', 'RESULTS_UPLOADED', 'PROTOCOL_ISSUED', 'COMPLETED',
        'REPLACEMENT_PROTOCOL',
    ],
    'TESTER': [
        'REGISTERED', 'MANUFACTURED', 'TRANSFERRED', 'REPLACEMENT_PROTOCOL',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
        'MANUFACTURING', 'CONDITIONING', 'READY_FOR_TEST',
        'IN_TESTING', 'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
    ],
    'WORKSHOP_HEAD': [
        'REGISTERED', 'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED', 'CANCELLED',
    ],
    'WORKSHOP': [
        'REGISTERED', 'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED', 'CANCELLED',
    ],
    'QMS_HEAD': [
        'DRAFT_READY', 'RESULTS_UPLOADED', 'PROTOCOL_ISSUED',
        'COMPLETED', 'CANCELLED', 'REPLACEMENT_PROTOCOL',
    ],
    'QMS_ADMIN': [
        'DRAFT_READY', 'RESULTS_UPLOADED', 'PROTOCOL_ISSUED',
        'COMPLETED', 'CANCELLED', 'REPLACEMENT_PROTOCOL',
    ],
    'SYSADMIN': [
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED',
        'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
        'CONDITIONING', 'READY_FOR_TEST', 'IN_TESTING', 'TESTED',
        'DRAFT_READY', 'RESULTS_UPLOADED', 'PROTOCOL_ISSUED', 'COMPLETED',
        'REPLACEMENT_PROTOCOL',
    ],
    'CTO': [
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED',
        'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
        'CONDITIONING', 'READY_FOR_TEST', 'IN_TESTING', 'TESTED',
        'DRAFT_READY', 'RESULTS_UPLOADED', 'PROTOCOL_ISSUED', 'COMPLETED',
        'REPLACEMENT_PROTOCOL',
    ],
    'CEO': [
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED',
        'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',  # ⭐ v3.15.0
        'CONDITIONING', 'READY_FOR_TEST', 'IN_TESTING', 'TESTED',
        'DRAFT_READY', 'RESULTS_UPLOADED', 'PROTOCOL_ISSUED', 'COMPLETED',
        'REPLACEMENT_PROTOCOL',
    ],
}

# ─────────────────────────────────────────────────────────────
# Автополя и readonly
# ─────────────────────────────────────────────────────────────

# Поля, которые заполняются автоматически и не редактируются через форму
AUTO_FIELDS = frozenset([
    'sequence_number', 'cipher', 'pi_number', 'deadline',
    'protocol_status', 'test_code', 'test_type', 'registration_date',
    'registered_by', 'verified_by', 'verified_at',
    'panel_id',
])

# DateTime-поля, автозаполняемые кнопками, но редактируемые для SYSADMIN/LAB_HEAD
DATETIME_AUTO_FIELDS = frozenset([
    'conditioning_start_datetime', 'conditioning_end_datetime',
    'testing_start_datetime', 'testing_end_datetime',
    'report_prepared_date', 'manufacturing_completion_date',
])

# Поля, всегда readonly в детальной карточке
BASE_READONLY_FIELDS = frozenset([
    'registered_by', 'verified_by', 'verified_at',
    'sequence_number', 'cipher', 'pi_number', 'deadline',
    'protocol_status', 'test_code', 'test_type',
    'panel_id',
])

# Действия, при которых перед сменой статуса сохраняются поля формы
STATUS_CHANGE_ACTIONS = frozenset([
    'complete_manufacturing', 'start_conditioning', 'ready_for_test',
    'start_testing', 'complete_test', 'draft_ready',
    'results_uploaded', 'protocol_issued', 'complete_sample',
    'complete_cutting_only',
    'accept_sample',
    'accept_from_moisture',  # ⭐ v3.15.0
])

# ─────────────────────────────────────────────────────────────
# Конфигурация заморозки блоков полей
# ─────────────────────────────────────────────────────────────

REGISTRATION_FIELDS = frozenset([
    'client', 'contract', 'contract_date', 'laboratory',
    'accompanying_doc_number',
    'accreditation_area', 'standards', 'test_code', 'test_type',
    'working_days', 'sample_received_date', 'object_info',
    'object_id', 'cutting_direction', 'test_conditions',
    'panel_id', 'material', 'preparation',
    'manufacturing', 'manufacturing_deadline', 'further_movement',
    'determined_parameters', 'sample_count',
    'additional_sample_count',
    'notes', 'admin_notes',
    'report_type',
    'uzk_required',
    'cutting_standard',  # ⭐ v3.15.0
    'moisture_conditioning', 'moisture_sample',  # ⭐ v3.15.0
    'replacement_protocol_required', 'replacement_pi_number',
    'acceptance_act',
])

WORKSHOP_FIELDS = frozenset([
    'workshop_status',
    'manufacturing_completion_date',
    'manufacturing_measuring_instruments',
    'manufacturing_testing_equipment',
    'manufacturing_auxiliary_equipment',
    'manufacturing_operators',
    'workshop_notes',
])

TESTER_FIELDS = frozenset([
    'conditioning_start_datetime',
    'conditioning_end_datetime',
    'testing_start_datetime',
    'testing_end_datetime',
    'report_prepared_date',
    'report_prepared_by',
    'operator_notes',
    'measuring_instruments',
    'testing_equipment',
    'auxiliary_equipment',
    'operators',
])

TESTER_FROZEN_STATUSES = frozenset([
    'DRAFT_READY', 'RESULTS_UPLOADED',
    'PROTOCOL_ISSUED', 'COMPLETED',
])

QMS_FIELDS = frozenset([
    'protocol_checked_by',
    'protocol_issued_date',
    'protocol_printed_date',
    'replacement_protocol_issued_date',
])

# ─────────────────────────────────────────────────────────────
# Роли
# ─────────────────────────────────────────────────────────────

QMS_ROLES = frozenset(['QMS_HEAD', 'QMS_ADMIN'])
WORKSHOP_ROLES = frozenset(['WORKSHOP_HEAD', 'WORKSHOP'])

REGISTRATION_UNFREEZE_ROLES = frozenset([
    'SYSADMIN', 'QMS_HEAD', 'QMS_ADMIN', 'LAB_HEAD',
    'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
])

# ─────────────────────────────────────────────────────────────
# Валидация латиницы
# ─────────────────────────────────────────────────────────────

LATIN_ONLY_FIELDS = frozenset([
    'object_id', 'accompanying_doc_number',
])
LATIN_ONLY_IF_MI = frozenset([
    'test_conditions',
])

# ─────────────────────────────────────────────────────────────
# Группы полей для «Создать + такой же» (v3.11.0)
# ─────────────────────────────────────────────────────────────

REPEAT_FIELD_GROUPS = {
    'basic': {
        'label': 'Лаборатория, заказчик, договор, рабочие дни',
        'fields': ['laboratory', 'client', 'contract', 'working_days'],
    },
    'doc': {
        'label': 'Сопроводительный документ + акт',
        'fields': ['accompanying_doc_number', 'acceptance_act'],
    },
    'testing': {
        'label': 'Область, стандарт, тип отчёта, параметры, кол-во',
        'fields': ['accreditation_area', 'standards', 'report_type',
                   'determined_parameters', 'sample_count', 'additional_sample_count'],
    },
    'object': {
        'label': 'Информация об объекте',
        'fields': ['object_id', 'cutting_direction', 'test_conditions',
                   'material', 'preparation', 'notes', 'object_info'],
        'warn': True,
    },
    'admin_notes': {
        'label': 'Примечания (мастерская + администратор)',
        'fields': ['workshop_notes', 'admin_notes'],
    },
    'manufacturing': {
        'label': 'Изготовление + влагонасыщение + дальнейшее движение',  # ⭐ v3.15.0: обновлено
        'fields': ['manufacturing', 'cutting_standard', 'moisture_conditioning', 'further_movement'],  # ⭐ v3.15.0
    },
}

# ─────────────────────────────────────────────────────────────
# Зависимости автополей (v3.12.0)
# ─────────────────────────────────────────────────────────────

AUTO_FIELD_DEPENDENCIES = {
    'accompanying_doc_number': {'cipher'},
    'object_id':               {'cipher', 'panel_id'},
    'test_conditions':         {'cipher'},
    'standards':                {'test_code', 'test_type', 'cipher', 'pi_number'},
    'laboratory':              {'pi_number'},
    'working_days':            {'deadline', 'manufacturing_deadline'},
    'sample_received_date':    {'deadline', 'manufacturing_deadline'},
    'manufacturing':           {'manufacturing_deadline', 'panel_id'},
    'further_movement':        {'manufacturing_deadline'},
}

# ─────────────────────────────────────────────────────────────
# Столбцы журнала
# ─────────────────────────────────────────────────────────────

JOURNAL_DISPLAYABLE_COLUMNS = [
    ('sequence_number', '№ п/п'),
    ('registration_date', 'Дата регистрации'),
    ('laboratory', 'Лаборатория'),
    ('cipher', 'Шифр'),
    ('client', 'Заказчик'),
    ('contract', 'Договор'),
    ('contract_date', 'Дата договора'),
    ('standards', 'Стандарт'),
    ('test_type', 'Тип испытания'),
    ('test_code', 'Код испытания'),
    ('accreditation_area', 'Область аккредитации'),
    ('object_info', 'Информация об объекте'),
    ('object_id', 'ID объекта'),
    ('cutting_direction', 'Направление вырезки'),
    ('test_conditions', 'Условия испытания'),
    ('panel_id', 'ID панели'),
    ('material', 'Материал'),
    ('preparation', 'Пробоподготовка'),
    ('determined_parameters', 'Определяемые параметры'),
    ('sample_count', 'Кол-во образцов'),
    ('additional_sample_count', 'Доп. образцы'),
    ('notes', 'Примечания'),
    ('workshop_notes', 'Примечания мастерской'),
    ('admin_notes', 'Комментарии'),
    ('working_days', 'Рабочих дней'),
    ('deadline', 'Срок выполнения'),
    ('manufacturing_deadline', 'Срок изготовления'),
    ('report_type', 'Отчётность'),
    ('pi_number', '№ ПИ'),
    ('manufacturing', 'Изготовление'),
    ('moisture_conditioning', 'Влагонасыщение'),  # ⭐ v3.15.0
    ('moisture_sample', 'Образец влагонасыщения'),  # ⭐ v3.15.0
    ('uzk_required', 'УЗК'),
    ('cutting_standard', 'Стандарт на нарезку'),  # ⭐ v3.15.0
    ('further_movement', 'Дальнейшее движение'),
    ('registered_by', 'Зарегистрировал'),
    ('verified_by', 'Проверил'),
    ('operators', 'Операторы'),
    ('workshop_status', 'Статус мастерской'),
    ('status', 'Статус'),
    ('conditioning_start_datetime', 'Начало конд.'),
    ('conditioning_end_datetime', 'Конец конд.'),
    ('testing_start_datetime', 'Начало испытания'),
    ('testing_end_datetime', 'Конец испытания'),
    ('manufacturing_completion_date', 'Дата изготовления'),
    ('report_prepared_date', 'Дата подготовки отчёта'),
    ('report_prepared_by', 'Подготовил отчёт'),
    ('operator_notes', 'Комментарий испытателя'),
    ('protocol_checked_by', 'Проверил (СМК)'),
    ('protocol_issued_date', 'Дата выпуска протокола'),
    ('protocol_printed_date', 'Дата печати протокола'),
    ('replacement_protocol_required', 'Замещающий протокол'),
    ('replacement_pi_number', '№ замещающего ПИ'),
    ('replacement_protocol_issued_date', 'Дата замещ. протокола'),
    ('sample_received_date', 'Дата получения'),
    ('accompanying_doc_number', '№ сопр. документа'),
    ('acceptance_act', 'Акт приёма-передачи'),
]

DISPLAYABLE_COLUMNS_DICT = dict(JOURNAL_DISPLAYABLE_COLUMNS)

DEFAULT_COLUMNS_BY_ROLE = {
    'CLIENT_MANAGER': [
        'registration_date', 'laboratory', 'cipher', 'client', 'contract',
        'standards', 'test_type', 'deadline', 'registered_by', 'verified_by', 'status',
    ],
    'CLIENT_DEPT_HEAD': [
        'registration_date', 'laboratory', 'cipher', 'client', 'contract',
        'standards', 'test_type', 'deadline', 'registered_by', 'verified_by', 'status',
    ],
    'SYSADMIN': [
        'registration_date', 'laboratory', 'cipher', 'client', 'contract',
        'standards', 'test_type', 'deadline', 'registered_by', 'verified_by', 'status',
    ],
    'QMS_HEAD': [
        'registration_date', 'laboratory', 'cipher', 'client', 'standards',
        'test_type', 'pi_number', 'operators', 'protocol_checked_by', 'status',
    ],
    'QMS_ADMIN': [
        'registration_date', 'laboratory', 'cipher', 'client', 'standards',
        'test_type', 'pi_number', 'operators', 'protocol_checked_by', 'status',
    ],
    'LAB_HEAD': [
        'registration_date', 'cipher', 'client', 'standards', 'test_type',
        'deadline', 'registered_by', 'verified_by', 'operators', 'status',
    ],
    'WORKSHOP_HEAD': [
        'registration_date', 'cipher', 'laboratory', 'manufacturing_deadline',
        'standards', 'workshop_status',
    ],
    'WORKSHOP': [
        'registration_date', 'cipher', 'laboratory', 'manufacturing_deadline',
        'standards', 'workshop_status',
    ],
    '_default': [
        'registration_date', 'accreditation_area', 'cipher', 'standards',
        'test_type', 'deadline', 'operators', 'status',
    ],
}

FILTERABLE_COLUMNS = {
    'status': {'type': 'select', 'label': 'Статус'},
    'workshop_status': {'type': 'select', 'label': 'Статус мастерской'},
    'laboratory': {'type': 'select', 'label': 'Лаборатория'},
    'client': {'type': 'select', 'label': 'Заказчик'},
    'contract': {'type': 'select', 'label': 'Договор'},
    'standards': {'type': 'select', 'label': 'Стандарт'},
    'accreditation_area': {'type': 'select', 'label': 'Область аккредитации'},
    'test_type': {'type': 'select', 'label': 'Тип испытания'},
    'report_type': {'type': 'select', 'label': 'Отчётность'},
    'further_movement': {'type': 'select', 'label': 'Дальнейшее движение'},
    'registered_by': {'type': 'select', 'label': 'Зарегистрировал'},
    'verified_by': {'type': 'select_nullable', 'label': 'Проверил'},
    'manufacturing': {'type': 'boolean', 'label': 'Изготовление'},
    'moisture_conditioning': {'type': 'boolean', 'label': 'Влагонасыщение'},  # ⭐ v3.15.0
    'uzk_required': {'type': 'boolean', 'label': 'УЗК'},
    'registration_date': {'type': 'date_range', 'label': 'Дата регистрации'},
    'deadline': {'type': 'date_range', 'label': 'Срок выполнения'},
    'manufacturing_deadline': {'type': 'date_range', 'label': 'Срок изготовления'},
    'cipher': {'type': 'text', 'label': 'Шифр'},
    'object_id': {'type': 'text', 'label': 'ID объекта'},
    'pi_number': {'type': 'text', 'label': '№ ПИ'},
    'accompanying_doc_number': {'type': 'text', 'label': '№ сопр. документа'},
    'acceptance_act': {'type': 'select', 'label': 'Акт приёма-передачи'},
}

ITEMS_PER_PAGE = 50
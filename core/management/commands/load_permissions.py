"""
Management command для заполнения journal_columns и role_permissions.

Запуск:
    python manage.py load_permissions

Что делает:
    1. Заполняет journal_columns — список столбцов для каждого журнала
    2. Заполняет role_permissions — права каждой роли к каждому столбцу

Логика прав (из variables_reference):
    - SYSADMIN — EDIT на всё
    - ADMIN — EDIT на журнал образцов (блок регистрации), VIEW на остальное
    - LAB_HEAD — EDIT почти на всё, кроме скрытых от испытателя полей (VIEW)
    - TESTER — скрытые поля = NONE, свои поля = EDIT, остальное = VIEW
    - QMS / QMS_HEAD — VIEW на образцы, EDIT на блок СМК
    - WORKSHOP — VIEW на образцы, EDIT на журнал мастерской
    - OTHER — NONE на всё
"""

from django.core.management.base import BaseCommand
from core.models import Journal, JournalColumn, RolePermission


# ---------------------------------------------------------------------
# СТОЛБЦЫ ЖУРНАЛОВ
# ---------------------------------------------------------------------
# Каждый элемент: (код поля, название, порядок отображения)
# ---------------------------------------------------------------------

SAMPLES_COLUMNS = [
    # Блок «Регистрация»
    ('sequence_number',                 '№ п/п',                                                          1),
    ('client',                          'Заказчик',                                                       2),
    ('contract',                        'Договор / счёт №',                                               3),
    ('contract_date',                   'Дата договора / счёта',                                          4),
    ('laboratory',                      'Код лаборатории',                                                5),
    ('accompanying_doc_number',         '№ сопроводительной документации',                                6),
    ('accompanying_doc_full_name',      'Полное название сопроводительной документации',                  7),
    ('accreditation_area',              'Область аккредитации',                                           8),
    ('standard',                        'Стандарт',                                                       9),
    ('test_code',                       'Код испытания',                                                 10),
    ('test_type',                       'Тип испытания',                                                 11),
    ('working_days',                    'Рабочих дней на выполнение работ',                              12),
    ('registration_date',               'Дата регистрации',                                              13),
    ('sample_received_date',            'Дата получения образца',                                        14),
    ('object_info',                     'Информация об объекте испытаний',                               15),
    ('object_id',                       'ID объекта испытаний',                                          16),
    ('cutting_direction',               'Направление вырезки / армирования',                             17),
    ('test_conditions',                 'Условия испытания',                                             18),
    ('panel_id',                        'Идентификационный номер панели',                                19),
    ('material',                        'Материал',                                                      20),
    ('cipher',                          'Идентификационный номер образца',                                21),
    ('preparation_required',            'Пробоподготовка',                                               22),
    ('determined_parameters',           'Определяемые параметры / кол-во образцов',                       23),
    ('admin_notes',                     'Примечания (администратор)',                                    24),
    ('deadline',                        'Срок выполнения',                                               25),
    ('report_type',                     'Отчётность',                                                    26),
    ('pi_number',                       '№ ПИ',                                                          27),
    ('manufacturing',                   'Изготовление',                                                  28),
    ('uzk_required',                    'Необходимость УЗК',                                             29),
    ('further_movement',                'Дальнейшее движение образцов',                                   30),
    ('registered_by',                   'Ответственный за регистрацию',                                  31),
    ('replacement_protocol_required',   'Необходимость замещающего протокола',                           32),
    ('replacement_pi_number',           '№ замещающего ПИ',                                              33),
    # Блок «Испытатель»
    ('test_status',                     'Статус испытания',                                              34),
    ('measuring_instruments',           'СИ — Средства измерения',                                       35),
    ('testing_equipment',               'ИО — Испытательное оборудование',                               36),
    ('test_date',                       'Дата испытания',                                                37),
    ('operators',                       'Операторы',                                                     38),
    ('report_status',                   'Отметка об отчётности',                                         39),
    ('report_prepared_date',            'Дата подготовки отчётности',                                    40),
    ('report_preparers',                'Подготовили отчётность',                                        41),  # ⭐ v3.84.0: было 'report_prepared_by' (FK)
    ('operator_notes',                  'Комментарий (испытатель)',                                      42),
    # Блок «СМК»
    ('registration_checked_by',         'Проверку регистрации провёл',                                    43),
    ('protocol_issued_date',            'Дата выпуска протокола',                                         44),
    ('protocol_printed_date',           'Дата печати протокола',                                          45),
    ('replacement_protocol_issued_date','Дата выпуска замещающего протокола',                             46),
]

EQUIPMENT_COLUMNS = [
    ('accounting_number',        'Учётный номер',                                        1),
    ('equipment_type',           'Вид',                                                  2),
    ('ownership',                'Принадлежность',                                       3),
    ('ownership_doc_number',     '№ УПД / № договора аренды',                            4),
    ('accreditation_areas',      'Область аккредитации',                                 5),
    ('name',                     'Наименование оборудования',                            6),
    ('manufacturer',             'Производитель',                                        7),
    ('year_of_manufacture',      'Год выпуска',                                          8),
    ('factory_number',           'Заводской номер',                                      9),
    ('inventory_number',         'Инвентарный номер',                                   10),
    ('condition_on_receipt',     'Состояние на момент получения',                       11),
    ('commissioning_info',       'Дата ввода в эксплуатацию + номер акта ввода',         12),
    ('technical_documentation',  'ТД (техническая документация)',                       13),
    ('intended_use',             'Назначение',                                          14),
    ('metrology_doc',            'Нормативный документ по МО / МП',                     15),
    ('state_registry_number',    'Номер СИ в госреестре',                               16),
    ('technical_specs',          'Технические характеристики',                          17),
    ('software',                 'Программное обеспечение',                             18),
    ('operating_conditions',     'Условия эксплуатации оборудования',                   19),
    ('laboratory',               'Лаборатория',                                         20),
    ('responsible_person',       'Ответственный',                                       21),
    ('substitute_person',        'Замещающий',                                          22),
    ('metrology_interval',       'Периодичность МО, мес.',                              23),
    ('modifications',            'Модификации',                                         24),
    ('notes',                    'Примечание',                                          25),
    ('status',                   'Текущее состояние',                                   26),
    ('files_path',               'Путь к папке с документацией',                        27),
]

CLIMATE_LOG_COLUMNS = [
    ('laboratory',   'Лаборатория',          1),
    ('measured_at',  'Дата и время замера',  2),
    ('temperature',  'Температура °C',       3),
    ('humidity',     'Влажность %',          4),
    ('measured_by',  'Кто измерил',          5),
    ('notes',        'Примечание',           6),
]

WEIGHT_LOG_COLUMNS = [
    ('sample',      'Образец',               1),
    ('measured_at', 'Дата и время замера',   2),
    ('weight',      'Масса, г',              3),
    ('test_type',   'Тип испытания',         4),
    ('measured_by', 'Кто измерил',           5),
    ('equipment',   'Оборудование',          6),
    ('notes',       'Примечание',            7),
]

WORKSHOP_LOG_COLUMNS = [
    ('sample',         'Образец',                  1),
    ('operator',       'Оператор',                2),
    ('operation_date', 'Дата операции',           3),
    ('operation_type', 'Тип операции',            4),
    ('equipment',      'Оборудование',            5),
    ('cutting_params', 'Параметры обработки',     6),
    ('quantity',       'Количество',              7),
    ('quality_check',  'Контроль качества',       8),
    ('notes',          'Примечание',              9),
]

TIME_LOG_COLUMNS = [
    ('employee',   'Сотрудник',        1),
    ('date',       'Дата',             2),
    ('start_time', 'Начало работы',    3),
    ('end_time',   'Конец работы',     4),
    ('work_type',  'Тип работы',       5),
    ('sample',     'Образец',           6),
    ('notes',      'Примечание',       7),
]

CLIENTS_COLUMNS = [
    ('name',      'Название организации',  1),
    ('inn',       'ИНН',                   2),
    ('address',   'Адрес',                 3),
    ('is_active', 'Активен',              4),
]


# ---------------------------------------------------------------------
# ПРАВА ДОСТУПА по ролям
# ---------------------------------------------------------------------
# Для каждого журнала: словарь {код_столбца: {роль: уровень_доступа}}
#
# Поля, скрытые от испытателя (из variables_reference, раздел 9):
#   client, contract, contract_date,
#   accompanying_doc_number, accompanying_doc_full_name,
#   object_info, object_id, registered_by,
#   replacement_protocol_required, replacement_pi_number, pi_number
# ---------------------------------------------------------------------

# Поля, скрытые от испытателя
TESTER_HIDDEN = {
    'client', 'contract', 'contract_date',
    'accompanying_doc_number', 'accompanying_doc_full_name',
    'object_info', 'object_id', 'registered_by',
    'replacement_protocol_required', 'replacement_pi_number', 'pi_number',
}

# Поля, которые испытатель редактирует (блок «Испытатель»)
TESTER_EDIT = {
    'test_status', 'measuring_instruments', 'testing_equipment',
    'test_date', 'operators', 'report_status',
    'report_prepared_date', 'report_preparers', 'operator_notes',  # ⭐ v3.84.0: было 'report_prepared_by'
}

# Блок СМК — редактируют QMS и QMS_HEAD
QMS_EDIT = {
    'registration_checked_by', 'protocol_issued_date',
    'protocol_printed_date', 'replacement_protocol_issued_date',
}


def get_samples_permissions():
    """Генерирует права для журнала SAMPLES для каждой роли и столбца."""
    perms = {}  # {код_столбца: {роль: уровень}}

    all_columns = [col[0] for col in SAMPLES_COLUMNS]

    for col in all_columns:
        perms[col] = {
            'SYSADMIN': 'EDIT',
            'ADMIN':    'EDIT',
            'LAB_HEAD': 'EDIT',
            'QMS_HEAD': 'VIEW',
            'QMS':      'VIEW',
            'WORKSHOP': 'VIEW',
            'OTHER':    'NONE',
        }

        # TESTER: скрытые = NONE, свои = EDIT, остальное = VIEW
        if col in TESTER_HIDDEN:
            perms[col]['TESTER'] = 'NONE'
        elif col in TESTER_EDIT:
            perms[col]['TESTER'] = 'EDIT'
        else:
            perms[col]['TESTER'] = 'VIEW'

        # QMS и QMS_HEAD — EDIT на блок СМК
        if col in QMS_EDIT:
            perms[col]['QMS']      = 'EDIT'
            perms[col]['QMS_HEAD'] = 'EDIT'

        # WORKSHOP — EDIT только на manufacturing
        if col == 'manufacturing':
            perms[col]['WORKSHOP'] = 'EDIT'

    return perms


def get_simple_permissions(columns, edit_roles=None):
    """
    Генерирует права для простых журналов (не SAMPLES).
    edit_roles — список ролей, которым дан EDIT. Остальные = VIEW или NONE.
    """
    if edit_roles is None:
        edit_roles = ['SYSADMIN']

    perms = {}
    for col in columns:
        col_code = col[0]
        perms[col_code] = {}
        for role in ['SYSADMIN', 'ADMIN', 'LAB_HEAD', 'TESTER', 'QMS_HEAD', 'QMS', 'WORKSHOP', 'OTHER']:
            if role in edit_roles:
                perms[col_code][role] = 'EDIT'
            elif role == 'OTHER':
                perms[col_code][role] = 'NONE'
            else:
                perms[col_code][role] = 'VIEW'
    return perms


# ---------------------------------------------------------------------
# КОНФИГУРАЦИЯ ЖУРНАЛОВ
# ---------------------------------------------------------------------
# (код журнала, список столбцов, функция генерации прав)
# ---------------------------------------------------------------------

JOURNALS_CONFIG = [
    ('SAMPLES',      SAMPLES_COLUMNS,      lambda: get_samples_permissions()),
    ('EQUIPMENT',    EQUIPMENT_COLUMNS,     lambda: get_simple_permissions(EQUIPMENT_COLUMNS, edit_roles=['SYSADMIN', 'LAB_HEAD'])),
    ('CLIMATE_LOG',  CLIMATE_LOG_COLUMNS,   lambda: get_simple_permissions(CLIMATE_LOG_COLUMNS, edit_roles=['SYSADMIN', 'TESTER', 'LAB_HEAD'])),
    ('WEIGHT_LOG',   WEIGHT_LOG_COLUMNS,    lambda: get_simple_permissions(WEIGHT_LOG_COLUMNS, edit_roles=['SYSADMIN', 'TESTER', 'LAB_HEAD'])),
    ('WORKSHOP_LOG', WORKSHOP_LOG_COLUMNS,  lambda: get_simple_permissions(WORKSHOP_LOG_COLUMNS, edit_roles=['SYSADMIN', 'WORKSHOP', 'LAB_HEAD'])),
    ('TIME_LOG',     TIME_LOG_COLUMNS,      lambda: get_simple_permissions(TIME_LOG_COLUMNS, edit_roles=['SYSADMIN', 'TESTER', 'LAB_HEAD', 'WORKSHOP'])),
    ('CLIENTS',      CLIENTS_COLUMNS,       lambda: get_simple_permissions(CLIENTS_COLUMNS, edit_roles=['SYSADMIN', 'ADMIN'])),
]


class Command(BaseCommand):
    help = 'Заполнение journal_columns и role_permissions'

    def handle(self, *args, **options):
        self.stdout.write('--- Начало загрузки прав доступа ---\n')

        for journal_code, columns, get_perms in JOURNALS_CONFIG:
            self.stdout.write(f'\n  Журнал: {journal_code}')

            try:
                journal = Journal.objects.get(code=journal_code)
            except Journal.DoesNotExist:
                self.stdout.write(f'    ❌ Журнал {journal_code} не найден в таблице journals!')
                continue

            # 1. Заполняем journal_columns
            col_objects = {}  # {код: объект JournalColumn}
            for code, name, order in columns:
                obj, created = JournalColumn.objects.get_or_create(
                    journal=journal,
                    code=code,
                    defaults={'name': name, 'display_order': order, 'is_active': True},
                )
                col_objects[code] = obj
                if created:
                    self.stdout.write(f'    + столбец: {code}')

            # 2. Заполняем role_permissions
            perms = get_perms()
            for col_code, role_levels in perms.items():
                column = col_objects.get(col_code)
                if not column:
                    continue
                for role, access_level in role_levels.items():
                    RolePermission.objects.get_or_create(
                        role=role,
                        journal=journal,
                        column=column,
                        defaults={'access_level': access_level},
                    )

            # Считаем итог для этого журнала
            col_count  = JournalColumn.objects.filter(journal=journal).count()
            perm_count = RolePermission.objects.filter(journal=journal).count()
            self.stdout.write(f'    ✓ столбцов: {col_count}, записей прав: {perm_count}')

        self.stdout.write('\n--- Загрузка прав доступа завершена ---\n')
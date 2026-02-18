"""
Management command для загрузки тестовых данных.

Запуск:
    python manage.py load_test_data

Что загружает:
    - 3 лаборатории
    - 3 заказчика с контактами и договорами
    - 5 стандартов с связями к областям аккредитации
    - 2 области аккредитации (+ «Вне области» уже есть)
    - 6 единиц оборудования
    - РАСШИРЕННЫЙ список пользователей (руководители + сотрудники по отделам/лабам)
    - праздники на 2026 год

Можно запускать несколько раз безопасно — если данные уже есть, они не дублируются.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password

from core.models import (
    Laboratory,
    Client,
    ClientContact,
    Contract,
    AccreditationArea,
    Standard,
    StandardAccreditationArea,
    Holiday,
    Equipment,
    EquipmentAccreditationArea,
    User,
)


class Command(BaseCommand):
    help = 'Загрузка тестовых данных в CISIS'

    def handle(self, *args, **options):
        self.stdout.write('--- Начало загрузки тестовых данных ---\n')

        self._load_laboratories()
        self._load_accreditation_areas()
        self._load_standards()
        self._load_clients()
        self._load_users()
        self._load_equipment()
        self._load_holidays()

        self.stdout.write('\n--- Загрузка завершена ---\n')

    # ─────────────────────────────────────────────────────────────────
    # ЛАБОРАТОРИИ
    # ─────────────────────────────────────────────────────────────────

    def _load_laboratories(self):
        labs = [
            {'name': 'Механические испытания',         'code': 'MI',  'code_display': 'МИ'},
            {'name': 'Химический анализ',              'code': 'ChA', 'code_display': 'ХА'},
            {'name': 'Технический анализ',             'code': 'TA',  'code_display': 'ТА'},
            {'name': 'Ускоренные климатические испытания', 'code': 'ACT', 'code_display': 'УКИ'},
        ]

        for lab_data in labs:
            obj, created = Laboratory.objects.update_or_create(
                code=lab_data['code'],
                defaults=lab_data
            )
            self.stdout.write(f'  Лаборатория: {obj.code_display} — {"создана" if created else "обновлена"}')

    # ─────────────────────────────────────────────────────────────────
    # ОБЛАСТИ АККРЕДИТАЦИИ
    # ─────────────────────────────────────────────────────────────────

    def _load_accreditation_areas(self):
        # «Вне области» уже создана через INSERT в schema.sql, пропускаем
        areas = [
            {'code': 'MECH',  'name': 'Механические испытания',  'description': 'Прочность, деформация, разрушение'},
            {'code': 'THERM', 'name': 'Термические испытания',   'description': 'Термогравиметрия, термоанализ'},
        ]
        for area in areas:
            obj, created = AccreditationArea.objects.get_or_create(code=area['code'], defaults=area)
            self.stdout.write(f'  Область аккредитации: {obj.code} — {"создана" if created else "уже есть"}')

    # ─────────────────────────────────────────────────────────────────
    # СТАНДАРТЫ
    # ─────────────────────────────────────────────────────────────────

    def _load_standards(self):
        standards = [
            {'code': 'ГОСТ 1234-56', 'name': 'Определение предельной прочности при растяжении', 'test_code': 'TEN', 'test_type': 'Растяжение'},
            {'code': 'ГОСТ 2345-67', 'name': 'Определение твёрдости по Роквелу',                'test_code': 'HRC', 'test_type': 'Испытание на твёрдость'},
            {'code': 'ГОСТ 3456-78', 'name': 'Термогравиметрический анализ',                    'test_code': 'TGA', 'test_type': 'Термогравиметрия'},
            {'code': 'ГОСТ 4567-89', 'name': 'Определение коэффициента теплового расширения',   'test_code': 'CTE', 'test_type': 'Термический анализ'},
            {'code': 'ГОСТ 5678-90', 'name': 'Испытание на ударный изгиб',                      'test_code': 'IMP', 'test_type': 'Ударные испытания'},
        ]

        # Связь стандарт → область аккредитации
        # TEN, HRC, IMP → MECH;  TGA, CTE → THERM
        area_map = {
            'TEN': 'MECH',
            'HRC': 'MECH',
            'IMP': 'MECH',
            'TGA': 'THERM',
            'CTE': 'THERM',
        }

        for std in standards:
            obj, created = Standard.objects.get_or_create(code=std['code'], defaults=std)
            self.stdout.write(f'  Стандарт: {obj.code} — {"создан" if created else "уже есть"}')

            # Привязываем к области аккредитации
            area_code = area_map.get(obj.test_code)
            if area_code:
                area = AccreditationArea.objects.get(code=area_code)
                StandardAccreditationArea.objects.get_or_create(
                    standard=obj,
                    accreditation_area=area,
                )

    # ─────────────────────────────────────────────────────────────────
    # ЗАКАЗЧИКИ
    # ─────────────────────────────────────────────────────────────────

    def _load_clients(self):
        clients = [
            {
                'name': 'ООО «Стальтехnika»',
                'inn': '770012345678',
                'address': 'г. Москва, ул. Промышленная, д. 10',
                'contacts': [
                    {'full_name': 'Иванов Иван Иванович',   'position': 'Генеральный директор', 'phone': '+7 (999) 111-11-11', 'is_primary': True},
                    {'full_name': 'Петров Пётр Петрович',    'position': 'Инженер-технолог',     'phone': '+7 (999) 222-22-22', 'is_primary': False},
                ],
                'contracts': [
                    {'number': 'ДГ-2026-001', 'date': '2026-01-15', 'status': 'ACTIVE', 'notes': 'Годовой договор'},
                ],
            },
            {
                'name': 'АО «Термоматериалы»',
                'inn': '771123456789',
                'address': 'г. Санкт-Петербург, пр. Индустриальный, д. 5',
                'contacts': [
                    {'full_name': 'Сидорова Марина Геннадьевна', 'position': 'Заменитель директора', 'phone': '+7 (812) 333-33-33', 'is_primary': True},
                ],
                'contracts': [
                    {'number': 'ДГ-2026-002', 'date': '2026-01-20', 'status': 'ACTIVE', 'notes': ''},
                ],
            },
            {
                'name': 'ФГБУ «НИИ Материалов»',
                'inn': '772234567890',
                'address': 'г. Нижний Новгород, ул. Научная, д. 3',
                'contacts': [
                    {'full_name': 'Козлов Алексей Юрьевич',  'position': 'Начальник лаб.',      'phone': '+7 (831) 444-44-44', 'is_primary': True},
                    {'full_name': 'Новикова Ольга Игоревна',  'position': 'Экспедитор',          'phone': '+7 (831) 555-55-55', 'is_primary': False},
                ],
                'contracts': [
                    {'number': 'ДГ-2025-010', 'date': '2025-06-01', 'end_date': '2025-12-31', 'status': 'EXPIRED', 'notes': 'Истёк, возможно продление'},
                    {'number': 'ДГ-2026-003', 'date': '2026-01-25', 'status': 'ACTIVE',       'notes': 'Новый договор на 2026'},
                ],
            },
        ]

        for client_data in clients:
            contacts = client_data.pop('contacts')
            contracts = client_data.pop('contracts')

            client, created = Client.objects.get_or_create(inn=client_data['inn'], defaults=client_data)
            self.stdout.write(f'  Заказчик: {client.name} — {"создан" if created else "уже есть"}')

            # Контакты
            for contact in contacts:
                ClientContact.objects.get_or_create(
                    client=client,
                    full_name=contact['full_name'],
                    defaults=contact,
                )

            # Договоры
            for contract in contracts:
                Contract.objects.get_or_create(
                    client=client,
                    number=contract['number'],
                    defaults=contract,
                )

    # ─────────────────────────────────────────────────────────────────
    # ПОЛЬЗОВАТЕЛИ (РАСШИРЕННЫЙ СПИСОК)
    # ─────────────────────────────────────────────────────────────────

    def _load_users(self):
        mi_lab  = Laboratory.objects.get(code='MI')   # латиница
        cha_lab = Laboratory.objects.get(code='ChA')  # латиница
        ta_lab  = Laboratory.objects.get(code='TA')   # латиница
        act_lab = Laboratory.objects.get(code='ACT')  # латиница - УКИ

        users = [
            # ══════════════════════════════════════════════════════════
            # РУКОВОДСТВО (по 1 человеку)
            # ══════════════════════════════════════════════════════════
            {
                'username': 'ceo',
                'first_name': 'Александр',
                'last_name': 'Волков',
                'email': 'volkov@cisis.ru',
                'role': 'CEO',
                'laboratory': None,
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'cto',
                'first_name': 'Михаил',
                'last_name': 'Новиков',
                'email': 'novikov@cisis.ru',
                'role': 'CTO',
                'laboratory': None,
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'sysadmin',
                'first_name': 'Дмитрий',
                'last_name': 'Белов',
                'email': 'belov@cisis.ru',
                'role': 'SYSADMIN',
                'laboratory': None,
                'is_staff': True,
                'is_superuser': True,
            },

            # ══════════════════════════════════════════════════════════
            # ЗАВЕДУЮЩИЕ ЛАБОРАТОРИЯМИ (по 1 на лабу)
            # ══════════════════════════════════════════════════════════
            {
                'username': 'ivanov_head',
                'first_name': 'Иван',
                'last_name': 'Иванов',
                'email': 'ivanov@cisis.ru',
                'role': 'LAB_HEAD',
                'laboratory': mi_lab,
                'is_staff': True,
            },
            {
                'username': 'petrov_head',
                'first_name': 'Пётр',
                'last_name': 'Петров',
                'email': 'petrov@cisis.ru',
                'role': 'LAB_HEAD',
                'laboratory': cha_lab,
                'is_staff': True,
            },
            {
                'username': 'sidorov_head',
                'first_name': 'Сергей',
                'last_name': 'Сидоров',
                'email': 'sidorov@cisis.ru',
                'role': 'LAB_HEAD',
                'laboratory': ta_lab,
                'is_staff': True,
            },
            {
                'username': 'alexeev_head',
                'first_name': 'Николай',
                'last_name': 'Алексеев',
                'email': 'alexeev@cisis.ru',
                'role': 'LAB_HEAD',
                'laboratory': act_lab,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # ИСПЫТАТЕЛИ (по 2-3 на лабу)
            # ══════════════════════════════════════════════════════════
            # Лаб МИ
            {
                'username': 'kuznetsova',
                'first_name': 'Алёна',
                'last_name': 'Кузнецова',
                'email': 'kuznetsova@cisis.ru',
                'role': 'TESTER',
                'laboratory': mi_lab,
                'is_staff': True,
            },
            {
                'username': 'sokolov',
                'first_name': 'Дмитрий',
                'last_name': 'Соколов',
                'email': 'sokolov@cisis.ru',
                'role': 'TESTER',
                'laboratory': mi_lab,
                'is_staff': True,
            },
            {
                'username': 'morozov',
                'first_name': 'Игорь',
                'last_name': 'Морозов',
                'email': 'morozov@cisis.ru',
                'role': 'TESTER',
                'laboratory': mi_lab,
                'is_staff': True,
            },
            # Лаб ХА
            {
                'username': 'volkova',
                'first_name': 'Елена',
                'last_name': 'Волкова',
                'email': 'volkova@cisis.ru',
                'role': 'TESTER',
                'laboratory': cha_lab,
                'is_staff': True,
            },
            {
                'username': 'lebedev',
                'first_name': 'Андрей',
                'last_name': 'Лебедев',
                'email': 'lebedev@cisis.ru',
                'role': 'TESTER',
                'laboratory': cha_lab,
                'is_staff': True,
            },
            # Лаб ТА
            {
                'username': 'smirnova',
                'first_name': 'Ольга',
                'last_name': 'Смирнова',
                'email': 'smirnova@cisis.ru',
                'role': 'TESTER',
                'laboratory': ta_lab,
                'is_staff': True,
            },
            {
                'username': 'kozlov',
                'first_name': 'Максим',
                'last_name': 'Козлов',
                'email': 'kozlov@cisis.ru',
                'role': 'TESTER',
                'laboratory': ta_lab,
                'is_staff': True,
            },
            # Лаб УКИ
            {
                'username': 'egorov',
                'first_name': 'Павел',
                'last_name': 'Егоров',
                'email': 'egorov@cisis.ru',
                'role': 'TESTER',
                'laboratory': act_lab,
                'is_staff': True,
            },
            {
                'username': 'kirillova',
                'first_name': 'Вероника',
                'last_name': 'Кириллова',
                'email': 'kirillova@cisis.ru',
                'role': 'TESTER',
                'laboratory': act_lab,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # АДМИНИСТРАТОРЫ (регистрация образцов) — 2-3 человека
            # ══════════════════════════════════════════════════════════
            {
                'username': 'admin1',
                'first_name': 'Анна',
                'last_name': 'Павлова',
                'email': 'pavlova@cisis.ru',
                'role': 'ADMIN',
                'laboratory': None,  # видят все лабы
                'is_staff': True,
            },
            {
                'username': 'admin2',
                'first_name': 'Мария',
                'last_name': 'Егорова',
                'email': 'egorova@cisis.ru',
                'role': 'ADMIN',
                'laboratory': None,
                'is_staff': True,
            },
            {
                'username': 'admin3',
                'first_name': 'Татьяна',
                'last_name': 'Федорова',
                'email': 'fedorova@cisis.ru',
                'role': 'ADMIN',
                'laboratory': None,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # СМК
            # ══════════════════════════════════════════════════════════
            {
                'username': 'qms_head',
                'first_name': 'Виктор',
                'last_name': 'Зайцев',
                'email': 'zaitsev@cisis.ru',
                'role': 'QMS_HEAD',
                'laboratory': None,
                'is_staff': True,
            },
            {
                'username': 'qms1',
                'first_name': 'Наталья',
                'last_name': 'Орлова',
                'email': 'orlova@cisis.ru',
                'role': 'QMS',
                'laboratory': None,
                'is_staff': True,
            },
            {
                'username': 'qms2',
                'first_name': 'Екатерина',
                'last_name': 'Васильева',
                'email': 'vasilyeva@cisis.ru',
                'role': 'QMS',
                'laboratory': None,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # МАСТЕРСКАЯ (относится к лабе МИ)
            # ══════════════════════════════════════════════════════════
            {
                'username': 'workshop1',
                'first_name': 'Геннадий',
                'last_name': 'Орлов',
                'email': 'g.orlov@cisis.ru',
                'role': 'WORKSHOP',
                'laboratory': mi_lab,
                'is_staff': True,
            },
            {
                'username': 'workshop2',
                'first_name': 'Владимир',
                'last_name': 'Романов',
                'email': 'romanov@cisis.ru',
                'role': 'WORKSHOP',
                'laboratory': mi_lab,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # ОТДЕЛ ПО РАБОТЕ С ЗАКАЗЧИКАМИ
            # ══════════════════════════════════════════════════════════
            {
                'username': 'client_mgr1',
                'first_name': 'Светлана',
                'last_name': 'Никитина',
                'email': 'nikitina@cisis.ru',
                'role': 'CLIENT_MANAGER',
                'laboratory': None,
                'is_staff': True,
            },
            {
                'username': 'client_mgr2',
                'first_name': 'Юлия',
                'last_name': 'Белова',
                'email': 'belova@cisis.ru',
                'role': 'CLIENT_MANAGER',
                'laboratory': None,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # ОТДЕЛ СОПРОВОЖДЕНИЯ ДОГОВОРОВ
            # ══════════════════════════════════════════════════════════
            {
                'username': 'contract1',
                'first_name': 'Алексей',
                'last_name': 'Григорьев',
                'email': 'grigoriev@cisis.ru',
                'role': 'CONTRACT_SPEC',
                'laboratory': None,
                'is_staff': True,
            },
            {
                'username': 'contract2',
                'first_name': 'Ирина',
                'last_name': 'Тимофеева',
                'email': 'timofeeva@cisis.ru',
                'role': 'CONTRACT_SPEC',
                'laboratory': None,
                'is_staff': True,
            },

            # ══════════════════════════════════════════════════════════
            # БУХГАЛТЕРИЯ
            # ══════════════════════════════════════════════════════════
            {
                'username': 'accountant1',
                'first_name': 'Людмила',
                'last_name': 'Макарова',
                'email': 'makarova@cisis.ru',
                'role': 'ACCOUNTANT',
                'laboratory': None,
                'is_staff': True,
            },
            {
                'username': 'accountant2',
                'first_name': 'Валентина',
                'last_name': 'Степанова',
                'email': 'stepanova@cisis.ru',
                'role': 'ACCOUNTANT',
                'laboratory': None,
                'is_staff': True,
            },
        ]

        for u in users:
            obj, created = User.objects.update_or_create(
                username=u['username'],
                defaults={
                    **u,
                    'password_hash': make_password('test123'),
                    'is_active': True,
                },
            )
            role_display = dict(User._meta.get_field('role').choices).get(obj.role, obj.role)
            lab_display = f' ({obj.laboratory.code_display})' if obj.laboratory else ''
            self.stdout.write(
                f'  Пользователь: {obj.last_name} {obj.first_name} — '
                f'{role_display}{lab_display} — '
                f'{"создан" if created else "обновлён"}'
            )

        # Привязываем заведующих к лабораториям
        mi_lab.head = User.objects.get(username='ivanov_head')
        mi_lab.save()
        cha_lab.head = User.objects.get(username='petrov_head')
        cha_lab.save()
        ta_lab.head = User.objects.get(username='sidorov_head')
        ta_lab.save()
        act_lab.head = User.objects.get(username='alexeev_head')
        act_lab.save()

        self.stdout.write(f'\n  Всего пользователей загружено: {len(users)}')

    # ─────────────────────────────────────────────────────────────────
    # ОБОРУДОВАНИЕ
    # ─────────────────────────────────────────────────────────────────

    def _load_equipment(self):
        mi_lab  = Laboratory.objects.get(code='MI')
        cha_lab = Laboratory.objects.get(code='ChA')
        ta_lab  = Laboratory.objects.get(code='TA')
        mech    = AccreditationArea.objects.get(code='MECH')
        therm   = AccreditationArea.objects.get(code='THERM')

        equipment_list = [
            # СИ — средства измерения
            {
                'accounting_number': 'СИ-001',
                'equipment_type': 'MEASURING',
                'name': 'Штангенциркуль ШЦ-1',
                'inventory_number': 'ИНВ-1001',
                'ownership': 'OWN',
                'manufacturer': 'ОАО «Нейтрон»',
                'laboratory': mi_lab,
                'status': 'OPERATIONAL',
                'areas': [mech],
            },
            {
                'accounting_number': 'СИ-002',
                'equipment_type': 'MEASURING',
                'name': 'Термопара тип К',
                'inventory_number': 'ИНВ-1002',
                'ownership': 'OWN',
                'manufacturer': 'ОАО «Нейтрон»',
                'laboratory': ta_lab,
                'status': 'OPERATIONAL',
                'areas': [therm],
            },
            # ИО — испытательное оборудование
            {
                'accounting_number': 'ИО-001',
                'equipment_type': 'TESTING',
                'name': 'Испытательная машина Zwick Roell Z250',
                'inventory_number': 'ИНВ-2001',
                'ownership': 'OWN',
                'manufacturer': 'Zwick Roell',
                'year_of_manufacture': 2020,
                'laboratory': mi_lab,
                'status': 'OPERATIONAL',
                'areas': [mech],
            },
            {
                'accounting_number': 'ИО-002',
                'equipment_type': 'TESTING',
                'name': 'Термогравиметрический анализатор TGA 850',
                'inventory_number': 'ИНВ-2002',
                'ownership': 'RENTED',
                'ownership_doc_number': 'ДГ-АРЕНДА-2026-01',
                'manufacturer': 'Mettler-Toledo',
                'year_of_manufacture': 2021,
                'laboratory': ta_lab,
                'status': 'OPERATIONAL',
                'areas': [therm],
            },
            {
                'accounting_number': 'ИО-003',
                'equipment_type': 'TESTING',
                'name': 'Копёр Charpy',
                'inventory_number': 'ИНВ-2003',
                'ownership': 'OWN',
                'manufacturer': 'Tinius Olsen',
                'year_of_manufacture': 2019,
                'laboratory': mi_lab,
                'status': 'MAINTENANCE',
                'areas': [mech],
            },
            # ВО — вспомогательное
            {
                'accounting_number': 'ВО-001',
                'equipment_type': 'AUXILIARY',
                'name': 'Весы аналитические AND GR-220EC',
                'inventory_number': 'ИНВ-3001',
                'ownership': 'OWN',
                'manufacturer': 'AND',
                'laboratory': cha_lab,
                'status': 'OPERATIONAL',
                'areas': [],  # вне области
            },
        ]

        for eq_data in equipment_list:
            areas = eq_data.pop('areas')
            obj, created = Equipment.objects.get_or_create(
                accounting_number=eq_data['accounting_number'],
                defaults=eq_data,
            )
            self.stdout.write(f'  Оборудование: {obj.accounting_number} — {obj.name} — {"создано" if created else "уже есть"}')

            # Привязка к областям аккредитации
            for area in areas:
                EquipmentAccreditationArea.objects.get_or_create(
                    equipment=obj,
                    accreditation_area=area,
                )

    # ─────────────────────────────────────────────────────────────────
    # ПРАЗДНИКИ 2026
    # ─────────────────────────────────────────────────────────────────

    def _load_holidays(self):
        holidays = [
            # Новогодние каникулы
            {'date': '2026-01-01', 'name': '1 Января — Новый год',              'is_working': False},
            {'date': '2026-01-02', 'name': '2 Января — Новогодние каникулы',    'is_working': False},
            {'date': '2026-01-03', 'name': '3 Января — Новогодние каникулы',    'is_working': False},
            {'date': '2026-01-04', 'name': '4 Января — Новогодние каникулы',    'is_working': False},
            {'date': '2026-01-05', 'name': '5 Января — Новогодние каникулы',    'is_working': False},
            {'date': '2026-01-06', 'name': '6 Января — Новогодние каникулы',    'is_working': False},
            {'date': '2026-01-07', 'name': '7 Января — Рождество Христово',     'is_working': False},
            {'date': '2026-01-08', 'name': '8 Января — Новогодние каникулы',    'is_working': False},
            # Перенесённые рабочие дни (примерные)
            {'date': '2026-01-10', 'name': '10 Января — перенос с 1 Января',    'is_working': True},
            # 23 Февраля
            {'date': '2026-02-23', 'name': '23 Февраля — День защитника',       'is_working': False},
            # 8 Марта
            {'date': '2026-03-08', 'name': '8 Марта — Международный день женщин','is_working': False},
            # 1 Мая
            {'date': '2026-05-01', 'name': '1 Мая — Праздник Труда',            'is_working': False},
            # 9 Мая
            {'date': '2026-05-09', 'name': '9 Мая — День Победы',               'is_working': False},
            # 12 Июня
            {'date': '2026-06-12', 'name': '12 Июня — День России',             'is_working': False},
            # 4 Ноября
            {'date': '2026-11-04', 'name': '4 Ноября — День народного единства','is_working': False},
        ]

        for h in holidays:
            obj, created = Holiday.objects.get_or_create(date=h['date'], defaults=h)
            self.stdout.write(f'  Праздник: {obj.date} {obj.name} — {"создан" if created else "уже есть"}')
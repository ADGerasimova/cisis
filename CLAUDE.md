# CISIS — Система управления испытательным центром

> **Версия:** 3.31.0 | **Дата:** 10 марта 2026 | **Сессий:** ~49

## Стек

- Django 6.0, Python 3.12, PostgreSQL 16 (Docker) / 18 (Windows)
- Vanilla JS, серверный рендеринг (Django templates)
- Docker Compose (nginx + gunicorn + postgres) на VPS
- reportlab (PDF этикетки), openpyxl (XLSX экспорт)
- python-dotenv (.env, не в Git)
- Миграции БД: SQL-файлы в `sql_migrations/` (все модели `managed=False`)

## Структура проекта

```
core/
├── models/
│   ├── __init__.py
│   ├── base.py              # Laboratory, AccreditationArea, Equipment, enums
│   ├── user.py              # User, UserRole
│   ├── equipment.py         # Equipment, EquipmentMaintenance, Plans, VerificationResult
│   ├── sample.py            # Sample, SampleStatus, M2M-связи
│   ├── permissions.py       # Journal, JournalColumn, RolePermission
│   ├── logs.py              # ClimateLog, WeightLog, WorkshopLog, TimeLog
│   └── files.py             # File (→ files), FileType
├── views/
│   ├── __init__.py
│   ├── views.py             # workspace_home, logout
│   ├── sample_views.py      # CRUD образцов, AJAX
│   ├── journal_views.py     # Журнал образцов, экспорт, столбцы
│   ├── constants.py         # AUTO_FIELDS, STATUS_CHANGE_ACTIONS, ROLES, GROUPS
│   ├── freeze_logic.py      # _is_field_frozen, _can_unfreeze_block
│   ├── field_utils.py       # get_field_info, is_readonly_for_user
│   ├── audit.py             # log_action, log_field_changes, log_m2m_changes
│   ├── bulk_views.py        # Массовые операции
│   ├── directory_views.py   # Справочник заказчиков
│   ├── act_views.py         # CRUD актов, реестр, AJAX
│   ├── label_views.py       # Генератор этикеток
│   ├── auth_views.py        # workspace_login
│   ├── file_views.py        # upload, download, delete, replace, thumbnail
│   ├── file_manager_views.py # Файловый менеджер
│   ├── api_views.py         # get_client_contracts
│   ├── parameter_views.py   # CRUD стандартов/показателей, toggle_exclusion
│   ├── permissions_views.py # manage_permissions
│   ├── audit_views.py       # audit_log_view + резолвинг
│   ├── analytics_views.py   # analytics_view + 6 api_*
│   ├── maintenance_views.py # Планы ТО + экспорт + столбцы
│   ├── employee_views.py    # employees CRUD + responsibility_matrix
│   └── equipment_views.py   # Реестр, карточка, ТО, поверки, файлы
├── templates/core/          # ~25 шаблонов (HTML)
├── static/dashboard/        # css/styles.css, js/dashboard.js
├── admin/user_admin.py
├── permissions.py           # PermissionChecker
├── management/commands/hash_passwords.py
└── urls.py
```

## Архитектура

### Цепочка сущностей
```
Заказчик (Client) → Договор (Contract) → Акт приёма-передачи (AcceptanceAct) → Образец (Sample)
```

### Лаборатории (department_type = 'LAB')
| ID | Код | Сокр. | Название |
|----|-----|-------|----------|
| 1 | MI | МИ | Механические испытания |
| 2 | TA | ТА | Термический анализ |
| 3 | ChA | ХА | Химический анализ |
| 4 | ACT | УКИ | Ускоренные климатические испытания |
| 5 | WORKSHOP | МАС | Мастерская |
| 6 | MSA | МСМА | Микроскопия и спектральные методы анализа |
| 8 | SMPC | УМКТ | Уплотнительных материалов и компонентов трубопроводов |

### Офисные подразделения (department_type = 'OFFICE')
| ID | Код | Сокр. | Название |
|----|-----|-------|----------|
| 7 | QMS | СМК | Система менеджмента качества |
| 10 | HQ | ДИР | Дирекция |
| 11 | TD | ТО | Техотдел |
| 12 | ACC | БУХ | Бухгалтерия |
| 13 | CD | ОСД | Отдел сопровождения договоров |
| 14 | CRD | ОРЗ | Отдел по работе с заказчиками |

### Роли
```
CEO, CTO                          — руководство
SYSADMIN                          — полный доступ (workspace + admin)
CLIENT_MANAGER, CLIENT_DEPT_HEAD  — регистрация образцов
LAB_HEAD                          — управление лабораторией
TESTER                            — испытания
WORKSHOP_HEAD, WORKSHOP           — мастерская
QMS_HEAD, QMS_ADMIN               — система менеджмента качества
METROLOGIST                       — метролог
CONTRACT_SPEC                     — специалист по договорам
ACCOUNTANT                        — бухгалтер
OTHER                             — прочий
```

### Статусы образца
```
PENDING_VERIFICATION → REGISTERED → [MANUFACTURING → TRANSFERRED → REGISTERED] →
  [MOISTURE_CONDITIONING → MOISTURE_READY → REGISTERED] →
  CONDITIONING → READY_FOR_TEST → IN_TESTING → TESTED →
  DRAFT_READY / RESULTS_UPLOADED → PROTOCOL_ISSUED → COMPLETED

Отдельно: CANCELLED, REPLACEMENT_PROTOCOL
workshop_status: IN_WORKSHOP → COMPLETED / CANCELLED
```

### Система прав
- `role_permissions`: role + journal_id + column_id → access_level (VIEW/EDIT/NONE)
- `user_permissions_override`: индивидуальные переопределения
- `role_laboratory_access`: видимость лабораторий по ролям
- `PermissionChecker` — утилитный класс (@classmethod методы)

### Журналы (journals)
SAMPLES, LABELS, CLIENTS, AUDIT_LOG, ACCEPTANCE_ACTS, FILES, STANDARDS, ANALYTICS, MAINTENANCE, EMPLOYEES, RESPONSIBILITY_MATRIX, EQUIPMENT

### Навигация «Оборудование» (3 таба)
| Таб | URL | View |
|-----|-----|------|
| Реестр | `/workspace/equipment/` | `equipment_list` |
| Планы ТО | `/workspace/maintenance/` | `maintenance_view` |
| Поверки | `/workspace/equipment/maintenance-log/` | `equipment_maintenance_log` |

### Файловый менеджер
| Таб | URL | Статус |
|-----|-----|--------|
| Оборудование | `/workspace/files/?category=EQUIPMENT` | Готово |
| Образцы / Клиенты / Стандарты | — | Заглушки (TODO) |

## История версий (краткая)

| Версия | Дата | Ключевое |
|--------|------|----------|
| v3.2.3–v3.4.3 | февраль | Мастерская, workshop_status, рефакторинг |
| v3.5.0–v3.5.1 | февраль | Заморозка полей |
| v3.6.0–v3.7.0 | февраль | Генератор этикеток, сроки |
| v3.8.0–v3.9.1 | февраль | Стажёры, доп. лаборатории, передача образцов |
| v3.10.0–v3.10.2 | февраль | Журнал: пагинация, 47 столбцов, 21 фильтр, баг-фиксы |
| v3.11.0–v3.11.2 | 16 фев | «Создать+такой же», общий протокол, фильтрация стандартов |
| v3.12.0–v3.12.1 | 16–18 фев | Разморозка, XLSX экспорт, рефакторинг views |
| v3.13.0 | 19 фев | Множественные стандарты (FK→M2M), Git |
| v3.14.0 | 20 фев | Журнал аудита |
| v3.15.0–v3.15.1 | 21–22 фев | Влагонасыщение, M2M комбобоксы |
| v3.16.0 | 22–23 фев | Массовые операции, справочник заказчиков, PermissionChecker |
| v3.17.0 | 23 фев | Видимость лабораторий через role_permissions |
| v3.18.0 | 26 фев | Аудит через PermissionChecker |
| v3.19.0–v3.19.1 | 26–27 фев | Акты приёма-передачи |
| v3.20.0 | 28 фев | Нарезка и влагонасыщение для зарег. образцов |
| v3.21.0–v3.21.1 | 28 фев | Файловая система (единая таблица files) |
| v3.22.0 | 1 мар | Справочник стандартов + пул показателей |
| v3.23.0 | 3 мар | Миграция данных (60 юзеров, 405 оборудования), деплой |
| v3.24.0 | 4 мар | Планы ТО, журнал STANDARDS |
| v3.25.0 | 6 мар | Аналитика + Техническое обслуживание |
| v3.26.0 | 7 мар | Реструктуризация подразделений (LAB/OFFICE) |
| v3.27.0 | 7 мар | Справочник сотрудников |
| v3.28.0 | 8 мар | Матрица ответственности, области аккредитации |
| v3.29.0 | 8 мар | Реестр оборудования + поверки |
| v3.30.0 | 9 мар | Файлы оборудования, планы ТО, табы, русификация |
| v3.31.0 | 10 мар | Унификация UI, файловый менеджер, подпапки |

## SQL-миграции

Папка `sql_migrations/incremental/` — 001 по 025 (последняя: `025_v3_31_0_file_type_defaults_equipment.sql`).
Данные: `sql_migrations/data/` (не в Git).

## Окружение

### .env (не в Git)
```
SECRET_KEY, DB_NAME=CISIS, DB_USER=postgres, DB_PASSWORD, DB_HOST=localhost, DB_PORT=5432
DEBUG=True, MEDIA_ROOT=D:\CISIS_Files\Выходные данные лабораторий, ALLOWED_HOSTS=127.0.0.1
```

### Деплой
```
VPS: 79.174.86.147, SSH порт 443
Docker Compose: nginx (80) + web (gunicorn) + db (postgres 16)
Код: /opt/cisis/ → git pull → docker compose up -d --build
```

## Известные ограничения

- Нет валидации последовательности статусов (можно перескочить)
- Нет уведомлений при смене статусов
- Нет синхронизации БД <-> диск для файлов
- Аналитика: SQL жёстко привязан к схеме (нет ORM)
- HTTPS не настроен на VPS
- Старые секреты в истории Git
- Пользователи не раскиданы по новым подразделениям (HQ, TD, ACC, CD, CRD)
- Поле `position` не заполнено для существующих юзеров
- Аудит: «Поле/Было/Стало» не для всех действий
- Файлы оборудования: аудит не резолвится
- Resize столбцов в файловом менеджере не работает корректно

## Запланированные задачи

### Средний приоритет
- Пул показателей: UI в карточке образца (чекбоксы при выборе стандарта)
- Resize столбцов файлового менеджера — переработка
- Файловый менеджер: категории SAMPLE, CLIENT
- Аудит для файлов оборудования (резолвинг EQUIPMENT)
- Файлы: загрузка при создании образца
- Результаты испытаний (таблица, формулы, автосборка протоколов)
- Клиентский портал (CLIENT_USER)
- Workflow: передача в лабораторию

### Низкий приоритет
- UI polish (вёрстка и дизайн)
- MEDIA_ROOT → общий путь
- HTTPS на VPS (Let's Encrypt)
- Номер помещения оборудования (room_number)
- Drag-and-drop столбцов в журнале образцов

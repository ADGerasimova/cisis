-- ============================================================
-- Миграция: 020_v3_25_0_maintenance_journal.sql
-- Версия:   v3.25.0
-- Описание: Журнал MAINTENANCE — техническое обслуживание
--
-- EDIT:  CEO, CTO, SYSADMIN, METROLOGIST, QMS_HEAD, QMS_ADMIN, LAB_HEAD
-- NONE:  CLIENT_MANAGER, CLIENT_DEPT_HEAD, TESTER, WORKSHOP_HEAD,
--        WORKSHOP, CONTRACT_SPEC, ACCOUNTANT, OTHER
-- ============================================================

BEGIN;

-- 1. Журнал
INSERT INTO journals (code, name,  is_active)
SELECT 'MAINTENANCE', 'Техническое обслуживание', TRUE
WHERE NOT EXISTS (SELECT 1 FROM journals WHERE code = 'MAINTENANCE');

-- 2. Столбец access
INSERT INTO journal_columns (journal_id, code, name, display_order, is_active)
SELECT
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    'access', 'Доступ к разделу', 1, TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM journal_columns
    WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND code = 'access'
);

-- 3. Права: EDIT
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'CEO',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'CEO'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'CTO',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'CTO'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'SYSADMIN',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'SYSADMIN'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'METROLOGIST',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'METROLOGIST'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'QMS_HEAD',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'QMS_HEAD'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'QMS_ADMIN',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'QMS_ADMIN'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'LAB_HEAD',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'EDIT'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'LAB_HEAD'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

-- 4. Права: NONE
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'CLIENT_MANAGER',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'CLIENT_MANAGER'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'CLIENT_DEPT_HEAD',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'CLIENT_DEPT_HEAD'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'TESTER',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'TESTER'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'WORKSHOP_HEAD',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'WORKSHOP_HEAD'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'WORKSHOP',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'WORKSHOP'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'CONTRACT_SPEC',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'CONTRACT_SPEC'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'ACCOUNTANT',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'ACCOUNTANT'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'OTHER',
    (SELECT id FROM journals WHERE code = 'MAINTENANCE'),
    (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access'),
    'NONE'
WHERE NOT EXISTS (
    SELECT 1 FROM role_permissions WHERE role = 'OTHER'
      AND journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE')
      AND column_id  = (SELECT id FROM journal_columns WHERE journal_id = (SELECT id FROM journals WHERE code = 'MAINTENANCE') AND code = 'access')
);

COMMIT;

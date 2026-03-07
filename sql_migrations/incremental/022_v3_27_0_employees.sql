-- =============================================
-- CISIS v3.27.0 — Справочник сотрудников
-- Файл: sql_migrations/incremental/022_v3_27_0_employees.sql
-- =============================================

-- 1. Добавляем поле phone в таблицу users
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- 2. Журнал EMPLOYEES
INSERT INTO journals (code, name)
VALUES ('EMPLOYEES', 'Справочник сотрудников')
ON CONFLICT (code) DO NOTHING;

-- 3. Столбец access
INSERT INTO journal_columns (journal_id, code, name, display_order)
SELECT j.id, 'access', 'Доступ', 1
FROM journals j WHERE j.code = 'EMPLOYEES'
ON CONFLICT DO NOTHING;

-- 4. Права: VIEW для всех ролей, EDIT для CEO/CTO/SYSADMIN/LAB_HEAD
DO $$
DECLARE
    j_id   INTEGER;
    c_id   INTEGER;
    r      TEXT;
    lvl    TEXT;
BEGIN
    SELECT id INTO j_id FROM journals WHERE code = 'EMPLOYEES';
    SELECT id INTO c_id FROM journal_columns WHERE journal_id = j_id AND code = 'access';

    FOR r IN
        SELECT unnest(ARRAY[
            'CEO','CTO','SYSADMIN','LAB_HEAD','TESTER',
            'CLIENT_DEPT_HEAD','CLIENT_MANAGER','CONTRACT_SPEC',
            'QMS_HEAD','QMS_ADMIN','METROLOGIST',
            'WORKSHOP_HEAD','WORKSHOP','ACCOUNTANT','OTHER'
        ])
    LOOP
        IF r IN ('CEO','CTO','SYSADMIN','LAB_HEAD') THEN
            lvl := 'EDIT';
        ELSE
            lvl := 'VIEW';
        END IF;

        INSERT INTO role_permissions (role, journal_id, column_id, access_level)
        VALUES (r, j_id, c_id, lvl)
        ON CONFLICT DO NOTHING;
    END LOOP;
END $$;

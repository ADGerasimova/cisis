-- ============================================================
-- Восстановление журнала CLIENTS (Справочник заказчиков)
-- ============================================================

-- 1. Журнал
INSERT INTO journals (code, name, is_active)
VALUES ('CLIENTS', 'Справочник заказчиков', TRUE)
ON CONFLICT (code) DO NOTHING;

-- 2. Столбец access
INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'CLIENTS'
ON CONFLICT (journal_id, code) DO NOTHING;

-- 3. Права: EDIT для управляющих ролей
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, j.id, jc.id, 'EDIT'
FROM journals j
JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
CROSS JOIN (VALUES
    ('CEO'), ('CTO'),
    ('LAB_HEAD'),
    ('CLIENT_DEPT_HEAD'),
    ('QMS_HEAD'), ('QMS_ADMIN')
) AS r(role)
WHERE j.code = 'CLIENTS'
ON CONFLICT (role, journal_id, column_id) DO NOTHING;

-- 4. Права: VIEW для специалиста по заказчикам (только просмотр)
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT 'CLIENT_MANAGER', j.id, jc.id, 'VIEW'
FROM journals j
JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
WHERE j.code = 'CLIENTS'
ON CONFLICT (role, journal_id, column_id) DO NOTHING;

-- ============================================================
-- Проверка: AUDIT_LOG тоже на месте?
-- ============================================================

INSERT INTO journals (code, name, is_active)
VALUES ('AUDIT_LOG', 'Журнал аудита', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'AUDIT_LOG'
ON CONFLICT (journal_id, code) DO NOTHING;

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, j.id, jc.id, 'EDIT'
FROM journals j
JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
CROSS JOIN (VALUES
    ('CEO'), ('CTO'),
    ('QMS_HEAD'), ('QMS_ADMIN'),
    ('LAB_HEAD'),
    ('CLIENT_DEPT_HEAD'), ('WORKSHOP_HEAD')
) AS r(role)
WHERE j.code = 'AUDIT_LOG'
ON CONFLICT (role, journal_id, column_id) DO NOTHING;

-- Очистка: удалить workspace_cards если ещё есть
DROP TABLE IF EXISTS workspace_card_users CASCADE;
DROP TABLE IF EXISTS workspace_card_roles CASCADE;
DROP TABLE IF EXISTS workspace_cards CASCADE;

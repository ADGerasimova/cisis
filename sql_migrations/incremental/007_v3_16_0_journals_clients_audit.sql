-- ============================================================
-- CISIS v3.16.0 — Журналы CLIENTS и AUDIT_LOG + очистка
-- ============================================================
-- Дата: 23 февраля 2026
-- Описание:
--   1. Создаём журналы CLIENTS и AUDIT_LOG в таблице journals
--   2. Создаём столбцы access для проверки has_journal_access()
--   3. Раздаём начальные права через role_permissions
--   4. Удаляем workspace_cards и связанные таблицы (не нужны)
-- ============================================================

-- ============================================================
-- 1. НОВЫЕ ЖУРНАЛЫ
-- ============================================================

INSERT INTO journals (code, name, is_active)
VALUES
    ('CLIENTS',   'Заказчики и договоры', TRUE),
    ('AUDIT_LOG', 'Журнал аудита',        TRUE)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 2. СТОЛБЦЫ ДЛЯ НОВЫХ ЖУРНАЛОВ
-- ============================================================

INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'CLIENTS'
ON CONFLICT (journal_id, code) DO NOTHING;

INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'AUDIT_LOG'
ON CONFLICT (journal_id, code) DO NOTHING;

-- ============================================================
-- 3. НАЧАЛЬНЫЕ ПРАВА
-- ============================================================

-- CLIENTS — кто видит справочник заказчиков
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, j.id, jc.id, 'VIEW'
FROM journals j
JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
CROSS JOIN (VALUES
    ('CEO'), ('CTO'),
    ('LAB_HEAD'),
    ('CLIENT_DEPT_HEAD'), ('CLIENT_MANAGER'),
    ('QMS_HEAD'), ('QMS_ADMIN')
) AS r(role)
WHERE j.code = 'CLIENTS'
ON CONFLICT (role, journal_id, column_id) DO NOTHING;

-- AUDIT_LOG — кто видит журнал аудита
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, j.id, jc.id, 'VIEW'
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

-- ============================================================
-- 4. ОЧИСТКА: удаляем workspace_cards и связанные таблицы
-- ============================================================

DROP TABLE IF EXISTS workspace_card_users CASCADE;
DROP TABLE IF EXISTS workspace_card_roles CASCADE;
DROP TABLE IF EXISTS workspace_cards CASCADE;

-- ============================================================
-- ГОТОВО
-- Доступ управляется через /permissions/?target_type=role
-- ============================================================

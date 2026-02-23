-- ============================================================
-- CISIS v3.16.0 — Рефакторинг: workspace_cards через permissions
-- ============================================================
-- Дата: 23 февраля 2026
-- Описание:
--   1. Добавляем journal_code и requires_column в workspace_cards
--   2. Удаляем workspace_card_roles и workspace_card_users
--   3. Создаём журналы CLIENTS и AUDIT_LOG
--   4. Добавляем journal_columns + role_permissions для них
--   5. Доступ к разделам теперь через единую систему permissions
-- ============================================================

-- ============================================================
-- 1. ИЗМЕНЕНИЯ workspace_cards
-- ============================================================

-- Добавляем привязку к журналу
ALTER TABLE workspace_cards
    ADD COLUMN IF NOT EXISTS journal_code VARCHAR(50) DEFAULT '';

-- Для этикеток: дополнительная проверка столбца (labels_access)
ALTER TABLE workspace_cards
    ADD COLUMN IF NOT EXISTS requires_column VARCHAR(100) DEFAULT '';

-- Заполняем journal_code для существующих карточек
UPDATE workspace_cards SET journal_code = 'SAMPLES', requires_column = '' WHERE code = 'JOURNAL';
UPDATE workspace_cards SET journal_code = 'SAMPLES', requires_column = 'labels_access' WHERE code = 'LABELS';
UPDATE workspace_cards SET journal_code = 'AUDIT_LOG', requires_column = '' WHERE code = 'AUDIT_LOG';
UPDATE workspace_cards SET journal_code = 'CLIENTS', requires_column = '' WHERE code = 'CLIENTS';

-- ============================================================
-- 2. УДАЛЕНИЕ ТАБЛИЦ РОЛЕЙ/ПОЛЬЗОВАТЕЛЕЙ (больше не нужны)
-- ============================================================

DROP TABLE IF EXISTS workspace_card_users CASCADE;
DROP TABLE IF EXISTS workspace_card_roles CASCADE;

-- ============================================================
-- 3. НОВЫЕ ЖУРНАЛЫ
-- ============================================================

INSERT INTO journals (code, name, is_active)
VALUES
    ('CLIENTS',   'Заказчики и договоры', TRUE),
    ('AUDIT_LOG', 'Журнал аудита',        TRUE)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 4. СТОЛБЦЫ ДЛЯ НОВЫХ ЖУРНАЛОВ
-- ============================================================
-- Минимально: один столбец "access" для проверки has_journal_access()
-- В будущем можно добавить гранулярные столбцы (client_name, inn и т.д.)

INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'CLIENTS'
ON CONFLICT (journal_id, code) DO NOTHING;

INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'AUDIT_LOG'
ON CONFLICT (journal_id, code) DO NOTHING;

-- ============================================================
-- 5. ПРАВА ДОСТУПА К НОВЫМ ЖУРНАЛАМ
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
-- ГОТОВО
-- Теперь доступ управляется через /permissions/?target_type=role
-- ============================================================

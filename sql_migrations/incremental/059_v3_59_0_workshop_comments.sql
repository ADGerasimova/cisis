-- ═══════════════════════════════════════════════════════════════
-- 059_v3_59_0.sql — Комментарий мастерской, переименование примечаний
-- ═══════════════════════════════════════════════════════════════

-- 1. Новое поле workshop_comment в таблице samples
ALTER TABLE samples ADD COLUMN IF NOT EXISTS workshop_comment TEXT NOT NULL DEFAULT '';

-- 2. Новый столбец в journal_columns
INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
VALUES (1, 'workshop_comment', 'Комментарий (мастерская)', true, 120)
ON CONFLICT DO NOTHING;

-- 3. Переименование существующих столбцов для ясности
UPDATE journal_columns SET name = 'Примечания (администратор)' WHERE id = 24;   -- admin_notes
UPDATE journal_columns SET name = 'Примечания (общие)'         WHERE id = 137;  -- notes
UPDATE journal_columns SET name = 'Примечания (мастерская)'    WHERE id = 141;  -- workshop_notes
-- operator_notes (id=42) уже называется «Комментарий (испытатель)» — ОК

-- 4. Активировать workshop_notes (был is_active=false)
UPDATE journal_columns SET is_active = true WHERE id = 141;

-- 5. Права по умолчанию для workshop_comment
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, 1, jc.id, 
    CASE 
        WHEN r.role IN ('SYSADMIN', 'WORKSHOP_HEAD', 'WORKSHOP', 'LAB_HEAD') THEN 'EDIT'
        WHEN r.role IN ('TESTER', 'OPERATOR') THEN 'VIEW'
        ELSE 'VIEW'
    END
FROM journal_columns jc
CROSS JOIN (
    VALUES ('SYSADMIN'), ('LAB_HEAD'), ('WORKSHOP_HEAD'), ('WORKSHOP'),
           ('TESTER'), ('OPERATOR'), ('CLIENT_MANAGER'), ('QMS_HEAD'),
           ('QMS_ADMIN'), ('CTO'), ('OTHER')
) AS r(role)
WHERE jc.code = 'workshop_comment'
ON CONFLICT DO NOTHING;

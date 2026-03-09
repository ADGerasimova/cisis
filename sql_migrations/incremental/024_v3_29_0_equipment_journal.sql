-- ═══════════════════════════════════════════════════════════════════
-- МИГРАЦИЯ v3.29.0 — Журнал оборудования (EQUIPMENT)
-- ═══════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. Журнал ───────────────────────────────────────────────────
INSERT INTO journals (code, name, is_active)
VALUES ('EQUIPMENT', 'Реестр оборудования', TRUE)
ON CONFLICT (code) DO NOTHING;

-- ─── 2. Столбец access ──────────────────────────────────────────
INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ', TRUE, 1
FROM journals j WHERE j.code = 'EQUIPMENT'
ON CONFLICT DO NOTHING;

-- ─── 3. Права доступа ───────────────────────────────────────────
-- VIEW для всех основных ролей
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, j.id, jc.id, 'VIEW'
FROM journals j
JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
CROSS JOIN (VALUES
    ('CEO'), ('CTO'), ('SYSADMIN'),
    ('LAB_HEAD'), ('TESTER'),
    ('WORKSHOP_HEAD'), ('WORKSHOP'),
    ('QMS_HEAD'), ('QMS_ADMIN'),
    ('CLIENT_MANAGER'), ('CLIENT_DEPT_HEAD'),
    ('METROLOGIST'),
    ('CONTRACT_SPEC'), ('ACCOUNTANT')
) AS r(role)
WHERE j.code = 'EQUIPMENT'
ON CONFLICT DO NOTHING;

-- EDIT для руководства, сисадмина, начальников лабораторий, метролога
UPDATE role_permissions
SET access_level = 'EDIT'
WHERE journal_id = (SELECT id FROM journals WHERE code = 'EQUIPMENT')
  AND column_id = (SELECT jc.id FROM journal_columns jc
                    JOIN journals j ON j.id = jc.journal_id
                    WHERE j.code = 'EQUIPMENT' AND jc.code = 'access')
  AND role IN ('CEO', 'CTO', 'SYSADMIN', 'LAB_HEAD', 'METROLOGIST');

COMMIT;

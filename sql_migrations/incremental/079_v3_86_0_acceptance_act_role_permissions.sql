-- ============================================================
-- CISIS v3.85.0 (1б): Пермишены для колонки 'acceptance_act'
--                     в role_permissions.
--
-- Применяется ПОСЛЕ миграции 077_v3_85_0_acceptance_act_journal_column.sql.
-- Создаёт записи role_permissions симметрично существующим записям
-- для колонки 'client' (Вариант 1 из обсуждения 1б):
--   кто может видеть/править client в SAMPLES — тот же доступ к
--   acceptance_act получает.
--
-- Логика: INSERT ... SELECT копирует access_level из каждой role_permissions
-- записи для client, подставляя column_id от acceptance_act. ON CONFLICT
-- DO NOTHING делает миграцию идемпотентной (повторный прогон не создаст
-- дубли, ничего не упадёт).
-- ============================================================

BEGIN;

INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT
    rp.role,
    rp.journal_id,
    (SELECT id FROM journal_columns
     WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
       AND code = 'acceptance_act') AS column_id,
    rp.access_level
FROM role_permissions rp
JOIN journal_columns jc ON rp.column_id = jc.id
WHERE jc.journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
  AND jc.code = 'client'
ON CONFLICT (role, journal_id, column_id) DO NOTHING;

-- Верификация: количество записей для acceptance_act должно совпадать
-- с количеством записей для client (симметрия Варианта 1).
DO $$
DECLARE
    client_count  INTEGER;
    act_count     INTEGER;
BEGIN
    SELECT COUNT(*) INTO client_count
    FROM role_permissions rp
    JOIN journal_columns jc ON rp.column_id = jc.id
    WHERE jc.journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
      AND jc.code = 'client';

    SELECT COUNT(*) INTO act_count
    FROM role_permissions rp
    JOIN journal_columns jc ON rp.column_id = jc.id
    WHERE jc.journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
      AND jc.code = 'acceptance_act';

    IF act_count <> client_count THEN
        RAISE EXCEPTION
            'Миграция не сошлась: для client % записей, для acceptance_act % записей',
            client_count, act_count;
    END IF;
    RAISE NOTICE 'Пермишены acceptance_act синхронизированы с client: % записей', act_count;
END $$;

COMMIT;

-- ============================================================
-- Откат (если понадобится):
-- ============================================================
-- BEGIN;
-- DELETE FROM role_permissions
-- WHERE column_id = (
--     SELECT id FROM journal_columns
--     WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
--       AND code = 'acceptance_act'
-- );
-- COMMIT;

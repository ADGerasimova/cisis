-- ============================================================
-- v3.54.0: Место хранения, условия хранения, тип отчёта «Графики»,
--          увеличение max_length, ID панели в журнале
-- ============================================================

-- ─── 1. Новые поля: место хранения и условия хранения ───
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS storage_location VARCHAR(30) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS storage_conditions VARCHAR(500) NOT NULL DEFAULT '';

COMMENT ON COLUMN samples.storage_location IS 'Место хранения образца (CONTAINER / FRIDGE_1 / FRIDGE_2)';
COMMENT ON COLUMN samples.storage_conditions IS 'Условия хранения образца (свободный текст)';

-- ─── 2. Увеличение max_length для полей, где 100-200 символов мало ───
ALTER TABLE samples
    ALTER COLUMN accompanying_doc_number TYPE VARCHAR(500),
    ALTER COLUMN material TYPE VARCHAR(500),
    ALTER COLUMN cutting_direction TYPE VARCHAR(500),
    ALTER COLUMN object_id TYPE VARCHAR(500),
    ALTER COLUMN panel_id TYPE VARCHAR(500);

-- ─── 3. journal_columns + role_permissions для новых полей ───
DO $$
DECLARE
    j_id INTEGER;
    col_id_loc INTEGER;
    col_id_cond INTEGER;
    col_id_panel INTEGER;
    r RECORD;
BEGIN
    SELECT id INTO j_id FROM journals WHERE code = 'SAMPLES' LIMIT 1;
    IF j_id IS NULL THEN
        RAISE NOTICE 'Journal SAMPLES not found, skipping';
        RETURN;
    END IF;

    -- ── journal_columns ──
    INSERT INTO journal_columns (journal_id, code, name, display_order, is_active)
    VALUES (j_id, 'storage_location', 'Место хранения', 161, TRUE)
    ON CONFLICT DO NOTHING;

    INSERT INTO journal_columns (journal_id, code, name, display_order, is_active)
    VALUES (j_id, 'storage_conditions', 'Условия хранения', 162, TRUE)
    ON CONFLICT DO NOTHING;

    INSERT INTO journal_columns (journal_id, code, name, display_order, is_active)
    VALUES (j_id, 'panel_id', 'ID панели', 181, TRUE)
    ON CONFLICT DO NOTHING;

    -- ── Получаем ID новых колонок ──
    SELECT id INTO col_id_loc FROM journal_columns
        WHERE code = 'storage_location' AND journal_id = j_id LIMIT 1;
    SELECT id INTO col_id_cond FROM journal_columns
        WHERE code = 'storage_conditions' AND journal_id = j_id LIMIT 1;
    SELECT id INTO col_id_panel FROM journal_columns
        WHERE code = 'panel_id' AND journal_id = j_id LIMIT 1;

    IF col_id_loc IS NULL OR col_id_cond IS NULL THEN
        RAISE NOTICE 'journal_columns not inserted, skipping permissions';
        RETURN;
    END IF;

    -- ── role_permissions: VIEW для всех ролей, EDIT для регистраторов ──
    FOR r IN
        SELECT DISTINCT role FROM role_permissions WHERE journal_id = j_id
    LOOP
        -- storage_location
        INSERT INTO role_permissions (role, journal_id, column_id, access_level)
        VALUES (
            r.role, j_id, col_id_loc,
            CASE WHEN r.role IN ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'SYSADMIN')
                 THEN 'EDIT' ELSE 'VIEW' END
        ) ON CONFLICT DO NOTHING;

        -- storage_conditions
        INSERT INTO role_permissions (role, journal_id, column_id, access_level)
        VALUES (
            r.role, j_id, col_id_cond,
            CASE WHEN r.role IN ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'SYSADMIN')
                 THEN 'EDIT' ELSE 'VIEW' END
        ) ON CONFLICT DO NOTHING;

        -- panel_id
        IF col_id_panel IS NOT NULL THEN
            INSERT INTO role_permissions (role, journal_id, column_id, access_level)
            VALUES (r.role, j_id, col_id_panel, 'VIEW')
            ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;
END $$;

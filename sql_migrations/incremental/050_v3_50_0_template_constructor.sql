-- ═══════════════════════════════════════════════════════════════
-- Миграция 049: поддержка конструктора шаблонов (v3.50.0)
-- ═══════════════════════════════════════════════════════════════
--
-- Что делает:
-- 1. source_id → nullable (конструктор создаёт шаблоны без xlsx-источника)
-- 2. sheet_name, start_row, end_row, header_row, data_start_row → nullable/дефолт
--    (нужны только для legacy xlsx-парсера, в конструкторе не используются)
-- 3. Добавляем uploaded_by_id в report_template_index (кто создал шаблон)
-- 4. Добавляем индекс на standard_id + is_current (уже есть, но на всякий случай)
--
-- БЕЗОПАСНО: существующие записи от парсера не затрагиваются.
-- ═══════════════════════════════════════════════════════════════

-- 1. source_id — снимаем NOT NULL (конструктор не привязывается к xlsx-файлу)
ALTER TABLE report_template_index
    ALTER COLUMN source_id DROP NOT NULL;

-- 2. Поля парсера — делаем необязательными с дефолтами (legacy не ломается)
ALTER TABLE report_template_index
    ALTER COLUMN sheet_name      SET DEFAULT '',
    ALTER COLUMN sheet_name      DROP NOT NULL,
    ALTER COLUMN start_row       SET DEFAULT 0,
    ALTER COLUMN start_row       DROP NOT NULL,
    ALTER COLUMN end_row         SET DEFAULT 0,
    ALTER COLUMN end_row         DROP NOT NULL,
    ALTER COLUMN header_row      SET DEFAULT 0,
    ALTER COLUMN header_row      DROP NOT NULL,
    ALTER COLUMN data_start_row  SET DEFAULT 0,
    ALTER COLUMN data_start_row  DROP NOT NULL;

-- 3. Добавляем uploaded_by_id (кто создал/обновил шаблон через конструктор)
--    Если столбец уже есть — ничего не делаем.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'report_template_index'
          AND column_name = 'uploaded_by_id'
    ) THEN
        ALTER TABLE report_template_index
            ADD COLUMN uploaded_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END;
$$;

-- 4. Индекс (идемпотентно)
CREATE INDEX IF NOT EXISTS idx_rti_standard_current
    ON report_template_index(standard_id, is_current)
    WHERE is_current = TRUE;

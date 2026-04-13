-- ═══════════════════════════════════════════════════════════════
-- CISIS v3.63.0 — Файлы спецификаций + типы файлов
-- ═══════════════════════════════════════════════════════════════

-- 1. FK спецификации на таблице files
ALTER TABLE files
    ADD COLUMN IF NOT EXISTS specification_id INTEGER
    REFERENCES specifications(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_files_specification_id
    ON files(specification_id) WHERE specification_id IS NOT NULL;

-- 2. Типы файлов для спецификаций
INSERT INTO file_type_defaults (category, file_type, default_visibility, default_subfolder)
VALUES
    ('CLIENT', 'SPEC_SCAN', 'ALL', ''),
    ('CLIENT', 'SPEC_OTHER', 'ALL', '')
ON CONFLICT (category, file_type) DO NOTHING;

-- ============================================================
-- 046_v3_49_0_template_versioning.sql
-- Версионирование шаблонов отчётов
-- ============================================================

-- 1. Добавляем поля версионирования
ALTER TABLE report_template_index
    ADD COLUMN version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN is_current BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN changes_description TEXT DEFAULT '';

-- 2. Убираем старый UNIQUE на standard_id (один стандарт = одна версия)
ALTER TABLE report_template_index
    DROP CONSTRAINT IF EXISTS report_template_index_standard_id_key;

-- 3. Новый UNIQUE: стандарт + версия
ALTER TABLE report_template_index
    ADD CONSTRAINT uq_rti_standard_version UNIQUE (standard_id, version);

-- 4. Индекс для быстрого поиска текущей версии
CREATE INDEX idx_rti_current ON report_template_index(standard_id, is_current)
    WHERE is_current = TRUE;

COMMENT ON COLUMN report_template_index.version IS 'Номер версии шаблона (1, 2, 3...)';
COMMENT ON COLUMN report_template_index.is_current IS 'Текущая (актуальная) версия для новых отчётов';
COMMENT ON COLUMN report_template_index.changes_description IS 'Описание изменений в версии';

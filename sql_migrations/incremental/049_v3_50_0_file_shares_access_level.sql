-- 049_v3_50_0_file_shares_access_level.sql
-- Добавляет колонку access_level в file_shares (VIEW/EDIT)
-- Таблица file_shares создана в 044_v3_48_0_file_shares.sql

ALTER TABLE file_shares
    ADD COLUMN IF NOT EXISTS access_level VARCHAR(10) NOT NULL DEFAULT 'VIEW';

COMMENT ON COLUMN file_shares.access_level IS 'Уровень доступа: VIEW или EDIT';

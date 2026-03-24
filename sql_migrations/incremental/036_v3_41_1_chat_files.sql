-- ============================================================
-- v3.40.1: Файлы в чат-сообщениях
-- ============================================================

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS file_name VARCHAR(255);
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS file_size BIGINT;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS file_type VARCHAR(50);  -- image/jpeg, application/pdf, etc.

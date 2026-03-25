-- ============================================================
-- v3.40.2: Аватарки пользователей
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_path VARCHAR(500);
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS is_manual BOOLEAN NOT NULL DEFAULT FALSE;
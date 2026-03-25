-- ============================================================
-- v3.42.0: Прочитанность + ответы + is_manual
-- ============================================================

-- 1. Прочитанность сообщений
CREATE TABLE IF NOT EXISTS chat_read_receipts (
    id SERIAL PRIMARY KEY,
    message_id INT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(message_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_read_receipts_msg ON chat_read_receipts(message_id);

-- 2. Ответы на сообщения
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS reply_to_id INT REFERENCES chat_messages(id) ON DELETE SET NULL;

-- 3. Ручное добавление в GENERAL чаты
ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS is_manual BOOLEAN NOT NULL DEFAULT FALSE;

-- v3.60.0: Чат — пересылка сообщений + поиск
-- Поле forwarded_from хранит имя оригинального отправителя при пересылке

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS forwarded_from VARCHAR(255) DEFAULT NULL;

-- Индекс для полнотекстового поиска по сообщениям
CREATE INDEX IF NOT EXISTS idx_chat_messages_text_search
ON chat_messages USING gin(to_tsvector('russian', COALESCE(text, '')));

ALTER TABLE chat_members ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE;


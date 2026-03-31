-- 043_chat_reactions.sql
-- Реакции на сообщения чата (v3.46.0)

CREATE TABLE IF NOT EXISTS chat_message_reactions (
    id          SERIAL PRIMARY KEY,
    message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji       VARCHAR(10) NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_reaction_per_user UNIQUE (message_id, user_id, emoji)
);

CREATE INDEX idx_chat_reactions_message ON chat_message_reactions(message_id);
CREATE INDEX idx_chat_reactions_user    ON chat_message_reactions(user_id);

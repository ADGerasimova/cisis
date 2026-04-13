-- 1. Новая таблица комментариев
CREATE TABLE feedback_comments (
    id                  SERIAL PRIMARY KEY,
    feedback_id         INTEGER NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    author_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text                TEXT    NOT NULL,
    is_read_by_author   BOOLEAN NOT NULL DEFAULT FALSE,
    is_read_by_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fb_comments_feedback ON feedback_comments(feedback_id);
CREATE INDEX idx_fb_comments_unread   ON feedback_comments(feedback_id)
    WHERE is_read_by_author = FALSE OR is_read_by_admin = FALSE;



-- 2. Удаляем колонку (раскомментируйте ПОСЛЕ проверки данных)
ALTER TABLE feedback DROP COLUMN admin_comment;

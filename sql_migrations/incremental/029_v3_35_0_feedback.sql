-- 030_v3_35_0_feedback.sql
-- Обратная связь от пользователей

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    description TEXT DEFAULT '' NOT NULL,
    page_url VARCHAR(500) DEFAULT '' NOT NULL,
    priority VARCHAR(20) DEFAULT 'MEDIUM' NOT NULL,
    status VARCHAR(20) DEFAULT 'NEW' NOT NULL,
    admin_comment TEXT DEFAULT '' NOT NULL,
    resolved_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX feedback_author_id_idx ON feedback (author_id);
CREATE INDEX feedback_status_idx ON feedback (status);
CREATE INDEX feedback_created_at_idx ON feedback (created_at DESC);

-- Регистрация журнала
INSERT INTO journals (code, name, is_active)
VALUES ('FEEDBACK', 'Обратная связь', TRUE)
ON CONFLICT (code) DO NOTHING;

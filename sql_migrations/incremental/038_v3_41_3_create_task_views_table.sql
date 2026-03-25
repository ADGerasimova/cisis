-- Таблица просмотров задач (read receipts)
-- Запустить в PostgreSQL перед деплоем

CREATE TABLE IF NOT EXISTS task_views (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (task_id, user_id)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_task_views_task_id ON task_views(task_id);
CREATE INDEX IF NOT EXISTS idx_task_views_user_id ON task_views(user_id);

COMMENT ON TABLE task_views IS 'Просмотры задач исполнителями (read receipts)';

-- 057_v3_57_0_feedback_files.sql
-- Множественные файлы в обратной связи

CREATE TABLE IF NOT EXISTS feedback_files (
    id          SERIAL PRIMARY KEY,
    feedback_id INTEGER NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(feedback_id, file_id)
);

CREATE INDEX idx_feedback_files_feedback ON feedback_files(feedback_id);

-- Миграция существующих скриншотов
INSERT INTO feedback_files (feedback_id, file_id, sort_order)
SELECT id, screenshot_file_id, 0
FROM feedback
WHERE screenshot_file_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- 057_v3_57_0_task_files.sql
-- Файлы, прикреплённые к задачам

CREATE TABLE IF NOT EXISTS task_files (
    id          SERIAL PRIMARY KEY,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(task_id, file_id)
);

CREATE INDEX idx_task_files_task ON task_files(task_id);

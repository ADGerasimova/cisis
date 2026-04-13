-- ─────────────────────────────────────────────────────────────
-- Миграция: таблица закреплённых задач (task_pins)
-- v3.61.0 — Закрепление задач пользователем (персональное)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE task_pins (
    id          SERIAL PRIMARY KEY,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- замените на вашу таблицу пользователей
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (task_id, user_id)
);

-- Индексы для быстрой выборки закреплённых задач пользователя
CREATE INDEX idx_task_pins_user  ON task_pins(user_id);
CREATE INDEX idx_task_pins_task  ON task_pins(task_id);

COMMENT ON TABLE task_pins IS 'Персональное закрепление задач (у каждого пользователя своё)';

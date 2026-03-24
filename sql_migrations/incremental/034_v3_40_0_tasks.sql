-- ═══════════════════════════════════════════════════════════════
-- v3.39.0: Таблица задач (tasks) + исполнители (task_assignees)
-- ═══════════════════════════════════════════════════════════════

-- Если таблица уже существует (из предыдущей попытки) — удаляем
DROP TABLE IF EXISTS task_assignees CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;

CREATE TABLE tasks (
    id              BIGSERIAL PRIMARY KEY,
    task_type       VARCHAR(30)  NOT NULL DEFAULT 'MANUAL',
    title           VARCHAR(500) NOT NULL,
    description     TEXT         NOT NULL DEFAULT '',

    -- Привязка к сущности (sample, acceptance_act, etc.)
    entity_type     VARCHAR(50)  NOT NULL DEFAULT '',
    entity_id       INTEGER      NULL,

    -- Кто создал (NULL = система)
    created_by_id   BIGINT       NULL REFERENCES users(id) ON DELETE SET NULL,

    -- Лаборатория (для фильтрации)
    laboratory_id   BIGINT       NULL REFERENCES laboratories(id) ON DELETE SET NULL,

    -- Сроки и приоритет
    deadline        DATE         NULL,
    priority        VARCHAR(10)  NOT NULL DEFAULT 'MEDIUM',

    -- Статус
    status          VARCHAR(20)  NOT NULL DEFAULT 'OPEN',

    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ  NULL
);

-- M2M: исполнители задачи (один или несколько)
CREATE TABLE task_assignees (
    id       BIGSERIAL PRIMARY KEY,
    task_id  BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (task_id, user_id)
);

-- Индексы
CREATE INDEX idx_tasks_entity ON tasks(entity_type, entity_id);
CREATE INDEX idx_tasks_status_deadline ON tasks(status, deadline);
CREATE INDEX idx_tasks_laboratory ON tasks(laboratory_id) WHERE laboratory_id IS NOT NULL;
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX idx_task_assignees_user ON task_assignees(user_id);
CREATE INDEX idx_task_assignees_task ON task_assignees(task_id);

-- Журнал для системы прав
INSERT INTO journals (code, name) VALUES ('TASKS', 'Задачи')
ON CONFLICT (code) DO NOTHING;

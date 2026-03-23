-- ═══════════════════════════════════════════════════════════════
-- v3.39.0: Таблица задач (tasks)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE tasks (
    id              BIGSERIAL PRIMARY KEY,
    task_type       VARCHAR(30)  NOT NULL DEFAULT 'MANUAL',
    title           VARCHAR(500) NOT NULL,
    description     TEXT         NOT NULL DEFAULT '',

    -- Привязка к сущности (sample, acceptance_act, etc.)
    entity_type     VARCHAR(50)  NOT NULL DEFAULT '',
    entity_id       INTEGER      NULL,

    -- Кому назначена
    assignee_id     BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,

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

-- Индексы
CREATE INDEX idx_tasks_assignee_status ON tasks(assignee_id, status);
CREATE INDEX idx_tasks_entity ON tasks(entity_type, entity_id);
CREATE INDEX idx_tasks_status_deadline ON tasks(status, deadline);
CREATE INDEX idx_tasks_laboratory ON tasks(laboratory_id) WHERE laboratory_id IS NOT NULL;
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- Журнал для системы прав
INSERT INTO journals (code, name) VALUES ('TASKS', 'Задачи')
ON CONFLICT (code) DO NOTHING;

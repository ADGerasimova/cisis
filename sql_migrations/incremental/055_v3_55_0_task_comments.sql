-- ═══════════════════════════════════════════════════════════════════════════════
-- Миграция: Добавление комментариев к задачам (упрощённая версия)
-- Версия: 3.52.0
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Создание таблицы комментариев
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS task_comments (
    id              SERIAL PRIMARY KEY,
    task_id         INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Индексы для быстрого поиска
-- ─────────────────────────────────────────────────────────────────────────────

-- Основной индекс: получение комментариев по задаче
CREATE INDEX IF NOT EXISTS idx_task_comments_task_id 
    ON task_comments(task_id);

-- Индекс для получения комментариев пользователя
CREATE INDEX IF NOT EXISTS idx_task_comments_author_id 
    ON task_comments(author_id);

-- Составной индекс: комментарии задачи отсортированные по времени
CREATE INDEX IF NOT EXISTS idx_task_comments_task_created 
    ON task_comments(task_id, created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Представление для удобного получения комментариев с информацией об авторе
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_task_comments AS
SELECT 
    tc.id,
    tc.task_id,
    tc.author_id,
    u.first_name || ' ' || u.last_name AS author_name,
    u.role AS author_role,
    l.code AS author_lab_code,
    tc.text,
    tc.created_at
FROM task_comments tc
JOIN users u ON tc.author_id = u.id
LEFT JOIN laboratories l ON u.laboratory_id = l.id
ORDER BY tc.created_at;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Функция для проверки права комментирования
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION can_comment_on_task(p_task_id INTEGER, p_user_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    v_user_role VARCHAR(20);
    v_is_creator BOOLEAN;
    v_is_assignee BOOLEAN;
BEGIN
    -- Получаем роль пользователя
    SELECT role INTO v_user_role FROM users WHERE id = p_user_id;
    
    -- Админы могут комментировать всё
    IF v_user_role IN ('SYSADMIN', 'ADMIN') THEN
        RETURN TRUE;
    END IF;
    
    -- Проверяем, является ли пользователь создателем задачи
    SELECT EXISTS(
        SELECT 1 FROM tasks WHERE id = p_task_id AND created_by_id = p_user_id
    ) INTO v_is_creator;
    
    IF v_is_creator THEN
        RETURN TRUE;
    END IF;
    
    -- Проверяем, является ли пользователь исполнителем
    SELECT EXISTS(
        SELECT 1 FROM task_assignees WHERE task_id = p_task_id AND user_id = p_user_id
    ) INTO v_is_assignee;
    
    RETURN v_is_assignee;
END;
$$ LANGUAGE plpgsql;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Триггер проверки прав на добавление комментария
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION check_comment_permission()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT can_comment_on_task(NEW.task_id, NEW.author_id) THEN
        RAISE EXCEPTION 'User % does not have permission to comment on task %', 
            NEW.author_id, NEW.task_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_comment_permission ON task_comments;
CREATE TRIGGER trg_check_comment_permission
    BEFORE INSERT ON task_comments
    FOR EACH ROW
    EXECUTE FUNCTION check_comment_permission();

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Счётчик комментариев в tasks (денормализация для скорости)
-- ─────────────────────────────────────────────────────────────────────────────

-- Добавляем колонку если её нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tasks' AND column_name = 'comments_count'
    ) THEN
        ALTER TABLE tasks ADD COLUMN comments_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Триггер для автоматического обновления счётчика
CREATE OR REPLACE FUNCTION update_task_comments_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE tasks SET comments_count = comments_count + 1 WHERE id = NEW.task_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE tasks SET comments_count = comments_count - 1 WHERE id = OLD.task_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_task_comments_count ON task_comments;
CREATE TRIGGER trg_task_comments_count
    AFTER INSERT OR DELETE ON task_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_task_comments_count();

-- Инициализируем счётчик для существующих задач
UPDATE tasks t
SET comments_count = COALESCE((
    SELECT COUNT(*) FROM task_comments tc WHERE tc.task_id = t.id
), 0);

-- ─────────────────────────────────────────────────────────────────────────────
-- Готово!
-- ─────────────────────────────────────────────────────────────────────────────

COMMENT ON TABLE task_comments IS 'Комментарии к задачам (v3.52.0)';
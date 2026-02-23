-- ============================================================
-- CISIS v3.14.0 — Журнал аудита (audit_log)
-- Выполнять в pgAdmin → Query Tool на базе CISIS
-- ============================================================

BEGIN;

-- 1. Создание таблицы audit_log
CREATE TABLE IF NOT EXISTS audit_log (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    entity_type     VARCHAR(50) NOT NULL,       -- 'sample', 'equipment', 'climate_log', ...
    entity_id       INTEGER NOT NULL,
    action          VARCHAR(30) NOT NULL,        -- 'create', 'update', 'status_change', 'delete', 'm2m_add', 'm2m_remove'
    field_name      VARCHAR(100),                -- nullable: имя поля (для update)
    old_value       TEXT,                        -- nullable: предыдущее значение
    new_value       TEXT,                        -- nullable: новое значение
    ip_address      INET,                        -- nullable: IP пользователя
    extra_data      JSONB                        -- nullable: доп. контекст
);

-- 2. Индексы для быстрой фильтрации
-- Основной: фильтр по конкретной сущности (кнопка «История» на карточке)
CREATE INDEX idx_audit_log_entity
    ON audit_log (entity_type, entity_id);

-- По пользователю (фильтр «кто делал»)
CREATE INDEX idx_audit_log_user
    ON audit_log (user_id);

-- По времени (сортировка, фильтр по периоду)
CREATE INDEX idx_audit_log_timestamp
    ON audit_log (timestamp DESC);

-- Составной: глобальный журнал с фильтром по типу + время
CREATE INDEX idx_audit_log_type_time
    ON audit_log (entity_type, timestamp DESC);

-- Составной: действия пользователя за период
CREATE INDEX idx_audit_log_user_time
    ON audit_log (user_id, timestamp DESC);

-- 3. Комментарии
COMMENT ON TABLE audit_log IS 'Единый журнал аудита всех действий в системе CISIS';
COMMENT ON COLUMN audit_log.entity_type IS 'Тип сущности: sample, equipment, climate_log и т.д.';
COMMENT ON COLUMN audit_log.action IS 'Тип действия: create, update, status_change, delete, m2m_add, m2m_remove';
COMMENT ON COLUMN audit_log.extra_data IS 'JSON с доп. контекстом (например, список изменённых M2M-связей)';

COMMIT;

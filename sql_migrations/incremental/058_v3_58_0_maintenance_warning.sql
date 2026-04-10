-- sql_migrations/058_v3_58_0_maintenance_warning.sql

-- Таблица для хранения запланированных техработ
CREATE TABLE IF NOT EXISTS maintenance_notices (
    id SERIAL PRIMARY KEY,
    created_by_id INTEGER NOT NULL REFERENCES users(id),
    minutes_until INTEGER NOT NULL,          -- через сколько минут
    message TEXT DEFAULT '',                  -- доп. сообщение (опционально)
    scheduled_at TIMESTAMPTZ NOT NULL,        -- когда начнутся работы (created_at + minutes)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE   -- можно отменить
);

CREATE INDEX idx_maintenance_notices_active ON maintenance_notices(is_active, scheduled_at);
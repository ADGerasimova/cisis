-- ============================================================
-- CISIS v3.16.0 — Настраиваемые карточки рабочего пространства
-- ============================================================
-- Дата: 23 февраля 2026
-- Описание: 3 таблицы для управления видимостью карточек
--           на главной странице через Django Admin
-- ============================================================

-- 1. Основная таблица карточек
CREATE TABLE IF NOT EXISTS workspace_cards (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    icon VARCHAR(10) DEFAULT '',
    description TEXT DEFAULT '',
    url VARCHAR(500) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE workspace_cards IS 'Карточки рабочего пространства (главная страница)';
COMMENT ON COLUMN workspace_cards.code IS 'Уникальный код карточки (JOURNAL, CLIENTS, AUDIT_LOG, LABELS)';
COMMENT ON COLUMN workspace_cards.url IS 'URL-путь раздела (напр. /workspace/samples/)';
COMMENT ON COLUMN workspace_cards.sort_order IS 'Порядок отображения (меньше = выше)';
COMMENT ON COLUMN workspace_cards.is_active IS 'Глобальное включение/выключение карточки';

-- 2. Доступ по ролям
CREATE TABLE IF NOT EXISTS workspace_card_roles (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES workspace_cards(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    UNIQUE(card_id, role)
);

COMMENT ON TABLE workspace_card_roles IS 'Какие роли видят какие карточки на главной';

-- 3. Доступ по конкретным пользователям (дополнительно к ролям)
CREATE TABLE IF NOT EXISTS workspace_card_users (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES workspace_cards(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(card_id, user_id)
);

COMMENT ON TABLE workspace_card_users IS 'Персональный доступ к карточкам (в дополнение к ролям)';

-- Индексы
CREATE INDEX IF NOT EXISTS idx_wc_roles_card ON workspace_card_roles(card_id);
CREATE INDEX IF NOT EXISTS idx_wc_roles_role ON workspace_card_roles(role);
CREATE INDEX IF NOT EXISTS idx_wc_users_card ON workspace_card_users(card_id);
CREATE INDEX IF NOT EXISTS idx_wc_users_user ON workspace_card_users(user_id);

-- ============================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ: 4 карточки
-- ============================================================

INSERT INTO workspace_cards (code, name, icon, description, url, sort_order, is_active)
VALUES
    ('JOURNAL',   'Журнал образцов',     '🧪', 'Регистрация и учёт образцов для испытаний',    '/workspace/samples/', 10, TRUE),
    ('LABELS',    'Генератор этикеток',  '🏷️', 'Печать этикеток для образцов',                 '/workspace/labels/',  20, TRUE),
    ('AUDIT_LOG', 'Журнал аудита',       '📋', 'Все действия пользователей в системе',          '/audit-log/',         30, TRUE),
    ('CLIENTS',   'Заказчики и договоры','🏢', 'Управление заказчиками и их договорами',        '/workspace/clients/', 40, TRUE)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- НАЧАЛЬНЫЕ ДАННЫЕ: роли для каждой карточки
-- ============================================================

-- Журнал образцов — все рабочие роли (кроме SYSADMIN — редирект на admin)
INSERT INTO workspace_card_roles (card_id, role)
SELECT c.id, r.role
FROM workspace_cards c,
     (VALUES
         ('CEO'), ('CTO'),
         ('LAB_HEAD'), ('TESTER'),
         ('CLIENT_DEPT_HEAD'), ('CLIENT_MANAGER'), ('CONTRACT_SPEC'),
         ('QMS_HEAD'), ('QMS_ADMIN'),
         ('METROLOGIST'),
         ('WORKSHOP_HEAD'), ('WORKSHOP'),
         ('ACCOUNTANT')
     ) AS r(role)
WHERE c.code = 'JOURNAL'
ON CONFLICT (card_id, role) DO NOTHING;

-- Генератор этикеток
INSERT INTO workspace_card_roles (card_id, role)
SELECT c.id, r.role
FROM workspace_cards c,
     (VALUES
         ('CLIENT_MANAGER'),
         ('CLIENT_DEPT_HEAD'),
         ('LAB_HEAD')
     ) AS r(role)
WHERE c.code = 'LABELS'
ON CONFLICT (card_id, role) DO NOTHING;

-- Журнал аудита
INSERT INTO workspace_card_roles (card_id, role)
SELECT c.id, r.role
FROM workspace_cards c,
     (VALUES
         ('CEO'), ('CTO'),
         ('QMS_HEAD'), ('QMS_ADMIN'),
         ('LAB_HEAD'),
         ('CLIENT_DEPT_HEAD'), ('WORKSHOP_HEAD')
     ) AS r(role)
WHERE c.code = 'AUDIT_LOG'
ON CONFLICT (card_id, role) DO NOTHING;

-- Заказчики и договоры
INSERT INTO workspace_card_roles (card_id, role)
SELECT c.id, r.role
FROM workspace_cards c,
     (VALUES
         ('CEO'), ('CTO'),
         ('LAB_HEAD'),
         ('CLIENT_DEPT_HEAD'),
         ('QMS_HEAD'), ('QMS_ADMIN')
     ) AS r(role)
WHERE c.code = 'CLIENTS'
ON CONFLICT (card_id, role) DO NOTHING;

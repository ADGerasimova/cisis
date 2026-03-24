-- ============================================================
-- v3.40.0: Чат сотрудников
-- ============================================================

-- 1. Комнаты чата
CREATE TABLE IF NOT EXISTS chat_rooms (
    id          SERIAL PRIMARY KEY,
    room_type   VARCHAR(10) NOT NULL DEFAULT 'GROUP',  -- GENERAL / GROUP / DIRECT
    name        VARCHAR(200),                           -- название (NULL для DIRECT)
    laboratory_id INT REFERENCES laboratories(id) ON DELETE SET NULL,  -- для GENERAL по подразделению
    is_global   BOOLEAN NOT NULL DEFAULT FALSE,        -- TRUE = общий чат всего центра
    created_by_id INT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chat_rooms_type ON chat_rooms(room_type);
CREATE INDEX idx_chat_rooms_lab ON chat_rooms(laboratory_id);

-- 2. Участники комнат
CREATE TABLE IF NOT EXISTS chat_members (
    id          SERIAL PRIMARY KEY,
    room_id     INT NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(10) NOT NULL DEFAULT 'MEMBER',  -- OWNER / MEMBER
    last_read_at TIMESTAMPTZ,                           -- для бейджа непрочитанных
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(room_id, user_id)
);

CREATE INDEX idx_chat_members_user ON chat_members(user_id);
CREATE INDEX idx_chat_members_room ON chat_members(room_id);

-- 3. Сообщения
CREATE TABLE IF NOT EXISTS chat_messages (
    id          SERIAL PRIMARY KEY,
    room_id     INT NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    sender_id   INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edited_at   TIMESTAMPTZ,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_chat_messages_room ON chat_messages(room_id, created_at DESC);
CREATE INDEX idx_chat_messages_sender ON chat_messages(sender_id);

-- 4. Создаём общий чат центра
INSERT INTO chat_rooms (room_type, name, is_global, created_at)
VALUES ('GENERAL', 'Общий чат', TRUE, NOW())
ON CONFLICT DO NOTHING;

-- 5. Создаём чаты для каждой лаборатории/подразделения
INSERT INTO chat_rooms (room_type, name, laboratory_id, created_at)
SELECT 'GENERAL', l.name, l.id, NOW()
FROM laboratories l
WHERE NOT EXISTS (
    SELECT 1 FROM chat_rooms cr
    WHERE cr.room_type = 'GENERAL' AND cr.laboratory_id = l.id
);

-- 6. Добавляем всех активных сотрудников в общий чат
INSERT INTO chat_members (room_id, user_id, role, joined_at)
SELECT cr.id, u.id, 'MEMBER', NOW()
FROM chat_rooms cr
CROSS JOIN users u
WHERE cr.is_global = TRUE
  AND u.is_active = TRUE
ON CONFLICT (room_id, user_id) DO NOTHING;

-- 7. Добавляем сотрудников в чаты своих подразделений
INSERT INTO chat_members (room_id, user_id, role, joined_at)
SELECT cr.id, u.id, 'MEMBER', NOW()
FROM chat_rooms cr
JOIN users u ON u.laboratory_id = cr.laboratory_id
WHERE cr.room_type = 'GENERAL'
  AND cr.laboratory_id IS NOT NULL
  AND u.is_active = TRUE
ON CONFLICT (room_id, user_id) DO NOTHING;

-- 7b. Добавляем совместителей (additional_laboratories)
INSERT INTO chat_members (room_id, user_id, role, joined_at)
SELECT cr.id, ual.user_id, 'MEMBER', NOW()
FROM chat_rooms cr
JOIN user_additional_laboratories ual ON ual.laboratory_id = cr.laboratory_id
JOIN users u ON u.id = ual.user_id
WHERE cr.room_type = 'GENERAL'
  AND cr.laboratory_id IS NOT NULL
  AND u.is_active = TRUE
ON CONFLICT (room_id, user_id) DO NOTHING;

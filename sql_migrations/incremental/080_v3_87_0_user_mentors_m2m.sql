-- ═══════════════════════════════════════════════════════════════
-- 080_v3_86_0_user_mentors_m2m.sql
-- v3.86.0: Переход mentor FK → mentors M2M
--
-- Что делает:
--   1) Создаёт через-таблицу user_mentors (user_id, mentor_id).
--   2) Переносит существующие пары из users.mentor_id.
--   3) Удаляет колонку users.mentor_id.
--
-- Зависимости: применяется ПОСЛЕ 079_*.sql
-- Идемпотентность: CREATE IF NOT EXISTS + ON CONFLICT DO NOTHING.
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. Создание таблицы ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_mentors (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mentor_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT user_mentors_unique   UNIQUE (user_id, mentor_id),
    CONSTRAINT user_mentors_not_self CHECK  (user_id <> mentor_id)
);

CREATE INDEX IF NOT EXISTS idx_user_mentors_user   ON user_mentors(user_id);
CREATE INDEX IF NOT EXISTS idx_user_mentors_mentor ON user_mentors(mentor_id);

-- ─── 2. Перенос данных из старого FK ────────────────────────────
-- Выполняется только если колонка users.mentor_id ещё существует
-- (на случай повторного прогона миграции).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'mentor_id'
    ) THEN
        INSERT INTO user_mentors (user_id, mentor_id)
        SELECT id, mentor_id
        FROM users
        WHERE mentor_id IS NOT NULL
        ON CONFLICT (user_id, mentor_id) DO NOTHING;

        RAISE NOTICE 'Данные из users.mentor_id перенесены в user_mentors';
    ELSE
        RAISE NOTICE 'Колонка users.mentor_id уже отсутствует — перенос пропущен';
    END IF;
END $$;

-- ─── 3. Верификация ─────────────────────────────────────────────
DO $$
DECLARE
    source_count INT := 0;
    target_count INT := 0;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'mentor_id'
    ) THEN
        SELECT COUNT(*) INTO source_count
        FROM users WHERE mentor_id IS NOT NULL;

        SELECT COUNT(*) INTO target_count FROM user_mentors;

        IF source_count <> target_count THEN
            RAISE EXCEPTION 'Миграция mentor: source=%, target=% — rollback',
                            source_count, target_count;
        END IF;

        RAISE NOTICE 'Верификация: перенесено % наставнических связей', target_count;
    END IF;
END $$;

-- ─── 4. Удаление старой колонки ─────────────────────────────────
ALTER TABLE users DROP COLUMN IF EXISTS mentor_id;

COMMIT;

-- ═══════════════════════════════════════════════════════════════
-- ОТКАТ (раскомментировать в случае ЧП)
-- ═══════════════════════════════════════════════════════════════
-- BEGIN;
--
-- ALTER TABLE users ADD COLUMN mentor_id INTEGER
--     REFERENCES users(id) ON DELETE SET NULL;
--
-- -- У стажёров с несколькими наставниками берём первого (MIN id).
-- UPDATE users u
-- SET mentor_id = (
--     SELECT MIN(mentor_id) FROM user_mentors WHERE user_id = u.id
-- )
-- WHERE EXISTS (SELECT 1 FROM user_mentors WHERE user_id = u.id);
--
-- DROP TABLE user_mentors;
--
-- COMMIT;

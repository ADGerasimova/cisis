-- =============================================================================
-- 073_v3_76_0_standard_access.sql
-- v3.76.0 — Полная симметрия: таблицы допусков user↔standard и equipment↔standard
-- =============================================================================
--
-- Создаём две новые таблицы:
--   1. user_standard_access      — заменяет user_standard_exclusions
--                                  (исключения становятся mode='REVOKED',
--                                   появляется возможность mode='GRANTED')
--   2. equipment_standard_access — новая, прямая связь оборудование↔стандарт
--                                  (до сих пор связь была только через области)
--
-- Данные из user_standard_exclusions переносятся как REVOKED.
-- Сама user_standard_exclusions НЕ удаляется этой миграцией — так
-- безопаснее: откат v3.76.0 = DROP TABLE user_standard_access (+ equipment_standard_access)
-- и всё. Удаление user_standard_exclusions — отдельной миграцией 074
-- после того как v3.76.0 отработает на проде неделю-две.
--
-- Применять в транзакции:
--   BEGIN;
--   \i 073_v3_76_0_standard_access.sql
--   -- проверить: SELECT mode, COUNT(*) FROM user_standard_access GROUP BY mode;
--   -- результат должен совпасть с SELECT COUNT(*) FROM user_standard_exclusions;
--   COMMIT;  -- или ROLLBACK; если что-то не так
-- =============================================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. user_standard_access
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_standard_access (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
    standard_id     INTEGER NOT NULL
                    REFERENCES standards(id) ON DELETE CASCADE,
    mode            VARCHAR(10) NOT NULL
                    CHECK (mode IN ('GRANTED', 'REVOKED')),
    reason          TEXT,
    assigned_by_id  INTEGER
                    REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT user_standard_access_uniq UNIQUE (user_id, standard_id)
);

CREATE INDEX IF NOT EXISTS idx_usa_user
    ON user_standard_access(user_id);
CREATE INDEX IF NOT EXISTS idx_usa_standard
    ON user_standard_access(standard_id);
CREATE INDEX IF NOT EXISTS idx_usa_mode
    ON user_standard_access(mode);

COMMENT ON TABLE user_standard_access IS
  'v3.76.0. Явный допуск/запрет сотрудника к конкретному стандарту. '
  'Заменяет user_standard_exclusions: старые исключения = mode REVOKED, '
  'mode GRANTED — стандарт, не входящий в области сотрудника, '
  'но который ему разрешён вручную.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. equipment_standard_access
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS equipment_standard_access (
    id              SERIAL PRIMARY KEY,
    equipment_id    INTEGER NOT NULL
                    REFERENCES equipment(id) ON DELETE CASCADE,
    standard_id     INTEGER NOT NULL
                    REFERENCES standards(id) ON DELETE CASCADE,
    mode            VARCHAR(10) NOT NULL
                    CHECK (mode IN ('GRANTED', 'REVOKED')),
    reason          TEXT,
    assigned_by_id  INTEGER
                    REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT equipment_standard_access_uniq UNIQUE (equipment_id, standard_id)
);

CREATE INDEX IF NOT EXISTS idx_esa_equipment
    ON equipment_standard_access(equipment_id);
CREATE INDEX IF NOT EXISTS idx_esa_standard
    ON equipment_standard_access(standard_id);
CREATE INDEX IF NOT EXISTS idx_esa_mode
    ON equipment_standard_access(mode);

COMMENT ON TABLE equipment_standard_access IS
  'v3.76.0. Явный допуск/запрет оборудования для работы по конкретному стандарту. '
  'REVOKED — стандарт попал в автонабор через общую область, но фактически '
  'оборудование по нему не работает. GRANTED — стандарт, не входящий ни в одну '
  'область оборудования, но назначен вручную.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Перенос данных: user_standard_exclusions → user_standard_access (REVOKED)
-- ─────────────────────────────────────────────────────────────────────────────

-- ON CONFLICT — на случай повторного запуска миграции (IF NOT EXISTS выше).
INSERT INTO user_standard_access
    (user_id, standard_id, mode, reason, assigned_by_id, created_at, updated_at)
SELECT
    use.user_id,
    use.standard_id,
    'REVOKED',
    use.reason,
    use.excluded_by_id,
    use.excluded_at,
    use.excluded_at
FROM user_standard_exclusions use
ON CONFLICT (user_id, standard_id) DO NOTHING;

-- Проверка: количество должно совпасть
DO $$
DECLARE
    old_cnt INTEGER;
    new_cnt INTEGER;
BEGIN
    SELECT COUNT(*) INTO old_cnt FROM user_standard_exclusions;
    SELECT COUNT(*) INTO new_cnt FROM user_standard_access WHERE mode = 'REVOKED';
    IF old_cnt <> new_cnt THEN
        RAISE EXCEPTION
          'Миграция 073: несовпадение строк! user_standard_exclusions=% vs user_standard_access REVOKED=%',
          old_cnt, new_cnt;
    END IF;
    RAISE NOTICE 'Миграция 073: перенесено % строк из user_standard_exclusions в user_standard_access', new_cnt;
END$$;

COMMIT;

-- =============================================================================
-- Откат (если что-то пошло не так ПОСЛЕ commit и деплоя кода):
-- =============================================================================
-- BEGIN;
-- DROP TABLE IF EXISTS user_standard_access;
-- DROP TABLE IF EXISTS equipment_standard_access;
-- COMMIT;
-- user_standard_exclusions не трогалась, код v3.75.0 с ней работает.

-- ═══════════════════════════════════════════════════════════════
-- v3.73.0: Ручные override'ы допуска сотрудников к оборудованию
-- ═══════════════════════════════════════════════════════════════
--
-- Итоговый набор сотрудников, допущенных к оборудованию (см.
-- core.services.equipment_access.get_equipment_allowed_users):
--
--   auto_set   = сотрудники, у которых:
--                 1) лаба ∈ (primary + additional) лаб оборудования
--                 2) user_accreditation_areas ∩ equipment_accreditation_areas ≠ ∅
--                 3) в этом пересечении есть хотя бы один стандарт,
--                    НЕ попавший в user_standard_exclusions
--
--   revoked   = { u : equipment_user_access(equipment, u, 'REVOKED') }
--   granted   = { u : equipment_user_access(equipment, u, 'GRANTED') }
--
--   result    = (auto_set ∖ revoked) ∪ granted ∪ {SYSADMIN}
--
-- Таблица user_standard_exclusions уже существует (v3.28.0).
-- Таблица user_accreditation_areas уже существует.
-- Новую добавляем только одну: equipment_user_access.

BEGIN;

CREATE TABLE IF NOT EXISTS equipment_user_access (
    id              SERIAL PRIMARY KEY,
    equipment_id    INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
    mode            VARCHAR(10) NOT NULL
                    CHECK (mode IN ('GRANTED', 'REVOKED')),
    assigned_by_id  INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    notes           TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (equipment_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_eua_equipment ON equipment_user_access(equipment_id);
CREATE INDEX IF NOT EXISTS idx_eua_user      ON equipment_user_access(user_id);
CREATE INDEX IF NOT EXISTS idx_eua_mode      ON equipment_user_access(mode);

COMMENT ON TABLE  equipment_user_access IS
    'v3.73.0: Ручные override допуска сотрудника к оборудованию поверх auto-расчёта (лаба + область аккредитации + не-исключённые стандарты)';
COMMENT ON COLUMN equipment_user_access.mode IS
    'GRANTED — допустить сверх auto; REVOKED — запретить несмотря на auto';
COMMENT ON COLUMN equipment_user_access.notes IS
    'Причина override (для аудита: «не прошёл инструктаж на прессе №5», «временный допуск на период отсутствия Иванова» и т.д.)';

COMMIT;

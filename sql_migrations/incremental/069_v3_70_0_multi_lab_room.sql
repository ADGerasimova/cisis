-- ═══════════════════════════════════════════════════════════════
-- CISIS v3.69.0 — Мультилаборатории и мультипомещения оборудования
-- ═══════════════════════════════════════════════════════════════
-- Паттерн: основная лаба/помещение остаются на equipment (primary FK),
--          дополнительные — через M2M таблицы по образцу существующих
--          equipment_accreditation_areas и user_additional_laboratories
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. Дополнительные лаборатории оборудования ─────────────────
CREATE TABLE IF NOT EXISTS equipment_laboratories (
    id             SERIAL PRIMARY KEY,
    equipment_id   INTEGER NOT NULL REFERENCES equipment(id)    ON DELETE CASCADE,
    laboratory_id  INTEGER NOT NULL REFERENCES laboratories(id) ON DELETE CASCADE,
    UNIQUE (equipment_id, laboratory_id)
);

CREATE INDEX IF NOT EXISTS idx_equipment_laboratories_equipment
    ON equipment_laboratories(equipment_id);

CREATE INDEX IF NOT EXISTS idx_equipment_laboratories_laboratory
    ON equipment_laboratories(laboratory_id);


-- ─── 2. Дополнительные помещения оборудования ───────────────────
CREATE TABLE IF NOT EXISTS equipment_rooms (
    id            SERIAL PRIMARY KEY,
    equipment_id  INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    room_id       INTEGER NOT NULL REFERENCES rooms(id)     ON DELETE CASCADE,
    UNIQUE (equipment_id, room_id)
);

CREATE INDEX IF NOT EXISTS idx_equipment_rooms_equipment
    ON equipment_rooms(equipment_id);

CREATE INDEX IF NOT EXISTS idx_equipment_rooms_room
    ON equipment_rooms(room_id);

COMMIT;

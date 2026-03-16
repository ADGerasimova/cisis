-- 027_v3_35_0_rooms.sql
-- Справочник помещений + привязка к оборудованию

-- Таблица помещений
CREATE TABLE IF NOT EXISTS rooms (
    id SERIAL PRIMARY KEY,
    number VARCHAR(50) NOT NULL,
    name VARCHAR(200) DEFAULT '' NOT NULL,
    building VARCHAR(100) DEFAULT '' NOT NULL,
    floor VARCHAR(20) DEFAULT '' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Уникальность по номеру
CREATE UNIQUE INDEX IF NOT EXISTS rooms_number_uniq ON rooms (number);

-- FK на equipment
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS equipment_room_id_idx ON equipment (room_id);

-- Начальные данные (примеры — отредактируйте под себя)
-- INSERT INTO rooms (number, name) VALUES
--     ('101', 'Лаборатория МИ'),
--     ('102', 'Лаборатория ХА'),
--     ('103', 'Мастерская'),
--     ('201', 'Лаборатория УКИ'),
--     ('202', 'Лаборатория ТА');

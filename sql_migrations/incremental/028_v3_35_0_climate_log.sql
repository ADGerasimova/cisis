-- 028_v3_35_0_climate_log.sql
-- Журнал климата помещений

-- Удаляем старую таблицу
DROP TABLE IF EXISTS climate_log CASCADE;
DELETE FROM journals WHERE code = 'CLIMATE_LOG' ;

-- Новая таблица журнала климата
CREATE TABLE IF NOT EXISTS climate_logs (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    temp_humidity_equipment_id INTEGER REFERENCES equipment(id) ON DELETE SET NULL,
    atmospheric_pressure DECIMAL(7,2),
    pressure_equipment_id INTEGER REFERENCES equipment(id) ON DELETE SET NULL,
    responsible_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX climate_logs_date_idx ON climate_logs (date);
CREATE INDEX climate_logs_room_id_idx ON climate_logs (room_id);
CREATE INDEX climate_logs_responsible_id_idx ON climate_logs (responsible_id);

-- Регистрация журнала
INSERT INTO journals (code, name, is_active)
VALUES ('CLIMATE', 'Журнал климата', TRUE)
ON CONFLICT (code) DO NOTHING;


-- Назначение СИ для журнала климата
 
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS is_temp_humidity BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS is_pressure BOOLEAN DEFAULT FALSE NOT NULL;
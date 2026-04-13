-- =====================================================================
-- v3.61.0: Калибровка барометров + поправка давления
-- =====================================================================
-- 1. rooms.height_above_zero — высота помещения над нулевым уровнем
-- 2. barometer_calibrations — калибровочные таблицы барометров
-- 3. climate_logs: pressure_raw, pressure_corrected, pressure_manually_edited
-- =====================================================================

-- ── 1. Высота помещения ──────────────────────────────────────────────
ALTER TABLE rooms
    ADD COLUMN IF NOT EXISTS height_above_zero NUMERIC(6,2) DEFAULT NULL;

COMMENT ON COLUMN rooms.height_above_zero IS 'Высота над нулевым уровнем (метры), для барометрической поправки';

-- ── 2. Калибровочная таблица барометров ──────────────────────────────
CREATE TABLE IF NOT EXISTS barometer_calibrations (
    id              SERIAL PRIMARY KEY,
    equipment_id    INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    reading_kpa     NUMERIC(7,2) NOT NULL,
    correction_kpa  NUMERIC(7,4) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(equipment_id, reading_kpa)
);

CREATE INDEX IF NOT EXISTS idx_barom_cal_equipment
    ON barometer_calibrations(equipment_id);

COMMENT ON TABLE barometer_calibrations IS 'Калибровочные поправки барометров (показание → поправка, кПа)';

-- ── 3. Новые поля давления в climate_logs ────────────────────────────
-- pressure_raw: сырое показание барометра (кПа), то что ввёл пользователь
ALTER TABLE climate_logs
    ADD COLUMN IF NOT EXISTS pressure_raw NUMERIC(7,2) DEFAULT NULL;

-- pressure_corrected: рассчитанное с поправками (калибровка + температура + высота)
ALTER TABLE climate_logs
    ADD COLUMN IF NOT EXISTS pressure_corrected NUMERIC(7,4) DEFAULT NULL;

-- Флаг ручного редактирования скорректированного значения
ALTER TABLE climate_logs
    ADD COLUMN IF NOT EXISTS pressure_manually_edited BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN climate_logs.pressure_raw IS 'Сырое показание барометра, кПа';
COMMENT ON COLUMN climate_logs.pressure_corrected IS 'Давление с поправками (калибровка + температура + высота), кПа';
COMMENT ON COLUMN climate_logs.pressure_manually_edited IS 'TRUE если скорректированное значение изменено вручную';
COMMENT ON COLUMN climate_logs.atmospheric_pressure IS 'Атм. давление итоговое, кПа (= pressure_corrected или ручное)';

-- ── 4. Бэкфилл: существующие записи → pressure_raw ──────────────────
-- (если ранее вводилось в мм рт.ст., раскомментировать конвертацию)
-- UPDATE climate_logs SET pressure_raw = atmospheric_pressure * 0.133322
--     WHERE atmospheric_pressure IS NOT NULL AND pressure_raw IS NULL;
-- Если данные уже были в кПа:
UPDATE climate_logs SET pressure_raw = atmospheric_pressure
    WHERE atmospheric_pressure IS NOT NULL AND pressure_raw IS NULL;

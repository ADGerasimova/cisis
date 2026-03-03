-- ============================================================================
-- CISIS v3.23.0 — Структурные изменения БД
-- Файл: sql_migrations/incremental/015_v3_23_0_schema_changes.sql
-- Дата: 3 марта 2026
-- Зависимость: 014_v3_22_0_parameters.sql
-- ============================================================================
--
-- Только ALTER TABLE / DROP CONSTRAINT — без конфиденциальных данных.
-- Данные (пользователи, лаборатории, оборудование) загружаются отдельным
-- файлом 015_v3_23_0_data.sql (НЕ попадает в Git).
-- ============================================================================

BEGIN;


-- ============================================================================
-- 1. Добавление столбца sur_name (отчество) в таблицу users
-- ============================================================================

ALTER TABLE users
ADD COLUMN IF NOT EXISTS sur_name VARCHAR(100) DEFAULT '';

COMMENT ON COLUMN users.sur_name IS 'Отчество пользователя';


-- ============================================================================
-- 2. Расширение столбца ownership (VARCHAR(20) -> VARCHAR(200))
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'equipment'
          AND column_name = 'ownership'
          AND character_maximum_length < 200
    ) THEN
        ALTER TABLE equipment ALTER COLUMN ownership TYPE VARCHAR(200);
    END IF;
END $$;


-- ============================================================================
-- 3. Расширение столбца intended_use (VARCHAR(200) -> TEXT)
-- ============================================================================

ALTER TABLE equipment ALTER COLUMN intended_use TYPE TEXT;


-- ============================================================================
-- 4. Снятие уникальности с inventory_number и accounting_number
-- ============================================================================

ALTER TABLE equipment DROP CONSTRAINT IF EXISTS equipment_inventory_number_key;
ALTER TABLE equipment DROP CONSTRAINT IF EXISTS equipment_accounting_number_key;


COMMIT;

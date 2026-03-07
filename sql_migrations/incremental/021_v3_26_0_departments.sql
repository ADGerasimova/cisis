-- =====================================================
-- CISIS v3.26.0 — Реструктуризация подразделений
-- Файл: sql_migrations/incremental/021_v3_26_0_departments.sql
-- =====================================================

BEGIN;

-- ─────────────────────────────────────────────────────
-- 1. Поле position (должность) в users
-- ─────────────────────────────────────────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS position VARCHAR(150) NULL;

COMMENT ON COLUMN users.position IS 'Должность (текст): инженер первой категории, ведущий специалист и т.п.';

-- ─────────────────────────────────────────────────────
-- 2. Обновить department_type: WORKSHOP → LAB, DEPARTMENT → OFFICE
-- ─────────────────────────────────────────────────────

-- Мастерская: WORKSHOP → LAB
UPDATE laboratories SET department_type = 'LAB' WHERE id = 5;

-- СМК: DEPARTMENT → OFFICE
UPDATE laboratories SET department_type = 'OFFICE' WHERE id = 7;

-- ─────────────────────────────────────────────────────
-- 3. Деактивировать ФМ (id=9)
-- ─────────────────────────────────────────────────────
-- Перепривязка оборудования ФМ → МСМА
UPDATE equipment SET laboratory_id = 6 WHERE laboratory_id = 9;

-- Удаление ФМ
DELETE FROM laboratories WHERE id = 9;

-- ─────────────────────────────────────────────────────
-- 4. Добавить новые подразделения
-- ─────────────────────────────────────────────────────
INSERT INTO laboratories (name, code, code_display, department_type, is_active)
VALUES
    ('Дирекция',                           'HQ',  'ДИР', 'OFFICE', TRUE),
    ('Техотдел',                           'TD',  'ТО',  'OFFICE', TRUE),
    ('Бухгалтерия',                        'ACC', 'БУХ', 'OFFICE', TRUE),
    ('Отдел сопровождения договоров',      'CD',  'ОСД', 'OFFICE', TRUE),
    ('Отдел по работе с заказчиками',      'CRD', 'ОРЗ', 'OFFICE', TRUE)
ON CONFLICT (code) DO NOTHING;

-- ─────────────────────────────────────────────────────
-- 5. Обновить CHECK constraint на department_type
--    (если был — пересоздаём; если не было — создаём)
-- ─────────────────────────────────────────────────────
ALTER TABLE laboratories DROP CONSTRAINT IF EXISTS laboratories_department_type_check;
ALTER TABLE laboratories ADD CONSTRAINT laboratories_department_type_check
    CHECK (department_type IN ('LAB', 'OFFICE'));

COMMIT;

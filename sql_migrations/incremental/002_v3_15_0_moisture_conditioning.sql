-- ============================================================
-- CISIS v3.15.0 — Влагонасыщение (moisture conditioning)
-- Миграция: 002_v3_15_0_moisture_conditioning.sql
-- Дата: 21 февраля 2026
-- ============================================================

-- 1. Новые поля в таблице samples
-- ────────────────────────────────

-- Чекбокс «Требуется влагонасыщение»
ALTER TABLE samples
    ADD COLUMN moisture_conditioning BOOLEAN NOT NULL DEFAULT FALSE;

-- FK на образец-влагонасыщение (Образец A в УКИ)
ALTER TABLE samples
    ADD COLUMN moisture_sample_id INTEGER NULL
        REFERENCES samples(id) ON DELETE SET NULL;

-- Индекс для FK
CREATE INDEX idx_samples_moisture_sample_id
    ON samples(moisture_sample_id)
    WHERE moisture_sample_id IS NOT NULL;

-- 2. Комментарии
-- ────────────────────────────────

COMMENT ON COLUMN samples.moisture_conditioning
    IS 'Требуется влагонасыщение перед испытанием';

COMMENT ON COLUMN samples.moisture_sample_id
    IS 'FK на образец влагонасыщения (УКИ). Образец A, к которому привязан данный образец B';

-- ============================================================
-- Примечание: статус MOISTURE_CONDITIONING добавляется на уровне
-- Django-модели (SampleStatus choices). В БД статусы хранятся
-- как VARCHAR, поэтому миграция БД не требуется — достаточно
-- обновить Python-код.
-- ============================================================

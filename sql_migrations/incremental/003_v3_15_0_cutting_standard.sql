-- ═══════════════════════════════════════════════════════════════
-- CISIS v3.15.0 — Дополнительная миграция: стандарт на нарезку
-- ═══════════════════════════════════════════════════════════════

-- Новое поле: стандарт, определяющий форму/размеры нарезки
-- (может отличаться от стандартов основного испытания)
ALTER TABLE samples
    ADD COLUMN cutting_standard_id INTEGER NULL
        REFERENCES standards(id) ON DELETE SET NULL;

CREATE INDEX idx_samples_cutting_standard_id ON samples(cutting_standard_id);

COMMENT ON COLUMN samples.cutting_standard_id IS 'Стандарт на нарезку (для мастерской). Если NULL — мастерская ориентируется на основные стандарты.';

-- ============================================================
-- Migration 066: УЗК (uzk_sample_id) + статус ACCEPTED_IN_LAB
-- Version: 3.64.0
-- Date: 2026-04-14
-- Session: 65
-- ============================================================

BEGIN;

-- 1. Новый FK: uzk_sample_id (ссылка на образец УЗК в лаборатории МИ)
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS uzk_sample_id INTEGER REFERENCES samples(id) ON DELETE SET NULL;

-- 2. Индекс для быстрого поиска зависимых образцов
CREATE INDEX IF NOT EXISTS idx_samples_uzk_sample_id ON samples(uzk_sample_id)
    WHERE uzk_sample_id IS NOT NULL;

-- 3. Чекбокс «Нарезать максимум» для мастерской
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS cut_maximum BOOLEAN NOT NULL DEFAULT FALSE;

-- 4. Обновляем CHECK constraint для статуса — добавляем UZK_TESTING, UZK_READY, ACCEPTED_IN_LAB
ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_status_check;

ALTER TABLE samples ADD CONSTRAINT samples_status_check CHECK (
    status IN (
        'PENDING_VERIFICATION',
        'REGISTERED',
        'CANCELLED',
        'MANUFACTURING',
        'MANUFACTURED',
        'TRANSFERRED',
        'UZK_TESTING',
        'UZK_READY',
        'MOISTURE_CONDITIONING',
        'MOISTURE_READY',
        'ACCEPTED_IN_LAB',
        'CONDITIONING',
        'READY_FOR_TEST',
        'IN_TESTING',
        'TESTED',
        'DRAFT_READY',
        'RESULTS_UPLOADED',
        'PROTOCOL_ISSUED',
        'COMPLETED',
        'REPLACEMENT_PROTOCOL'
    )
);

COMMIT;
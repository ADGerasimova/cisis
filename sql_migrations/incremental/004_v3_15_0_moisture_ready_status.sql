-- ═══════════════════════════════════════════════════════════════
-- CISIS v3.15.0 — Дополнительная миграция: статус MOISTURE_READY
-- ═══════════════════════════════════════════════════════════════

-- Обновляем CHECK constraint, добавляя MOISTURE_READY
ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_status_check;

ALTER TABLE samples ADD CONSTRAINT samples_status_check CHECK (
    status IN (
        'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED',
        'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
        'MOISTURE_CONDITIONING', 'MOISTURE_READY',
        'CONDITIONING', 'READY_FOR_TEST', 'IN_TESTING', 'TESTED',
        'DRAFT_READY', 'RESULTS_UPLOADED',
        'PROTOCOL_ISSUED', 'COMPLETED',
        'REPLACEMENT_PROTOCOL'
    )
);

COMMENT ON CONSTRAINT samples_status_check ON samples IS 'v3.15.0: Допустимые статусы образца, включая MOISTURE_CONDITIONING и MOISTURE_READY';

-- =============================================================================
-- Миграция: 081_v3_92_1_file_sha256_dedup.sql
-- Версия:   v3.92.1
-- Дата:     29 апреля 2026
-- Описание: Добавляет content_sha256 в files для дедупликации по контенту.
-- =============================================================================

BEGIN;

ALTER TABLE files
    ADD COLUMN IF NOT EXISTS content_sha256 CHAR(64) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_files_content_sha256_active
    ON files (content_sha256)
    WHERE content_sha256 <> '' AND is_deleted = FALSE AND current_version = TRUE;

COMMIT;

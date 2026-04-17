-- ═══════════════════════════════════════════════════════════════
-- 070_v3_71_0_maintenance_edit_tracking.sql
-- Отслеживание редактирования записей журнала ТО
-- ═══════════════════════════════════════════════════════════════
--
-- Добавляет в equipment_maintenance_logs два поля:
--   - edited_at    — timestamp последнего редактирования
--   - edited_by_id — FK на пользователя, который редактировал
--
-- Нужно, чтобы в таблице истории ТО показывать бейдж «отредактировано»
-- рядом с записями, которые меняли постфактум (завлаб+).
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE equipment_maintenance_logs
    ADD COLUMN IF NOT EXISTS edited_at    TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS edited_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_eml_edited_by
    ON equipment_maintenance_logs(edited_by_id)
    WHERE edited_by_id IS NOT NULL;

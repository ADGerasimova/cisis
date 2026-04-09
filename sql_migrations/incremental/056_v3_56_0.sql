-- ═══════════════════════════════════════════════════════════
-- CISIS v3.56.0: Прямая привязка акта к заказчику
-- ═══════════════════════════════════════════════════════════

-- Добавляем client_id в acceptance_acts (для актов без договора/счёта)
ALTER TABLE acceptance_acts
    ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE;

-- Индекс для быстрого поиска актов по заказчику
CREATE INDEX IF NOT EXISTS idx_acceptance_acts_client_id
    ON acceptance_acts(client_id)
    WHERE client_id IS NOT NULL;

-- Обновляем CHECK constraint: разрешаем акт с одним только client_id
ALTER TABLE acceptance_acts DROP CONSTRAINT IF EXISTS chk_act_parent;
ALTER TABLE acceptance_acts ADD CONSTRAINT chk_act_parent
    CHECK (contract_id IS NOT NULL OR invoice_id IS NOT NULL OR client_id IS NOT NULL);

-- Заполняем client_id для существующих актов (из договора или счёта)
UPDATE acceptance_acts a
SET client_id = c.client_id
FROM contracts c
WHERE a.contract_id = c.id
  AND a.client_id IS NULL;

UPDATE acceptance_acts a
SET client_id = i.client_id
FROM invoices i
WHERE a.invoice_id = i.id
  AND a.client_id IS NULL
  AND a.contract_id IS NULL;
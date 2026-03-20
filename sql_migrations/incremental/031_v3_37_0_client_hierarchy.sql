-- ============================================================
-- CISIS v3.37.0 — Расширение иерархии заказчиков
-- Файл: sql_migrations/incremental/031_v3_37_0_client_hierarchy.sql
--
-- Новые таблицы:
--   invoices                  — счета (работа без договора)
--   specifications            — спецификации / ТЗ (к договору)
--   specification_laboratories — M2M спецификация ↔ лаборатория
--   closing_document_batches  — массовые закрывающие документы
--   closing_batch_acts        — M2M батч ↔ акт ПП
--
-- Изменения:
--   acceptance_acts           — contract_id nullable, + specification_id, invoice_id
-- ============================================================

BEGIN;

-- =============================================================
-- 1. СЧЕТА (работа без договора)
-- =============================================================

CREATE TABLE IF NOT EXISTS invoices (
    id                SERIAL PRIMARY KEY,
    client_id         INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,

    -- Реквизиты
    number            VARCHAR(100) NOT NULL,
    date              DATE NOT NULL,
    notes             TEXT NOT NULL DEFAULT '',

    -- Финансы (наследуются актами ПП)
    services_count    INTEGER,
    work_cost         NUMERIC(12, 2),
    payment_terms     VARCHAR(30) NOT NULL DEFAULT '',
    payment_invoice   VARCHAR(200) NOT NULL DEFAULT '',
    advance_date      DATE,
    full_payment_date DATE,

    -- Закрывающие документы (наследуются актами ПП)
    completion_act    VARCHAR(200) NOT NULL DEFAULT '',
    invoice_number    VARCHAR(200) NOT NULL DEFAULT '',
    document_flow     VARCHAR(20) NOT NULL DEFAULT '',
    closing_status    VARCHAR(30) NOT NULL DEFAULT '',
    sending_method    VARCHAR(30) NOT NULL DEFAULT '',

    -- Метаданные
    status            VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (client_id, number)
);

CREATE INDEX idx_invoices_client ON invoices(client_id);
CREATE INDEX idx_invoices_status ON invoices(status);

COMMENT ON TABLE invoices IS 'Счета — верхний уровень при работе без договора';


-- =============================================================
-- 2. СПЕЦИФИКАЦИИ / ТЗ (к договору)
-- =============================================================

CREATE TABLE IF NOT EXISTS specifications (
    id                SERIAL PRIMARY KEY,
    contract_id       INTEGER NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,

    -- Тип: спецификация или техническое задание
    spec_type         VARCHAR(20) NOT NULL DEFAULT 'SPEC',
    -- SPEC = спецификация, TZ = техническое задание

    -- Реквизиты
    number            VARCHAR(100) NOT NULL DEFAULT '',
    date              DATE,
    work_deadline     DATE,
    notes             TEXT NOT NULL DEFAULT '',

    -- Финансы (наследуются актами ПП)
    services_count    INTEGER,
    work_cost         NUMERIC(12, 2),
    payment_terms     VARCHAR(30) NOT NULL DEFAULT '',
    payment_invoice   VARCHAR(200) NOT NULL DEFAULT '',
    advance_date      DATE,
    full_payment_date DATE,

    -- Закрывающие документы (наследуются актами ПП)
    completion_act    VARCHAR(200) NOT NULL DEFAULT '',
    invoice_number    VARCHAR(200) NOT NULL DEFAULT '',
    document_flow     VARCHAR(20) NOT NULL DEFAULT '',
    closing_status    VARCHAR(30) NOT NULL DEFAULT '',
    sending_method    VARCHAR(30) NOT NULL DEFAULT '',

    -- Метаданные
    status            VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (contract_id, number)
);

CREATE INDEX idx_specifications_contract ON specifications(contract_id);

COMMENT ON TABLE specifications IS 'Спецификации и ТЗ — второй уровень к договору';


-- =============================================================
-- 3. СПЕЦИФИКАЦИЯ ↔ ЛАБОРАТОРИИ (M2M)
-- =============================================================

CREATE TABLE IF NOT EXISTS specification_laboratories (
    id                SERIAL PRIMARY KEY,
    specification_id  INTEGER NOT NULL REFERENCES specifications(id) ON DELETE CASCADE,
    laboratory_id     INTEGER NOT NULL REFERENCES laboratories(id) ON DELETE RESTRICT,

    UNIQUE (specification_id, laboratory_id)
);

COMMENT ON TABLE specification_laboratories IS 'Лаборатории, задействованные в спецификации';


-- =============================================================
-- 4. МАССОВЫЕ ЗАКРЫВАЮЩИЕ ДОКУМЕНТЫ
-- =============================================================

CREATE TABLE IF NOT EXISTS closing_document_batches (
    id                SERIAL PRIMARY KEY,

    -- Реквизиты батча
    batch_number      VARCHAR(200) NOT NULL DEFAULT '',
    completion_act    VARCHAR(200) NOT NULL DEFAULT '',
    invoice_number    VARCHAR(200) NOT NULL DEFAULT '',
    document_flow     VARCHAR(20) NOT NULL DEFAULT '',
    closing_status    VARCHAR(30) NOT NULL DEFAULT '',
    sending_method    VARCHAR(30) NOT NULL DEFAULT '',
    notes             TEXT NOT NULL DEFAULT '',

    -- Финансы (общий счёт)
    work_cost         NUMERIC(12, 2),
    payment_date      DATE,

    -- Метаданные
    created_by_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE closing_document_batches IS 'Массовые закрывающие документы (группировка актов ПП)';


-- =============================================================
-- 5. БАТЧ ↔ АКТЫ ПП (M2M)
-- =============================================================

CREATE TABLE IF NOT EXISTS closing_batch_acts (
    id        SERIAL PRIMARY KEY,
    batch_id  INTEGER NOT NULL REFERENCES closing_document_batches(id) ON DELETE CASCADE,
    act_id    INTEGER NOT NULL REFERENCES acceptance_acts(id) ON DELETE CASCADE,

    UNIQUE (batch_id, act_id)
);

CREATE INDEX idx_closing_batch_acts_batch ON closing_batch_acts(batch_id);
CREATE INDEX idx_closing_batch_acts_act ON closing_batch_acts(act_id);

COMMENT ON TABLE closing_batch_acts IS 'Связь: батч закрывающих документов ↔ акты ПП';


-- =============================================================
-- 6. ИЗМЕНЕНИЯ В acceptance_acts
-- =============================================================

-- Делаем contract_id nullable (раньше NOT NULL)
ALTER TABLE acceptance_acts
    ALTER COLUMN contract_id DROP NOT NULL;

-- Добавляем FK на спецификацию
ALTER TABLE acceptance_acts
    ADD COLUMN IF NOT EXISTS specification_id INTEGER
    REFERENCES specifications(id) ON DELETE SET NULL;

-- Добавляем FK на счёт
ALTER TABLE acceptance_acts
    ADD COLUMN IF NOT EXISTS invoice_id INTEGER
    REFERENCES invoices(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_acceptance_acts_specification ON acceptance_acts(specification_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_acts_invoice ON acceptance_acts(invoice_id);

-- Constraint: должен быть заполнен contract_id ИЛИ invoice_id
-- (оба NULL нельзя, оба заполнены — нельзя)
ALTER TABLE acceptance_acts
    ADD CONSTRAINT chk_act_parent
    CHECK (
        (contract_id IS NOT NULL AND invoice_id IS NULL)
        OR
        (contract_id IS NULL AND invoice_id IS NOT NULL)
    );

COMMENT ON COLUMN acceptance_acts.specification_id IS 'FK спецификация/ТЗ (nullable, только для актов по договору)';
COMMENT ON COLUMN acceptance_acts.invoice_id IS 'FK счёт (nullable, альтернатива contract_id)';


-- =============================================================
-- 7. ЖУРНАЛЫ ДЛЯ НОВЫХ МОДУЛЕЙ
-- =============================================================

INSERT INTO journals (code, name)
VALUES
    ('INVOICES', 'Счета'),
    ('SPECIFICATIONS', 'Спецификации')
ON CONFLICT (code) DO NOTHING;


COMMIT;

-- ============================================================
-- CISIS v3.19.0 — Акты приёма-передачи
-- Файл: sql_migrations/incremental/010_v3_19_0_acceptance_acts.sql
-- Дата: 26 февраля 2026
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1. Таблица acceptance_acts
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS acceptance_acts (
    id                  SERIAL PRIMARY KEY,

    -- Связи
    contract_id         INTEGER NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
    created_by_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Входная часть
    doc_number          VARCHAR(100) NOT NULL DEFAULT '',          -- короткий код: "M1092" (латиница, для шифра)
    document_name       VARCHAR(500) NOT NULL DEFAULT '',          -- "Сопроводительное письмо № М1092 от 30.01.2026"
    document_status     VARCHAR(30)  NOT NULL DEFAULT '',          -- сканы получены / оригиналы получены
    samples_received_date DATE,                                    -- дата получения образцов
    work_deadline       DATE,                                      -- срок завершения работ (может быть неизвестен)
    payment_terms       VARCHAR(30)  NOT NULL DEFAULT '',          -- предоплата / постоплата / аванс 50% / ...
    has_subcontract     BOOLEAN      NOT NULL DEFAULT FALSE,       -- есть работы на субподряде
    comment             TEXT         NOT NULL DEFAULT '',

    -- Финансы
    services_count      INTEGER,                                   -- количество услуг
    work_cost           DECIMAL(12,2),                             -- стоимость работ
    payment_invoice     VARCHAR(200) NOT NULL DEFAULT '',          -- счёт на оплату
    advance_date        DATE,                                      -- дата аванса
    full_payment_date   DATE,                                      -- дата полной оплаты

    -- Закрывающие документы
    completion_act      VARCHAR(200) NOT NULL DEFAULT '',          -- акт выполненных работ
    invoice_number      VARCHAR(200) NOT NULL DEFAULT '',          -- счёт-фактура
    document_flow       VARCHAR(20)  NOT NULL DEFAULT '',          -- бумажный / ЭДО
    closing_status      VARCHAR(30)  NOT NULL DEFAULT '',          -- подготовлено / передано / получено / ...
    work_status         VARCHAR(20)  NOT NULL DEFAULT 'IN_PROGRESS', -- в работе / закрыто / отмена
    sending_method      VARCHAR(30)  NOT NULL DEFAULT '',          -- курьер / email / почта / ...

    -- Метаданные
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_acceptance_acts_contract ON acceptance_acts(contract_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_acts_work_status ON acceptance_acts(work_status);
CREATE INDEX IF NOT EXISTS idx_acceptance_acts_work_deadline ON acceptance_acts(work_deadline);

COMMENT ON TABLE acceptance_acts IS 'Акты приёма-передачи (входящие документы)';
COMMENT ON COLUMN acceptance_acts.doc_number IS 'Короткий код латиницей (M1092) — для шифра образца';
COMMENT ON COLUMN acceptance_acts.document_name IS 'Название документа как передано заказчиком';
COMMENT ON COLUMN acceptance_acts.document_status IS 'Статус: SCANS_RECEIVED, ORIGINALS_RECEIVED';
COMMENT ON COLUMN acceptance_acts.payment_terms IS 'Условия оплаты: PREPAID, POSTPAID, ADVANCE_50, ADVANCE_30, OTHER';
COMMENT ON COLUMN acceptance_acts.document_flow IS 'Документооборот: PAPER, EDO';
COMMENT ON COLUMN acceptance_acts.closing_status IS 'Статус закрывающих: PREPARED, SENT_TO_CLIENT, RECEIVED, CANCELLED, NONE';
COMMENT ON COLUMN acceptance_acts.work_status IS 'Статус работ: IN_PROGRESS, CLOSED, CANCELLED';
COMMENT ON COLUMN acceptance_acts.sending_method IS 'Способ отправки: COURIER, EMAIL, RUSSIAN_POST, GARANTPOST, IN_PERSON';


-- ─────────────────────────────────────────────────────────────
-- 2. Таблица acceptance_act_laboratories (M2M: акт ↔ лаборатория)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS acceptance_act_laboratories (
    id              SERIAL PRIMARY KEY,
    act_id          INTEGER NOT NULL REFERENCES acceptance_acts(id) ON DELETE CASCADE,
    laboratory_id   INTEGER NOT NULL REFERENCES laboratories(id) ON DELETE RESTRICT,
    completed_date  DATE,    -- автозаполнение: дата последнего протокола когда все образцы закрыты

    UNIQUE(act_id, laboratory_id)
);

CREATE INDEX IF NOT EXISTS idx_aal_act ON acceptance_act_laboratories(act_id);
CREATE INDEX IF NOT EXISTS idx_aal_lab ON acceptance_act_laboratories(laboratory_id);

COMMENT ON TABLE acceptance_act_laboratories IS 'Лаборатории, задействованные в акте';
COMMENT ON COLUMN acceptance_act_laboratories.completed_date IS 'Авто: дата последнего протокола, когда все образцы по этой лабе закрыты';


-- ─────────────────────────────────────────────────────────────
-- 3. Добавить acceptance_act_id в samples
-- ─────────────────────────────────────────────────────────────

ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS acceptance_act_id INTEGER
    REFERENCES acceptance_acts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_samples_acceptance_act ON samples(acceptance_act_id);

COMMENT ON COLUMN samples.acceptance_act_id IS 'Привязка образца к акту приёма-передачи';

-- Удаляем accompanying_doc_full_name — теперь это acceptance_acts.document_name
ALTER TABLE samples DROP COLUMN IF EXISTS accompanying_doc_full_name;


-- ─────────────────────────────────────────────────────────────
-- 4. Журнал ACCEPTANCE_ACTS в таблице journals + role_permissions
-- ─────────────────────────────────────────────────────────────

-- Добавляем журнал
INSERT INTO journals (code, name, is_active)
VALUES ('ACCEPTANCE_ACTS', 'Реестр актов', TRUE)
ON CONFLICT (code) DO NOTHING;

-- Создаём столбец access для нового журнала
INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT j.id, 'access', 'Доступ к разделу', TRUE, 1
FROM journals j WHERE j.code = 'ACCEPTANCE_ACTS'
ON CONFLICT DO NOTHING;

-- VIEW для всех основных ролей
INSERT INTO role_permissions (role, journal_id, column_id, access_level)
SELECT r.role, j.id, jc.id, 'VIEW'
FROM (VALUES
    ('CEO'), ('CTO'), ('SYSADMIN'),
    ('CLIENT_MANAGER'), ('CLIENT_DEPT_HEAD'),
    ('LAB_HEAD'), ('TESTER'),
    ('WORKSHOP_HEAD'), ('WORKSHOP'),
    ('QMS_HEAD'), ('QMS_ADMIN'),
    ('METROLOGIST'), ('CONTRACT_SPEC'), ('ACCOUNTANT')
) AS r(role)
CROSS JOIN journals j
INNER JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
WHERE j.code = 'ACCEPTANCE_ACTS'
ON CONFLICT DO NOTHING;

-- EDIT для ролей, которые могут редактировать
UPDATE role_permissions rp
SET access_level = 'EDIT'
FROM journals j
INNER JOIN journal_columns jc ON jc.journal_id = j.id AND jc.code = 'access'
WHERE j.code = 'ACCEPTANCE_ACTS'
  AND rp.journal_id = j.id
  AND rp.column_id = jc.id
  AND rp.role IN ('CEO', 'CTO', 'SYSADMIN', 'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'ACCOUNTANT', 'CONTRACT_SPEC');


COMMIT;

-- v3.38.0: Добавление поля invoice_id в таблицу samples
-- Связь: Sample → Invoice (многие к одному, nullable)

ALTER TABLE samples ADD COLUMN invoice_id BIGINT NULL;

ALTER TABLE samples ADD CONSTRAINT fk_samples_invoice
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
    ON DELETE RESTRICT;

CREATE INDEX idx_samples_invoice_id ON samples(invoice_id);

ALTER TABLE report_template_index ADD COLUMN IF NOT EXISTS additional_tables jsonb;
ALTER TABLE test_reports ADD COLUMN IF NOT EXISTS additional_tables_data jsonb;
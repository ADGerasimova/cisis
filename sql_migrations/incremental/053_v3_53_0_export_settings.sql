ALTER TABLE test_reports 
ADD COLUMN IF NOT EXISTS export_settings JSONB DEFAULT '{}';

COMMENT ON COLUMN test_reports.export_settings IS 
'Настройки экспорта таблиц в протокол. Пример: {"main": true, "sub_measurements": false, "utok": true}';

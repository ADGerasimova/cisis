-- ═══════════════════════════════════════════════════════════
-- v3.51.0: Полное название сопроводительного документа
-- + убрана заморозка регистрации (все изменения логгируются)
-- ═══════════════════════════════════════════════════════════

-- 1. Добавляем поле для полного названия сопроводительного документа
ALTER TABLE samples
ADD COLUMN IF NOT EXISTS accompanying_doc_full_name VARCHAR(500) NOT NULL DEFAULT '';

COMMENT ON COLUMN samples.accompanying_doc_full_name
IS 'Полное название сопроводительного документа (из акта приёма-передачи)';

-- 2. Заполняем из актов для существующих образцов (если есть привязка)
UPDATE samples s
SET accompanying_doc_full_name = COALESCE(a.document_name, '')
FROM acceptance_acts a
WHERE s.acceptance_act_id = a.id
  AND s.accompanying_doc_full_name = ''
  AND a.document_name IS NOT NULL
  AND a.document_name != '';


-- ═══════════════════════════════════════════════════════════
-- v3.51.0: Индивидуальное выполнение задач (completion_mode)
-- ═══════════════════════════════════════════════════════════

-- 1. Режим выполнения: ANY (один за всех) или ALL (каждый отдельно)
ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS completion_mode VARCHAR(10) NOT NULL DEFAULT 'ANY';

COMMENT ON COLUMN tasks.completion_mode
IS 'ANY — один выполнил = все (по умолчанию), ALL — каждый исполнитель должен выполнить';

-- 2. Дата индивидуального выполнения исполнителя
ALTER TABLE task_assignees
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN task_assignees.completed_at
IS 'Когда конкретный исполнитель отметил выполнение (для режима ALL)';

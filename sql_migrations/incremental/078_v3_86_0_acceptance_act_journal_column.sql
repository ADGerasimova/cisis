-- ============================================================
-- CISIS v3.85.0 (1б): Добавление колонки 'acceptance_act'
--                     в journal_columns.
--
-- Цель: сделать FK acceptance_act видимым и редактируемым в
-- sample_detail (блок «Основная информация»). Без этой записи
-- _build_fields_data в sample_views.py отфильтровывает поле на
-- строке `all_columns.filter(code=field_code).first()`.
--
-- Display order = 6.5 → 7, смещаем последующие колонки на +1.
-- Новая позиция: сразу после 'accompanying_doc_number' (6).
-- Это логично — сначала пользователь видит автозаполненный номер
-- документа, под ним — селект акта, из которого номер подтягивается.
--
-- Можно было поставить display_order=6 и accompanying_doc_number
-- сдвинуть на 7, но порядок уже устоялся в UI — проще добавить
-- в конец секции и дать пользователю нижний селект.
-- ============================================================

BEGIN;

-- Сдвигаем display_order у всех колонок SAMPLES, идущих после
-- accompanying_doc_number, чтобы освободить слот под acceptance_act.
UPDATE journal_columns
SET display_order = display_order + 1
WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
  AND display_order > (
      SELECT display_order FROM journal_columns
      WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
        AND code = 'accompanying_doc_number'
  );

-- Вставляем новую колонку сразу после accompanying_doc_number.
INSERT INTO journal_columns (journal_id, code, name, is_active, display_order)
SELECT
    (SELECT id FROM journals WHERE code = 'SAMPLES'),
    'acceptance_act',
    'Акт приёма-передачи',
    TRUE,
    (SELECT display_order + 1 FROM journal_columns
     WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
       AND code = 'accompanying_doc_number')
WHERE NOT EXISTS (
    SELECT 1 FROM journal_columns
    WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
      AND code = 'acceptance_act'
);

-- Верификация
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM journal_columns
    WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
      AND code = 'acceptance_act'
      AND is_active = TRUE;
    IF col_count <> 1 THEN
        RAISE EXCEPTION 'Миграция не сошлась: ожидается 1 запись acceptance_act, найдено %', col_count;
    END IF;
    RAISE NOTICE 'Колонка acceptance_act добавлена успешно';
END $$;

COMMIT;

-- ============================================================
-- Откат (если понадобится):
-- ============================================================
-- BEGIN;
-- DELETE FROM journal_columns
-- WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
--   AND code = 'acceptance_act';
--
-- -- Восстановить исходный display_order (сдвинуть обратно):
-- UPDATE journal_columns
-- SET display_order = display_order - 1
-- WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
--   AND display_order > (
--       SELECT display_order FROM journal_columns
--       WHERE journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES')
--         AND code = 'accompanying_doc_number'
--   );
-- COMMIT;

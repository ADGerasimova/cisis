-- ═══════════════════════════════════════════════════════════
-- CISIS v3.84.0: M2M-поле «Отчёт подготовили» (report_preparers)
-- ═══════════════════════════════════════════════════════════
--
-- Что делает:
--   1. Создаёт таблицу sample_report_preparers (посредник M2M Sample ↔ User).
--   2. Переносит 118 существующих связей из samples.report_prepared_by_id
--      в новую M2M-таблицу.
--   3. Дропает устаревшие столбцы:
--      - samples.report_prepared_by_id  (заменён на M2M)
--      - samples.report_verified_by_id  (система проверки отчёта наставником
--        упразднена — ответственность перенесена на наличие не-стажёра
--        в M2M report_preparers)
--      - samples.report_verified_date   (тот же блок упразднён)
--
-- Диагностика перед миграцией (выполнено 20.04.2026 на prod-БД):
--   - Образцов в статусе PENDING_MENTOR_REVIEW: 0 (миграция статусов не нужна)
--   - samples с report_prepared_by_id IS NOT NULL: 118
--     (82 DRAFT_READY + 35 RESULTS_UPLOADED + 1 PROTOCOL_ISSUED)
--   - samples с report_verified_by_id IS NOT NULL: 1 (мусор —
--     report_verified_date пустой, содержательной информации нет)
--   - samples с report_verified_date IS NOT NULL: 0
--
-- Статус PENDING_MENTOR_REVIEW в enum БД (если он там есть как CHECK-constraint
-- или в справочнике) — НЕ трогаем. Django managed=False, CHECK на status
-- никогда не создавался. Константа убирается только из Python-choices.
-- ═══════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. Таблица-посредник sample_report_preparers ───
CREATE TABLE sample_report_preparers (
    id          SERIAL PRIMARY KEY,
    sample_id   INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id)   ON DELETE RESTRICT,
    CONSTRAINT uniq_sample_user_report_preparer UNIQUE (sample_id, user_id)
);

CREATE INDEX idx_sample_report_preparers_sample_id
    ON sample_report_preparers (sample_id);

CREATE INDEX idx_sample_report_preparers_user_id
    ON sample_report_preparers (user_id);

COMMENT ON TABLE  sample_report_preparers               IS 'M2M: образец ↔ подготовившие отчёт (v3.84.0)';
COMMENT ON COLUMN sample_report_preparers.sample_id     IS 'FK на samples.id';
COMMENT ON COLUMN sample_report_preparers.user_id       IS 'FK на users.id — подготовивший отчёт сотрудник';

-- ─── 2. Перенос 118 существующих связей FK → M2M ───
-- (ON CONFLICT DO NOTHING на случай повторного запуска — но т.к. UNIQUE
-- создан выше только что, конфликтов быть не должно)
INSERT INTO sample_report_preparers (sample_id, user_id)
SELECT id, report_prepared_by_id
FROM samples
WHERE report_prepared_by_id IS NOT NULL
ON CONFLICT (sample_id, user_id) DO NOTHING;

-- Верификация переноса
DO $$
DECLARE
    fk_count   INTEGER;
    m2m_count  INTEGER;
BEGIN
    SELECT COUNT(*) INTO fk_count  FROM samples WHERE report_prepared_by_id IS NOT NULL;
    SELECT COUNT(*) INTO m2m_count FROM sample_report_preparers;

    IF fk_count <> m2m_count THEN
        RAISE EXCEPTION 'Миграция M2M не сошлась: FK=%, M2M=%', fk_count, m2m_count;
    END IF;

    RAISE NOTICE 'Перенесено связей FK → M2M: %', m2m_count;
END $$;

-- ─── 3. Удаление устаревших столбцов ───
-- DROP COLUMN автоматически удалит FK-constraint и индекс по столбцу.

ALTER TABLE samples
    DROP COLUMN report_prepared_by_id,
    DROP COLUMN report_verified_by_id,
    DROP COLUMN report_verified_date;

-- ─── 4. Переименование в journal_columns / role_permissions ───
-- ⭐ Permission-записи для поля ссылаются на journal_columns по id (FK),
-- поэтому достаточно UPDATE code в одной таблице — FK-связи сохраняются.
-- Это избавляет от дублирования при следующем запуске `load_permissions`.
UPDATE journal_columns
SET code = 'report_preparers',
    name = 'Подготовили отчётность'
WHERE code = 'report_prepared_by'
  AND journal_id = (SELECT id FROM journals WHERE code = 'SAMPLES' LIMIT 1);

-- Верификация: должна быть ровно одна запись с code='report_preparers' в журнале SAMPLES
DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT COUNT(*) INTO cnt
    FROM journal_columns jc
    JOIN journals j ON jc.journal_id = j.id
    WHERE j.code = 'SAMPLES' AND jc.code = 'report_preparers';

    IF cnt = 0 THEN
        RAISE NOTICE 'journal_columns.code=report_preparers не найден — возможно, не было старой записи. Не страшно.';
    ELSIF cnt > 1 THEN
        RAISE EXCEPTION 'journal_columns содержит % записей с code=report_preparers — дубль', cnt;
    ELSE
        RAISE NOTICE 'journal_columns: переименовано report_prepared_by → report_preparers';
    END IF;
END $$;

COMMIT;

-- ═══════════════════════════════════════════════════════════
-- ПОСЛЕ ПРИМЕНЕНИЯ:
--   docker compose restart web   (перечитать Django-модели)
--
-- ОТКАТ (если понадобится до рестарта web):
--   BEGIN;
--   ALTER TABLE samples
--       ADD COLUMN report_prepared_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
--       ADD COLUMN report_verified_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
--       ADD COLUMN report_verified_date  TIMESTAMP WITH TIME ZONE;
--   UPDATE samples s
--   SET report_prepared_by_id = srp.user_id
--   FROM sample_report_preparers srp
--   WHERE srp.sample_id = s.id;
--   -- Внимание: если на образце было > 1 preparer, откат выберет случайного.
--   DROP TABLE sample_report_preparers;
--   COMMIT;
-- ═══════════════════════════════════════════════════════════
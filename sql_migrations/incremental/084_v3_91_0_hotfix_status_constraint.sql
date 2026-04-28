-- =====================================================================
-- Hotfix v3.91.0: пересоздание CHECK constraint samples_status_check
-- =====================================================================
--
-- ОШИБКА, КОТОРУЮ ЭТО ЛЕЧИТ:
--     IntegrityError: новая строка в отношении "samples" нарушает
--     ограничение-проверку "samples_status_check"
--     при попытке записать status='DRAFT_REGISTERED'.
--
-- ПРИЧИНА:
--     В БД есть CHECK constraint, ограничивающий значения колонки
--     samples.status фиксированным списком. Этот constraint был
--     создан вручную (Django сам такие не создаёт — choices живут
--     только в Python-слое). После добавления в код нового статуса
--     DRAFT_REGISTERED constraint надо обновить.
--
-- ЧТО ДЕЛАЕТ ЭТОТ ФАЙЛ:
--     1. Перед удалением выводит текущее определение constraint —
--        чтобы было что вернуть, если что-то пойдёт не так.
--     2. Удаляет старый constraint.
--     3. Создаёт новый со всеми текущими значениями SampleStatus,
--        включая DRAFT_REGISTERED.
--     4. Всё в одной транзакции — если упадёт, БД останется как была.
--
-- ПЕРЕД ЗАПУСКОМ — бэкап:
--     pg_dump -U <user> -d <database> -F c -f backup_before_v392_hotfix.dump
--
-- ЗАПУСК:
--     psql -U <user> -d <database> -f hotfix_v392_status_constraint.sql
--
-- =====================================================================

BEGIN;

-- ──────────────────────────────────────────────────────────────────
-- ШАГ 1. Аудит: какой constraint сейчас есть, как он выглядит,
--        и сколько каких значений status в таблице.
-- ──────────────────────────────────────────────────────────────────
DO $$
DECLARE
    rec RECORD;
    found boolean := false;
BEGIN
    FOR rec IN
        SELECT con.conname, pg_get_constraintdef(con.oid) AS definition
          FROM pg_constraint con
          JOIN pg_class cls ON cls.oid = con.conrelid
         WHERE cls.relname = 'samples'
           AND con.conname = 'samples_status_check'
    LOOP
        found := true;
        RAISE NOTICE '  Текущий constraint: %', rec.conname;
        RAISE NOTICE '  Определение: %', rec.definition;
    END LOOP;

    IF NOT found THEN
        RAISE NOTICE '  Constraint samples_status_check не найден — '
                     'возможно, его уже удалили или у него другое имя.';
    END IF;

    RAISE NOTICE '──── Распределение значений samples.status ────';
    FOR rec IN
        SELECT status, COUNT(*) AS cnt
          FROM samples
         GROUP BY status
         ORDER BY cnt DESC
    LOOP
        RAISE NOTICE '  % : %', rpad(rec.status::text, 25), rec.cnt;
    END LOOP;
END $$;

-- ──────────────────────────────────────────────────────────────────
-- ШАГ 2. Удаляем старый constraint.
-- ──────────────────────────────────────────────────────────────────
ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_status_check;

-- ──────────────────────────────────────────────────────────────────
-- ШАГ 3. Создаём новый со всеми актуальными статусами.
-- Список значений идёт из core/models/sample.py → class SampleStatus.
-- ──────────────────────────────────────────────────────────────────
ALTER TABLE samples ADD CONSTRAINT samples_status_check
    CHECK (status IN (
        -- Регистрация
        'DRAFT',
        'DRAFT_REGISTERED',           -- ⭐ v3.92.0: новый статус
        'PENDING_VERIFICATION',
        'REGISTERED',
        'CANCELLED',
        -- Изготовление (для лаборатории)
        'MANUFACTURING',
        'MANUFACTURED',
        'TRANSFERRED',
        'UZK_TESTING',
        'UZK_READY',
        'MOISTURE_CONDITIONING',
        'MOISTURE_READY',
        -- Испытания
        'ACCEPTED_IN_LAB',
        'CONDITIONING',
        'READY_FOR_TEST',
        'IN_TESTING',
        'TESTED',
        'DRAFT_READY',
        'RESULTS_UPLOADED',
        -- СМК
        'PROTOCOL_ISSUED',
        'COMPLETED',
        -- Замещающий протокол
        'REPLACEMENT_PROTOCOL'
    ));

-- ──────────────────────────────────────────────────────────────────
-- ШАГ 4. Проверка: новый constraint на месте, и значения проходят.
-- ──────────────────────────────────────────────────────────────────
DO $$
DECLARE
    new_def text;
BEGIN
    SELECT pg_get_constraintdef(con.oid)
      INTO new_def
      FROM pg_constraint con
      JOIN pg_class cls ON cls.oid = con.conrelid
     WHERE cls.relname = 'samples'
       AND con.conname = 'samples_status_check';

    IF new_def IS NULL THEN
        RAISE EXCEPTION 'Не удалось создать новый constraint';
    END IF;

    RAISE NOTICE 'OK: новый constraint создан.';
    RAISE NOTICE '  Определение: %', new_def;
END $$;

COMMIT;

-- =====================================================================
-- ОТКАТ (если потребуется — но обычно не нужен, миграция «безопасная»):
--
--     BEGIN;
--     ALTER TABLE samples DROP CONSTRAINT samples_status_check;
--     ALTER TABLE samples ADD CONSTRAINT samples_status_check
--         CHECK (status IN (
--             -- ... СТАРЫЙ список без DRAFT_REGISTERED, который был
--             -- выведен на ШАГЕ 1 этого скрипта. Скопируйте его
--             -- из вывода в логах psql.
--         ));
--     COMMIT;
--
-- =====================================================================

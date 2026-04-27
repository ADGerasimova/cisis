-- ═══════════════════════════════════════════════════════════════
-- 082_v3_89_0_parallel_sample_registration.sql
-- v3.89.0: Параллельная регистрация образцов (черновики)
--
-- Что делает:
--   1) Снимает NOT NULL с samples.sequence_number и samples.cipher,
--      чтобы образец в статусе DRAFT мог существовать без присвоенных
--      номера и шифра.
--   2) Верифицирует, что UNIQUE-ограничения на этих колонках остаются
--      обычными (не partial). В PostgreSQL UNIQUE не конфликтует с NULL,
--      поэтому множественные черновики с NULL-шифрами допустимы.
--   3) Расширяет CHECK-constraint samples_status_check:
--        - добавляет 'DRAFT' (новый статус черновика регистрации)
--        - удаляет 'PENDING_MENTOR_REVIEW' (упразднён в v3.84.0,
--          оставался в CHECK как долг — на момент миграции в БД
--          таких записей нет)
--
-- ВАЖНО: registration_date, client, laboratory и прочие бизнес-поля
-- остаются NOT NULL. Черновик — это полностью заполненная форма
-- образца, у которой не присвоены только три «номерных» поля,
-- вычисляемые в момент выпуска.
--
-- Зависимости: применяется ПОСЛЕ 081_*.sql (SHA-256 дедупликация).
-- Идемпотентность: безопасно запускать повторно — DROP NOT NULL,
-- DROP CONSTRAINT IF EXISTS и пересоздание CHECK не падают
-- при повторном прогоне.
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. Снятие NOT NULL ─────────────────────────────────────────
ALTER TABLE samples ALTER COLUMN sequence_number DROP NOT NULL;
ALTER TABLE samples ALTER COLUMN cipher          DROP NOT NULL;

-- ─── 2. Верификация UNIQUE-индексов ─────────────────────────────
-- Цель: убедиться, что UNIQUE-ограничения на sequence_number и
-- cipher — это обычные индексы (без WHERE-предиката). Если они
-- partial (например, WHERE sequence_number IS NOT NULL), нужно
-- пересоздать как полные — иначе два DRAFT с NULL-шифром всё
-- равно будут конфликтовать.
DO $$
DECLARE
    rec RECORD;
    problem_count INT := 0;
BEGIN
    FOR rec IN
        SELECT i.relname AS index_name,
               a.attname  AS column_name,
               pg_get_indexdef(ix.indexrelid) AS definition
        FROM pg_index ix
        JOIN pg_class i   ON i.oid = ix.indexrelid
        JOIN pg_class t   ON t.oid = ix.indrelid
        JOIN pg_attribute a ON a.attrelid = t.oid
                           AND a.attnum = ANY(ix.indkey)
        WHERE t.relname = 'samples'
          AND ix.indisunique = true
          AND a.attname IN ('sequence_number', 'cipher')
    LOOP
        IF rec.definition ~* 'WHERE' THEN
            RAISE WARNING
                'Индекс % на samples.% является PARTIAL: %',
                rec.index_name, rec.column_name, rec.definition;
            problem_count := problem_count + 1;
        ELSE
            RAISE NOTICE
                'Индекс % на samples.% — OK (полный UNIQUE)',
                rec.index_name, rec.column_name;
        END IF;
    END LOOP;

    IF problem_count > 0 THEN
        RAISE EXCEPTION
            'Найдено % partial UNIQUE-индексов — требуется ручная '
            'пересборка. Смотри предупреждения выше.', problem_count;
    END IF;
END $$;

-- ─── 3. Финальная проверка, что колонки действительно nullable ──
DO $$
DECLARE
    seq_nullable TEXT;
    cipher_nullable TEXT;
BEGIN
    SELECT is_nullable INTO seq_nullable
    FROM information_schema.columns
    WHERE table_name = 'samples' AND column_name = 'sequence_number';

    SELECT is_nullable INTO cipher_nullable
    FROM information_schema.columns
    WHERE table_name = 'samples' AND column_name = 'cipher';

    IF seq_nullable <> 'YES' OR cipher_nullable <> 'YES' THEN
        RAISE EXCEPTION
            'NOT NULL не снят: sequence_number=%, cipher=% — rollback',
            seq_nullable, cipher_nullable;
    END IF;

    RAISE NOTICE
        'samples.sequence_number и samples.cipher теперь nullable — OK';
END $$;

-- ─── 4. Обновление CHECK-constraint статусов ────────────────────
-- Защитная проверка: если в БД остались записи со старым статусом
-- PENDING_MENTOR_REVIEW (упразднён в v3.84.0), миграция падает —
-- такие записи нужно сначала перевести в актуальный статус
-- вручную.
DO $$
DECLARE
    legacy_count INT;
BEGIN
    SELECT COUNT(*) INTO legacy_count
    FROM samples
    WHERE status = 'PENDING_MENTOR_REVIEW';

    IF legacy_count > 0 THEN
        RAISE EXCEPTION
            'Найдено % образцов со статусом PENDING_MENTOR_REVIEW '
            '(удалён в v3.84.0). Сначала переведите их в актуальный '
            'статус, затем повторите миграцию.', legacy_count;
    END IF;

    RAISE NOTICE
        'Записей со статусом PENDING_MENTOR_REVIEW нет — продолжаем';
END $$;

ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_status_check;

ALTER TABLE samples ADD CONSTRAINT samples_status_check
    CHECK (status IN (
        'DRAFT',                  -- ⭐ v3.89.0
        'PENDING_VERIFICATION',
        'REGISTERED',
        'CANCELLED',
        'MANUFACTURING',
        'MANUFACTURED',
        'TRANSFERRED',
        'UZK_TESTING',
        'UZK_READY',
        'MOISTURE_CONDITIONING',
        'MOISTURE_READY',
        'ACCEPTED_IN_LAB',
        'CONDITIONING',
        'READY_FOR_TEST',
        'IN_TESTING',
        'TESTED',
        'DRAFT_READY',
        'RESULTS_UPLOADED',
        'PROTOCOL_ISSUED',
        'COMPLETED',
        'REPLACEMENT_PROTOCOL'
    ));

DO $$
BEGIN
    RAISE NOTICE
        'CHECK samples_status_check пересобран: + DRAFT, − PENDING_MENTOR_REVIEW';
END $$;

COMMIT;

-- ═══════════════════════════════════════════════════════════════
-- ОТКАТ (раскомментировать в случае ЧП)
-- ═══════════════════════════════════════════════════════════════
-- ВНИМАНИЕ: откат упадёт, если в БД уже существуют DRAFT-образцы
-- с NULL-шифрами или NULL-номерами. Перед откатом нужно либо
-- выпустить черновики, либо удалить их физически:
--   DELETE FROM samples WHERE status = 'DRAFT';
--
-- BEGIN;
--
-- ALTER TABLE samples ALTER COLUMN sequence_number SET NOT NULL;
-- ALTER TABLE samples ALTER COLUMN cipher          SET NOT NULL;
--
-- ALTER TABLE samples DROP CONSTRAINT IF EXISTS samples_status_check;
-- ALTER TABLE samples ADD CONSTRAINT samples_status_check
--     CHECK (status IN (
--         'PENDING_VERIFICATION', 'REGISTERED', 'CANCELLED',
--         'MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
--         'UZK_TESTING', 'UZK_READY',
--         'MOISTURE_CONDITIONING', 'MOISTURE_READY',
--         'ACCEPTED_IN_LAB', 'CONDITIONING', 'READY_FOR_TEST',
--         'IN_TESTING', 'TESTED',
--         'PENDING_MENTOR_REVIEW',  -- восстанавливаем легаси
--         'DRAFT_READY', 'RESULTS_UPLOADED',
--         'PROTOCOL_ISSUED', 'COMPLETED',
--         'REPLACEMENT_PROTOCOL'
--     ));
--
-- COMMIT;
-- =====================================================================
-- 085_v3_92_0_protocol_leader.sql
-- =====================================================================
-- v3.92.0: Поле samples.protocol_leader_id — реляционная связь между
-- образцами одного протокола.
--
-- Назначение
-- ----------
-- До v3.92.0 связь "образцы одного протокола" выражалась только через
-- совпадение строкового поля samples.pi_number. Это работало для
-- зарегистрированных образцов (у них pi_number всегда заполнен), но
-- сломалось с появлением черновиков (DRAFT/DRAFT_REGISTERED), у которых
-- pi_number = NULL до выпуска пула — нельзя было привязать новый черновик
-- к черновику-лидеру, потому что не к чему привязываться.
--
-- Это поле решает обе проблемы единым механизмом:
-- 1) Для черновиков — связь до момента, когда у лидера появится pi_number.
-- 2) Для зарегистрированных — единый UI прикрепления (вместо отдельной
--    логики "перепиши строку pi_number" в save_logic.py).
--
-- Семантика
-- ---------
-- protocol_leader_id IS NULL  → образец сам себе лидер (или одиночный).
-- protocol_leader_id = X      → pi_number у этого образца материализуется
--                               из самого Sample.save() как leader.pi_number
--                               (если у лидера он уже есть).
--
-- При выпуске пула черновиков (finalize_drafts):
--   - Лидер выпускается первым → получает pi_number через generate_pi_number().
--   - Followers выпускаются после лидера → их pi_number = leader.pi_number.
--   - Топологическая сортировка пула делается в Python в finalize_drafts.
--
-- При удалении лидера (delete_draft) — ON DELETE SET NULL: followers
-- становятся "свободными", и при выпуске получат свой pi_number через
-- generate_pi_number().
--
-- Backfill
-- --------
-- Намеренно НЕ делается. Все исторические образцы остаются с
-- protocol_leader_id = NULL и продолжают группироваться по совпадению
-- pi_number (как и раньше). Никаких массовых UPDATE на таблицу samples.
--
-- Постепенное обогащение БД новыми связями произойдёт органически: при
-- любом новом действии "прикрепить к существующему протоколу" система
-- проставит protocol_leader_id (а не перепишет pi_number-строку, как до
-- v3.93.0).
--
-- Безопасность
-- ------------
-- - Колонка nullable, без значения по умолчанию у новых записей.
-- - FK с ON DELETE SET NULL (а не CASCADE) — удаление лидера не убивает
--   followers, только рвёт связь.
-- - Создаём индекс по protocol_leader_id (нужен для запросов
--   "followers лидера X" и для каскадных операций FK).
-- - Без CHECK на запрет циклов — циклы предотвращаются на уровне
--   приложения (Sample.clean()), потому что в SQL-проверке цикла
--   пришлось бы делать рекурсивный CTE на каждый INSERT/UPDATE.
-- =====================================================================

BEGIN;

-- 1. Колонка
ALTER TABLE samples
    ADD COLUMN protocol_leader_id INTEGER NULL
    REFERENCES samples(id) ON DELETE SET NULL;

-- 2. Индекс — для запросов "followers лидера X" и эффективного ON DELETE
CREATE INDEX idx_samples_protocol_leader
    ON samples(protocol_leader_id)
    WHERE protocol_leader_id IS NOT NULL;

-- 3. Лог результата для psql-логов: убедиться, что колонка реально создана
DO $$
DECLARE
    col_exists BOOLEAN;
    idx_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'samples' AND column_name = 'protocol_leader_id'
    ) INTO col_exists;

    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'samples' AND indexname = 'idx_samples_protocol_leader'
    ) INTO idx_exists;

    RAISE NOTICE '085_v3_93_0: column protocol_leader_id exists = %', col_exists;
    RAISE NOTICE '085_v3_93_0: index idx_samples_protocol_leader exists = %', idx_exists;

    IF NOT col_exists OR NOT idx_exists THEN
        RAISE EXCEPTION '085_v3_93_0: миграция не применилась корректно';
    END IF;
END $$;

COMMIT;

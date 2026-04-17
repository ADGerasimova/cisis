-- Миграция: добавление полей "Проверил отчёт" для стажёров
-- Версия: v3.72.0 (или следующая за твоей текущей)

ALTER TABLE samples
    ADD COLUMN report_verified_by_id BIGINT NULL,
    ADD COLUMN report_verified_date  TIMESTAMP WITH TIME ZONE NULL;

-- FK на users с поведением SET NULL (как у report_prepared_by_id)
ALTER TABLE samples
    ADD CONSTRAINT samples_report_verified_by_id_fkey
        FOREIGN KEY (report_verified_by_id)
        REFERENCES users(id)
        ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED;

-- Индекс для фильтрации "что проверил конкретный наставник"
CREATE INDEX samples_report_verified_by_id_idx
    ON samples (report_verified_by_id);

-- Комментарии (опционально, но помогает в pgAdmin/DBeaver)
COMMENT ON COLUMN samples.report_verified_by_id IS
    'Наставник, проверивший отчёт стажёра. Заполняется если report_prepared_by — стажёр (users.is_trainee = true)';
COMMENT ON COLUMN samples.report_verified_date IS
    'Дата и время проверки отчёта наставником';
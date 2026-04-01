-- ============================================================
-- 045_v3_49_0_test_reports.sql
-- Отчёты об испытаниях: шаблоны + данные
-- ============================================================

-- 1. Источники шаблонов (xlsx-файлы, загруженные админом)
-- Один файл может содержать шаблоны для нескольких стандартов
CREATE TABLE IF NOT EXISTS report_template_sources (
    id              SERIAL PRIMARY KEY,
    laboratory_id   INTEGER REFERENCES laboratories(id) ON DELETE SET NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,           -- путь в S3 или локально
    description     TEXT DEFAULT '',
    uploaded_by_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rts_laboratory ON report_template_sources(laboratory_id);
CREATE INDEX idx_rts_active ON report_template_sources(is_active);

COMMENT ON TABLE report_template_sources IS 'Xlsx-файлы с шаблонами таблиц для отчётов об испытаниях (30 файлов на лабораторию)';

-- 2. Индекс шаблонов: стандарт → файл + лист + диапазон строк
-- Создаётся автоматически при загрузке xlsx парсером
CREATE TABLE IF NOT EXISTS report_template_index (
    id                      SERIAL PRIMARY KEY,
    standard_id             INTEGER NOT NULL REFERENCES standards(id) ON DELETE CASCADE,
    source_id               INTEGER NOT NULL REFERENCES report_template_sources(id) ON DELETE CASCADE,
    sheet_name              VARCHAR(255) NOT NULL,       -- имя листа в xlsx
    start_row               INTEGER NOT NULL,            -- первая строка блока (ячейка "Дата:")
    end_row                 INTEGER NOT NULL,            -- последняя строка блока
    header_row              INTEGER NOT NULL,            -- строка заголовков таблицы ("№ образца", "σ", ...)
    data_start_row          INTEGER NOT NULL,            -- первая строка данных (после заголовков)
    stats_start_row         INTEGER,                     -- первая строка статистики (NULL если нет)

    -- Конфигурация (извлекается парсером из xlsx)
    column_config           JSONB NOT NULL DEFAULT '[]', -- [{code, name, unit, col_letter, type: INPUT|CALCULATED|SUB_AVG, formula, decimal_places}]
    header_config           JSONB NOT NULL DEFAULT '{}', -- {force_sensor_cell, speed_cell, conditions_cell, ...}
    statistics_config       JSONB NOT NULL DEFAULT '[]', -- [{type: MEAN|STDEV|CV|CONFIDENCE, row_offset, columns}]
    sub_measurements_config JSONB DEFAULT NULL,          -- {start_col, cols: [{code, name, unit}], measurements_per_specimen: 3}

    layout_type             VARCHAR(10) DEFAULT 'A',     -- тип раскладки (A/B/C)
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW(),

    UNIQUE(standard_id)     -- один стандарт = один шаблон
);

CREATE INDEX idx_rti_source ON report_template_index(source_id);
CREATE INDEX idx_rti_standard ON report_template_index(standard_id);

COMMENT ON TABLE report_template_index IS 'Маппинг: стандарт → конкретный блок в xlsx-файле с конфигурацией столбцов';

-- 3. Отчёты об испытаниях (основная таблица, растёт)
CREATE TABLE IF NOT EXISTS test_reports (
    id                  SERIAL PRIMARY KEY,
    sample_id           INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    standard_id         INTEGER NOT NULL REFERENCES standards(id) ON DELETE RESTRICT,
    template_id         INTEGER REFERENCES report_template_index(id) ON DELETE SET NULL,
    created_by_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,

    status              VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
                        CHECK (status IN ('DRAFT', 'COMPLETED', 'APPROVED')),

    -- Шапка (предзаполняется из БД + ручной ввод)
    header_data         JSONB NOT NULL DEFAULT '{}',
    -- Примеры полей в header_data:
    -- {
    --   "force_sensor": "50 кН",
    --   "traverse_speed": "2 мм/мин",
    --   "specimen_count": 6,
    --   "notes": "образцы с накладками",
    --   "conditions": "RTD",
    --   "room": "Лаб. 205"
    -- }

    -- Полные данные таблицы (JSONB — любая структура)
    table_data          JSONB NOT NULL DEFAULT '{"specimens": []}',
    -- Пример:
    -- {
    --   "specimens": [
    --     {
    --       "number": 1,
    --       "marking": "25-001-A",
    --       "sub_measurements": {"h": [1.02, 1.01, 1.03], "b": [12.50, 12.48, 12.52]},
    --       "values": {"h_avg": 1.02, "b_avg": 12.50, "F": 5.23, "sigma": 410.5, ...}
    --     }
    --   ]
    -- }

    -- Статистика (среднее, ст.откл, CV%, дов.интервал)
    statistics_data     JSONB NOT NULL DEFAULT '{}',
    -- Пример:
    -- {
    --   "sigma": {"mean": 412.3, "stdev": 15.2, "cv": 3.7, "ci_lo": 396.1, "ci_hi": 428.5},
    --   "E":     {"mean": 42.1, "stdev": 1.8, "cv": 4.3, "ci_lo": 40.2, "ci_hi": 44.0}
    -- }

    -- Ключевые показатели (для быстрой аналитики, заполняются при сохранении)
    specimen_count      INTEGER,
    mean_strength       NUMERIC(12,4),          -- среднее σ / σВ / Ftu
    mean_modulus        NUMERIC(12,4),           -- среднее E
    mean_elongation     NUMERIC(12,4),           -- среднее δ / ε
    cv_strength         NUMERIC(8,4),            -- коэффициент вариации прочности, %

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tr_sample ON test_reports(sample_id);
CREATE INDEX idx_tr_standard ON test_reports(standard_id);
CREATE INDEX idx_tr_status ON test_reports(status);
CREATE INDEX idx_tr_created_by ON test_reports(created_by_id);
CREATE INDEX idx_tr_created_at ON test_reports(created_at);
-- Для аналитики по показателям:
CREATE INDEX idx_tr_strength ON test_reports(standard_id, mean_strength) WHERE mean_strength IS NOT NULL;

COMMENT ON TABLE test_reports IS 'Отчёты об испытаниях: JSONB с полной таблицей + ключевые показатели для аналитики';
COMMENT ON COLUMN test_reports.table_data IS 'Полная таблица данных: образцы, промежуточные замеры, значения';
COMMENT ON COLUMN test_reports.mean_strength IS 'Среднее прочности (σ/σВ/Ftu) — для быстрых запросов аналитики';

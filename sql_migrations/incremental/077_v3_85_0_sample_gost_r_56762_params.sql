BEGIN;

CREATE TABLE IF NOT EXISTS sample_gost_r_56762_params (
    sample_id INTEGER PRIMARY KEY,
    temperature_c NUMERIC(7,2),
    relative_humidity_percent NUMERIC(5,2)
        CHECK (
            relative_humidity_percent IS NULL
            OR (relative_humidity_percent >= 0 AND relative_humidity_percent <= 100)
        ),

    water_exposure BOOLEAN NOT NULL DEFAULT FALSE,
    boiling_water_exposure BOOLEAN NOT NULL DEFAULT FALSE,

    other_fluid_medium TEXT,
    gas_exposure_environment TEXT,

    duration_value NUMERIC(10,2)
        CHECK (duration_value IS NULL OR duration_value >= 0),

    duration_unit VARCHAR(100),
    long_term_exposure_type VARCHAR(255),

    criterion_value NUMERIC(10,2),

    mass_control_type VARCHAR(255),

    periodicity_text TEXT,
    periodicity_unit VARCHAR(100),

    method_text TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_sample_gost_r_56762_params_sample
        FOREIGN KEY (sample_id)
        REFERENCES samples(id)
        ON DELETE CASCADE
);

COMMIT;
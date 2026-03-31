-- 044_v3_48_0_file_shares.sql
-- Шаринг отдельных файлов между сотрудниками

CREATE TABLE IF NOT EXISTS file_shares (
    id              SERIAL PRIMARY KEY,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    shared_by_id    INTEGER NOT NULL REFERENCES users(id),
    shared_with_id  INTEGER NOT NULL REFERENCES users(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT file_shares_unique UNIQUE (file_id, shared_with_id)
);

CREATE INDEX idx_file_shares_shared_with ON file_shares (shared_with_id);
CREATE INDEX idx_file_shares_file ON file_shares (file_id);

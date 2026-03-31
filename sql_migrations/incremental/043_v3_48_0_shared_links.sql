-- 043_v3_48_0_shared_links.sql
-- Публичные ссылки для внешнего доступа к файлам без регистрации

CREATE TABLE IF NOT EXISTS shared_links (
    id              SERIAL PRIMARY KEY,
    token           VARCHAR(64) NOT NULL UNIQUE,
    file_id         INTEGER REFERENCES files(id) ON DELETE CASCADE,
    folder_id       INTEGER REFERENCES personal_folders(id) ON DELETE CASCADE,
    created_by_id   INTEGER NOT NULL REFERENCES users(id),
    label           VARCHAR(255) DEFAULT '',          -- необязательная метка (напр. "Для ООО Рога")
    password_hash   VARCHAR(255) DEFAULT '',          -- bcrypt hash, пустая = без пароля
    expires_at      TIMESTAMP WITH TIME ZONE,         -- NULL = бессрочная
    max_downloads   INTEGER DEFAULT 0,                -- 0 = без лимита
    download_count  INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Ровно одно из двух должно быть заполнено
    CONSTRAINT shared_links_target_check CHECK (
        (file_id IS NOT NULL AND folder_id IS NULL) OR
        (file_id IS NULL AND folder_id IS NOT NULL)
    )
);

CREATE INDEX idx_shared_links_token ON shared_links (token);
CREATE INDEX idx_shared_links_file ON shared_links (file_id) WHERE file_id IS NOT NULL;
CREATE INDEX idx_shared_links_folder ON shared_links (folder_id) WHERE folder_id IS NOT NULL;
CREATE INDEX idx_shared_links_created_by ON shared_links (created_by_id);

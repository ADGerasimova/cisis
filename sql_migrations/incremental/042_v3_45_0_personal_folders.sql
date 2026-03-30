-- ============================================================
-- CISIS v3.45.0 — Личные папки для файлового менеджера
-- ============================================================

-- Дерево личных папок
CREATE TABLE IF NOT EXISTS personal_folders (
    id          SERIAL PRIMARY KEY,
    owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id   INTEGER REFERENCES personal_folders(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT personal_folders_name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_personal_folders_owner  ON personal_folders(owner_id);
CREATE INDEX IF NOT EXISTS idx_personal_folders_parent ON personal_folders(parent_id);

-- Шаринг конкретных папок
CREATE TABLE IF NOT EXISTS personal_folder_shares (
    id             SERIAL PRIMARY KEY,
    folder_id      INTEGER NOT NULL REFERENCES personal_folders(id) ON DELETE CASCADE,
    shared_with_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_level   VARCHAR(10) NOT NULL DEFAULT 'VIEW'
                   CHECK (access_level IN ('VIEW', 'EDIT')),
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(folder_id, shared_with_id)
);

CREATE INDEX IF NOT EXISTS idx_pf_shares_folder      ON personal_folder_shares(folder_id);
CREATE INDEX IF NOT EXISTS idx_pf_shares_shared_with ON personal_folder_shares(shared_with_id);

-- Привязка файлов к личным папкам
ALTER TABLE files
    ADD COLUMN IF NOT EXISTS personal_folder_id INTEGER
        REFERENCES personal_folders(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_files_personal_folder ON files(personal_folder_id)
    WHERE personal_folder_id IS NOT NULL;

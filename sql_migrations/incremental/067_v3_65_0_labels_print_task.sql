ALTER TABLE samples
    ADD COLUMN label_printed BOOLEAN NOT NULL DEFAULT FALSE;


ALTER TABLE task_assignees
    ADD COLUMN IF NOT EXISTS started_at timestamp with time zone NULL;
ALTER TABLE feedback_comments
ADD COLUMN file_id INTEGER NULL REFERENCES files(id) ON DELETE SET NULL;

CREATE INDEX idx_feedback_comments_file_id ON feedback_comments(file_id);
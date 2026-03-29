-- v3.44.0: Расширение полей chat_messages для S3-ключей
ALTER TABLE chat_messages ALTER COLUMN file_path TYPE varchar(500);
ALTER TABLE chat_messages ALTER COLUMN file_type TYPE varchar(255);
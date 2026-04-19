-- Миграция 075 v3.79.0: per-area для user_standard_access и
-- equipment_standard_access. REVOKED/GRANTED становятся тройками
-- (subject, standard, area) вместо пар (subject, standard).
--
-- Запуск:
--   cat sql_migrations/075_v3_79_0_per_area_access.sql \
--     | docker compose exec -T db psql -U cisis_user -d cisis
--
-- Откат: только из бэкапа БД (DROP COLUMN теряет информацию о том,
-- какую из per-area строк оставлять как единственную глобальную).

BEGIN;

-- (0) Диагностика: субъекты с access-записями, но без областей.
-- При JOIN дадут 0 строк и оригиналы будут снесены DELETE'ом — потеря данных.
DO $$
DECLARE
  orphan_usa INT;
  orphan_esa INT;
BEGIN
  SELECT COUNT(*) INTO orphan_usa
  FROM user_standard_access usa
  WHERE NOT EXISTS (
    SELECT 1 FROM user_accreditation_areas uaa WHERE uaa.user_id = usa.user_id
  );
  SELECT COUNT(*) INTO orphan_esa
  FROM equipment_standard_access esa
  WHERE NOT EXISTS (
    SELECT 1 FROM equipment_accreditation_areas eaa WHERE eaa.equipment_id = esa.equipment_id
  );
  IF orphan_usa > 0 OR orphan_esa > 0 THEN
    RAISE EXCEPTION
      'Миграция 075: осиротевшие access-записи (usa=%, esa=%). Субъект без областей потеряет access-строки при дублировании.',
      orphan_usa, orphan_esa;
  END IF;
  RAISE NOTICE 'Миграция 075: осиротевших нет, едем.';
END $$;

-- (1) Добавляем area_id, пока NULLable (для шага 3)
ALTER TABLE user_standard_access
  ADD COLUMN area_id INTEGER REFERENCES accreditation_areas(id) ON DELETE CASCADE;
ALTER TABLE equipment_standard_access
  ADD COLUMN area_id INTEGER REFERENCES accreditation_areas(id) ON DELETE CASCADE;

-- (2) Снимаем СТАРЫЙ UNIQUE (subject, standard) ДО INSERT'а дублей.
-- Иначе дубль (149, 104, <area>) конфликтует с оригиналом (149, 104, NULL)
-- по старому ограничению, которое не знает про area_id.
ALTER TABLE user_standard_access
  DROP CONSTRAINT user_standard_access_uniq;
ALTER TABLE equipment_standard_access
  DROP CONSTRAINT equipment_standard_access_uniq;

-- (3) Дублируем каждую старую (subject, std) под каждую текущую область субъекта
INSERT INTO user_standard_access
  (user_id, standard_id, area_id, mode, reason, assigned_by_id, created_at, updated_at)
SELECT usa.user_id, usa.standard_id, uaa.accreditation_area_id, usa.mode, usa.reason,
       usa.assigned_by_id, usa.created_at, usa.updated_at
FROM user_standard_access usa
JOIN user_accreditation_areas uaa ON uaa.user_id = usa.user_id
WHERE usa.area_id IS NULL;

INSERT INTO equipment_standard_access
  (equipment_id, standard_id, area_id, mode, reason, assigned_by_id, created_at, updated_at)
SELECT esa.equipment_id, esa.standard_id, eaa.accreditation_area_id, esa.mode, esa.reason,
       esa.assigned_by_id, esa.created_at, esa.updated_at
FROM equipment_standard_access esa
JOIN equipment_accreditation_areas eaa ON eaa.equipment_id = esa.equipment_id
WHERE esa.area_id IS NULL;

-- (4) Сносим оригиналы без area_id
DELETE FROM user_standard_access WHERE area_id IS NULL;
DELETE FROM equipment_standard_access WHERE area_id IS NULL;

-- (5) Sanity-check после переноса: не осталось NULL и нет дублей тройки
DO $$
DECLARE
  nulls_usa INT;
  nulls_esa INT;
  dups_usa INT;
  dups_esa INT;
BEGIN
  SELECT COUNT(*) INTO nulls_usa FROM user_standard_access WHERE area_id IS NULL;
  SELECT COUNT(*) INTO nulls_esa FROM equipment_standard_access WHERE area_id IS NULL;
  IF nulls_usa > 0 OR nulls_esa > 0 THEN
    RAISE EXCEPTION
      'Миграция 075: после переноса остались строки с area_id IS NULL (usa=%, esa=%)',
      nulls_usa, nulls_esa;
  END IF;

  -- Защита от будущего ADD CONSTRAINT: если вдруг где-то сдублировалась
  -- тройка (subject, std, area), новый UNIQUE упадёт с невнятной ошибкой.
  -- Ловим здесь с понятным сообщением.
  SELECT COUNT(*) INTO dups_usa FROM (
    SELECT user_id, standard_id, area_id, COUNT(*) c
    FROM user_standard_access
    GROUP BY user_id, standard_id, area_id
    HAVING COUNT(*) > 1
  ) t;
  SELECT COUNT(*) INTO dups_esa FROM (
    SELECT equipment_id, standard_id, area_id, COUNT(*) c
    FROM equipment_standard_access
    GROUP BY equipment_id, standard_id, area_id
    HAVING COUNT(*) > 1
  ) t;
  IF dups_usa > 0 OR dups_esa > 0 THEN
    RAISE EXCEPTION
      'Миграция 075: дубли троек (usa=%, esa=%). Смотри GROUP BY ... HAVING COUNT(*) > 1 вручную.',
      dups_usa, dups_esa;
  END IF;
END $$;

-- (6) NOT NULL + новый UNIQUE (subject, standard, area)
ALTER TABLE user_standard_access
  ALTER COLUMN area_id SET NOT NULL;
ALTER TABLE user_standard_access
  ADD CONSTRAINT user_standard_access_uniq
  UNIQUE (user_id, standard_id, area_id);

ALTER TABLE equipment_standard_access
  ALTER COLUMN area_id SET NOT NULL;
ALTER TABLE equipment_standard_access
  ADD CONSTRAINT equipment_standard_access_uniq
  UNIQUE (equipment_id, standard_id, area_id);

-- (7) Индексы под per-area фильтры
CREATE INDEX idx_usa_area ON user_standard_access(area_id);
CREATE INDEX idx_esa_area ON equipment_standard_access(area_id);

COMMIT;
-- ⭐ v3.78.0. Удаление устаревшей таблицы user_standard_exclusions.
--
-- Контекст:
--   В v3.76.0 (миграция 073) данные были перенесены из user_standard_exclusions
--   в user_standard_access с mode='REVOKED'. Таблица user_standard_exclusions
--   оставалась как страховка отката на 1–2 недели.
--
--   19 апреля 2026 пакет v3.73.0–v3.77.0 задеплоен на прод и отработал
--   стабильно. В коде v3.77.0+ обращений к user_standard_exclusions уже нет
--   (алиас api_standard_toggle_exclusion перенаправляет в новую таблицу).
--
--   Можно дропать.
--
-- Безопасность:
--   Перед DROP идёт sanity-check. Если вдруг миграцию 073 на текущем
--   окружении не прогоняли (например, новый сервер) — в user_standard_exclusions
--   могут быть строки, которых нет в user_standard_access. В этом случае
--   миграция прерывается с RAISE EXCEPTION, данные не теряются.

BEGIN;

DO $$
DECLARE
    old_count INTEGER;
    new_count INTEGER;
BEGIN
    SELECT count(*) INTO old_count FROM user_standard_exclusions;
    SELECT count(*) INTO new_count
      FROM user_standard_access
      WHERE mode = 'REVOKED';

    IF old_count > new_count THEN
        RAISE EXCEPTION
            'Миграция 074 прервана: в user_standard_exclusions % строк, '
            'а в user_standard_access (mode=REVOKED) только %. '
            'Сначала проверь, что миграция 073 отработала корректно.',
            old_count, new_count;
    END IF;

    RAISE NOTICE 'Миграция 074: удаляем user_standard_exclusions (% строк). '
                 'В user_standard_access (REVOKED): % строк.',
                 old_count, new_count;
END $$;

DROP TABLE user_standard_exclusions;

COMMIT;

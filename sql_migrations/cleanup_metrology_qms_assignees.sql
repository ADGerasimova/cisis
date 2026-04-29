-- ============================================================================
-- Разовая чистка: снять QMS_HEAD / QMS_ADMIN с исполнителей METROLOGY-задач
-- ============================================================================
-- Контекст: до v3.93.0 в core/services/metrology_checker.py автозадачи МО
-- ошибочно назначались всем работникам отдела СМК (QMS_HEAD, QMS_ADMIN,
-- METROLOGIST). По требованию — задачи должны идти ТОЛЬКО метрологам
-- (плюс ответственный за прибор и его заместитель — это другая ветка кода,
-- не трогается).
--
-- Этот скрипт чистит исторические назначения на ВСЕХ METROLOGY-задачах
-- (в т.ч. закрытых). Метрологи, ответственные за приборы и сами задачи
-- остаются нетронутыми.
--
-- ВАЖНО: это НЕ миграция схемы — это одноразовая чистка данных только
-- для прод-БД. На свежей инсталляции выполнять не нужно (там этих строк
-- просто нет).
--
-- Запуск: dbshell, вручную, под наблюдением. Не класть в incremental/.
-- ============================================================================

BEGIN;

-- 1) Превью того, что будет удалено (необязательный шаг — для самопроверки)
SELECT
    ta.id           AS assignee_id,
    ta.task_id,
    t.title,
    t.status,
    u.id            AS user_id,
    u.username,
    u.role
FROM task_assignees ta
JOIN tasks t ON t.id = ta.task_id
JOIN users u ON u.id = ta.user_id
WHERE t.task_type = 'METROLOGY'
  AND u.role IN ('QMS_HEAD', 'QMS_ADMIN')
ORDER BY t.id;

-- 2) Удаление
DELETE FROM task_assignees
WHERE id IN (
    SELECT ta.id
    FROM task_assignees ta
    JOIN tasks t ON t.id = ta.task_id
    JOIN users u ON u.id = ta.user_id
    WHERE t.task_type = 'METROLOGY'
      AND u.role IN ('QMS_HEAD', 'QMS_ADMIN')
);

-- 3) Контрольная проверка — должно вернуть 0 строк
SELECT COUNT(*) AS remaining_qms_on_metrology
FROM task_assignees ta
JOIN tasks t ON t.id = ta.task_id
JOIN users u ON u.id = ta.user_id
WHERE t.task_type = 'METROLOGY'
  AND u.role IN ('QMS_HEAD', 'QMS_ADMIN');

-- Если результат COUNT = 0 и DELETE отработал ожидаемое число строк:
COMMIT;

-- Если что-то выглядит не так:
-- ROLLBACK;

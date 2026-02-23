-- ============================================================================
-- CISIS v3.17.0 — Управление видимостью лабораторий
-- Файл: sql_migrations/incremental/009_v3_17_0_laboratory_access.sql
-- Дата: 23 февраля 2026
-- ============================================================================

-- ────────────────────────────────────────────────────────────────
-- 1. Тип подразделения в таблице laboratories
-- ────────────────────────────────────────────────────────────────

ALTER TABLE laboratories
ADD COLUMN IF NOT EXISTS department_type VARCHAR(20) DEFAULT 'LAB';

COMMENT ON COLUMN laboratories.department_type IS 'LAB = лаборатория, WORKSHOP = мастерская, DEPARTMENT = подразделение';

UPDATE laboratories SET department_type = 'LAB'      WHERE code IN ('MI', 'TA', 'ChA', 'ACT');
UPDATE laboratories SET department_type = 'WORKSHOP'  WHERE code = 'WORKSHOP';

-- При необходимости — добавить подразделения:
-- INSERT INTO laboratories (code, code_display, name, department_type, is_active)
-- VALUES ('CLIENT_DEPT', 'ОРЗ', 'Отдел по работе с заказчиками', 'DEPARTMENT', TRUE);
-- INSERT INTO laboratories (code, code_display, name, department_type, is_active)
-- VALUES ('QMS_DEPT', 'СМК', 'Служба менеджмента качества', 'DEPARTMENT', TRUE);


-- ────────────────────────────────────────────────────────────────
-- 2. Таблица role_laboratory_access
-- ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS role_laboratory_access (
    id            SERIAL PRIMARY KEY,
    role          VARCHAR(20)  NOT NULL,
    journal_id    INTEGER      NOT NULL REFERENCES journals(id) ON DELETE CASCADE,
    laboratory_id INTEGER      REFERENCES laboratories(id) ON DELETE CASCADE
    -- laboratory_id = NULL означает "ВСЕ лаборатории"
);

COMMENT ON TABLE role_laboratory_access IS 'Видимость лабораторий по ролям для каждого журнала';
COMMENT ON COLUMN role_laboratory_access.laboratory_id IS 'NULL = все лаборатории';

-- Уникальность для конкретных лабораторий
CREATE UNIQUE INDEX IF NOT EXISTS uq_role_lab_access_specific
ON role_laboratory_access (role, journal_id, laboratory_id)
WHERE laboratory_id IS NOT NULL;

-- Уникальность для "все лаборатории" (одна запись на role+journal)
CREATE UNIQUE INDEX IF NOT EXISTS uq_role_lab_access_all
ON role_laboratory_access (role, journal_id)
WHERE laboratory_id IS NULL;

-- Индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_role_lab_access_lookup
ON role_laboratory_access (role, journal_id);


-- ────────────────────────────────────────────────────────────────
-- 3. Начальные данные: роли, которые видят ВСЕ лаборатории
-- ────────────────────────────────────────────────────────────────
-- Текущий хардкод из _build_base_queryset:
-- CLIENT_MANAGER, CLIENT_DEPT_HEAD, SYSADMIN, QMS_HEAD, QMS_ADMIN,
-- METROLOGIST, CTO, CEO → Sample.objects.all()

INSERT INTO role_laboratory_access (role, journal_id, laboratory_id)
SELECT r.role, j.id, NULL
FROM (VALUES
    ('CEO'),
    ('CTO'),
    ('SYSADMIN'),
    ('CLIENT_MANAGER'),
    ('CLIENT_DEPT_HEAD'),
    ('QMS_HEAD'),
    ('QMS_ADMIN'),
    ('METROLOGIST')
) AS r(role)
CROSS JOIN journals j
WHERE j.code = 'SAMPLES'
ON CONFLICT DO NOTHING;

-- LAB_HEAD и TESTER — НЕ добавляем: они используют fallback
-- (user.laboratory + additional_laboratories)

-- WORKSHOP, WORKSHOP_HEAD — НЕ добавляем: у них отдельная логика
-- (фильтрация по manufacturing/workshop_status, не по лаборатории)


-- ────────────────────────────────────────────────────────────────
-- 4. Проверка
-- ────────────────────────────────────────────────────────────────

-- SELECT r.role, j.code as journal, l.code_display as laboratory
-- FROM role_laboratory_access r
-- JOIN journals j ON j.id = r.journal_id
-- LEFT JOIN laboratories l ON l.id = r.laboratory_id
-- ORDER BY r.role, j.code;

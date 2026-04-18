"""
core/services/equipment_access.py — Допуски: стандарты, оборудование, сотрудники
v3.77.0

═══════════════════════════════════════════════════════════════════════
МОДЕЛЬ ДОПУСКА (v3.77.0, лаб-фильтр + 4-сторонний допуск)
═══════════════════════════════════════════════════════════════════════

Три уровня допуска (сильный бьёт слабого):

  1. Явные overrides в equipment_user_access:
       REVOKED → финал (запрещено);
       GRANTED → финал (разрешено).
  2. SYSADMIN с is_active=True → всегда разрешено.
  3. Автонабор (4-сторонний, v3.77.0):
       ∃ lab L, area A, standard S такие что:
         L ∈ labs(сотрудник) ∩ labs(оборудование)
         A ∈ areas(сотрудник) ∩ areas(оборудование)
         S ∈ standards(A, L)  — стандарт в этой области И лабе
         S ∉ REVOKED(сотрудник)
         S ∉ REVOKED(оборудование)

Эффективные стандарты ОБОРУДОВАНИЯ (v3.77.0):

  эфф.стандарты(eq) = (стандарты, где area ∈ areas(eq) AND lab ∈ labs(eq))
                       ∖ REVOKED_eq  ∪  GRANTED_eq (тоже с лаб-фильтром)

Эффективные стандарты СОТРУДНИКА — без изменений:

  эфф.стандарты(user) = (стандарты_областей(user) ∖ REVOKED_user) ∪ GRANTED_user

GRANTED-стандарт сотрудника НЕ даёт авто-допуск к оборудованию.
Нужен → выдавай equipment_user_access GRANTED напрямую.

───────────────────────────────────────────────────────────────────────
Направленность связей (важно!)

  user_standard_access        — влияет на эфф.стандарты сотрудника,
                                  → меняет его автонабор оборудования
                                  (транзитивно).
  equipment_standard_access   — влияет на эфф.стандарты оборудования,
                                  → меняет его автонабор сотрудников
                                  (транзитивно).
  equipment_user_access       — влияет ТОЛЬКО на связь user↔equipment,
                                  НЕ добавляет сотруднику стандарты
                                  (нет обратной транзитивности).

«Вне области» (accreditation_areas.is_default=TRUE) — валидная область,
не фильтруется нигде в v3.76.0 (фикс от v3.74.0/v3.75.0 отозван).
═══════════════════════════════════════════════════════════════════════
"""

from django.db import connection


# ═════════════════════════════════════════════════════════════════════
# 0. SQL-фрагменты «эффективных стандартов» — используются многократно
# ═════════════════════════════════════════════════════════════════════
#
# Почему CTE, а не хелпер-функция: Postgres хорошо оптимизирует inlined
# CTE (с 12+), плюс запросы-потребители часто фильтруют не только
# по standard_id, но и по смежным полям (лаба, область) — CTE встраивается
# в общий план запроса, отдельная функция — нет.

_USER_EFF_STD_CTE = """
    user_eff_stds AS (
        -- Стандарты областей сотрудника, кроме REVOKED
        SELECT DISTINCT saa.standard_id
        FROM user_accreditation_areas uaa
        JOIN accreditation_areas aa
             ON aa.id = uaa.accreditation_area_id AND aa.is_active = TRUE
        JOIN standard_accreditation_areas saa
             ON saa.accreditation_area_id = aa.id
        JOIN standards s
             ON s.id = saa.standard_id AND s.is_active = TRUE
        WHERE uaa.user_id = %(uid)s
          AND NOT EXISTS (
              SELECT 1 FROM user_standard_access usa
              WHERE usa.user_id = %(uid)s
                AND usa.standard_id = saa.standard_id
                AND usa.mode = 'REVOKED'
          )
        UNION
        -- GRANTED overrides (включая стандарты вне областей сотрудника)
        SELECT usa.standard_id
        FROM user_standard_access usa
        JOIN standards s
             ON s.id = usa.standard_id AND s.is_active = TRUE
        WHERE usa.user_id = %(uid)s
          AND usa.mode = 'GRANTED'
    )
"""

_EQ_EFF_STD_CTE = """
    eq_labs AS (
        SELECT laboratory_id FROM equipment WHERE id = %(eid)s
        UNION
        SELECT laboratory_id FROM equipment_laboratories WHERE equipment_id = %(eid)s
    ),
    eq_eff_stds AS (
        -- Авто: область оборудования ∩ область стандарта ∩ лаба оборудования ∩ лаба стандарта
        SELECT DISTINCT saa.standard_id
        FROM equipment_accreditation_areas eaa
        JOIN accreditation_areas aa
             ON aa.id = eaa.accreditation_area_id AND aa.is_active = TRUE
        JOIN standard_accreditation_areas saa
             ON saa.accreditation_area_id = aa.id
        JOIN standards s
             ON s.id = saa.standard_id AND s.is_active = TRUE
        JOIN standard_laboratories sl
             ON sl.standard_id = s.id
        WHERE eaa.equipment_id = %(eid)s
          AND sl.laboratory_id IN (SELECT laboratory_id FROM eq_labs)
          AND NOT EXISTS (
              SELECT 1 FROM equipment_standard_access esa
              WHERE esa.equipment_id = %(eid)s
                AND esa.standard_id = saa.standard_id
                AND esa.mode = 'REVOKED'
          )
        UNION
        -- GRANTED: вручную, но тоже только если стандарт в лабе оборудования
        SELECT esa.standard_id
        FROM equipment_standard_access esa
        JOIN standards s
             ON s.id = esa.standard_id AND s.is_active = TRUE
        JOIN standard_laboratories sl
             ON sl.standard_id = s.id
        WHERE esa.equipment_id = %(eid)s
          AND esa.mode = 'GRANTED'
          AND sl.laboratory_id IN (SELECT laboratory_id FROM eq_labs)
    )
"""


# ═════════════════════════════════════════════════════════════════════
# 1. Основная: допущенные сотрудники для конкретного оборудования
# ═════════════════════════════════════════════════════════════════════

def get_equipment_allowed_users(equipment, include_trainees=True):
    """
    QuerySet сотрудников, допущенных к работе с этим оборудованием.

    Автонабор (вариант B, v3.76.0):
      лаба ∈ лабы_оборудования  И  эфф.стандарты пересекаются.
    Плюс SYSADMIN и GRANTED overrides, минус REVOKED overrides.
    """
    from core.models import User
    from core.models.equipment import EquipmentUserAccess, EquipmentAccessMode

    if equipment is None or not equipment.pk:
        return User.objects.none()

    # ── 1. Overrides equipment↔user ──────────────────────────────────
    overrides = list(
        EquipmentUserAccess.objects
            .filter(equipment=equipment)
            .values_list('user_id', 'mode')
    )
    revoked_ids = {uid for uid, m in overrides if m == EquipmentAccessMode.REVOKED}
    granted_ids = {uid for uid, m in overrides if m == EquipmentAccessMode.GRANTED}

    # ── 2. SYSADMIN ──────────────────────────────────────────────────
    sysadmin_ids = set(
        User.objects
            .filter(is_active=True, role='SYSADMIN')
            .values_list('id', flat=True)
    )

    # ── 3. Автонабор: лаба + пересечение эфф.стандартов ──────────────
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    auto_ids = _compute_auto_allowed_user_ids(equipment.pk, eq_lab_ids) if eq_lab_ids else set()

    # ── 4. Итог ──────────────────────────────────────────────────────
    final_ids = (auto_ids - revoked_ids) | granted_ids | sysadmin_ids

    qs = (User.objects
              .filter(id__in=final_ids, is_active=True)
              .select_related('laboratory'))
    if not include_trainees:
        qs = qs.exclude(is_trainee=True)
    return qs.order_by('last_name', 'first_name')


def _compute_auto_allowed_user_ids(equipment_id, eq_lab_ids):
    """
    Сырой SQL: set[user_id] — автонабор для оборудования.

    v3.77.0: 4-сторонняя проверка — для допуска нужен общий стандарт
    в общей лабе, в общей области. GRANTED-стандарты сотрудника
    НЕ дают авто-допуск к оборудованию.
    """
    if not eq_lab_ids:
        return set()

    sql = f"""
        WITH
        {_EQ_EFF_STD_CTE}
        SELECT DISTINCT u.id
        FROM users u
        LEFT JOIN user_additional_laboratories ual ON ual.user_id = u.id
        WHERE u.is_active = TRUE
          AND (u.laboratory_id = ANY(%(lab_ids)s) OR ual.laboratory_id = ANY(%(lab_ids)s))
          AND EXISTS (
              -- Стандарт из ОБЛАСТИ сотрудника (не GRANTED!),
              -- который в эфф.стандартах оборудования,
              -- и привязан к ОБЩЕЙ лабе (user ∩ equipment)
              SELECT 1
              FROM user_accreditation_areas uaa
              JOIN accreditation_areas aa
                   ON aa.id = uaa.accreditation_area_id AND aa.is_active = TRUE
              JOIN standard_accreditation_areas saa
                   ON saa.accreditation_area_id = aa.id
              JOIN standards s
                   ON s.id = saa.standard_id AND s.is_active = TRUE
              JOIN standard_laboratories sl
                   ON sl.standard_id = s.id
              WHERE uaa.user_id = u.id
                -- Стандарт не REVOKED у сотрудника
                AND NOT EXISTS (
                    SELECT 1 FROM user_standard_access usa
                    WHERE usa.user_id = u.id
                      AND usa.standard_id = saa.standard_id
                      AND usa.mode = 'REVOKED'
                )
                -- Стандарт есть в эфф.стандартах оборудования
                AND saa.standard_id IN (SELECT standard_id FROM eq_eff_stds)
                -- Стандарт привязан к лабе, общей для сотрудника и оборудования
                AND sl.laboratory_id IN (SELECT laboratory_id FROM eq_labs)
                AND (sl.laboratory_id = u.laboratory_id
                     OR sl.laboratory_id IN (
                         SELECT ual2.laboratory_id
                         FROM user_additional_laboratories ual2
                         WHERE ual2.user_id = u.id
                     ))
          )
    """
    with connection.cursor() as cur:
        cur.execute(sql, {'eid': equipment_id, 'lab_ids': eq_lab_ids})
        return {row[0] for row in cur.fetchall()}


# ═════════════════════════════════════════════════════════════════════
# 2. Обёртки для точечных проверок
# ═════════════════════════════════════════════════════════════════════

def can_user_access_equipment(user, equipment):
    """Быстрая проверка: допущен ли user к equipment."""
    if user is None or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser or user.role == 'SYSADMIN':
        return True
    return get_equipment_allowed_users(equipment).filter(id=user.id).exists()


# ═════════════════════════════════════════════════════════════════════
# 3. Обратная сторона: стандарты и оборудование для СОТРУДНИКА
# ═════════════════════════════════════════════════════════════════════

def get_user_allowed_standards(user):
    """
    Эффективные стандарты сотрудника, сгруппированные для рендера.

    Структура:
        [
            {'area_id': 1, 'area_name': 'Бетоны',
             'standards': [{'id','code','name'}, ...]},
            ...
            # Отдельная группа в конце — GRANTED вне областей сотрудника:
            {'area_id': None, 'area_name': '🔓 Назначены вручную',
             'standards': [...]},
        ]

    «Вне области» (is_default=TRUE) — обычная область, не фильтруется
    (в v3.74.0/v3.75.0 фильтр был, с v3.76.0 снят).
    """
    if user is None or not user.pk:
        return []

        # ⭐ v3.78.0: лабы сотрудника для фильтрации стандартов
        user_lab_ids = list(user.all_laboratory_ids)

        # ── Стандарты через области (с учётом REVOKED и лаб) ─────────────
        sql_area = """
            SELECT aa.id, aa.name, s.id, s.code, s.name
            FROM user_accreditation_areas uaa
            JOIN accreditation_areas aa
                 ON aa.id = uaa.accreditation_area_id AND aa.is_active = TRUE
            JOIN standard_accreditation_areas saa
                 ON saa.accreditation_area_id = aa.id
            JOIN standards s
                 ON s.id = saa.standard_id AND s.is_active = TRUE
            -- ⭐ v3.78.0: стандарт должен быть в одной из лабораторий сотрудника
            JOIN standard_laboratories sl
                 ON sl.standard_id = s.id
            WHERE uaa.user_id = %s
              AND sl.laboratory_id = ANY(%s)
              AND NOT EXISTS (
                  SELECT 1 FROM user_standard_access usa
                  WHERE usa.user_id = uaa.user_id
                    AND usa.standard_id = s.id
                    AND usa.mode = 'REVOKED'
              )
            ORDER BY aa.name, s.code
        """
        # ── Стандарты, назначенные вручную вне областей ──────────────────
        sql_granted = """
            SELECT s.id, s.code, s.name
            FROM user_standard_access usa
            JOIN standards s ON s.id = usa.standard_id AND s.is_active = TRUE
            -- ⭐ v3.78.0: GRANTED тоже фильтруем по лабам сотрудника
            JOIN standard_laboratories sl
                 ON sl.standard_id = s.id
            WHERE usa.user_id = %s
              AND usa.mode = 'GRANTED'
              AND sl.laboratory_id = ANY(%s)
              -- и стандарт НЕ попадает ни в одну область сотрудника (иначе
              -- дубль — он уже виден в области)
              AND NOT EXISTS (
                  SELECT 1 FROM user_accreditation_areas uaa2
                  JOIN standard_accreditation_areas saa2
                       ON saa2.accreditation_area_id = uaa2.accreditation_area_id
                  WHERE uaa2.user_id = usa.user_id
                    AND saa2.standard_id = usa.standard_id
              )
            ORDER BY s.code
        """

        with connection.cursor() as cur:
            cur.execute(sql_area, [user.pk, user_lab_ids])
            area_rows = cur.fetchall()
            cur.execute(sql_granted, [user.pk, user_lab_ids])
            granted_rows = cur.fetchall()

    grouped = {}
    for aid, aname, sid, scode, sname in area_rows:
        b = grouped.setdefault(aid, {'area_id': aid, 'area_name': aname, 'standards': []})
        b['standards'].append({'id': sid, 'code': scode, 'name': sname})

    result = list(grouped.values())
    if granted_rows:
        result.append({
            'area_id': None,
            'area_name': '🔓 Назначены вручную',
            'standards': [{'id': sid, 'code': scode, 'name': sname}
                          for sid, scode, sname in granted_rows],
        })
    return result


def get_user_allowed_equipment(user):
    """
    QuerySet оборудования, к которому допущен сотрудник.

    Автонабор (вариант B): лаба пользователя ∈ лабы оборудования
    И эфф.стандарты пересекаются. Плюс GRANTED, минус REVOKED.
    """
    from core.models.equipment import Equipment, EquipmentUserAccess, EquipmentAccessMode

    if user is None or not user.pk or not user.is_active:
        return Equipment.objects.none()

    # SYSADMIN — всё оборудование
    if user.is_superuser or user.role == 'SYSADMIN':
        return (Equipment.objects
                          .select_related('laboratory', 'room')
                          .order_by('accounting_number'))

    # Overrides
    overrides = list(
        EquipmentUserAccess.objects.filter(user=user).values_list('equipment_id', 'mode')
    )
    revoked_eq_ids = {eid for eid, m in overrides if m == EquipmentAccessMode.REVOKED}
    granted_eq_ids = {eid for eid, m in overrides if m == EquipmentAccessMode.GRANTED}

    # Автонабор
    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        auto_eq_ids = set()
    else:
        auto_eq_ids = _compute_auto_allowed_equipment_ids(user.pk, user_lab_ids)

    final_eq_ids = (auto_eq_ids - revoked_eq_ids) | granted_eq_ids

    return (Equipment.objects
                      .filter(id__in=final_eq_ids)
                      .select_related('laboratory', 'room')
                      .order_by('accounting_number'))


def _compute_auto_allowed_equipment_ids(user_id, user_lab_ids):
    """
    Сырой SQL: set[equipment_id] — автонабор для сотрудника.

    v3.77.0: 4-сторонняя проверка, симметрично _compute_auto_allowed_user_ids.
    Общий стандарт должен быть в общей лабе.
    GRANTED-стандарты сотрудника НЕ дают авто-допуск.
    """
    if not user_lab_ids:
        return set()

    sql = """
        SELECT DISTINCT e.id
        FROM equipment e
        LEFT JOIN equipment_laboratories el ON el.equipment_id = e.id
        WHERE (e.laboratory_id = ANY(%(lab_ids)s) OR el.laboratory_id = ANY(%(lab_ids)s))
          AND EXISTS (
              -- Стандарт из ОБЛАСТИ сотрудника (не GRANTED),
              -- который в авто-стандартах оборудования (область + лаба),
              -- и привязан к ОБЩЕЙ лабе
              SELECT 1
              FROM user_accreditation_areas uaa
              JOIN accreditation_areas aa
                   ON aa.id = uaa.accreditation_area_id AND aa.is_active = TRUE
              JOIN standard_accreditation_areas saa
                   ON saa.accreditation_area_id = aa.id
              JOIN standards s
                   ON s.id = saa.standard_id AND s.is_active = TRUE
              JOIN standard_laboratories sl
                   ON sl.standard_id = s.id
              WHERE uaa.user_id = %(uid)s
                -- Стандарт не REVOKED у сотрудника
                AND NOT EXISTS (
                    SELECT 1 FROM user_standard_access usa
                    WHERE usa.user_id = %(uid)s
                      AND usa.standard_id = saa.standard_id
                      AND usa.mode = 'REVOKED'
                )
                -- Стандарт в области оборудования
                AND EXISTS (
                    SELECT 1
                    FROM equipment_accreditation_areas eaa
                    JOIN standard_accreditation_areas saa2
                         ON saa2.accreditation_area_id = eaa.accreditation_area_id
                    WHERE eaa.equipment_id = e.id
                      AND saa2.standard_id = s.id
                )
                -- Стандарт не REVOKED у оборудования
                AND NOT EXISTS (
                    SELECT 1 FROM equipment_standard_access esa
                    WHERE esa.equipment_id = e.id
                      AND esa.standard_id = s.id
                      AND esa.mode = 'REVOKED'
                )
                -- Стандарт привязан к лабе, общей для сотрудника и оборудования
                AND (sl.laboratory_id = e.laboratory_id
                     OR sl.laboratory_id IN (
                         SELECT el2.laboratory_id
                         FROM equipment_laboratories el2
                         WHERE el2.equipment_id = e.id
                     ))
                AND sl.laboratory_id = ANY(%(lab_ids)s)
          )
    """
    with connection.cursor() as cur:
        cur.execute(sql, {'uid': user_id, 'lab_ids': user_lab_ids})
        return {row[0] for row in cur.fetchall()}


# ═════════════════════════════════════════════════════════════════════
# 4. Breakdown'ы для UI — симметричные по трём сущностям
# ═════════════════════════════════════════════════════════════════════
#
# Каждый breakdown возвращает {'auto', 'granted', 'revoked', 'overrides_by_*'}.
# На объектах granted/revoked прикреплены override_reason и override_assigned_by.


def get_equipment_access_breakdown(equipment):
    """
    Допущенные сотрудники с разбивкой по источнику.
    {auto, granted, revoked, overrides_by_user}.
    SYSADMIN в 'auto' не попадают — не показываем их как обычных операторов.
    """
    from core.models import User
    from core.models.equipment import EquipmentUserAccess, EquipmentAccessMode

    empty = {'auto': [], 'granted': [], 'revoked': [], 'overrides_by_user': {}}
    if equipment is None or not equipment.pk:
        return empty

    # Overrides
    override_qs = (EquipmentUserAccess.objects
                       .filter(equipment=equipment)
                       .select_related('user__laboratory', 'assigned_by'))
    overrides_by_user = {}
    granted_ids, revoked_ids = set(), set()
    for ov in override_qs:
        overrides_by_user[ov.user_id] = {
            'mode': ov.mode, 'reason': ov.notes or '',
            'assigned_by': ov.assigned_by, 'created_at': ov.created_at,
        }
        if ov.mode == EquipmentAccessMode.GRANTED:
            granted_ids.add(ov.user_id)
        elif ov.mode == EquipmentAccessMode.REVOKED:
            revoked_ids.add(ov.user_id)

    # Автонабор (без SYSADMIN)
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    auto_ids = _compute_auto_allowed_user_ids(equipment.pk, eq_lab_ids) if eq_lab_ids else set()
    auto_only_ids = auto_ids - revoked_ids - granted_ids

    # Грузим всех одним запросом
    all_ids = auto_only_ids | granted_ids | revoked_ids
    users_map = {}
    if all_ids:
        for u in (User.objects
                      .filter(id__in=all_ids, is_active=True)
                      .select_related('laboratory')
                      .order_by('last_name', 'first_name')):
            users_map[u.id] = u

    _sort = lambda u: (u.last_name or '', u.first_name or '')
    auto_list    = sorted((users_map[i] for i in auto_only_ids if i in users_map), key=_sort)
    granted_list = sorted((users_map[i] for i in granted_ids    if i in users_map), key=_sort)
    revoked_list = sorted((users_map[i] for i in revoked_ids    if i in users_map), key=_sort)

    for u in granted_list + revoked_list:
        ov = overrides_by_user.get(u.id) or {}
        u.override_reason      = ov.get('reason', '')
        u.override_assigned_by = ov.get('assigned_by')

    return {
        'auto': auto_list, 'granted': granted_list, 'revoked': revoked_list,
        'overrides_by_user': overrides_by_user,
    }


def get_user_equipment_breakdown(user):
    """
    Оборудование сотрудника с разбивкой по источнику.
    {auto, granted, revoked, overrides_by_eq}.
    """
    from core.models.equipment import Equipment, EquipmentUserAccess, EquipmentAccessMode

    empty = {'auto': [], 'granted': [], 'revoked': [], 'overrides_by_eq': {}}
    if user is None or not user.pk or not user.is_active:
        return empty

    override_qs = (EquipmentUserAccess.objects
                       .filter(user=user)
                       .select_related('assigned_by'))
    overrides_by_eq = {}
    granted_ids, revoked_ids = set(), set()
    for ov in override_qs:
        overrides_by_eq[ov.equipment_id] = {
            'mode': ov.mode, 'reason': ov.notes or '',
            'assigned_by': ov.assigned_by, 'created_at': ov.created_at,
        }
        if ov.mode == EquipmentAccessMode.GRANTED:
            granted_ids.add(ov.equipment_id)
        elif ov.mode == EquipmentAccessMode.REVOKED:
            revoked_ids.add(ov.equipment_id)

    user_lab_ids = list(user.all_laboratory_ids)
    auto_ids = _compute_auto_allowed_equipment_ids(user.pk, user_lab_ids) if user_lab_ids else set()
    auto_only_ids = auto_ids - revoked_ids - granted_ids

    all_ids = auto_only_ids | granted_ids | revoked_ids
    eq_map = {}
    if all_ids:
        for e in (Equipment.objects
                      .filter(id__in=all_ids)
                      .select_related('laboratory', 'room')
                      .order_by('laboratory__code_display', 'accounting_number')):
            eq_map[e.id] = e

    _sort = lambda e: (
        (e.laboratory.code_display if e.laboratory else ''),
        e.accounting_number or '',
    )
    auto_list    = sorted((eq_map[i] for i in auto_only_ids if i in eq_map), key=_sort)
    granted_list = sorted((eq_map[i] for i in granted_ids    if i in eq_map), key=_sort)
    revoked_list = sorted((eq_map[i] for i in revoked_ids    if i in eq_map), key=_sort)

    for e in granted_list + revoked_list:
        ov = overrides_by_eq.get(e.id) or {}
        e.override_reason      = ov.get('reason', '')
        e.override_assigned_by = ov.get('assigned_by')

    return {
        'auto': auto_list, 'granted': granted_list, 'revoked': revoked_list,
        'overrides_by_eq': overrides_by_eq,
    }


def get_user_standard_breakdown(user):
    """
    ⭐ v3.76.0. Стандарты сотрудника с разбивкой по источнику.

    {
        'by_area':    [{'area_id','area_name','standards':[{'id','code','name'}]}, ...],
                      # Стандарты автонабора (из областей, кроме REVOKED), сгруппированные
        'granted':    [{'id','code','name','reason','assigned_by'}],
                      # GRANTED overrides (стандарт вне областей, добавлен вручную)
        'revoked':    [{'id','code','name','reason','assigned_by','area_names':[...]}],
                      # REVOKED overrides (из областей, но явно отозваны)
        'overrides_by_std': {standard_id: {'mode','reason','assigned_by'}},
    }
    """
    from core.models import Standard, User

    empty = {'by_area': [], 'granted': [], 'revoked': [], 'overrides_by_std': {}}
    if user is None or not user.pk:
        return empty

    # ── Overrides с деталями ─────────────────────────────────────────
    sql_ov = """
        SELECT usa.standard_id, usa.mode, usa.reason, usa.assigned_by_id
        FROM user_standard_access usa
        WHERE usa.user_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql_ov, [user.pk])
        ov_rows = cur.fetchall()

    overrides_by_std = {sid: {'mode': m, 'reason': r or '', 'assigned_by_id': aid}
                        for sid, m, r, aid in ov_rows}
    granted_sids = {sid for sid, m, *_ in ov_rows if m == 'GRANTED'}
    revoked_sids = {sid for sid, m, *_ in ov_rows if m == 'REVOKED'}

    # ── Заранее подгружаем assigned_by (один SELECT) ────────────────
    assigned_by_ids = {d['assigned_by_id'] for d in overrides_by_std.values() if d['assigned_by_id']}
    assigned_by_map = {u.id: u for u in User.objects.filter(id__in=assigned_by_ids)} if assigned_by_ids else {}

    # ⭐ v3.78.0: лабы сотрудника для фильтрации стандартов
    user_lab_ids = list(user.all_laboratory_ids)

    # ── by_area: стандарты областей сотрудника, КРОМЕ revoked ──────
    sql_area = """
            SELECT aa.id, aa.name, s.id, s.code, s.name
            FROM user_accreditation_areas uaa
            JOIN accreditation_areas aa
                 ON aa.id = uaa.accreditation_area_id AND aa.is_active = TRUE
            JOIN standard_accreditation_areas saa
                 ON saa.accreditation_area_id = aa.id
            JOIN standards s
                 ON s.id = saa.standard_id AND s.is_active = TRUE
            -- ⭐ v3.78.0: стандарт должен быть в одной из лабораторий сотрудника
            JOIN standard_laboratories sl
                 ON sl.standard_id = s.id
            WHERE uaa.user_id = %s
              AND sl.laboratory_id = ANY(%s)
            ORDER BY aa.name, s.code
        """
    with connection.cursor() as cur:
        cur.execute(sql_area, [user.pk, user_lab_ids])
        area_rows = cur.fetchall()

    # Группируем, одновременно собирая имена областей для revoked-стандартов
    grouped = {}
    revoked_area_names = {}  # sid -> [area_name, ...]
    for aid, aname, sid, scode, sname in area_rows:
        if sid in revoked_sids:
            revoked_area_names.setdefault(sid, []).append(aname)
            continue
        b = grouped.setdefault(aid, {'area_id': aid, 'area_name': aname, 'standards': []})
        b['standards'].append({'id': sid, 'code': scode, 'name': sname})
    by_area = list(grouped.values())

    # ── granted (только те, что НЕ в области сотрудника — иначе дубль) ──
    # Область уже подгружена: если sid есть в area_rows, значит он из области.
    area_sids = {sid for _, _, sid, _, _ in area_rows}
    granted_only_sids = granted_sids - area_sids

    granted_list = []
    if granted_only_sids:
        for s in Standard.objects.filter(id__in=granted_only_sids, is_active=True).order_by('code'):
            d = overrides_by_std.get(s.id, {})
            granted_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': d.get('reason', ''),
                'assigned_by': assigned_by_map.get(d.get('assigned_by_id')),
            })

    # ── revoked: все стандарты с mode=REVOKED, независимо от того,
    #    в области ли они (обычно в области, но может быть и артефакт) ──
    revoked_list = []
    if revoked_sids:
        for s in Standard.objects.filter(id__in=revoked_sids, is_active=True).order_by('code'):
            d = overrides_by_std.get(s.id, {})
            revoked_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': d.get('reason', ''),
                'assigned_by': assigned_by_map.get(d.get('assigned_by_id')),
                'area_names': revoked_area_names.get(s.id, []),
            })

    return {
        'by_area': by_area,
        'granted': granted_list,
        'revoked': revoked_list,
        'overrides_by_std': {sid: {'mode': d['mode'], 'reason': d['reason'],
                                     'assigned_by': assigned_by_map.get(d['assigned_by_id'])}
                              for sid, d in overrides_by_std.items()},
    }


def get_equipment_standard_breakdown(equipment):
    """
    ⭐ v3.76.0. Стандарты оборудования с разбивкой по источнику.
    Симметрично get_user_standard_breakdown.
    """
    from core.models import Standard, User

    empty = {'by_area': [], 'granted': [], 'revoked': [], 'overrides_by_std': {}}
    if equipment is None or not equipment.pk:
        return empty

    sql_ov = """
        SELECT esa.standard_id, esa.mode, esa.reason, esa.assigned_by_id
        FROM equipment_standard_access esa
        WHERE esa.equipment_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql_ov, [equipment.pk])
        ov_rows = cur.fetchall()

    overrides_by_std = {sid: {'mode': m, 'reason': r or '', 'assigned_by_id': aid}
                        for sid, m, r, aid in ov_rows}
    granted_sids = {sid for sid, m, *_ in ov_rows if m == 'GRANTED'}
    revoked_sids = {sid for sid, m, *_ in ov_rows if m == 'REVOKED'}

    assigned_by_ids = {d['assigned_by_id'] for d in overrides_by_std.values() if d['assigned_by_id']}
    assigned_by_map = {u.id: u for u in User.objects.filter(id__in=assigned_by_ids)} if assigned_by_ids else {}

    # ⭐ v3.77.0: лабы оборудования для фильтрации стандартов
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))

    sql_area = """
        SELECT aa.id, aa.name, s.id, s.code, s.name
        FROM equipment_accreditation_areas eaa
        JOIN accreditation_areas aa
             ON aa.id = eaa.accreditation_area_id AND aa.is_active = TRUE
        JOIN standard_accreditation_areas saa
             ON saa.accreditation_area_id = aa.id
        JOIN standards s
             ON s.id = saa.standard_id AND s.is_active = TRUE
        -- ⭐ v3.77.0: стандарт должен быть в одной из лабораторий оборудования
        JOIN standard_laboratories sl
             ON sl.standard_id = s.id
        WHERE eaa.equipment_id = %s
          AND sl.laboratory_id = ANY(%s)
        ORDER BY aa.name, s.code
    """
    with connection.cursor() as cur:
        cur.execute(sql_area, [equipment.pk, eq_lab_ids])
        area_rows = cur.fetchall()

    grouped = {}
    revoked_area_names = {}
    for aid, aname, sid, scode, sname in area_rows:
        if sid in revoked_sids:
            revoked_area_names.setdefault(sid, []).append(aname)
            continue
        b = grouped.setdefault(aid, {'area_id': aid, 'area_name': aname, 'standards': []})
        b['standards'].append({'id': sid, 'code': scode, 'name': sname})
    by_area = list(grouped.values())

    area_sids = {sid for _, _, sid, _, _ in area_rows}
    granted_only_sids = granted_sids - area_sids

    granted_list = []
    if granted_only_sids:
        # ⭐ v3.77.0: GRANTED тоже фильтруем по лабам оборудования
        for s in (Standard.objects
                      .filter(id__in=granted_only_sids, is_active=True,
                              standardlaboratory__laboratory_id__in=eq_lab_ids)
                      .distinct()
                      .order_by('code')):
            d = overrides_by_std.get(s.id, {})
            granted_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': d.get('reason', ''),
                'assigned_by': assigned_by_map.get(d.get('assigned_by_id')),
            })

    revoked_list = []
    if revoked_sids:
        for s in Standard.objects.filter(id__in=revoked_sids, is_active=True).order_by('code'):
            d = overrides_by_std.get(s.id, {})
            revoked_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': d.get('reason', ''),
                'assigned_by': assigned_by_map.get(d.get('assigned_by_id')),
                'area_names': revoked_area_names.get(s.id, []),
            })

    return {
        'by_area': by_area,
        'granted': granted_list,
        'revoked': revoked_list,
        'overrides_by_std': {sid: {'mode': d['mode'], 'reason': d['reason'],
                                     'assigned_by': assigned_by_map.get(d['assigned_by_id'])}
                              for sid, d in overrides_by_std.items()},
    }


# ═════════════════════════════════════════════════════════════════════
# 5. Кандидаты для dropdown'ов «+ Добавить ...»
# ═════════════════════════════════════════════════════════════════════

def get_manual_grant_candidates(equipment):
    """
    Сотрудники для dropdown «+ Разрешить вручную» в карточке оборудования.
    Минус: уже в автонаборе, с любым override, SYSADMIN, стажёры.
    """
    from core.models import User
    from core.models.equipment import EquipmentUserAccess

    if equipment is None or not equipment.pk:
        return User.objects.none()

    override_user_ids = set(
        EquipmentUserAccess.objects
            .filter(equipment=equipment)
            .values_list('user_id', flat=True)
    )
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    auto_ids = _compute_auto_allowed_user_ids(equipment.pk, eq_lab_ids) if eq_lab_ids else set()
    excluded_ids = override_user_ids | auto_ids

    return (User.objects
              .filter(is_active=True)
              .exclude(role='SYSADMIN')
              .exclude(is_trainee=True)
              .exclude(id__in=excluded_ids)
              .select_related('laboratory')
              .order_by('laboratory__code_display', 'last_name', 'first_name'))


def get_user_grant_equipment_candidates(user):
    """Оборудование для dropdown «+ Разрешить вручную» в карточке сотрудника."""
    from django.db.models import Q
    from core.models.equipment import Equipment, EquipmentUserAccess

    if user is None or not user.pk or not user.is_active:
        return Equipment.objects.none()

    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        return Equipment.objects.none()

    override_eq_ids = set(
        EquipmentUserAccess.objects.filter(user=user).values_list('equipment_id', flat=True)
    )
    auto_eq_ids = _compute_auto_allowed_equipment_ids(user.pk, user_lab_ids)
    excluded = override_eq_ids | auto_eq_ids

    return (Equipment.objects
              .filter(Q(laboratory_id__in=user_lab_ids) |
                      Q(additional_laboratories__id__in=user_lab_ids))
              .exclude(id__in=excluded)
              .exclude(status='RETIRED')
              .distinct()
              .select_related('laboratory', 'room')
              .order_by('laboratory__code_display', 'accounting_number'))


def get_user_grant_standard_candidates(user):
    """
    ⭐ v3.76.0. Стандарты для dropdown «+ Добавить стандарт» в карточке сотрудника.

    Минус:
      - стандарты, уже попавшие в области сотрудника (они и так в автонаборе,
        если и хочется убрать — это REVOKED из карточки);
      - стандарты, уже в user_standard_access с любым mode.

    Плюс:
      - ограничиваем лабораториями сотрудника (стандарт должен быть
        актуальным хотя бы в одной из его лаб через StandardLaboratory).
    """
    from core.models import Standard

    if user is None or not user.pk or not user.is_active:
        return Standard.objects.none()

    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        return Standard.objects.none()

    # Стандарты в областях сотрудника — исключаем
    sql_in_areas = """
        SELECT DISTINCT saa.standard_id
        FROM user_accreditation_areas uaa
        JOIN standard_accreditation_areas saa
             ON saa.accreditation_area_id = uaa.accreditation_area_id
        WHERE uaa.user_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql_in_areas, [user.pk])
        in_area_ids = {row[0] for row in cur.fetchall()}
        cur.execute(
            "SELECT standard_id FROM user_standard_access WHERE user_id = %s",
            [user.pk],
        )
        in_access_ids = {row[0] for row in cur.fetchall()}

    excluded = in_area_ids | in_access_ids

    # Стандарты в лабах сотрудника — через ORM (Django сам знает имя таблицы).
    return (Standard.objects
              .filter(is_active=True,
                      standardlaboratory__laboratory_id__in=user_lab_ids)
              .exclude(id__in=excluded)
              .distinct()
              .order_by('code'))


def get_equipment_grant_standard_candidates(equipment):
    """
    ⭐ v3.76.0. Стандарты для dropdown «+ Добавить стандарт» в карточке оборудования.
    Симметрично get_user_grant_standard_candidates.
    """
    from core.models import Standard

    if equipment is None or not equipment.pk:
        return Standard.objects.none()

    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    if not eq_lab_ids:
        return Standard.objects.none()

    # ⭐ v3.77.0: кандидат «уже в авто» только если стандарт в области И лабе оборудования
    sql_in_areas = """
        SELECT DISTINCT saa.standard_id
        FROM equipment_accreditation_areas eaa
        JOIN standard_accreditation_areas saa
             ON saa.accreditation_area_id = eaa.accreditation_area_id
        JOIN standard_laboratories sl
             ON sl.standard_id = saa.standard_id
        WHERE eaa.equipment_id = %s
          AND sl.laboratory_id = ANY(%s)
    """
    with connection.cursor() as cur:
        cur.execute(sql_in_areas, [equipment.pk, eq_lab_ids])
        in_area_ids = {row[0] for row in cur.fetchall()}
        cur.execute(
            "SELECT standard_id FROM equipment_standard_access WHERE equipment_id = %s",
            [equipment.pk],
        )
        in_access_ids = {row[0] for row in cur.fetchall()}

    excluded = in_area_ids | in_access_ids

    return (Standard.objects
              .filter(is_active=True,
                      standardlaboratory__laboratory_id__in=eq_lab_ids)
              .exclude(id__in=excluded)
              .distinct()
              .order_by('code'))


# ═════════════════════════════════════════════════════════════════════
# 6. Стандарты/оборудование — «плоские» списки для отображения
# ═════════════════════════════════════════════════════════════════════

def get_equipment_standards(equipment):
    """
    Стандарты оборудования, сгруппированные по областям.
    С учётом equipment_standard_access (REVOKED убирает, GRANTED добавляет
    как отдельную группу «🔓 Назначены вручную»).

    Для обратной совместимости: формат [{'area_id','area_name','standards':[...]}].
    """
    breakdown = get_equipment_standard_breakdown(equipment)
    result = list(breakdown['by_area'])
    if breakdown['granted']:
        result.append({
            'area_id': None,
            'area_name': '🔓 Назначены вручную',
            'standards': [{'id': g['id'], 'code': g['code'], 'name': g['name']}
                          for g in breakdown['granted']],
        })
    return result


def get_standard_equipment(standard):
    """
    Оборудование, работающее по стандарту, с фильтром по лабам стандарта.

    ⭐ v3.75.0: добавлен фильтр по лабам стандарта.
    ⭐ v3.76.0: учитывает equipment_standard_access:
                 REVOKED убирает, GRANTED добавляет (даже если нет общей области).
    """
    from django.db.models import Q
    from core.models.equipment import Equipment

    if standard is None or not standard.pk:
        return Equipment.objects.none()

    area_ids = list(standard.standardaccreditationarea_set
                            .values_list('accreditation_area_id', flat=True))
    std_lab_ids = list(standard.standardlaboratory_set
                               .values_list('laboratory_id', flat=True))
    if not std_lab_ids:
        return Equipment.objects.none()

    # ── 1. Базовый автонабор: оборудование с общей областью и общей лабой
    base_ids = set()
    if area_ids:
        base_ids = set(
            Equipment.objects
                .filter(accreditation_areas__id__in=area_ids)
                .filter(Q(laboratory_id__in=std_lab_ids) |
                        Q(additional_laboratories__id__in=std_lab_ids))
                .values_list('id', flat=True)
        )

    # ── 2. equipment_standard_access overrides для этого стандарта ──
    sql = """
        SELECT esa.equipment_id, esa.mode
        FROM equipment_standard_access esa
        WHERE esa.standard_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql, [standard.pk])
        ov = cur.fetchall()
    granted_ids = {eid for eid, m in ov if m == 'GRANTED'}
    revoked_ids = {eid for eid, m in ov if m == 'REVOKED'}

    final_ids = (base_ids - revoked_ids) | granted_ids

    # GRANTED-оборудование тоже должно быть в лабах стандарта
    # (иначе кросс-лабораторная утечка, как в баге v3.75.0).
    if granted_ids:
        granted_in_labs = set(
            Equipment.objects
                .filter(id__in=granted_ids)
                .filter(Q(laboratory_id__in=std_lab_ids) |
                        Q(additional_laboratories__id__in=std_lab_ids))
                .values_list('id', flat=True)
        )
        final_ids = (final_ids - granted_ids) | granted_in_labs

    return (Equipment.objects
              .filter(id__in=final_ids)
              .distinct()
              .select_related('laboratory', 'room')
              .order_by('laboratory__code_display', 'accounting_number'))


# ═════════════════════════════════════════════════════════════════════
# 7. Операции записи — вызываются из API-views
# ═════════════════════════════════════════════════════════════════════
#
# Эти функции НЕ проверяют права — проверка в вызывающем view.
# Возвращают короткий статус для формирования сообщения/аудита.

def toggle_user_standard_access(user_id, standard_id, mode, reason, actor_id):
    """
    Применяет override user↔standard.

    :param mode: 'GRANTED' | 'REVOKED' | None
                 None — удалить запись (вернуть к «чисто по областям»).
    :return: ('created' | 'updated' | 'deleted' | 'noop', prev_mode or None)
    """
    if mode not in ('GRANTED', 'REVOKED', None):
        raise ValueError(f"mode должен быть 'GRANTED', 'REVOKED' или None, получено: {mode!r}")

    with connection.cursor() as cur:
        cur.execute(
            "SELECT mode FROM user_standard_access WHERE user_id=%s AND standard_id=%s",
            [user_id, standard_id],
        )
        row = cur.fetchone()
        prev_mode = row[0] if row else None

        if mode is None:
            if prev_mode is None:
                return ('noop', None)
            cur.execute(
                "DELETE FROM user_standard_access WHERE user_id=%s AND standard_id=%s",
                [user_id, standard_id],
            )
            return ('deleted', prev_mode)

        if prev_mode is None:
            cur.execute(
                "INSERT INTO user_standard_access "
                "  (user_id, standard_id, mode, reason, assigned_by_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                [user_id, standard_id, mode, reason, actor_id],
            )
            return ('created', None)

        if prev_mode == mode:
            # Обновим reason/assigned_by, но mode не меняется
            cur.execute(
                "UPDATE user_standard_access "
                "SET reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
                "WHERE user_id=%s AND standard_id=%s",
                [reason, actor_id, user_id, standard_id],
            )
            return ('noop', prev_mode)

        cur.execute(
            "UPDATE user_standard_access "
            "SET mode=%s, reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
            "WHERE user_id=%s AND standard_id=%s",
            [mode, reason, actor_id, user_id, standard_id],
        )
        return ('updated', prev_mode)


def toggle_equipment_standard_access(equipment_id, standard_id, mode, reason, actor_id):
    """Симметрично toggle_user_standard_access, но для equipment_standard_access."""
    if mode not in ('GRANTED', 'REVOKED', None):
        raise ValueError(f"mode должен быть 'GRANTED', 'REVOKED' или None, получено: {mode!r}")

    with connection.cursor() as cur:
        cur.execute(
            "SELECT mode FROM equipment_standard_access "
            "WHERE equipment_id=%s AND standard_id=%s",
            [equipment_id, standard_id],
        )
        row = cur.fetchone()
        prev_mode = row[0] if row else None

        if mode is None:
            if prev_mode is None:
                return ('noop', None)
            cur.execute(
                "DELETE FROM equipment_standard_access "
                "WHERE equipment_id=%s AND standard_id=%s",
                [equipment_id, standard_id],
            )
            return ('deleted', prev_mode)

        if prev_mode is None:
            cur.execute(
                "INSERT INTO equipment_standard_access "
                "  (equipment_id, standard_id, mode, reason, assigned_by_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                [equipment_id, standard_id, mode, reason, actor_id],
            )
            return ('created', None)

        if prev_mode == mode:
            cur.execute(
                "UPDATE equipment_standard_access "
                "SET reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
                "WHERE equipment_id=%s AND standard_id=%s",
                [reason, actor_id, equipment_id, standard_id],
            )
            return ('noop', prev_mode)

        cur.execute(
            "UPDATE equipment_standard_access "
            "SET mode=%s, reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
            "WHERE equipment_id=%s AND standard_id=%s",
            [mode, reason, actor_id, equipment_id, standard_id],
        )
        return ('updated', prev_mode)


def replace_user_areas(user_id, area_ids, actor_id=None):
    """
    Полная замена областей аккредитации сотрудника (вариант «А» — «клиент шлёт
    весь список, сервер DELETE + INSERT в транзакции»).

    :param area_ids: итерируемое с id активных областей.
    :param actor_id: ID пользователя, выполняющего операцию (для assigned_by_id).
    :return: {'added': int, 'removed': int, 'kept': int}
    """
    new_ids = set(area_ids)

    with connection.cursor() as cur:
        cur.execute(
            "SELECT accreditation_area_id FROM user_accreditation_areas WHERE user_id=%s",
            [user_id],
        )
        old_ids = {row[0] for row in cur.fetchall()}

        to_add = new_ids - old_ids
        to_remove = old_ids - new_ids
        kept = old_ids & new_ids

        if to_remove:
            cur.execute(
                "DELETE FROM user_accreditation_areas "
                "WHERE user_id=%s AND accreditation_area_id = ANY(%s)",
                [user_id, list(to_remove)],
            )
        if to_add:
            # VALUES (%s, %s, %s), … — строим плейсхолдеры вручную
            values_sql = ','.join(['(%s, %s, %s)'] * len(to_add))
            params = []
            for aid in to_add:
                params.extend([user_id, aid, actor_id])
            cur.execute(
                f"INSERT INTO user_accreditation_areas "
                f"  (user_id, accreditation_area_id, assigned_by_id) VALUES {values_sql} "
                f"  ON CONFLICT DO NOTHING",
                params,
            )

    return {'added': len(to_add), 'removed': len(to_remove), 'kept': len(kept)}


def replace_equipment_areas(equipment_id, area_ids, actor_id=None):
    """
    Симметрично replace_user_areas — через equipment_accreditation_areas.

    :param actor_id: игнорируется, если в таблице нет колонки assigned_by_id
                     (у equipment_accreditation_areas её нет в v3.75.0 — оставляем
                     аргумент для совместимости вызовов).
    """
    new_ids = set(area_ids)

    with connection.cursor() as cur:
        cur.execute(
            "SELECT accreditation_area_id FROM equipment_accreditation_areas "
            "WHERE equipment_id=%s",
            [equipment_id],
        )
        old_ids = {row[0] for row in cur.fetchall()}

        to_add = new_ids - old_ids
        to_remove = old_ids - new_ids
        kept = old_ids & new_ids

        if to_remove:
            cur.execute(
                "DELETE FROM equipment_accreditation_areas "
                "WHERE equipment_id=%s AND accreditation_area_id = ANY(%s)",
                [equipment_id, list(to_remove)],
            )
        if to_add:
            values_sql = ','.join(['(%s, %s)'] * len(to_add))
            params = []
            for aid in to_add:
                params.extend([equipment_id, aid])
            cur.execute(
                f"INSERT INTO equipment_accreditation_areas "
                f"  (equipment_id, accreditation_area_id) VALUES {values_sql} "
                f"  ON CONFLICT DO NOTHING",
                params,
            )

    return {'added': len(to_add), 'removed': len(to_remove), 'kept': len(kept)}


# ═════════════════════════════════════════════════════════════════════
# 8. Хелперы проверки прав — используются view'ами
# ═════════════════════════════════════════════════════════════════════

def can_manage_user_standard_access(actor, target_user):
    """
    Может ли actor редактировать user_standard_access для target_user.

    v3.76.0 правило: SYSADMIN + LAB_HEAD primary-лабы сотрудника.
    Доп.лабы тут НЕ учитываются — стандарты это вопрос квалификации,
    решает «родной» завлаб.
    """
    if actor is None or not actor.is_authenticated or not actor.is_active:
        return False
    if actor.is_superuser or actor.role == 'SYSADMIN':
        return True
    if actor.role == 'LAB_HEAD' and target_user is not None:
        actor_lab_ids = set(actor.all_laboratory_ids)
        return target_user.laboratory_id in actor_lab_ids
    return False


def can_manage_equipment_standard_access(actor, equipment):
    """
    Может ли actor редактировать equipment_standard_access для equipment.

    v3.76.0 правило: SYSADMIN + LAB_HEAD primary-лабы оборудования.
    Доп.лабы НЕ учитываются — стандарты = метрология единицы,
    решает «хозяйка» оборудования (primary-лаба).
    """
    if actor is None or not actor.is_authenticated or not actor.is_active:
        return False
    if actor.is_superuser or actor.role == 'SYSADMIN':
        return True
    if actor.role == 'LAB_HEAD' and equipment is not None:
        actor_lab_ids = set(actor.all_laboratory_ids)
        return equipment.laboratory_id in actor_lab_ids
    return False
"""
core/services/equipment_access.py — Допуски: стандарты, оборудование, сотрудники
v3.79.0

═══════════════════════════════════════════════════════════════════════
МОДЕЛЬ ДОПУСКА (v3.79.0, per-area REVOKED/GRANTED)
═══════════════════════════════════════════════════════════════════════

⭐ v3.79.0: user_standard_access и equipment_standard_access хранят
тройки (subject, standard, area) вместо пар (subject, standard).
Эффективные стандарты теперь — множество ПАР (standard, area), а не
просто множество standards. Аттестация в одной области не означает
аттестации в другой, даже по тому же стандарту.

Три уровня допуска (сильный бьёт слабого):

  1. Явные overrides в equipment_user_access:
       REVOKED → финал (запрещено);
       GRANTED → финал (разрешено).
  2. SYSADMIN с is_active=True → всегда разрешено.
  3. Автонабор (4-сторонний, v3.79.0, пересечение ПАР):
       ∃ lab L, area A, standard S такие что:
         L ∈ labs(сотрудник) ∩ labs(оборудование)
         A ∈ areas(сотрудник) ∩ areas(оборудование)
         S ∈ standards(A, L)  — стандарт в этой области И лабе
         (S, A) ∉ REVOKED(сотрудник)     — не отозван в этой области
         (S, A) ∉ REVOKED(оборудование)  — не отозван в этой области

Эффективные стандарты ОБОРУДОВАНИЯ (v3.79.0, пары):

  эфф.пары(eq) = {(S, A) : area A ∈ areas(eq), lab ∈ labs(eq),
                            (S, A) ∉ REVOKED_eq}
                 ∪ {(S, A) : (eq, S, A) ∈ GRANTED_eq, lab ∈ labs(eq)}

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


_EQ_EFF_STD_PAIRS_CTE = """
    eq_labs AS (
        SELECT laboratory_id FROM equipment WHERE id = %(eid)s
        UNION
        SELECT laboratory_id FROM equipment_laboratories WHERE equipment_id = %(eid)s
    ),
    eq_eff_std_pairs AS (
        -- ⭐ v3.79.0: пары (standard_id, area_id), а не просто standards.
        -- Авто: область оборудования ∩ область стандарта ∩ лаба оборудования ∩ лаба стандарта,
        -- и пара (std, area) не отозвана у оборудования в этой области.
        SELECT DISTINCT saa.standard_id, saa.accreditation_area_id AS area_id
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
                AND esa.area_id = saa.accreditation_area_id
                AND esa.mode = 'REVOKED'
          )
        UNION
        -- GRANTED: пары (std, area) выданы вручную, но только в лабах оборудования
        SELECT esa.standard_id, esa.area_id
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

    ⭐ v3.79.0: пересечение ПАР (standard, area). Для допуска нужен общий
    стандарт в общей лабе И общей области, не отозванный per-area.
    GRANTED-стандарты сотрудника НЕ дают авто-допуск к оборудованию.
    """
    if not eq_lab_ids:
        return set()

    sql = f"""
        WITH
        {_EQ_EFF_STD_PAIRS_CTE}
        SELECT DISTINCT u.id
        FROM users u
        LEFT JOIN user_additional_laboratories ual ON ual.user_id = u.id
        WHERE u.is_active = TRUE
          AND (u.laboratory_id = ANY(%(lab_ids)s) OR ual.laboratory_id = ANY(%(lab_ids)s))
          AND EXISTS (
              -- Пара (std, area) из области сотрудника, которая есть в
              -- эфф.парах оборудования, привязана к общей лабе и не
              -- отозвана у сотрудника per-area.
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
                -- ⭐ v3.79.0: пара (std, area) не отозвана у сотрудника
                AND NOT EXISTS (
                    SELECT 1 FROM user_standard_access usa
                    WHERE usa.user_id = u.id
                      AND usa.standard_id = saa.standard_id
                      AND usa.area_id = saa.accreditation_area_id
                      AND usa.mode = 'REVOKED'
                )
                -- ⭐ v3.79.0: пара (std, area) в эфф.парах оборудования
                AND (saa.standard_id, saa.accreditation_area_id) IN (
                    SELECT standard_id, area_id FROM eq_eff_std_pairs
                )
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

    ⭐ v3.79.0: пересечение ПАР (standard, area), симметрично
    _compute_auto_allowed_user_ids. Общий стандарт должен быть в общей
    лабе и общей области, не отозванный per-area ни у одного из субъектов.
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
              -- Пара (std, area) из области сотрудника, общая с областью
              -- оборудования, не отозванная ни у одного из субъектов.
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
                -- ⭐ v3.79.0: пара (std, area) не отозвана у сотрудника
                AND NOT EXISTS (
                    SELECT 1 FROM user_standard_access usa
                    WHERE usa.user_id = %(uid)s
                      AND usa.standard_id = saa.standard_id
                      AND usa.area_id = saa.accreditation_area_id
                      AND usa.mode = 'REVOKED'
                )
                -- ⭐ v3.79.0: стандарт в ТОЙ ЖЕ области оборудования
                -- (не просто «в какой-то» области, как было в v3.77.0)
                AND EXISTS (
                    SELECT 1
                    FROM equipment_accreditation_areas eaa
                    WHERE eaa.equipment_id = e.id
                      AND eaa.accreditation_area_id = saa.accreditation_area_id
                )
                -- ⭐ v3.79.0: пара (std, area) не отозвана у оборудования
                AND NOT EXISTS (
                    SELECT 1 FROM equipment_standard_access esa
                    WHERE esa.equipment_id = e.id
                      AND esa.standard_id = s.id
                      AND esa.area_id = saa.accreditation_area_id
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
    ⭐ v3.79.0. Стандарты сотрудника с разбивкой по источнику, per-area.

    {
        'by_area':    [{'area_id','area_name','standards':[{'id','code','name'}]}, ...],
                      # Стандарты автонабора, сгруппированные по областям.
                      # Стандарт из области сотрудника ПРОПУСКАЕТСЯ в by_area,
                      # если (std, area) есть в revoked_pairs — он попадёт
                      # только в revoked-список ниже с этой областью в area_names.
                      # Один стандарт может быть одновременно в by_area (в одних
                      # областях) и в revoked (в других областях).
        'granted':    [{'id','code','name','reason','assigned_by'}],
                      # GRANTED-пары на стандарты, которых нет в областях сотрудника.
                      # Редкий edge case: GRANTED в области, которой у user нет.
        'revoked':    [{'id','code','name','reason','assigned_by','area_names':[...]}],
                      # REVOKED per-area. area_names — области, где именно
                      # эта пара (std, area) отозвана; НЕ все области стандарта.
        'overrides_by_std': {},
                      # ⭐ v3.79.0: старая форма несовместима с per-area
                      # (у одного sid разные mode в разных областях).
                      # Шаблон должен читать статусы из by_area/revoked/granted.
    }
    """
    from core.models import Standard, User

    empty = {'by_area': [], 'granted': [], 'revoked': [],
             'revoked_pairs': [], 'overrides_by_std': {}}
    if user is None or not user.pk:
        return empty

    # ── Overrides per-area с именами областей (одним запросом) ──────
    sql_ov = """
        SELECT usa.standard_id, usa.area_id, usa.mode, usa.reason,
               usa.assigned_by_id, aa.name AS area_name
        FROM user_standard_access usa
        JOIN accreditation_areas aa ON aa.id = usa.area_id
        WHERE usa.user_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql_ov, [user.pk])
        ov_rows = cur.fetchall()

    # Ключ override'а — пара (sid, aid), а не просто sid.
    overrides_by_pair = {
        (sid, aid): {'mode': m, 'reason': r or '',
                     'assigned_by_id': abid, 'area_name': an}
        for sid, aid, m, r, abid, an in ov_rows
    }
    revoked_pairs = {pair for pair, d in overrides_by_pair.items() if d['mode'] == 'REVOKED'}
    granted_pairs = {pair for pair, d in overrides_by_pair.items() if d['mode'] == 'GRANTED'}

    # Предзагрузка assigned_by (один SELECT)
    assigned_by_ids = {d['assigned_by_id'] for d in overrides_by_pair.values() if d['assigned_by_id']}
    assigned_by_map = {u.id: u for u in User.objects.filter(id__in=assigned_by_ids)} if assigned_by_ids else {}

    # Лабы сотрудника для фильтрации стандартов
    user_lab_ids = list(user.all_laboratory_ids)

    # ── by_area: стандарты областей сотрудника, КРОМЕ (sid, aid) revoked ──
    sql_area = """
        SELECT aa.id, aa.name, s.id, s.code, s.name
        FROM user_accreditation_areas uaa
        JOIN accreditation_areas aa
             ON aa.id = uaa.accreditation_area_id AND aa.is_active = TRUE
        JOIN standard_accreditation_areas saa
             ON saa.accreditation_area_id = aa.id
        JOIN standards s
             ON s.id = saa.standard_id AND s.is_active = TRUE
        JOIN standard_laboratories sl
             ON sl.standard_id = s.id
        WHERE uaa.user_id = %s
          AND sl.laboratory_id = ANY(%s)
        ORDER BY aa.name, s.code
    """
    with connection.cursor() as cur:
        cur.execute(sql_area, [user.pk, user_lab_ids])
        area_rows = cur.fetchall()

    # Пары (sid, aid) в областях сотрудника — для отсева «orphan GRANTED»
    area_pairs = {(sid, aid) for aid, _, sid, _, _ in area_rows}

    grouped = {}
    for aid, aname, sid, scode, sname in area_rows:
        # ⭐ v3.79.0: пропуск per-area, а не по всему стандарту
        if (sid, aid) in revoked_pairs:
            continue
        b = grouped.setdefault(aid, {'area_id': aid, 'area_name': aname, 'standards': []})
        b['standards'].append({'id': sid, 'code': scode, 'name': sname})
    by_area = list(grouped.values())

    # ── revoked_pairs: по одной записи на пару (std, area) ──
    # В отличие от revoked (deduplicated по sid), revoked_pairs показывает
    # каждую пару отдельно — нужно для UI, где каждая пара — своя плашка
    # с ↩-кнопкой, знающей конкретную область для возврата.
    revoked_pairs_list = []
    if revoked_pairs:
        std_ids_for_pairs = {sid for sid, _ in revoked_pairs}
        std_map_pairs = {s.id: s for s in Standard.objects.filter(
            id__in=list(std_ids_for_pairs), is_active=True
        )}
        for (sid, aid) in revoked_pairs:
            s = std_map_pairs.get(sid)
            if s is None:
                continue
            d = overrides_by_pair[(sid, aid)]
            revoked_pairs_list.append({
                'standard_id': s.id, 'code': s.code, 'name': s.name,
                'area_id': aid, 'area_name': d['area_name'],
                'reason': d['reason'],
                'assigned_by': assigned_by_map.get(d['assigned_by_id']),
            })
        revoked_pairs_list.sort(key=lambda x: (x['code'], x['area_name']))

    # ── revoked_list: уникальные sid, area_names из revoked_pairs ──
    revoked_by_sid = {}
    for (sid, aid) in revoked_pairs:
        d = overrides_by_pair[(sid, aid)]
        entry = revoked_by_sid.setdefault(sid, {
            'reason': d['reason'],
            'assigned_by_id': d['assigned_by_id'],
            'area_names': [],
        })
        entry['area_names'].append(d['area_name'])

    revoked_list = []
    if revoked_by_sid:
        std_map = {s.id: s for s in Standard.objects.filter(
            id__in=list(revoked_by_sid.keys()), is_active=True
        )}
        for sid, entry in revoked_by_sid.items():
            s = std_map.get(sid)
            if s is None:
                continue
            revoked_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': entry['reason'],
                'assigned_by': assigned_by_map.get(entry['assigned_by_id']),
                'area_names': sorted(entry['area_names']),
            })
        revoked_list.sort(key=lambda x: x['code'])

    # ── granted_list: GRANTED-пары на стандарты вне области сотрудника ──
    orphan_granted_pairs = granted_pairs - area_pairs

    granted_by_sid = {}
    for (sid, aid) in orphan_granted_pairs:
        d = overrides_by_pair[(sid, aid)]
        entry = granted_by_sid.setdefault(sid, {
            'reason': d['reason'],
            'assigned_by_id': d['assigned_by_id'],
        })

    granted_list = []
    if granted_by_sid:
        std_map = {s.id: s for s in Standard.objects.filter(
            id__in=list(granted_by_sid.keys()), is_active=True
        )}
        for sid, entry in granted_by_sid.items():
            s = std_map.get(sid)
            if s is None:
                continue
            granted_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': entry['reason'],
                'assigned_by': assigned_by_map.get(entry['assigned_by_id']),
            })
        granted_list.sort(key=lambda x: x['code'])

    return {
        'by_area': by_area,
        'granted': granted_list,
        'revoked': revoked_list,
        # ⭐ v3.79.0: per-area список (одна запись = одна пара), для UI
        # с независимыми плашками и ↩-кнопкой, знающей область.
        'revoked_pairs': revoked_pairs_list,
        # Пустой — форма несовместима с per-area.
        # Шаблон должен читать статусы из by_area/revoked/granted/revoked_pairs.
        'overrides_by_std': {},
    }


def get_equipment_standard_breakdown(equipment):
    """
    ⭐ v3.79.0. Стандарты оборудования с разбивкой по источнику, per-area.
    Симметрично get_user_standard_breakdown (см. там подробный комментарий
    по структуре возврата). GRANTED-пары дополнительно фильтруются по
    лабам оборудования (наследие v3.77.0 — предотвращает кросс-лаб утечку).
    """
    from core.models import Standard, User

    empty = {'by_area': [], 'granted': [], 'revoked': [],
             'revoked_pairs': [], 'overrides_by_std': {}}
    if equipment is None or not equipment.pk:
        return empty

    # ── Overrides per-area с именами областей ──
    sql_ov = """
        SELECT esa.standard_id, esa.area_id, esa.mode, esa.reason,
               esa.assigned_by_id, aa.name AS area_name
        FROM equipment_standard_access esa
        JOIN accreditation_areas aa ON aa.id = esa.area_id
        WHERE esa.equipment_id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql_ov, [equipment.pk])
        ov_rows = cur.fetchall()

    overrides_by_pair = {
        (sid, aid): {'mode': m, 'reason': r or '',
                     'assigned_by_id': abid, 'area_name': an}
        for sid, aid, m, r, abid, an in ov_rows
    }
    revoked_pairs = {pair for pair, d in overrides_by_pair.items() if d['mode'] == 'REVOKED'}
    granted_pairs = {pair for pair, d in overrides_by_pair.items() if d['mode'] == 'GRANTED'}

    assigned_by_ids = {d['assigned_by_id'] for d in overrides_by_pair.values() if d['assigned_by_id']}
    assigned_by_map = {u.id: u for u in User.objects.filter(id__in=assigned_by_ids)} if assigned_by_ids else {}

    # Лабы оборудования для фильтрации стандартов
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
        JOIN standard_laboratories sl
             ON sl.standard_id = s.id
        WHERE eaa.equipment_id = %s
          AND sl.laboratory_id = ANY(%s)
        ORDER BY aa.name, s.code
    """
    with connection.cursor() as cur:
        cur.execute(sql_area, [equipment.pk, eq_lab_ids])
        area_rows = cur.fetchall()

    area_pairs = {(sid, aid) for aid, _, sid, _, _ in area_rows}

    grouped = {}
    for aid, aname, sid, scode, sname in area_rows:
        if (sid, aid) in revoked_pairs:
            continue
        b = grouped.setdefault(aid, {'area_id': aid, 'area_name': aname, 'standards': []})
        b['standards'].append({'id': sid, 'code': scode, 'name': sname})
    by_area = list(grouped.values())

    # ── revoked_pairs: по одной записи на пару (std, area) ──
    # Симметрично user-версии.
    revoked_pairs_list = []
    if revoked_pairs:
        std_ids_for_pairs = {sid for sid, _ in revoked_pairs}
        std_map_pairs = {s.id: s for s in Standard.objects.filter(
            id__in=list(std_ids_for_pairs), is_active=True
        )}
        for (sid, aid) in revoked_pairs:
            s = std_map_pairs.get(sid)
            if s is None:
                continue
            d = overrides_by_pair[(sid, aid)]
            revoked_pairs_list.append({
                'standard_id': s.id, 'code': s.code, 'name': s.name,
                'area_id': aid, 'area_name': d['area_name'],
                'reason': d['reason'],
                'assigned_by': assigned_by_map.get(d['assigned_by_id']),
            })
        revoked_pairs_list.sort(key=lambda x: (x['code'], x['area_name']))

    # ── revoked_list: уникальные sid, area_names из revoked_pairs ──
    revoked_by_sid = {}
    for (sid, aid) in revoked_pairs:
        d = overrides_by_pair[(sid, aid)]
        entry = revoked_by_sid.setdefault(sid, {
            'reason': d['reason'],
            'assigned_by_id': d['assigned_by_id'],
            'area_names': [],
        })
        entry['area_names'].append(d['area_name'])

    revoked_list = []
    if revoked_by_sid:
        std_map = {s.id: s for s in Standard.objects.filter(
            id__in=list(revoked_by_sid.keys()), is_active=True
        )}
        for sid, entry in revoked_by_sid.items():
            s = std_map.get(sid)
            if s is None:
                continue
            revoked_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': entry['reason'],
                'assigned_by': assigned_by_map.get(entry['assigned_by_id']),
                'area_names': sorted(entry['area_names']),
            })
        revoked_list.sort(key=lambda x: x['code'])

    # ── granted_list: GRANTED-пары на стандарты вне области оборудования ──
    # Дополнительно фильтруем по лабам оборудования (v3.77.0 инвариант).
    orphan_granted_pairs = granted_pairs - area_pairs

    granted_by_sid = {}
    for (sid, aid) in orphan_granted_pairs:
        d = overrides_by_pair[(sid, aid)]
        granted_by_sid.setdefault(sid, {
            'reason': d['reason'],
            'assigned_by_id': d['assigned_by_id'],
        })

    granted_list = []
    if granted_by_sid:
        # Фильтр по лабам оборудования — наследие v3.77.0: GRANTED-стандарт
        # вне лабы eq всё равно не показывается.
        std_map = {
            s.id: s for s in (Standard.objects
                              .filter(id__in=list(granted_by_sid.keys()),
                                      is_active=True,
                                      standardlaboratory__laboratory_id__in=eq_lab_ids)
                              .distinct())
        }
        for sid, entry in granted_by_sid.items():
            s = std_map.get(sid)
            if s is None:
                continue
            granted_list.append({
                'id': s.id, 'code': s.code, 'name': s.name,
                'reason': entry['reason'],
                'assigned_by': assigned_by_map.get(entry['assigned_by_id']),
            })
        granted_list.sort(key=lambda x: x['code'])

    return {
        'by_area': by_area,
        'granted': granted_list,
        'revoked': revoked_list,
        # ⭐ v3.79.0: per-area список (одна запись = одна пара)
        'revoked_pairs': revoked_pairs_list,
        # Пустой — несовместим с per-area.
        'overrides_by_std': {},
    }

def get_standard_allowed_users_raw(standard):
    """
    ⭐ v3.79.0. Сырой список сотрудников, допущенных к стандарту, per-area.

    Автонабор: у сотрудника есть область стандарта И пересечение лаб
    (primary или additional) с лабами стандарта.
    Каждая строка помечается флагом `excluded=True`, если для тройки
    (user, standard, area) есть REVOKED-запись в user_standard_access
    ⭐ v3.79.0: исключение per-area, а не по всему стандарту.

    Возвращает: список dict с ключами
      area_id, area_name,
      user_id, last_name, first_name, sur_name,
      lab_display, excluded.

    Один сотрудник может встречаться несколько раз — по записи на каждую
    его область, совпадающую с областями стандарта. Упорядочен по
    (area_name, lab_display, last_name, first_name).
    """
    if standard is None or not standard.pk:
        return []

    area_ids = list(
        standard.standardaccreditationarea_set.values_list('accreditation_area_id', flat=True)
    )
    if not area_ids:
        return []

    with connection.cursor() as cur:
        # ⭐ v3.79.0: REVOKED-исключения — пары (user_id, area_id)
        cur.execute(
            "SELECT user_id, area_id FROM user_standard_access "
            "WHERE standard_id = %s AND mode = 'REVOKED'",
            [standard.pk],
        )
        excluded_pairs = {(uid, aid) for uid, aid in cur.fetchall()}

        # Сотрудники: пересечение областей стандарта с областями сотрудника
        # + стандарт должен быть привязан к одной из лаб сотрудника.
        cur.execute("""
            SELECT DISTINCT
                aa.id AS area_id, aa.name AS area_name,
                u.id AS user_id, u.last_name, u.first_name, u.sur_name,
                l.code_display AS lab_display
            FROM user_accreditation_areas uaa
            JOIN accreditation_areas aa ON aa.id = uaa.accreditation_area_id
            JOIN users u ON u.id = uaa.user_id AND u.is_active = TRUE
            LEFT JOIN laboratories l ON l.id = u.laboratory_id
            WHERE uaa.accreditation_area_id = ANY(%s)
              AND EXISTS (
                  SELECT 1 FROM standard_laboratories sl
                  WHERE sl.standard_id = %s
                    AND (
                        sl.laboratory_id = u.laboratory_id
                        OR sl.laboratory_id IN (
                            SELECT ual.laboratory_id
                            FROM user_additional_laboratories ual
                            WHERE ual.user_id = u.id
                        )
                    )
              )
            ORDER BY aa.name, l.code_display, u.last_name, u.first_name
        """, [area_ids, standard.pk])

        columns = [col[0] for col in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    for r in rows:
        # ⭐ v3.79.0: флаг исключения проверяется per-area
        r['excluded'] = (r['user_id'], r['area_id']) in excluded_pairs
    return rows


def group_standard_users_by_area(raw_rows):
    """
    ⭐ v3.78.0. Группировка результата get_standard_allowed_users_raw
    по (area_id, area_name). Формат под рендер карточки стандарта.

    Возвращает: список dict с ключами
      area_id, area_name, users (список сырых dict), count, excluded_count.
    """
    from itertools import groupby
    result = []
    for (area_id, area_name), group in groupby(
        raw_rows, key=lambda r: (r['area_id'], r['area_name'])
    ):
        users_list = list(group)
        result.append({
            'area_id': area_id,
            'area_name': area_name,
            'users': users_list,
            'count': sum(1 for u in users_list if not u['excluded']),
            'excluded_count': sum(1 for u in users_list if u['excluded']),
        })
    return result

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
    ⭐ v3.79.0. Стандарты для dropdown «+ Добавить стандарт» в карточке сотрудника.

    Правило per-area (Кусок 8): исключаем стандарт только если ВО ВСЕХ
    областях сотрудника он уже покрыт — либо авто (стандарт в области +
    стандарт в лабе сотрудника), либо есть запись в user_standard_access
    для этой пары (GRANTED или REVOKED).

    Иными словами: показываем стандарт в dropdown'е, если существует хотя
    бы одна область сотрудника, где bulk-GRANT реально что-то изменит.
    Если в одной области REVOKED, а в другой ничего нет — стандарт
    показываем, GRANT добавит только во вторую (вариант A2).

    Плюс: ограничиваем лабораториями сотрудника — стандарт должен быть
    в одной из его лаб через StandardLaboratory.
    """
    from core.models import Standard

    if user is None or not user.pk or not user.is_active:
        return Standard.objects.none()

    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        return Standard.objects.none()

    # Стандарт — кандидат, если у user'а есть ХОТЯ БЫ ОДНА область, где:
    #   - стандарт в этой области у user'а (есть запись saa(std, area) и uaa(user, area))
    #     НО нет записи в user_standard_access(user, std, area) — авто-покрытие,
    #     bulk-GRANT пропустит (skipped++), поэтому эта область НЕ делает
    #     стандарт кандидатом.
    #   - ИЛИ стандарт НЕ в этой области у user'а, и нет записи access —
    #     bulk-GRANT добавит, стандарт кандидат.
    # Проще сформулировать через NOT EXISTS: «существует область user'а,
    # где (std, area) не в access И (std НЕ в этой области авто-покрыт)».
    # Ещё короче: «есть область user'а, в которую bulk-GRANT добавит строку».
    #
    # Это сводится к: EXISTS uaa где нет записи usa(user, std, area).
    # (Если уже есть любая запись — bulk пропустит; если нет записи и
    # область пустая по авто — bulk добавит GRANT; если нет записи и
    # по авто покрывает — это означает, что в user_standard_access
    # записи тоже нет, bulk добавит GRANT поверх авто. Последний случай —
    # «бесполезный» с точки зрения эффективного допуска, но технически
    # строка в БД появится, так что стандарт всё равно кандидат.)
    #
    # Единственный способ «уже покрыто во всех областях» — запись в access
    # есть для каждой области user'а. Тогда стандарт НЕ кандидат.
    sql = """
        SELECT DISTINCT sl.standard_id
        FROM standard_laboratories sl
        JOIN standards s ON s.id = sl.standard_id AND s.is_active = TRUE
        WHERE sl.laboratory_id = ANY(%(user_labs)s)
          AND EXISTS (
              SELECT 1 FROM user_accreditation_areas uaa
              WHERE uaa.user_id = %(uid)s
                AND NOT EXISTS (
                    SELECT 1 FROM user_standard_access usa
                    WHERE usa.user_id = uaa.user_id
                      AND usa.standard_id = sl.standard_id
                      AND usa.area_id = uaa.accreditation_area_id
                )
          )
    """
    with connection.cursor() as cur:
        cur.execute(sql, {'uid': user.pk, 'user_labs': user_lab_ids})
        candidate_ids = [row[0] for row in cur.fetchall()]

    if not candidate_ids:
        return Standard.objects.none()

    return (Standard.objects
              .filter(id__in=candidate_ids)
              .order_by('code'))


def get_equipment_grant_standard_candidates(equipment):
    """
    ⭐ v3.79.0. Стандарты для dropdown «+ Добавить стандарт» в карточке оборудования.
    Симметрично get_user_grant_standard_candidates — см. там подробный комментарий.
    """
    from core.models import Standard

    if equipment is None or not equipment.pk:
        return Standard.objects.none()

    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    if not eq_lab_ids:
        return Standard.objects.none()

    sql = """
        SELECT DISTINCT sl.standard_id
        FROM standard_laboratories sl
        JOIN standards s ON s.id = sl.standard_id AND s.is_active = TRUE
        WHERE sl.laboratory_id = ANY(%(eq_labs)s)
          AND EXISTS (
              SELECT 1 FROM equipment_accreditation_areas eaa
              WHERE eaa.equipment_id = %(eid)s
                AND NOT EXISTS (
                    SELECT 1 FROM equipment_standard_access esa
                    WHERE esa.equipment_id = eaa.equipment_id
                      AND esa.standard_id = sl.standard_id
                      AND esa.area_id = eaa.accreditation_area_id
                )
          )
    """
    with connection.cursor() as cur:
        cur.execute(sql, {'eid': equipment.pk, 'eq_labs': eq_lab_ids})
        candidate_ids = [row[0] for row in cur.fetchall()]

    if not candidate_ids:
        return Standard.objects.none()

    return (Standard.objects
              .filter(id__in=candidate_ids)
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
    ⭐ v3.76.0: учитывает equipment_standard_access (REVOKED/GRANTED).
    ⭐ v3.79.0: per-area. Сначала считаем пары (eq_id, area_id), затем
    deduplicate по eq_id. Оборудование, у которого стандарт REVOKED
    в одной области, но работает в другой (через автонабор или GRANT) —
    остаётся в результате.
    """
    from django.db.models import Q
    from core.models.equipment import Equipment

    if standard is None or not standard.pk:
        return Equipment.objects.none()

    std_lab_ids = list(standard.standardlaboratory_set
                               .values_list('laboratory_id', flat=True))
    if not std_lab_ids:
        return Equipment.objects.none()

    # Один SQL возвращает уже отфильтрованные eq_id — пары вычисляются
    # внутри CTE-подобной конструкции и сворачиваются на выходе.
    # Логика:
    #   base_pairs      = (eq_id, area_id) где area у std ∩ area у eq
    #                                       и лаба у std ∩ лаба у eq
    #   effective_pairs = base_pairs ∖ REVOKED_pairs ∪ GRANTED_pairs
    #   GRANTED-пары тоже фильтруются по лабам eq (v3.77.0 инвариант,
    #   защита от кросс-лабораторной утечки).
    sql = """
        WITH
        base_pairs AS (
            SELECT DISTINCT eaa.equipment_id, eaa.accreditation_area_id AS area_id
            FROM equipment_accreditation_areas eaa
            JOIN standard_accreditation_areas saa
                 ON saa.accreditation_area_id = eaa.accreditation_area_id
            JOIN equipment e ON e.id = eaa.equipment_id
            LEFT JOIN equipment_laboratories el ON el.equipment_id = e.id
            WHERE saa.standard_id = %(sid)s
              AND (e.laboratory_id = ANY(%(std_labs)s)
                   OR el.laboratory_id = ANY(%(std_labs)s))
        ),
        revoked_pairs AS (
            SELECT esa.equipment_id, esa.area_id
            FROM equipment_standard_access esa
            WHERE esa.standard_id = %(sid)s AND esa.mode = 'REVOKED'
        ),
        granted_pairs AS (
            -- GRANTED в лабах стандарта (v3.77.0 инвариант).
            -- area_id здесь может не совпадать ни с одной area у eq —
            -- это OK, GRANT как раз может «добавлять» новую область.
            SELECT DISTINCT esa.equipment_id, esa.area_id
            FROM equipment_standard_access esa
            JOIN equipment e ON e.id = esa.equipment_id
            LEFT JOIN equipment_laboratories el ON el.equipment_id = e.id
            WHERE esa.standard_id = %(sid)s
              AND esa.mode = 'GRANTED'
              AND (e.laboratory_id = ANY(%(std_labs)s)
                   OR el.laboratory_id = ANY(%(std_labs)s))
        ),
        effective_pairs AS (
            SELECT equipment_id, area_id FROM base_pairs
            EXCEPT
            SELECT equipment_id, area_id FROM revoked_pairs
            UNION
            SELECT equipment_id, area_id FROM granted_pairs
        )
        SELECT DISTINCT equipment_id FROM effective_pairs
    """
    with connection.cursor() as cur:
        cur.execute(sql, {'sid': standard.pk, 'std_labs': std_lab_ids})
        final_ids = {row[0] for row in cur.fetchall()}

    if not final_ids:
        return Equipment.objects.none()

    return (Equipment.objects
              .filter(id__in=final_ids)
              .select_related('laboratory', 'room')
              .order_by('laboratory__code_display', 'accounting_number'))


# ═════════════════════════════════════════════════════════════════════
# 7. Операции записи — вызываются из API-views
# ═════════════════════════════════════════════════════════════════════
#
# Эти функции НЕ проверяют права — проверка в вызывающем view.
# Возвращают короткий статус для формирования сообщения/аудита.

def toggle_user_standard_access(user_id, standard_id, area_id, mode, reason, actor_id):
    """
    Применяет override user↔standard в конкретной области.

    ⭐ v3.79.0: теперь работает per-area. Одна запись в user_standard_access
    = тройка (user, standard, area). Чтобы отозвать стандарт во всех
    областях сотрудника — вызывается N раз, по разу на каждую область
    (это делает caller; сервис оперирует одной тройкой).

    :param area_id: id области аккредитации, в которой меняем доступ.
    :param mode: 'GRANTED' | 'REVOKED' | None
                 None — удалить запись (вернуть к «чисто по области»).
    :return: ('created' | 'updated' | 'deleted' | 'noop', prev_mode or None)
    """
    if mode not in ('GRANTED', 'REVOKED', None):
        raise ValueError(f"mode должен быть 'GRANTED', 'REVOKED' или None, получено: {mode!r}")

    with connection.cursor() as cur:
        cur.execute(
            "SELECT mode FROM user_standard_access "
            "WHERE user_id=%s AND standard_id=%s AND area_id=%s",
            [user_id, standard_id, area_id],
        )
        row = cur.fetchone()
        prev_mode = row[0] if row else None

        if mode is None:
            if prev_mode is None:
                return ('noop', None)
            cur.execute(
                "DELETE FROM user_standard_access "
                "WHERE user_id=%s AND standard_id=%s AND area_id=%s",
                [user_id, standard_id, area_id],
            )
            return ('deleted', prev_mode)

        if prev_mode is None:
            cur.execute(
                "INSERT INTO user_standard_access "
                "  (user_id, standard_id, area_id, mode, reason, assigned_by_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [user_id, standard_id, area_id, mode, reason, actor_id],
            )
            return ('created', None)

        if prev_mode == mode:
            # Обновим reason/assigned_by, но mode не меняется
            cur.execute(
                "UPDATE user_standard_access "
                "SET reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
                "WHERE user_id=%s AND standard_id=%s AND area_id=%s",
                [reason, actor_id, user_id, standard_id, area_id],
            )
            return ('noop', prev_mode)

        cur.execute(
            "UPDATE user_standard_access "
            "SET mode=%s, reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
            "WHERE user_id=%s AND standard_id=%s AND area_id=%s",
            [mode, reason, actor_id, user_id, standard_id, area_id],
        )
        return ('updated', prev_mode)


def toggle_equipment_standard_access(equipment_id, standard_id, area_id, mode, reason, actor_id):
    """
    Симметрично toggle_user_standard_access, но для equipment_standard_access.
    ⭐ v3.79.0: per-area, принимает area_id.
    """
    if mode not in ('GRANTED', 'REVOKED', None):
        raise ValueError(f"mode должен быть 'GRANTED', 'REVOKED' или None, получено: {mode!r}")

    with connection.cursor() as cur:
        cur.execute(
            "SELECT mode FROM equipment_standard_access "
            "WHERE equipment_id=%s AND standard_id=%s AND area_id=%s",
            [equipment_id, standard_id, area_id],
        )
        row = cur.fetchone()
        prev_mode = row[0] if row else None

        if mode is None:
            if prev_mode is None:
                return ('noop', None)
            cur.execute(
                "DELETE FROM equipment_standard_access "
                "WHERE equipment_id=%s AND standard_id=%s AND area_id=%s",
                [equipment_id, standard_id, area_id],
            )
            return ('deleted', prev_mode)

        if prev_mode is None:
            cur.execute(
                "INSERT INTO equipment_standard_access "
                "  (equipment_id, standard_id, area_id, mode, reason, assigned_by_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [equipment_id, standard_id, area_id, mode, reason, actor_id],
            )
            return ('created', None)

        if prev_mode == mode:
            cur.execute(
                "UPDATE equipment_standard_access "
                "SET reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
                "WHERE equipment_id=%s AND standard_id=%s AND area_id=%s",
                [reason, actor_id, equipment_id, standard_id, area_id],
            )
            return ('noop', prev_mode)

        cur.execute(
            "UPDATE equipment_standard_access "
            "SET mode=%s, reason=%s, assigned_by_id=%s, updated_at=CURRENT_TIMESTAMP "
            "WHERE equipment_id=%s AND standard_id=%s AND area_id=%s",
            [mode, reason, actor_id, equipment_id, standard_id, area_id],
        )
        return ('updated', prev_mode)


# ═════════════════════════════════════════════════════════════════════
# ⭐ v3.79.0 Кусок 6: bulk-операции для «+ Добавить стандарт» dropdown'ов
# ═════════════════════════════════════════════════════════════════════
#
# Dropdown «+ Добавить стандарт» глобально выбирает стандарт и даёт его
# субъекту во всех его областях. Операция симметричная — ✕ на «🔓-плашке»
# удаляет GRANT'ы во всех областях для этого стандарта.
#
# Семантика bulk GRANT (вариант A2): INSERT только туда, где нет записи.
# Осознанно поставленный REVOKED в какой-то области не перезаписывается.
# Если во всех областях уже есть запись — add=0, операция noop.


def grant_standard_to_all_user_areas(user_id, standard_id, reason, actor_id):
    """
    Вставить GRANTED-запись (user, standard, area) во все области сотрудника,
    где для этой пары ещё нет записи в user_standard_access.

    Существующие REVOKED не перезаписываем (вариант A2).

    :return: {'added': int, 'skipped': int, 'user_area_count': int}
             skipped — области, где уже была запись (REVOKED или GRANTED).
    """
    with connection.cursor() as cur:
        # Сколько всего областей у сотрудника (для метрики skipped)
        cur.execute(
            "SELECT COUNT(*) FROM user_accreditation_areas WHERE user_id=%s",
            [user_id],
        )
        user_area_count = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO user_standard_access
                (user_id, standard_id, area_id, mode, reason, assigned_by_id)
            SELECT %s, %s, uaa.accreditation_area_id, 'GRANTED', %s, %s
            FROM user_accreditation_areas uaa
            WHERE uaa.user_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM user_standard_access usa
                  WHERE usa.user_id = uaa.user_id
                    AND usa.standard_id = %s
                    AND usa.area_id = uaa.accreditation_area_id
              )
            """,
            [user_id, standard_id, reason, actor_id, user_id, standard_id],
        )
        added = cur.rowcount

    return {
        'added': added,
        'skipped': user_area_count - added,
        'user_area_count': user_area_count,
    }


def clear_standard_grant_all_user_areas(user_id, standard_id):
    """
    Снять GRANTED-записи во всех областях для пары (user, standard).
    REVOKED не трогаем (парный к grant_standard_to_all_user_areas).

    :return: {'deleted': int}
    """
    with connection.cursor() as cur:
        cur.execute(
            "DELETE FROM user_standard_access "
            "WHERE user_id=%s AND standard_id=%s AND mode='GRANTED'",
            [user_id, standard_id],
        )
        deleted = cur.rowcount
    return {'deleted': deleted}


def grant_standard_to_all_equipment_areas(equipment_id, standard_id, reason, actor_id):
    """
    Симметрично grant_standard_to_all_user_areas — для оборудования.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM equipment_accreditation_areas WHERE equipment_id=%s",
            [equipment_id],
        )
        eq_area_count = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO equipment_standard_access
                (equipment_id, standard_id, area_id, mode, reason, assigned_by_id)
            SELECT %s, %s, eaa.accreditation_area_id, 'GRANTED', %s, %s
            FROM equipment_accreditation_areas eaa
            WHERE eaa.equipment_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM equipment_standard_access esa
                  WHERE esa.equipment_id = eaa.equipment_id
                    AND esa.standard_id = %s
                    AND esa.area_id = eaa.accreditation_area_id
              )
            """,
            [equipment_id, standard_id, reason, actor_id, equipment_id, standard_id],
        )
        added = cur.rowcount

    return {
        'added': added,
        'skipped': eq_area_count - added,
        'equipment_area_count': eq_area_count,
    }


def clear_standard_grant_all_equipment_areas(equipment_id, standard_id):
    """
    Симметрично clear_standard_grant_all_user_areas — для оборудования.
    """
    with connection.cursor() as cur:
        cur.execute(
            "DELETE FROM equipment_standard_access "
            "WHERE equipment_id=%s AND standard_id=%s AND mode='GRANTED'",
            [equipment_id, standard_id],
        )
        deleted = cur.rowcount
    return {'deleted': deleted}


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
"""
core/services/equipment_access.py — Допуски сотрудников к оборудованию
v3.73.0

Итоговый набор допущенных сотрудников:

    auto_set   = сотрудники с is_active=True, у которых
                   1) лаба ∈ (primary + additional) лабы оборудования
                   2) user_accreditation_areas ∩ equipment_accreditation_areas ≠ ∅
                   3) в этом пересечении есть хотя бы один стандарт,
                      НЕ попавший в user_standard_exclusions у этого сотрудника
    revoked    = { u : EquipmentUserAccess(equipment, u, 'REVOKED') }
    granted    = { u : EquipmentUserAccess(equipment, u, 'GRANTED') }

    result     = (auto_set ∖ revoked) ∪ granted ∪ {SYSADMIN, is_active=True}

Функции-обёртки:
    get_equipment_allowed_users(equipment, include_trainees=True)
        → QuerySet[User], уже отсортированный по ФИО
    can_user_access_equipment(user, equipment)
        → bool
    get_user_allowed_equipment_ids(user)
        → set[int] — список id оборудования, к которому сотрудник допущен
                     (обратный расчёт — для карточки сотрудника)
    get_user_allowed_standards(user)
        → list[dict] — стандарты, к которым допущен сотрудник, сгруппированные
                       по областям (все стандарты его областей минус исключения)
"""

from django.db import connection


# ═════════════════════════════════════════════════════════════════
# Основная: допущенные сотрудники для конкретного оборудования
# ═════════════════════════════════════════════════════════════════

def get_equipment_allowed_users(equipment, include_trainees=True):
    """
    Возвращает QuerySet сотрудников, допущенных к работе с этим оборудованием.

    :param equipment: инстанс Equipment
    :param include_trainees: если False — исключить стажёров из результата
    :return: QuerySet[User] с select_related('laboratory'), отсортированный по ФИО
    """
    from core.models import User
    from core.models.equipment import EquipmentUserAccess, EquipmentAccessMode

    if equipment is None:
        return User.objects.none()

    # ── 1. Overrides ──────────────────────────────────────────────
    overrides = list(
        EquipmentUserAccess.objects
            .filter(equipment=equipment)
            .values_list('user_id', 'mode')
    )
    revoked_ids = {uid for uid, mode in overrides if mode == EquipmentAccessMode.REVOKED}
    granted_ids = {uid for uid, mode in overrides if mode == EquipmentAccessMode.GRANTED}

    # ── 2. SYSADMIN — всегда в списке ─────────────────────────────
    sysadmin_ids = set(
        User.objects
            .filter(is_active=True, role='SYSADMIN')
            .values_list('id', flat=True)
    )

    # ── 3. Автонабор ──────────────────────────────────────────────
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    eq_area_ids = list(equipment.accreditation_areas.values_list('id', flat=True))

    if eq_lab_ids and eq_area_ids:
        auto_ids = _compute_auto_allowed_ids(eq_lab_ids, eq_area_ids)
    else:
        auto_ids = set()

    # ── 4. Итог ───────────────────────────────────────────────────
    final_ids = (auto_ids - revoked_ids) | granted_ids | sysadmin_ids

    qs = (User.objects
              .filter(id__in=final_ids, is_active=True)
              .select_related('laboratory'))

    if not include_trainees:
        qs = qs.exclude(is_trainee=True)

    return qs.order_by('last_name', 'first_name')


def _compute_auto_allowed_ids(eq_lab_ids, eq_area_ids):
    """
    Сырым SQL считает автонабор (без overrides / SYSADMIN).

    Условия:
      - is_active=True
      - лаба пользователя (primary ИЛИ additional) ∈ eq_lab_ids
      - хотя бы одна область пользователя ∈ eq_area_ids
      - в этих общих областях есть хотя бы один стандарт,
        которого нет в user_standard_exclusions у этого сотрудника

    Возвращает: set[int] — id сотрудников.
    """
    if not eq_lab_ids or not eq_area_ids:
        return set()

    sql = """
        SELECT DISTINCT u.id
        FROM users u
        LEFT JOIN user_additional_laboratories ual ON ual.user_id = u.id
        JOIN user_accreditation_areas uaa ON uaa.user_id = u.id
        WHERE u.is_active = TRUE
          AND (u.laboratory_id = ANY(%s) OR ual.laboratory_id = ANY(%s))
          AND uaa.accreditation_area_id = ANY(%s)
          AND EXISTS (
              -- В пересечённой области есть хотя бы один стандарт,
              -- которого нет в исключениях у этого сотрудника
              SELECT 1
              FROM standard_accreditation_areas saa
              WHERE saa.accreditation_area_id = uaa.accreditation_area_id
                AND NOT EXISTS (
                    SELECT 1
                    FROM user_standard_exclusions use
                    WHERE use.user_id = u.id
                      AND use.standard_id = saa.standard_id
                )
          )
    """
    with connection.cursor() as cur:
        cur.execute(sql, [eq_lab_ids, eq_lab_ids, eq_area_ids])
        return {row[0] for row in cur.fetchall()}


# ═════════════════════════════════════════════════════════════════
# Обёртки для точечных проверок
# ═════════════════════════════════════════════════════════════════

def can_user_access_equipment(user, equipment):
    """
    Быстрая проверка: допущен ли конкретный пользователь к конкретному оборудованию.

    SYSADMIN и суперпользователи — всегда True.
    Неавторизованный / неактивный — всегда False.
    """
    if user is None or not user.is_authenticated:
        return False
    if not user.is_active:
        return False
    if user.is_superuser or user.role == 'SYSADMIN':
        return True

    return get_equipment_allowed_users(equipment).filter(id=user.id).exists()


# ═════════════════════════════════════════════════════════════════
# Обратные расчёты для карточки сотрудника
# ═════════════════════════════════════════════════════════════════

def get_user_allowed_standards(user):
    """
    Возвращает стандарты, к которым фактически допущен сотрудник:
    все стандарты его областей аккредитации, МИНУС исключения.

    Группирует по областям для удобного рендера в карточке.

    :return: list[dict] вида:
        [
            {
                'area_id':   1,
                'area_name': 'Бетоны',
                'standards': [
                    {'id': 17, 'code': 'ГОСТ 10180-2012', 'name': '…'},
                    …
                ],
            },
            …
        ]
    """
    if user is None or not user.pk:
        return []

    sql = """
        SELECT
            aa.id          AS area_id,
            aa.name        AS area_name,
            s.id           AS standard_id,
            s.code         AS standard_code,
            s.name         AS standard_name
        FROM user_accreditation_areas uaa
        JOIN accreditation_areas aa        ON aa.id = uaa.accreditation_area_id
        JOIN standard_accreditation_areas saa ON saa.accreditation_area_id = aa.id
        JOIN standards s                    ON s.id  = saa.standard_id
        WHERE uaa.user_id = %s
          AND aa.is_active = TRUE
          AND aa.is_default = FALSE    -- ⭐ v3.74.0: исключаем «Вне области»
          AND s.is_active  = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM user_standard_exclusions use
              WHERE use.user_id = uaa.user_id
                AND use.standard_id = s.id
          )
        ORDER BY aa.name, s.code
    """
    with connection.cursor() as cur:
        cur.execute(sql, [user.pk])
        rows = cur.fetchall()

    # Группируем по областям
    grouped = {}
    for area_id, area_name, std_id, std_code, std_name in rows:
        bucket = grouped.setdefault(area_id, {
            'area_id':   area_id,
            'area_name': area_name,
            'standards': [],
        })
        bucket['standards'].append({
            'id':   std_id,
            'code': std_code,
            'name': std_name,
        })

    return list(grouped.values())


def get_user_allowed_equipment(user):
    """
    Возвращает оборудование, к которому допущен сотрудник.

    Логика симметрична get_equipment_allowed_users, но идёт от пользователя:
      1. Список оборудования, где лаба пересекается с лабами пользователя
         и область — с областями пользователя, и есть не-исключённые стандарты.
      2. Плюс GRANTED override'ы на него.
      3. Минус REVOKED override'ы.

    Возвращает: QuerySet[Equipment] (select_related('laboratory', 'room'),
                 отсортированный по accounting_number).
    """
    from core.models.equipment import (
        Equipment, EquipmentUserAccess, EquipmentAccessMode,
    )

    if user is None or not user.pk or not user.is_active:
        return Equipment.objects.none()

    # SYSADMIN видит всё оборудование
    if user.is_superuser or user.role == 'SYSADMIN':
        return (Equipment.objects
                          .select_related('laboratory', 'room')
                          .order_by('accounting_number'))

    # ── Overrides ─────────────────────────────────────────────────
    overrides = list(
        EquipmentUserAccess.objects
            .filter(user=user)
            .values_list('equipment_id', 'mode')
    )
    revoked_eq_ids = {eid for eid, mode in overrides if mode == EquipmentAccessMode.REVOKED}
    granted_eq_ids = {eid for eid, mode in overrides if mode == EquipmentAccessMode.GRANTED}

    # ── Автонабор: сырым SQL, симметрично _compute_auto_allowed_ids ──
    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        auto_eq_ids = set()
    else:
        sql = """
            SELECT DISTINCT e.id
            FROM equipment e
            LEFT JOIN equipment_laboratories el ON el.equipment_id = e.id
            JOIN equipment_accreditation_areas eaa ON eaa.equipment_id = e.id
            JOIN user_accreditation_areas uaa
                 ON uaa.accreditation_area_id = eaa.accreditation_area_id
                AND uaa.user_id = %s
            WHERE (e.laboratory_id = ANY(%s) OR el.laboratory_id = ANY(%s))
              AND EXISTS (
                  SELECT 1
                  FROM standard_accreditation_areas saa
                  WHERE saa.accreditation_area_id = eaa.accreditation_area_id
                    AND NOT EXISTS (
                        SELECT 1 FROM user_standard_exclusions use
                        WHERE use.user_id = %s
                          AND use.standard_id = saa.standard_id
                    )
              )
        """
        with connection.cursor() as cur:
            cur.execute(sql, [user.pk, user_lab_ids, user_lab_ids, user.pk])
            auto_eq_ids = {row[0] for row in cur.fetchall()}

    final_eq_ids = (auto_eq_ids - revoked_eq_ids) | granted_eq_ids

    return (Equipment.objects
                      .filter(id__in=final_eq_ids)
                      .select_related('laboratory', 'room')
                      .order_by('accounting_number'))


# ═════════════════════════════════════════════════════════════════
# ⭐ v3.74.0 — Детализация допуска для UI карточки оборудования
# ═════════════════════════════════════════════════════════════════

def get_equipment_access_breakdown(equipment):
    """
    Возвращает допущенных сотрудников с пометкой источника допуска.

    Итоговая структура для UI:
        {
            'auto':    [User, …],  # автонабор (минус REVOKED, минус GRANTED)
            'granted': [User, …],  # override GRANTED (в т.ч. повторно-разрешённые)
            'revoked': [User, …],  # override REVOKED (были бы в auto, но явно запрещены)
            'overrides_by_user': {user_id: {'mode', 'reason', 'assigned_by'}},
        }

    SYSADMIN в 'auto' не попадают — они допущены технически, не показываем их
    в UI карточки оборудования как обычных операторов.
    """
    from core.models import User
    from core.models.equipment import EquipmentUserAccess, EquipmentAccessMode

    if equipment is None:
        return {'auto': [], 'granted': [], 'revoked': [], 'overrides_by_user': {}}

    # ── Overrides с деталями ──────────────────────────────────────
    override_qs = (EquipmentUserAccess.objects
                       .filter(equipment=equipment)
                       .select_related('user__laboratory', 'assigned_by'))
    overrides_by_user = {}
    granted_ids, revoked_ids = set(), set()
    for ov in override_qs:
        overrides_by_user[ov.user_id] = {
            'mode': ov.mode,
            'reason': ov.notes or '',
            'assigned_by': ov.assigned_by,
            'created_at': ov.created_at,
        }
        if ov.mode == EquipmentAccessMode.GRANTED:
            granted_ids.add(ov.user_id)
        elif ov.mode == EquipmentAccessMode.REVOKED:
            revoked_ids.add(ov.user_id)

    # ── Автонабор (как в get_equipment_allowed_users, но БЕЗ sysadmin) ──
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    eq_area_ids = list(equipment.accreditation_areas.values_list('id', flat=True))

    if eq_lab_ids and eq_area_ids:
        auto_ids = _compute_auto_allowed_ids(eq_lab_ids, eq_area_ids)
    else:
        auto_ids = set()

    # Из auto убираем тех, кто в revoked и granted
    auto_only_ids = auto_ids - revoked_ids - granted_ids

    # Загружаем все группы одним запросом
    all_ids = auto_only_ids | granted_ids | revoked_ids
    users_map = {}
    if all_ids:
        for u in (User.objects
                      .filter(id__in=all_ids, is_active=True)
                      .select_related('laboratory')
                      .order_by('last_name', 'first_name')):
            users_map[u.id] = u

    auto_list    = [users_map[uid] for uid in auto_only_ids if uid in users_map]
    granted_list = [users_map[uid] for uid in granted_ids    if uid in users_map]
    revoked_list = [users_map[uid] for uid in revoked_ids    if uid in users_map]

    # Сортировка по ФИО
    _sort_key = lambda u: (u.last_name or '', u.first_name or '')
    auto_list.sort(key=_sort_key)
    granted_list.sort(key=_sort_key)
    revoked_list.sort(key=_sort_key)

    # Прикрепляем override-детали к user-объектам для удобства в шаблоне
    for u in granted_list + revoked_list:
        ov = overrides_by_user.get(u.id) or {}
        u.override_reason      = ov.get('reason', '')
        u.override_assigned_by = ov.get('assigned_by')

    return {
        'auto':               auto_list,
        'granted':            granted_list,
        'revoked':            revoked_list,
        'overrides_by_user':  overrides_by_user,
    }


def get_manual_grant_candidates(equipment):
    """
    Сотрудники, которых можно добавить к оборудованию через GRANTED override.

    Это все активные сотрудники, МИНУС:
      - те, кто уже в автонаборе (им override не нужен);
      - те, на ком уже есть override (любой — GRANTED или REVOKED);
      - SYSADMIN (они и так допущены);
      - стажёры (не должны получать ручной допуск к оборудованию).

    :return: QuerySet[User] для dropdown'а «+ Разрешить вручную»
    """
    from core.models import User
    from core.models.equipment import EquipmentUserAccess

    if equipment is None:
        return User.objects.none()

    # Все, у кого уже есть override (любого типа) — исключаем
    override_user_ids = set(
        EquipmentUserAccess.objects
            .filter(equipment=equipment)
            .values_list('user_id', flat=True)
    )

    # Авто-допущенные — исключаем
    eq_lab_ids = list(equipment.all_laboratories.values_list('id', flat=True))
    eq_area_ids = list(equipment.accreditation_areas.values_list('id', flat=True))
    if eq_lab_ids and eq_area_ids:
        auto_ids = _compute_auto_allowed_ids(eq_lab_ids, eq_area_ids)
    else:
        auto_ids = set()

    excluded_ids = override_user_ids | auto_ids

    qs = (User.objects
              .filter(is_active=True)
              .exclude(role='SYSADMIN')
              .exclude(is_trainee=True)
              .exclude(id__in=excluded_ids)
              .select_related('laboratory')
              .order_by('laboratory__code_display', 'last_name', 'first_name'))
    return qs


# ═════════════════════════════════════════════════════════════════
# Стандарты оборудования / оборудование по стандарту
# ═════════════════════════════════════════════════════════════════

def get_equipment_standards(equipment):
    """
    Стандарты, по которым работает оборудование — через области аккредитации.

    Возвращает стандарты, сгруппированные по областям:
        [
            {'area_id': 1, 'area_name': 'Бетоны',
             'standards': [{'id', 'code', 'name'}, …]},
            …
        ]
    """
    if equipment is None or not equipment.pk:
        return []

    sql = """
        SELECT
            aa.id   AS area_id,
            aa.name AS area_name,
            s.id    AS standard_id,
            s.code  AS standard_code,
            s.name  AS standard_name
        FROM equipment_accreditation_areas eaa
        JOIN accreditation_areas aa           ON aa.id = eaa.accreditation_area_id
        JOIN standard_accreditation_areas saa ON saa.accreditation_area_id = aa.id
        JOIN standards s                       ON s.id = saa.standard_id
        WHERE eaa.equipment_id = %s
          AND aa.is_active = TRUE
          AND s.is_active  = TRUE
        ORDER BY aa.name, s.code
    """
    with connection.cursor() as cur:
        cur.execute(sql, [equipment.pk])
        rows = cur.fetchall()

    grouped = {}
    for area_id, area_name, std_id, std_code, std_name in rows:
        bucket = grouped.setdefault(area_id, {
            'area_id':   area_id,
            'area_name': area_name,
            'standards': [],
        })
        bucket['standards'].append({
            'id':   std_id,
            'code': std_code,
            'name': std_name,
        })
    return list(grouped.values())


def get_standard_equipment(standard):
    """
    Оборудование, в областях аккредитации которого присутствует этот стандарт
    И лаба которого (primary или доп) пересекается с лабами стандарта.

    ⭐ v3.75.0: добавлен фильтр по лабам — иначе в карточку стандарта
    попадало оборудование чужой лабы, случайно имеющее общую область
    с этим стандартом.
    """
    from django.db.models import Q
    from core.models.equipment import Equipment

    if standard is None or not standard.pk:
        return Equipment.objects.none()

    area_ids = list(
        standard.standardaccreditationarea_set
                .values_list('accreditation_area_id', flat=True)
    )
    std_lab_ids = list(
        standard.standardlaboratory_set
                .values_list('laboratory_id', flat=True)
    )
    if not area_ids or not std_lab_ids:
        return Equipment.objects.none()

    return (Equipment.objects
              .filter(accreditation_areas__id__in=area_ids)
              .filter(Q(laboratory_id__in=std_lab_ids) |
                      Q(additional_laboratories__id__in=std_lab_ids))
              .distinct()
              .select_related('laboratory', 'room')
              .order_by('laboratory__code_display', 'accounting_number'))

# ═════════════════════════════════════════════════════════════════
# ⭐ v3.75.0 — Детализация допуска для UI карточки СОТРУДНИКА
# ═════════════════════════════════════════════════════════════════

def get_user_equipment_breakdown(user):
    """
    Разбивка оборудования, к которому допущен сотрудник — для UI карточки.

    Симметрично get_equipment_access_breakdown(equipment), но «с обратной стороны».

    Возвращает:
        {
            'auto':    [Equipment, …],  # автонабор (минус REVOKED, минус GRANTED)
            'granted': [Equipment, …],  # override GRANTED
            'revoked': [Equipment, …],  # override REVOKED (попали бы в auto, но запрещены)
            'overrides_by_eq': {eq_id: {'mode', 'reason', 'assigned_by'}},
        }

    На объектах из granted/revoked прикреплены атрибуты override_reason
    и override_assigned_by для удобного рендера в шаблоне.
    """
    from core.models.equipment import Equipment, EquipmentUserAccess, EquipmentAccessMode

    empty = {'auto': [], 'granted': [], 'revoked': [], 'overrides_by_eq': {}}
    if user is None or not user.pk or not user.is_active:
        return empty

    # ── Overrides с деталями ──────────────────────────────────────
    override_qs = (EquipmentUserAccess.objects
                       .filter(user=user)
                       .select_related('assigned_by'))
    overrides_by_eq = {}
    granted_ids, revoked_ids = set(), set()
    for ov in override_qs:
        overrides_by_eq[ov.equipment_id] = {
            'mode': ov.mode,
            'reason': ov.notes or '',
            'assigned_by': ov.assigned_by,
            'created_at': ov.created_at,
        }
        if ov.mode == EquipmentAccessMode.GRANTED:
            granted_ids.add(ov.equipment_id)
        elif ov.mode == EquipmentAccessMode.REVOKED:
            revoked_ids.add(ov.equipment_id)

    # ── Автонабор ────────────────────────────────────────────────
    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        auto_ids = set()
    else:
        sql = """
            SELECT DISTINCT e.id
            FROM equipment e
            LEFT JOIN equipment_laboratories el ON el.equipment_id = e.id
            JOIN equipment_accreditation_areas eaa ON eaa.equipment_id = e.id
            JOIN user_accreditation_areas uaa
                 ON uaa.accreditation_area_id = eaa.accreditation_area_id
                AND uaa.user_id = %s
            WHERE (e.laboratory_id = ANY(%s) OR el.laboratory_id = ANY(%s))
              AND EXISTS (
                  SELECT 1 FROM standard_accreditation_areas saa
                  WHERE saa.accreditation_area_id = eaa.accreditation_area_id
                    AND NOT EXISTS (
                        SELECT 1 FROM user_standard_exclusions use
                        WHERE use.user_id = %s
                          AND use.standard_id = saa.standard_id
                    )
              )
        """
        with connection.cursor() as cur:
            cur.execute(sql, [user.pk, user_lab_ids, user_lab_ids, user.pk])
            auto_ids = {row[0] for row in cur.fetchall()}

    # Из auto убираем тех, кто в revoked/granted
    auto_only_ids = auto_ids - revoked_ids - granted_ids

    # Грузим все группы одним запросом
    all_ids = auto_only_ids | granted_ids | revoked_ids
    eq_map = {}
    if all_ids:
        for e in (Equipment.objects
                      .filter(id__in=all_ids)
                      .select_related('laboratory', 'room')
                      .order_by('laboratory__code_display', 'accounting_number')):
            eq_map[e.id] = e

    auto_list    = [eq_map[i] for i in auto_only_ids if i in eq_map]
    granted_list = [eq_map[i] for i in granted_ids    if i in eq_map]
    revoked_list = [eq_map[i] for i in revoked_ids    if i in eq_map]

    _sort = lambda e: (
        (e.laboratory.code_display if e.laboratory else ''),
        e.accounting_number or '',
    )
    auto_list.sort(key=_sort)
    granted_list.sort(key=_sort)
    revoked_list.sort(key=_sort)

    # Прикрепляем override-детали к объектам Equipment для шаблона
    for e in granted_list + revoked_list:
        ov = overrides_by_eq.get(e.id) or {}
        e.override_reason      = ov.get('reason', '')
        e.override_assigned_by = ov.get('assigned_by')

    return {
        'auto':            auto_list,
        'granted':         granted_list,
        'revoked':         revoked_list,
        'overrides_by_eq': overrides_by_eq,
    }

def get_user_grant_equipment_candidates(user):
    """
    ⭐ v3.75.0 — Оборудование для dropdown «+ Разрешить вручную» в карточке сотрудника.

    Возвращает QuerySet[Equipment]: оборудование в лабах сотрудника,
    МИНУС: уже в автонаборе, уже override'нутое, выведенное из эксплуатации.

    Симметрично get_manual_grant_candidates(equipment).
    """
    from django.db.models import Q
    from core.models.equipment import Equipment, EquipmentUserAccess

    if user is None or not user.pk or not user.is_active:
        return Equipment.objects.none()

    user_lab_ids = list(user.all_laboratory_ids)
    if not user_lab_ids:
        return Equipment.objects.none()

    # Override'ы сотрудника — исключаем (у него уже есть запись)
    override_eq_ids = set(
        EquipmentUserAccess.objects
            .filter(user=user)
            .values_list('equipment_id', flat=True)
    )

    # Автонабор — исключаем (сотрудник и так допущен)
    breakdown = get_user_equipment_breakdown(user)
    auto_eq_ids = {e.id for e in breakdown['auto']}

    excluded = override_eq_ids | auto_eq_ids

    # Оборудование в лабах сотрудника (primary или доп) и не выведенное
    return (Equipment.objects
              .filter(Q(laboratory_id__in=user_lab_ids) |
                      Q(additional_laboratories__id__in=user_lab_ids))
              .exclude(id__in=excluded)
              .exclude(status='RETIRED')
              .distinct()
              .select_related('laboratory', 'room')
              .order_by('laboratory__code_display', 'accounting_number'))
"""
analytics_views.py — Страница аналитики + все API-эндпоинты
v4.0.0 — полная переделка

Расположение: core/views/analytics_views.py

Что изменилось по сравнению с v3.38.0:
    • Добавлены блоки: воронка/конвейер, риски, drill-down,
      производительность сотрудников, матрица загрузки.
    • KPI-карточки теперь возвращают {value, previous, delta_pct}
      для отображения дельт к прошлому периоду.
    • Безопасная сборка SQL без f-строк внутри WHERE.
    • Кеширование тяжёлых агрегатов (TTL 60 сек).
    • Поддержка пресетов периодов: today/week/month/quarter/year/custom.
    • Единый формат ответов {data, meta}.
    • Медианы вместо средних там, где это честнее.
    • Учёт ЗАМ-протоколов как метрики качества.
    • Drill-down: возвращает список образцов по любым фильтрам.
"""

from datetime import date, timedelta, datetime
from functools import wraps
import hashlib
import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache

from core.permissions import PermissionChecker


# ═════════════════════════════════════════════════════════════════════════════
# 1. БАЗОВЫЕ ХЕЛПЕРЫ
# ═════════════════════════════════════════════════════════════════════════════

def _fetchall(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetchval(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return row[0] if row else None


def _fetchone(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


# ─────────────────────────────────────────────────────────────────────────────
# Период: пресеты + custom
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_period(request):
    """
    Возвращает (date_from, date_to, period_label) как date-объекты + строка.

    Поддерживаемые значения параметра ?period=:
        today, week, month (по умолчанию), quarter, year, custom.

    Для custom используются ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD.
    Если период не распознан — fallback на текущий месяц.
    """
    period = (request.GET.get('period') or 'month').strip().lower()
    today = date.today()

    if period == 'today':
        return today, today, 'today'

    if period == 'week':
        # Понедельник текущей недели → сегодня
        return today - timedelta(days=today.weekday()), today, 'week'

    if period == 'month':
        return today.replace(day=1), today, 'month'

    if period == 'quarter':
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=q_start_month, day=1), today, 'quarter'

    if period == 'year':
        return today.replace(month=1, day=1), today, 'year'

    if period == 'custom':
        try:
            df = datetime.strptime(request.GET['date_from'], '%Y-%m-%d').date()
            dt = datetime.strptime(request.GET['date_to'], '%Y-%m-%d').date()
            if df > dt:
                df, dt = dt, df
            return df, dt, 'custom'
        except (KeyError, ValueError):
            pass  # fallback ниже

    # Fallback
    return today.replace(day=1), today, 'month'


def _previous_period(date_from, date_to):
    """Возвращает предыдущий период такой же длины (для расчёта дельт)."""
    delta = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=delta - 1)
    return prev_from, prev_to


def _delta_pct(current, previous):
    """Процентное изменение. None если previous=0 и current!=0 (бесконечность)."""
    if previous is None or previous == 0:
        return None if (current or 0) != 0 else 0.0
    return round(((current or 0) - previous) / previous * 100, 1)


def _kpi_card(value, previous):
    """Унифицированный формат карточки KPI."""
    return {
        'value': value,
        'previous': previous,
        'delta_pct': _delta_pct(value, previous),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Сборка WHERE-условий
# ─────────────────────────────────────────────────────────────────────────────

class Filters:
    """
    Безопасный сборщик WHERE для samples.

    Использование:
        f = Filters.from_request(request)
        sql = f"SELECT COUNT(*) FROM samples s WHERE 1=1 {f.where}"
        _fetchval(sql, f.params)
    """

    def __init__(self, conditions, params, date_from, date_to,
                 lab_id, period_label, alias='s'):
        self.conditions = conditions  # list[str]
        self.params = params          # list
        self.date_from = date_from
        self.date_to = date_to
        self.lab_id = lab_id
        self.period_label = period_label
        self.alias = alias

    @property
    def where(self):
        """Возвращает 'AND cond1 AND cond2 ...' или ''."""
        return ' AND ' + ' AND '.join(self.conditions) if self.conditions else ''

    @classmethod
    def from_request(cls, request, alias='s', date_column='registration_date'):
        date_from, date_to, period_label = _resolve_period(request)
        lab_id = int(request.GET.get('lab_id') or 0)

        col = f'{alias}.{date_column}'
        conditions = [
            f'{col} >= %s',
            f'{col} < %s::date + INTERVAL \'1 day\'',
        ]
        params = [date_from, date_to]

        if lab_id:
            conditions.append(f'{alias}.laboratory_id = %s')
            params.append(lab_id)

        return cls(conditions, params, date_from, date_to,
                   lab_id, period_label, alias)

    def for_previous_period(self):
        """Версия фильтра для предыдущего периода (той же длины)."""
        prev_from, prev_to = _previous_period(self.date_from, self.date_to)
        col = f'{self.alias}.registration_date'
        conditions = [
            f'{col} >= %s',
            f'{col} < %s::date + INTERVAL \'1 day\'',
        ]
        params = [prev_from, prev_to]
        if self.lab_id:
            conditions.append(f'{self.alias}.laboratory_id = %s')
            params.append(self.lab_id)
        return Filters(conditions, params, prev_from, prev_to,
                       self.lab_id, 'previous', self.alias)

    def meta(self):
        return {
            'date_from': self.date_from.isoformat(),
            'date_to': self.date_to.isoformat(),
            'period': self.period_label,
            'lab_id': self.lab_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Декораторы: права + кеширование
# ─────────────────────────────────────────────────────────────────────────────

def analytics_access_required(view_func):
    """Проверяет право ANALYTICS/access. При отсутствии — 403."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
            return JsonResponse({'error': 'forbidden'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def cached_api(ttl=60):
    """
    Кеширует JSON-ответ API-эндпоинта на TTL секунд.
    Ключ — хэш от (view_name, user_id, GET-параметры).

    Кеш автоматически использует настроенный бэкенд:
    LocMem в DEBUG, Redis в продакшене (из settings.CACHES).
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            key_raw = json.dumps({
                'view': view_func.__name__,
                'user': request.user.id,
                'params': dict(sorted(request.GET.items())),
                'args': args,
                'kwargs': kwargs,
            }, default=str, sort_keys=True)
            cache_key = 'analytics:' + hashlib.md5(key_raw.encode()).hexdigest()

            cached = cache.get(cache_key)
            if cached is not None:
                return JsonResponse(cached, safe=False)

            response = view_func(request, *args, **kwargs)
            if isinstance(response, JsonResponse) and response.status_code == 200:
                payload = json.loads(response.content.decode())
                cache.set(cache_key, payload, ttl)
            return response
        return wrapper
    return decorator


def _ok(data, meta=None):
    """Успешный ответ в унифицированном формате."""
    payload = {'data': data}
    if meta is not None:
        payload['meta'] = meta
    return JsonResponse(payload, safe=False)


# ═════════════════════════════════════════════════════════════════════════════
# 2. СТРАНИЦЫ (HTML)
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def analytics_view(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return redirect('workspace_home')
    return render(request, 'core/analytics.html', {
        'can_edit': PermissionChecker.can_edit(request.user, 'ANALYTICS', 'access'),
    })


@login_required
def analytics_employees_view(request):
    """Отдельная страница: производительность сотрудников."""
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return redirect('workspace_home')
    return render(request, 'core/analytics_employees.html', {
        'can_edit': PermissionChecker.can_edit(request.user, 'ANALYTICS', 'access'),
    })


@login_required
def analytics_employee_detail_view(request, user_id):
    """Персональная страница сотрудника (drill-down)."""
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return redirect('workspace_home')
    return render(request, 'core/analytics_employee_detail.html', {
        'target_user_id': user_id,
    })


# ═════════════════════════════════════════════════════════════════════════════
# 3. СПРАВОЧНИКИ ДЛЯ ФИЛЬТРОВ
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=300)
def api_laboratories(request):
    rows = _fetchall("""
        SELECT id, name, code, code_display
        FROM laboratories
        WHERE is_active = TRUE AND department_type = 'LAB'
        ORDER BY name
    """)
    data = [{'id': 0, 'name': 'Все лаборатории', 'code': 'ALL',
             'code_display': 'ALL'}] + rows
    return _ok(data)


@analytics_access_required
@cached_api(ttl=300)
def api_test_types(request):
    """Справочник типов испытаний (из samples.test_type/test_code)."""
    rows = _fetchall("""
        SELECT test_code, test_type, COUNT(*) AS samples_count
        FROM samples
        WHERE test_code != '' AND test_type != ''
        GROUP BY test_code, test_type
        ORDER BY samples_count DESC
    """)
    return _ok(rows)


# ═════════════════════════════════════════════════════════════════════════════
# 4. БЛОК 1 — KPI-КАРТОЧКИ (С ДЕЛЬТАМИ)
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=60)
def api_kpi(request):
    """
    Возвращает все KPI-карточки с расчётом дельт к предыдущему периоду.
    Формат каждой карточки: {value, previous, delta_pct}.
    """
    f = Filters.from_request(request)
    fp = f.for_previous_period()

    def count_cur(extra_cond=''):
        sql = f"SELECT COUNT(*) FROM samples s WHERE 1=1 {f.where} {extra_cond}"
        return _fetchval(sql, f.params) or 0

    def count_prev(extra_cond=''):
        sql = f"SELECT COUNT(*) FROM samples s WHERE 1=1 {fp.where} {extra_cond}"
        return _fetchval(sql, fp.params) or 0

    # 1. Всего образцов (не отменённых)
    total_cur = count_cur("AND s.status != 'CANCELLED'")
    total_prev = count_prev("AND s.status != 'CANCELLED'")

    # 2. Завершено
    completed_cur = count_cur("AND s.status = 'COMPLETED'")
    completed_prev = count_prev("AND s.status = 'COMPLETED'")

    # 3. В работе (не считаем предыдущий период — метрика «сейчас»)
    active = _fetchval(f"""
        SELECT COUNT(*) FROM samples s
        WHERE s.status NOT IN ('COMPLETED','CANCELLED') {f.where}
    """, f.params) or 0

    # 4. Просрочено (deadline прошёл, не завершён)
    overdue = _fetchval(f"""
        SELECT COUNT(*) FROM samples s
        WHERE s.deadline < CURRENT_DATE
          AND s.status NOT IN ('COMPLETED','CANCELLED')
          {f.where}
    """, f.params) or 0

    # 5. SLA — % завершённых до deadline (от всех завершённых за период)
    sla_cur = _fetchone(f"""
        SELECT
            COUNT(*) FILTER (WHERE s.testing_end_datetime::date <= s.deadline) AS in_time,
            COUNT(*) AS total
        FROM samples s
        WHERE s.status = 'COMPLETED'
          AND s.testing_end_datetime IS NOT NULL
          AND s.deadline IS NOT NULL
          {f.where}
    """, f.params) or {'in_time': 0, 'total': 0}
    sla_prev = _fetchone(f"""
        SELECT
            COUNT(*) FILTER (WHERE s.testing_end_datetime::date <= s.deadline) AS in_time,
            COUNT(*) AS total
        FROM samples s
        WHERE s.status = 'COMPLETED'
          AND s.testing_end_datetime IS NOT NULL
          AND s.deadline IS NOT NULL
          {fp.where}
    """, fp.params) or {'in_time': 0, 'total': 0}

    sla_pct_cur = round(sla_cur['in_time'] / sla_cur['total'] * 100, 1) \
        if sla_cur['total'] else 0.0
    sla_pct_prev = round(sla_prev['in_time'] / sla_prev['total'] * 100, 1) \
        if sla_prev['total'] else 0.0

    # 6. Медианная длительность испытания (только само испытание)
    median_test_hours_cur = _fetchval(f"""
        SELECT COALESCE(ROUND(
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (s.testing_end_datetime - s.testing_start_datetime)) / 3600
            )::numeric, 1
        ), 0)
        FROM samples s
        WHERE s.testing_start_datetime IS NOT NULL
          AND s.testing_end_datetime IS NOT NULL
          {f.where}
    """, f.params) or 0
    median_test_hours_prev = _fetchval(f"""
        SELECT COALESCE(ROUND(
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (s.testing_end_datetime - s.testing_start_datetime)) / 3600
            )::numeric, 1
        ), 0)
        FROM samples s
        WHERE s.testing_start_datetime IS NOT NULL
          AND s.testing_end_datetime IS NOT NULL
          {fp.where}
    """, fp.params) or 0

    # 7. Отменено
    cancelled_cur = count_cur("AND s.status = 'CANCELLED'")
    cancelled_prev = count_prev("AND s.status = 'CANCELLED'")

    # 8. Замещающие протоколы — индикатор качества
    replacement_cur = count_cur("AND s.replacement_count > 0")
    replacement_prev = count_prev("AND s.replacement_count > 0")

    # 9. Активных сотрудников (LAB) — метрика «сейчас»
    emp_sql = """
        SELECT COUNT(*) FROM users u
        JOIN laboratories l ON u.laboratory_id = l.id
        WHERE u.is_active = TRUE AND l.department_type = 'LAB'
    """
    emp_params = []
    if f.lab_id:
        emp_sql += " AND u.laboratory_id = %s"
        emp_params.append(f.lab_id)
    employees = _fetchval(emp_sql, emp_params) or 0

    # 10. Оборудование в работе
    eq_sql = "SELECT COUNT(*) FROM equipment WHERE status = 'OPERATIONAL'"
    eq_params = []
    if f.lab_id:
        eq_sql += " AND laboratory_id = %s"
        eq_params.append(f.lab_id)
    equipment_ok = _fetchval(eq_sql, eq_params) or 0

    # 11. Оборудование с истекающей поверкой (30 дней)
    eq_expiring_sql = """
        SELECT COUNT(DISTINCT e.id)
        FROM equipment e
        JOIN equipment_maintenance em ON em.equipment_id = e.id
        WHERE em.valid_until IS NOT NULL
          AND em.valid_until BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
          AND e.status != 'RETIRED'
    """
    eq_expiring_params = []
    if f.lab_id:
        eq_expiring_sql += " AND e.laboratory_id = %s"
        eq_expiring_params.append(f.lab_id)
    equipment_expiring = _fetchval(eq_expiring_sql, eq_expiring_params) or 0

    # 12. Активные договоры и уникальные заказчики за период
    active_contracts = _fetchval("""
        SELECT COUNT(*) FROM contracts WHERE status = 'ACTIVE'
    """) or 0

    unique_clients_cur = _fetchval(f"""
        SELECT COUNT(DISTINCT s.client_id)
        FROM samples s
        WHERE s.status != 'CANCELLED' {f.where}
    """, f.params) or 0
    unique_clients_prev = _fetchval(f"""
        SELECT COUNT(DISTINCT s.client_id)
        FROM samples s
        WHERE s.status != 'CANCELLED' {fp.where}
    """, fp.params) or 0

    data = {
        'total_samples':         _kpi_card(total_cur, total_prev),
        'completed':             _kpi_card(completed_cur, completed_prev),
        'active_samples':        _kpi_card(active, None),
        'overdue_samples':       _kpi_card(overdue, None),
        'sla_pct':               _kpi_card(sla_pct_cur, sla_pct_prev),
        'median_test_hours':     _kpi_card(float(median_test_hours_cur),
                                           float(median_test_hours_prev)),
        'cancelled':             _kpi_card(cancelled_cur, cancelled_prev),
        'replacement_samples':   _kpi_card(replacement_cur, replacement_prev),
        'active_employees':      _kpi_card(employees, None),
        'equipment_operational': _kpi_card(equipment_ok, None),
        'equipment_expiring':    _kpi_card(equipment_expiring, None),
        'active_contracts':      _kpi_card(active_contracts, None),
        'unique_clients':        _kpi_card(unique_clients_cur, unique_clients_prev),
    }

    return _ok(data, meta=f.meta())


# ═════════════════════════════════════════════════════════════════════════════
# 5. БЛОК 2 — ВОРОНКА / КОНВЕЙЕР
# ═════════════════════════════════════════════════════════════════════════════

# Группировка 22 статусов по этапам жизненного цикла
STAGE_MAP = {
    'Регистрация':   ['PENDING_VERIFICATION', 'REGISTERED'],
    'Изготовление':  ['MANUFACTURING', 'MANUFACTURED', 'TRANSFERRED',
                      'UZK_TESTING', 'UZK_READY'],
    'Подготовка':    ['MOISTURE_CONDITIONING', 'MOISTURE_READY',
                      'ACCEPTED_IN_LAB', 'CONDITIONING', 'READY_FOR_TEST'],
    'Испытание':     ['IN_TESTING', 'TESTED'],
    'Отчёт':         ['DRAFT_READY', 'RESULTS_UPLOADED'],
    'СМК':           ['PROTOCOL_ISSUED'],
    'Готово':        ['COMPLETED'],
    'Отменён':       ['CANCELLED'],
    'Замещающий':    ['REPLACEMENT_PROTOCOL'],
}
STAGE_ORDER = list(STAGE_MAP.keys())


@analytics_access_required
@cached_api(ttl=60)
def api_funnel(request):
    """
    Воронка/конвейер: сколько образцов на каждом этапе жизненного цикла.
    Группирует 22 статуса в укрупнённые этапы.
    """
    f = Filters.from_request(request)

    rows = _fetchall(f"""
        SELECT s.status, COUNT(*) AS count
        FROM samples s
        WHERE s.status IS NOT NULL {f.where}
        GROUP BY s.status
    """, f.params)

    status_to_count = {r['status']: r['count'] for r in rows}
    funnel = []
    for stage_name in STAGE_ORDER:
        total = sum(status_to_count.get(st, 0) for st in STAGE_MAP[stage_name])
        funnel.append({
            'stage': stage_name,
            'count': total,
            'statuses': STAGE_MAP[stage_name],
        })

    return _ok(funnel, meta=f.meta())


@analytics_access_required
@cached_api(ttl=120)
def api_stage_durations(request):
    """
    Медианное время, которое образцы проводят на каждом этапе.
    Используется для поиска узких мест в процессе.
    """
    f = Filters.from_request(request)

    rows = _fetchall(f"""
        SELECT
            'Изготовление' AS stage,
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    s.manufacturing_completion_date - s.registration_date::timestamp
                )) / 86400
            )::numeric(10,1) AS median_days
        FROM samples s
        WHERE s.manufacturing_completion_date IS NOT NULL {f.where}

        UNION ALL

        SELECT 'Испытание',
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    s.testing_end_datetime - s.testing_start_datetime
                )) / 86400
            )::numeric(10,1)
        FROM samples s
        WHERE s.testing_start_datetime IS NOT NULL
          AND s.testing_end_datetime IS NOT NULL {f.where}

        UNION ALL

        SELECT 'Отчёт',
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    s.report_prepared_date - s.testing_end_datetime
                )) / 86400
            )::numeric(10,1)
        FROM samples s
        WHERE s.report_prepared_date IS NOT NULL
          AND s.testing_end_datetime IS NOT NULL {f.where}

        UNION ALL

        SELECT 'Проверка СМК',
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    s.protocol_checked_at - s.report_prepared_date
                )) / 86400
            )::numeric(10,1)
        FROM samples s
        WHERE s.protocol_checked_at IS NOT NULL
          AND s.report_prepared_date IS NOT NULL {f.where}

        UNION ALL

        SELECT 'Оформление',
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY (s.protocol_issued_date - s.protocol_checked_at::date)
            )::numeric(10,1)
        FROM samples s
        WHERE s.protocol_issued_date IS NOT NULL
          AND s.protocol_checked_at IS NOT NULL {f.where}
    """, f.params * 5)

    return _ok(rows, meta=f.meta())


# ═════════════════════════════════════════════════════════════════════════════
# 6. БЛОК 3 — ДИНАМИКА
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=60)
def api_daily_dynamics(request):
    """
    Регистрации и завершения по дням — на одном графике.
    Возвращает массив {date, registrations, completions}.
    """
    f = Filters.from_request(request)

    rows = _fetchall(f"""
        WITH reg AS (
            SELECT s.registration_date AS d, COUNT(*) AS cnt
            FROM samples s
            WHERE 1=1 {f.where}
            GROUP BY s.registration_date
        ),
        comp AS (
            SELECT s.testing_end_datetime::date AS d, COUNT(*) AS cnt
            FROM samples s
            WHERE s.status = 'COMPLETED'
              AND s.testing_end_datetime IS NOT NULL
              {f.where}
            GROUP BY s.testing_end_datetime::date
        )
        SELECT
            TO_CHAR(COALESCE(reg.d, comp.d), 'YYYY-MM-DD') AS date,
            COALESCE(reg.cnt, 0) AS registrations,
            COALESCE(comp.cnt, 0) AS completions
        FROM reg
        FULL OUTER JOIN comp ON reg.d = comp.d
        ORDER BY date
    """, f.params * 2)

    return _ok(rows, meta=f.meta())


@analytics_access_required
@cached_api(ttl=120)
def api_monthly_labor(request):
    """Трудоёмкость по месяцам за выбранный период."""
    f = Filters.from_request(request)
    rows = _fetchall(f"""
        SELECT TO_CHAR(s.registration_date, 'YYYY-MM') AS month,
               COUNT(*) AS samples_count,
               COALESCE(SUM(s.sample_count), 0) AS total_units
        FROM samples s
        WHERE 1=1 {f.where}
        GROUP BY TO_CHAR(s.registration_date, 'YYYY-MM')
        ORDER BY month
    """, f.params)
    return _ok(rows, meta=f.meta())


# ═════════════════════════════════════════════════════════════════════════════
# 7. БЛОК 4 — СРЕЗЫ
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=60)
def api_laboratory_distribution(request):
    """Распределение по лабораториям + SLA и средняя длительность."""
    date_from, date_to, period_label = _resolve_period(request)
    rows = _fetchall("""
        SELECT
            l.id AS lab_id,
            COALESCE(l.name, 'Без лаборатории') AS laboratory,
            l.code_display AS code,
            COUNT(s.id) AS samples_count,
            COUNT(*) FILTER (WHERE s.status = 'COMPLETED') AS completed,
            COUNT(*) FILTER (
                WHERE s.status = 'COMPLETED'
                  AND s.testing_end_datetime::date <= s.deadline
            ) AS in_time,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (
                        s.testing_end_datetime - s.testing_start_datetime
                    )) / 3600
                )::numeric, 1
            ) AS median_test_hours
        FROM samples s
        LEFT JOIN laboratories l ON s.laboratory_id = l.id
        WHERE s.registration_date BETWEEN %s AND %s
          AND (l.department_type = 'LAB' OR l.id IS NULL)
        GROUP BY l.id, l.name, l.code_display
        ORDER BY samples_count DESC
    """, [date_from, date_to])

    for r in rows:
        r['sla_pct'] = (round(r['in_time'] / r['completed'] * 100, 1)
                        if r['completed'] else 0.0)

    return _ok(rows, meta={
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'period': period_label,
    })


@analytics_access_required
@cached_api(ttl=60)
def api_status_distribution(request):
    """Распределение по статусам (без агрегации в этапы)."""
    f = Filters.from_request(request)
    rows = _fetchall(f"""
        SELECT s.status, COUNT(*) AS count
        FROM samples s
        WHERE s.status IS NOT NULL {f.where}
        GROUP BY s.status ORDER BY count DESC
    """, f.params)
    return _ok(rows, meta=f.meta())


@analytics_access_required
@cached_api(ttl=120)
def api_test_type_distribution(request):
    """Распределение по типам/кодам испытаний."""
    f = Filters.from_request(request)
    rows = _fetchall(f"""
        SELECT
            COALESCE(NULLIF(s.test_code, ''), '—') AS test_code,
            COALESCE(NULLIF(s.test_type, ''), 'Не указан') AS test_type,
            COUNT(*) AS count,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (
                        s.testing_end_datetime - s.testing_start_datetime
                    )) / 3600
                )::numeric, 1
            ) AS median_test_hours
        FROM samples s
        WHERE 1=1 {f.where}
        GROUP BY s.test_code, s.test_type
        ORDER BY count DESC
    """, f.params)
    return _ok(rows, meta=f.meta())


@analytics_access_required
@cached_api(ttl=120)
def api_accreditation_distribution(request):
    """Распределение по областям аккредитации."""
    f = Filters.from_request(request)
    rows = _fetchall(f"""
        SELECT
            a.id, a.name, a.code,
            COUNT(s.id) AS count
        FROM samples s
        JOIN accreditation_areas a ON s.accreditation_area_id = a.id
        WHERE 1=1 {f.where}
        GROUP BY a.id, a.name, a.code
        ORDER BY count DESC
    """, f.params)
    return _ok(rows, meta=f.meta())


@analytics_access_required
@cached_api(ttl=120)
def api_report_type_distribution(request):
    """
    Распределение по типам отчётов.

    samples.report_type хранит комбинации через запятую, например
    'RESULTS_CLIENT,PHOTO'. Разворачиваем строку в массив и считаем
    каждый тип отдельно — один образец с комбинацией из N типов
    даёт +1 к каждой из N категорий.

    Поэтому сумма по категориям МОЖЕТ превышать число образцов.
    Это корректно — метрика показывает «сколько образцов потребовали
    данный тип отчётности», а не «сколько образцов распределены
    по категориям».
    """
    f = Filters.from_request(request)
    rows = _fetchall(f"""
        SELECT
            TRIM(rt.report_type) AS report_type,
            COUNT(*) AS count
        FROM samples s
        CROSS JOIN LATERAL UNNEST(
            STRING_TO_ARRAY(COALESCE(s.report_type, ''), ',')
        ) AS rt(report_type)
        WHERE 1=1 {f.where}
          AND TRIM(rt.report_type) != ''
        GROUP BY TRIM(rt.report_type)
        ORDER BY count DESC
    """, f.params)
    return _ok(rows, meta=f.meta())


# ═════════════════════════════════════════════════════════════════════════════
# 8. БЛОК 5 — ТОПЫ
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=120)
def api_top_clients(request):
    """Топ-N заказчиков по объёму образцов."""
    f = Filters.from_request(request)
    limit = min(int(request.GET.get('limit', 10)), 50)

    rows = _fetchall(f"""
        SELECT
            c.id AS client_id,
            c.name AS client_name,
            c.inn AS client_inn,
            COUNT(s.id) AS samples_count,
            COUNT(*) FILTER (WHERE s.status = 'COMPLETED') AS completed,
            COUNT(*) FILTER (
                WHERE s.deadline < CURRENT_DATE
                  AND s.status NOT IN ('COMPLETED', 'CANCELLED')
            ) AS overdue
        FROM samples s
        JOIN clients c ON s.client_id = c.id
        WHERE 1=1 {f.where}
        GROUP BY c.id, c.name, c.inn
        ORDER BY samples_count DESC
        LIMIT %s
    """, f.params + [limit])

    return _ok(rows, meta=f.meta())


@analytics_access_required
@cached_api(ttl=120)
def api_top_standards(request):
    """Топ-N стандартов/методик."""
    f = Filters.from_request(request)
    limit = min(int(request.GET.get('limit', 10)), 50)

    rows = _fetchall(f"""
        SELECT
            st.id AS standard_id,
            st.code AS standard_code,
            st.name AS standard_name,
            st.test_type,
            COUNT(DISTINCT s.id) AS samples_count
        FROM samples s
        JOIN sample_standards ss ON ss.sample_id = s.id
        JOIN standards st ON ss.standard_id = st.id
        WHERE 1=1 {f.where}
        GROUP BY st.id, st.code, st.name, st.test_type
        ORDER BY samples_count DESC
        LIMIT %s
    """, f.params + [limit])

    return _ok(rows, meta=f.meta())


# ═════════════════════════════════════════════════════════════════════════════
# 9. БЛОК 6 — РИСКИ
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=60)
def api_risk_stuck_samples(request):
    """
    «Застрявшие» образцы — в работе дольше N дней.
    По умолчанию порог = 30 дней, настраивается параметром ?threshold.
    """
    threshold = int(request.GET.get('threshold', 30))
    lab_id = int(request.GET.get('lab_id') or 0)

    params = [threshold]
    lab_cond = ''
    if lab_id:
        lab_cond = 'AND s.laboratory_id = %s'
        params.append(lab_id)

    rows = _fetchall(f"""
        SELECT
            s.id,
            s.sequence_number,
            s.cipher,
            s.status,
            s.registration_date,
            s.deadline,
            CURRENT_DATE - s.registration_date AS age_days,
            l.code_display AS lab_code,
            c.name AS client_name
        FROM samples s
        JOIN laboratories l ON s.laboratory_id = l.id
        JOIN clients c ON s.client_id = c.id
        WHERE s.status NOT IN ('COMPLETED', 'CANCELLED')
          AND CURRENT_DATE - s.registration_date > %s
          {lab_cond}
        ORDER BY age_days DESC
        LIMIT 50
    """, params)

    return _ok(rows, meta={'threshold_days': threshold, 'lab_id': lab_id})


@analytics_access_required
@cached_api(ttl=60)
def api_risk_equipment_expiring(request):
    """Оборудование с истекающей в 30 дней поверкой/калибровкой."""
    lab_id = int(request.GET.get('lab_id') or 0)
    days = int(request.GET.get('days', 30))

    params = [days]
    lab_cond = ''
    if lab_id:
        lab_cond = 'AND e.laboratory_id = %s'
        params.append(lab_id)

    rows = _fetchall(f"""
        SELECT DISTINCT ON (e.id)
            e.id,
            e.accounting_number,
            e.name,
            e.equipment_type,
            e.status,
            em.valid_until,
            em.maintenance_type,
            em.certificate_number,
            em.valid_until - CURRENT_DATE AS days_left,
            l.code_display AS lab_code
        FROM equipment e
        JOIN equipment_maintenance em ON em.equipment_id = e.id
        LEFT JOIN laboratories l ON e.laboratory_id = l.id
        WHERE em.valid_until IS NOT NULL
          AND em.valid_until BETWEEN CURRENT_DATE
                                 AND CURRENT_DATE + (%s || ' days')::interval
          AND e.status != 'RETIRED'
          {lab_cond}
        ORDER BY e.id, em.valid_until ASC
    """, params)

    rows.sort(key=lambda r: r['days_left'])
    return _ok(rows, meta={'days_horizon': days, 'lab_id': lab_id})


@analytics_access_required
@cached_api(ttl=120)
def api_risk_replacement_protocols(request):
    """Образцы с несколькими замещающими протоколами (индикатор качества)."""
    f = Filters.from_request(request)

    rows = _fetchall(f"""
        SELECT
            s.id,
            s.sequence_number,
            s.cipher,
            s.replacement_count,
            s.replacement_protocol_issued_date,
            l.code_display AS lab_code,
            c.name AS client_name
        FROM samples s
        JOIN laboratories l ON s.laboratory_id = l.id
        JOIN clients c ON s.client_id = c.id
        WHERE s.replacement_count > 0 {f.where}
        ORDER BY s.replacement_count DESC, s.replacement_protocol_issued_date DESC
        LIMIT 50
    """, f.params)

    return _ok(rows, meta=f.meta())


# ═════════════════════════════════════════════════════════════════════════════
# 10. БЛОК 7 — DRILL-DOWN (универсальный список образцов)
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
def api_samples_drill_down(request):
    """
    Универсальный эндпоинт: возвращает список образцов по гибким фильтрам.
    Используется при клике на любой KPI/сегмент графика.

    Поддерживает:
        ?period=..., ?lab_id=..., ?date_from/to (как обычно)
        ?status=COMPLETED        — конкретный статус
        ?status_group=Испытание  — группа статусов (из STAGE_MAP)
        ?overdue=1               — только просроченные
        ?client_id=N
        ?operator_id=N
        ?replacement=1           — только с замещающими
        ?test_code=MI
        ?limit=50 (макс 500), ?offset=0
    """
    f = Filters.from_request(request)
    conditions = list(f.conditions)
    params = list(f.params)

    status = request.GET.get('status')
    if status:
        conditions.append('s.status = %s')
        params.append(status)

    status_group = request.GET.get('status_group')
    if status_group and status_group in STAGE_MAP:
        placeholders = ','.join(['%s'] * len(STAGE_MAP[status_group]))
        conditions.append(f's.status IN ({placeholders})')
        params.extend(STAGE_MAP[status_group])

    if request.GET.get('overdue') == '1':
        conditions.append("s.deadline < CURRENT_DATE")
        conditions.append("s.status NOT IN ('COMPLETED','CANCELLED')")

    if request.GET.get('replacement') == '1':
        conditions.append('s.replacement_count > 0')

    for key, col in [('client_id', 's.client_id'),
                     ('test_code', 's.test_code')]:
        val = request.GET.get(key)
        if val:
            conditions.append(f'{col} = %s')
            params.append(val)

    operator_id = request.GET.get('operator_id')
    if operator_id:
        conditions.append("""s.id IN (
            SELECT sample_id FROM sample_operators WHERE user_id = %s
        )""")
        params.append(operator_id)

    limit = min(int(request.GET.get('limit', 50)), 500)
    offset = max(int(request.GET.get('offset', 0)), 0)

    where_sql = ' AND '.join(conditions) if conditions else 'TRUE'

    total = _fetchval(
        f"SELECT COUNT(*) FROM samples s WHERE {where_sql}",
        params,
    ) or 0

    rows = _fetchall(f"""
        SELECT
            s.id,
            s.sequence_number,
            s.cipher,
            s.status,
            s.registration_date,
            s.deadline,
            s.testing_start_datetime,
            s.testing_end_datetime,
            s.replacement_count,
            l.code_display AS lab_code,
            l.name AS lab_name,
            c.name AS client_name,
            s.test_code,
            s.test_type,
            CASE
                WHEN s.status = 'COMPLETED'
                 AND s.testing_end_datetime::date <= s.deadline THEN 'in_time'
                WHEN s.status = 'COMPLETED'
                 AND s.testing_end_datetime::date > s.deadline THEN 'late'
                WHEN s.deadline < CURRENT_DATE
                 AND s.status NOT IN ('COMPLETED','CANCELLED') THEN 'overdue'
                ELSE 'normal'
            END AS sla_flag
        FROM samples s
        JOIN laboratories l ON s.laboratory_id = l.id
        JOIN clients c ON s.client_id = c.id
        WHERE {where_sql}
        ORDER BY s.registration_date DESC, s.sequence_number DESC
        LIMIT %s OFFSET %s
    """, params + [limit, offset])

    return _ok(rows, meta={
        'total': total,
        'limit': limit,
        'offset': offset,
        **f.meta(),
    })


# ═════════════════════════════════════════════════════════════════════════════
# 11. ПРОИЗВОДИТЕЛЬНОСТЬ СОТРУДНИКОВ
# ═════════════════════════════════════════════════════════════════════════════

@analytics_access_required
@cached_api(ttl=60)
def api_employees_overview(request):
    """
    Верхнеуровневые KPI по сотрудникам. Набор метрик зависит от роли:

    role=TESTER (по умолчанию) — испытатели:
        • Всего испытателей
        • Активных за период
        • Медиана образцов на человека
        • Средний SLA
        • Коэффициент неравномерности загрузки (CV)

    role=CLIENT — отдел сопровождения договоров (CLIENT_DEPT_HEAD, CLIENT_MANAGER):
        • Всего в отделе
        • Активных за период
        • Зарегистрировано образцов (всего)
        • Проверок регистрации (всего)
    """
    f = Filters.from_request(request)
    role_group = (request.GET.get('role') or 'TESTER').upper()

    if role_group == 'CLIENT':
        return _overview_for_client(f)

    # Остальные роли пока показывают overview испытателей (универсальный fallback)
    return _overview_for_testers(f)


def _overview_for_testers(f):
    lab_cond = ''
    lab_params = []
    if f.lab_id:
        lab_cond = 'AND u.laboratory_id = %s'
        lab_params.append(f.lab_id)

    # Число испытаний на каждого испытателя за период
    rows = _fetchall(f"""
        SELECT
            u.id,
            COUNT(DISTINCT so.sample_id) AS samples_done
        FROM users u
        LEFT JOIN sample_operators so ON so.user_id = u.id
        LEFT JOIN samples s ON so.sample_id = s.id
            AND s.testing_end_datetime IS NOT NULL
            AND s.registration_date BETWEEN %s AND %s
        WHERE u.is_active = TRUE
          AND u.role = 'TESTER'
          {lab_cond}
        GROUP BY u.id
    """, [f.date_from, f.date_to] + lab_params)

    counts = [r['samples_done'] for r in rows]
    total_testers = len(counts)
    active_testers = sum(1 for c in counts if c > 0)

    # Медиана
    counts_sorted = sorted(counts)
    if counts_sorted:
        mid = len(counts_sorted) // 2
        median_samples = (
            counts_sorted[mid] if len(counts_sorted) % 2
            else (counts_sorted[mid - 1] + counts_sorted[mid]) / 2
        )
    else:
        median_samples = 0

    # Коэффициент вариации (стд.откл / среднее) — показывает неравномерность
    if counts and sum(counts):
        mean = sum(counts) / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        stddev = variance ** 0.5
        cv = round(stddev / mean, 2) if mean else 0
    else:
        cv = 0

    # Средний SLA по испытателям (macro-average, не по образцам)
    sla_rows = _fetchall(f"""
        SELECT
            u.id,
            COUNT(*) FILTER (
                WHERE s.status = 'COMPLETED'
                  AND s.testing_end_datetime::date <= s.deadline
            ) AS in_time,
            COUNT(*) FILTER (WHERE s.status = 'COMPLETED') AS completed
        FROM users u
        JOIN sample_operators so ON so.user_id = u.id
        JOIN samples s ON so.sample_id = s.id
            AND s.registration_date BETWEEN %s AND %s
        WHERE u.is_active = TRUE
          AND u.role = 'TESTER'
          {lab_cond}
        GROUP BY u.id
        HAVING COUNT(*) FILTER (WHERE s.status = 'COMPLETED') > 0
    """, [f.date_from, f.date_to] + lab_params)

    slas = [r['in_time'] / r['completed'] * 100
            for r in sla_rows if r['completed']]
    avg_sla = round(sum(slas) / len(slas), 1) if slas else 0.0

    return _ok({
        'role':                      'TESTER',
        'total_testers':             total_testers,
        'active_testers':            active_testers,
        'median_samples_per_tester': float(median_samples),
        'avg_sla_pct':               avg_sla,
        'load_cv':                   cv,
    }, meta=f.meta())


def _overview_for_client(f):
    """Сводка по отделу сопровождения договоров."""
    # Всего сотрудников отдела — без фильтра периода, это срез «сейчас»
    total_in_dept = _fetchval("""
        SELECT COUNT(*) FROM users
        WHERE is_active = TRUE
          AND role IN ('CLIENT_DEPT_HEAD', 'CLIENT_MANAGER')
    """) or 0

    # Активные за период — те, кто что-то зарегистрировал ИЛИ проверил
    active_in_period = _fetchval("""
        SELECT COUNT(DISTINCT uid) FROM (
            SELECT DISTINCT s.registered_by_id AS uid
            FROM samples s
            WHERE s.registration_date BETWEEN %s AND %s
              AND s.registered_by_id IN (
                  SELECT id FROM users
                  WHERE is_active = TRUE
                    AND role IN ('CLIENT_DEPT_HEAD', 'CLIENT_MANAGER')
              )
            UNION
            SELECT DISTINCT s.verified_by AS uid
            FROM samples s
            WHERE s.verified_at BETWEEN %s AND %s::date + INTERVAL '1 day'
              AND s.verified_by IN (
                  SELECT id FROM users
                  WHERE is_active = TRUE
                    AND role IN ('CLIENT_DEPT_HEAD', 'CLIENT_MANAGER')
              )
        ) t
    """, [f.date_from, f.date_to, f.date_from, f.date_to]) or 0

    # Зарегистрировано образцов за период
    registered = _fetchval("""
        SELECT COUNT(*) FROM samples
        WHERE registration_date BETWEEN %s AND %s
    """, [f.date_from, f.date_to]) or 0

    # Проверок регистрации за период
    verifications = _fetchval("""
        SELECT COUNT(*) FROM samples
        WHERE verified_at BETWEEN %s AND %s::date + INTERVAL '1 day'
    """, [f.date_from, f.date_to]) or 0

    return _ok({
        'role':               'CLIENT',
        'total_in_dept':      int(total_in_dept),
        'active_in_period':   int(active_in_period),
        'samples_registered': int(registered),
        'verifications_done': int(verifications),
    }, meta=f.meta())


@analytics_access_required
@cached_api(ttl=60)
def api_employees_leaderboard(request):
    """
    Лидерборд сотрудников с мульти-метриками.
    Фильтры:
        ?role=TESTER|WORKSHOP|QMS|CLIENT|LAB_HEAD
        ?hide_trainees=1
    Возвращает полный набор метрик — сортировка на фронте.
    """
    f = Filters.from_request(request)
    role_group = (request.GET.get('role') or 'TESTER').upper()
    hide_trainees = request.GET.get('hide_trainees') == '1'

    role_filter_map = {
        'TESTER':   "u.role = 'TESTER'",
        'WORKSHOP': "u.role IN ('WORKSHOP', 'WORKSHOP_HEAD')",
        'QMS':      "u.role IN ('QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST')",
        'CLIENT':   "u.role IN ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD')",
        'LAB_HEAD': "u.role = 'LAB_HEAD'",
    }
    role_cond = role_filter_map.get(role_group, role_filter_map['TESTER'])
    trainee_cond = 'AND u.is_trainee = FALSE' if hide_trainees else ''

    lab_cond = ''
    lab_params = []
    if f.lab_id:
        lab_cond = 'AND u.laboratory_id = %s'
        lab_params.append(f.lab_id)

    # ─── Испытатели ───
    if role_group == 'TESTER':
        rows = _fetchall(f"""
            WITH tester_samples AS (
                SELECT
                    u.id AS user_id,
                    s.id AS sample_id,
                    s.status,
                    s.deadline,
                    s.testing_start_datetime,
                    s.testing_end_datetime,
                    s.replacement_count
                FROM users u
                JOIN sample_operators so ON so.user_id = u.id
                JOIN samples s ON so.sample_id = s.id
                    AND s.registration_date BETWEEN %s AND %s
                WHERE u.is_active = TRUE
                  AND {role_cond}
                  {trainee_cond}
                  {lab_cond}
            ),
            tester_standards AS (
                SELECT DISTINCT so.user_id, ss.standard_id
                FROM sample_operators so
                JOIN sample_standards ss ON ss.sample_id = so.sample_id
                JOIN samples s ON s.id = so.sample_id
                    AND s.registration_date BETWEEN %s AND %s
            )
            SELECT
                u.id,
                u.last_name,
                u.first_name,
                u.sur_name,
                u.position,
                u.is_trainee,
                l.code_display AS lab_code,
                l.name AS lab_name,

                COUNT(DISTINCT ts.sample_id) AS samples_total,

                COUNT(DISTINCT ts.sample_id) FILTER (
                    WHERE ts.status = 'COMPLETED'
                ) AS samples_completed,

                COUNT(DISTINCT ts.sample_id) FILTER (
                    WHERE ts.status = 'COMPLETED'
                      AND ts.testing_end_datetime::date <= ts.deadline
                ) AS samples_in_time,

                ROUND(
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY EXTRACT(EPOCH FROM (
                            ts.testing_end_datetime - ts.testing_start_datetime
                        )) / 3600
                    ) FILTER (
                        WHERE ts.testing_start_datetime IS NOT NULL
                          AND ts.testing_end_datetime IS NOT NULL
                    )::numeric, 1
                ) AS median_test_hours,

                COUNT(DISTINCT ts.sample_id) FILTER (
                    WHERE ts.replacement_count > 0
                ) AS samples_with_replacement,

                (SELECT COUNT(*) FROM tester_standards ts2
                 WHERE ts2.user_id = u.id) AS unique_standards
            FROM users u
            JOIN laboratories l ON u.laboratory_id = l.id
            LEFT JOIN tester_samples ts ON ts.user_id = u.id
            WHERE u.is_active = TRUE
              AND {role_cond}
              {trainee_cond}
              {lab_cond}
            GROUP BY u.id, u.last_name, u.first_name, u.sur_name, u.position,
                     u.is_trainee, l.code_display, l.name
            ORDER BY samples_total DESC
        """,
            [f.date_from, f.date_to] + lab_params
            + [f.date_from, f.date_to]
            + lab_params
        )

        for r in rows:
            r['sla_pct'] = (
                round(r['samples_in_time'] / r['samples_completed'] * 100, 1)
                if r['samples_completed'] else None
            )
            r['replacement_pct'] = (
                round(r['samples_with_replacement']
                      / r['samples_completed'] * 100, 1)
                if r['samples_completed'] else None
            )

        return _ok(rows, meta={'role': role_group, **f.meta()})

    # ─── Мастерская ───
    if role_group == 'WORKSHOP':
        rows = _fetchall(f"""
            SELECT
                u.id,
                u.last_name, u.first_name, u.sur_name,
                u.position, u.is_trainee,
                l.code_display AS lab_code,
                COUNT(DISTINCT smo.sample_id) AS samples_manufactured,
                ROUND(
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY EXTRACT(DAY FROM (
                            s.manufacturing_completion_date
                            - s.registration_date::timestamp
                        ))
                    )::numeric, 1
                ) AS median_manufacturing_days
            FROM users u
            JOIN laboratories l ON u.laboratory_id = l.id
            LEFT JOIN sample_manufacturing_operators smo ON smo.user_id = u.id
            LEFT JOIN samples s ON s.id = smo.sample_id
                AND s.manufacturing_completion_date IS NOT NULL
                AND s.registration_date BETWEEN %s AND %s
            WHERE u.is_active = TRUE
              AND {role_cond}
              {trainee_cond}
              {lab_cond}
            GROUP BY u.id, u.last_name, u.first_name, u.sur_name, u.position,
                     u.is_trainee, l.code_display
            ORDER BY samples_manufactured DESC
        """, [f.date_from, f.date_to] + lab_params)
        return _ok(rows, meta={'role': role_group, **f.meta()})

    # ─── СМК (FK-колонка: protocol_checked_by, БЕЗ _id) ───
    if role_group == 'QMS':
        rows = _fetchall(f"""
            SELECT
                u.id,
                u.last_name, u.first_name, u.sur_name,
                u.position, u.is_trainee,
                l.code_display AS lab_code,
                COUNT(s.id) AS protocols_checked,
                ROUND(
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY EXTRACT(EPOCH FROM (
                            s.protocol_checked_at - s.report_prepared_date
                        )) / 3600
                    )::numeric, 1
                ) AS median_check_hours
            FROM users u
            LEFT JOIN laboratories l ON u.laboratory_id = l.id
            LEFT JOIN samples s ON s.protocol_checked_by = u.id
                AND s.registration_date BETWEEN %s AND %s
            WHERE u.is_active = TRUE
              AND {role_cond}
              {trainee_cond}
            GROUP BY u.id, u.last_name, u.first_name, u.sur_name, u.position,
                     u.is_trainee, l.code_display
            ORDER BY protocols_checked DESC
        """, [f.date_from, f.date_to])
        return _ok(rows, meta={'role': role_group, **f.meta()})

    # ─── Отдел клиентов: регистрации + проверки регистрации ───
    # registered_by — FK с _id; verified_by — FK без _id (колонка называется verified_by)
    if role_group == 'CLIENT':
        rows = _fetchall(f"""
            WITH regs AS (
                SELECT s.registered_by_id AS uid,
                       COUNT(*) AS cnt,
                       COUNT(*) FILTER (WHERE s.status = 'CANCELLED') AS cancelled
                FROM samples s
                WHERE s.registration_date BETWEEN %s AND %s
                GROUP BY s.registered_by_id
            ),
            verifs AS (
                SELECT s.verified_by AS uid,
                       COUNT(*) AS cnt,
                       ROUND(
                           PERCENTILE_CONT(0.5) WITHIN GROUP (
                               ORDER BY EXTRACT(EPOCH FROM (
                                   s.verified_at - s.registration_date::timestamp
                               )) / 3600
                           )::numeric, 1
                       ) AS median_hours
                FROM samples s
                WHERE s.verified_at BETWEEN %s AND %s::date + INTERVAL '1 day'
                GROUP BY s.verified_by
            )
            SELECT
                u.id,
                u.last_name, u.first_name, u.sur_name,
                u.position, u.is_trainee,
                COALESCE(r.cnt, 0) AS samples_registered,
                COALESCE(r.cancelled, 0) AS cancelled_after,
                COALESCE(v.cnt, 0) AS verifications_done,
                v.median_hours AS median_verification_hours
            FROM users u
            LEFT JOIN regs r ON r.uid = u.id
            LEFT JOIN verifs v ON v.uid = u.id
            WHERE u.is_active = TRUE
              AND {role_cond}
              {trainee_cond}
            ORDER BY samples_registered DESC, verifications_done DESC
        """, [f.date_from, f.date_to, f.date_from, f.date_to])
        return _ok(rows, meta={'role': role_group, **f.meta()})

    # Роль не поддерживается
    return _ok([], meta={'role': role_group, **f.meta()})


@analytics_access_required
@cached_api(ttl=120)
def api_employees_heatmap(request):
    """
    Матрица загрузки: сотрудники × недели (или дни) × счётчик.

    Параметры:
        ?mode=testing (default) — завершённые испытания (TESTER),
              через sample_operators + testing_end_datetime.
        ?mode=registration — регистрации образцов (CLIENT_DEPT_HEAD+CLIENT_MANAGER),
              через s.registered_by_id + registration_date.
        ?mode=verification — проверки регистрации (те же роли),
              через s.verified_by + verified_at.
        ?granularity=week|day
    """
    f = Filters.from_request(request)
    granularity = request.GET.get('granularity', 'week')
    mode = (request.GET.get('mode') or 'testing').lower()

    lab_cond = ''
    lab_params = []
    if f.lab_id:
        lab_cond = 'AND u.laboratory_id = %s'
        lab_params.append(f.lab_id)

    if mode == 'registration':
        # Регистрации: дата — registration_date, связь — s.registered_by_id = u.id
        date_col = 's.registration_date'
        bucket_expr = (
            f"TO_CHAR({date_col}, 'YYYY-MM-DD')"
            if granularity == 'day'
            else f"TO_CHAR(DATE_TRUNC('week', {date_col}), 'YYYY-MM-DD')"
        )
        sql = f"""
            SELECT
                u.id AS user_id,
                u.last_name || ' ' || LEFT(u.first_name, 1) || '.' AS display_name,
                u.is_trainee,
                {bucket_expr} AS bucket,
                COUNT(*) AS samples
            FROM users u
            JOIN samples s ON s.registered_by_id = u.id
                AND s.registration_date BETWEEN %s AND %s
            WHERE u.is_active = TRUE
              AND u.role IN ('CLIENT_DEPT_HEAD', 'CLIENT_MANAGER')
            GROUP BY u.id, u.last_name, u.first_name, u.is_trainee, bucket
            ORDER BY u.last_name, bucket
        """
        params = [f.date_from, f.date_to]

    elif mode == 'verification':
        # Проверки: дата — verified_at, связь — s.verified_by = u.id
        date_col = 's.verified_at'
        bucket_expr = (
            f"TO_CHAR({date_col}, 'YYYY-MM-DD')"
            if granularity == 'day'
            else f"TO_CHAR(DATE_TRUNC('week', {date_col}), 'YYYY-MM-DD')"
        )
        sql = f"""
            SELECT
                u.id AS user_id,
                u.last_name || ' ' || LEFT(u.first_name, 1) || '.' AS display_name,
                u.is_trainee,
                {bucket_expr} AS bucket,
                COUNT(*) AS samples
            FROM users u
            JOIN samples s ON s.verified_by = u.id
                AND s.verified_at BETWEEN %s AND %s::date + INTERVAL '1 day'
            WHERE u.is_active = TRUE
              AND u.role IN ('CLIENT_DEPT_HEAD', 'CLIENT_MANAGER')
            GROUP BY u.id, u.last_name, u.first_name, u.is_trainee, bucket
            ORDER BY u.last_name, bucket
        """
        params = [f.date_from, f.date_to]

    else:
        # testing (по умолчанию) — текущее поведение для испытателей
        date_col = 's.testing_end_datetime'
        bucket_expr = (
            f"TO_CHAR({date_col}, 'YYYY-MM-DD')"
            if granularity == 'day'
            else f"TO_CHAR(DATE_TRUNC('week', {date_col}), 'YYYY-MM-DD')"
        )
        sql = f"""
            SELECT
                u.id AS user_id,
                u.last_name || ' ' || LEFT(u.first_name, 1) || '.' AS display_name,
                u.is_trainee,
                {bucket_expr} AS bucket,
                COUNT(DISTINCT so.sample_id) AS samples
            FROM users u
            JOIN sample_operators so ON so.user_id = u.id
            JOIN samples s ON s.id = so.sample_id
                AND s.testing_end_datetime IS NOT NULL
                AND s.testing_end_datetime::date BETWEEN %s AND %s
            WHERE u.is_active = TRUE
              AND u.role = 'TESTER'
              {lab_cond}
            GROUP BY u.id, u.last_name, u.first_name, u.is_trainee, bucket
            ORDER BY u.last_name, bucket
        """
        params = [f.date_from, f.date_to] + lab_params

    rows = _fetchall(sql, params)
    return _ok(rows, meta={'granularity': granularity, 'mode': mode, **f.meta()})


@analytics_access_required
@cached_api(ttl=60)
def api_employee_detail(request, user_id):
    """
    Подробная статистика по одному сотруднику.

    Набор данных зависит от роли:
    • CLIENT_DEPT_HEAD / CLIENT_MANAGER — регистрации и проверки регистрации,
      динамика регистраций vs проверок, последние регистрации.
    • Остальные — испытательские метрики (образцы, SLA, топ стандартов, долгие).
    """
    f = Filters.from_request(request)

    user = _fetchone("""
        SELECT u.id, u.last_name, u.first_name, u.sur_name,
               u.position, u.role, u.is_trainee, u.is_active,
               l.name AS lab_name, l.code_display AS lab_code
        FROM users u
        LEFT JOIN laboratories l ON u.laboratory_id = l.id
        WHERE u.id = %s
    """, [user_id])

    if not user:
        return JsonResponse({'error': 'not_found'}, status=404)

    if user['role'] in ('CLIENT_DEPT_HEAD', 'CLIENT_MANAGER'):
        return _employee_detail_client(f, user, user_id)

    return _employee_detail_tester(f, user, user_id)


def _employee_detail_tester(f, user, user_id):
    """Детализация для испытателя и всех остальных ролей (fallback)."""
    totals = _fetchone("""
        SELECT
            COUNT(DISTINCT s.id) AS samples_total,
            COUNT(DISTINCT s.id) FILTER (WHERE s.status = 'COMPLETED') AS completed,
            COUNT(DISTINCT s.id) FILTER (
                WHERE s.status = 'COMPLETED'
                  AND s.testing_end_datetime::date <= s.deadline
            ) AS in_time,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (
                        s.testing_end_datetime - s.testing_start_datetime
                    )) / 3600
                )::numeric, 1
            ) AS median_test_hours,
            COUNT(DISTINCT s.id) FILTER (WHERE s.replacement_count > 0) AS with_replacement
        FROM sample_operators so
        JOIN samples s ON s.id = so.sample_id
            AND s.registration_date BETWEEN %s AND %s
        WHERE so.user_id = %s
    """, [f.date_from, f.date_to, user_id]) or {}

    totals['sla_pct'] = (
        round(totals['in_time'] / totals['completed'] * 100, 1)
        if totals.get('completed') else None
    )

    dynamics = _fetchall("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', s.registration_date), 'YYYY-MM') AS month,
            COUNT(DISTINCT s.id) AS samples
        FROM sample_operators so
        JOIN samples s ON s.id = so.sample_id
        WHERE so.user_id = %s
          AND s.registration_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
        GROUP BY DATE_TRUNC('month', s.registration_date)
        ORDER BY month
    """, [user_id])

    top_standards = _fetchall("""
        SELECT
            st.id, st.code, st.name,
            COUNT(DISTINCT s.id) AS samples_count
        FROM sample_operators so
        JOIN samples s ON s.id = so.sample_id
            AND s.registration_date BETWEEN %s AND %s
        JOIN sample_standards ss ON ss.sample_id = s.id
        JOIN standards st ON st.id = ss.standard_id
        WHERE so.user_id = %s
        GROUP BY st.id, st.code, st.name
        ORDER BY samples_count DESC
        LIMIT 10
    """, [f.date_from, f.date_to, user_id])

    longest = _fetchall("""
        SELECT
            s.id, s.sequence_number, s.cipher,
            ROUND(
                (EXTRACT(EPOCH FROM (
                    s.testing_end_datetime - s.testing_start_datetime
                )) / 3600)::numeric, 1
            ) AS test_hours,
            s.deadline,
            s.testing_end_datetime::date - s.deadline AS days_over_deadline
        FROM sample_operators so
        JOIN samples s ON s.id = so.sample_id
            AND s.registration_date BETWEEN %s AND %s
        WHERE so.user_id = %s
          AND s.testing_start_datetime IS NOT NULL
          AND s.testing_end_datetime IS NOT NULL
        ORDER BY test_hours DESC NULLS LAST
        LIMIT 10
    """, [f.date_from, f.date_to, user_id])

    return _ok({
        'kind':             'tester',
        'user':             user,
        'totals':           totals,
        'monthly_dynamics': dynamics,
        'top_standards':    top_standards,
        'longest_samples':  longest,
    }, meta=f.meta())


def _employee_detail_client(f, user, user_id):
    """Детализация для сотрудника отдела клиентов (регистрации + проверки)."""

    # Агрегированные счётчики за период
    totals = _fetchone("""
        SELECT
            (SELECT COUNT(*) FROM samples
             WHERE registered_by_id = %s
               AND registration_date BETWEEN %s AND %s
            ) AS registrations,

            (SELECT COUNT(*) FROM samples
             WHERE registered_by_id = %s
               AND registration_date BETWEEN %s AND %s
               AND status = 'CANCELLED'
            ) AS cancelled_after,

            (SELECT COUNT(*) FROM samples
             WHERE verified_by = %s
               AND verified_at BETWEEN %s AND %s::date + INTERVAL '1 day'
            ) AS verifications,

            (SELECT ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (
                        verified_at - registration_date::timestamp
                    )) / 3600
                )::numeric, 1)
             FROM samples
             WHERE verified_by = %s
               AND verified_at BETWEEN %s AND %s::date + INTERVAL '1 day'
               AND verified_at IS NOT NULL
               AND registration_date IS NOT NULL
            ) AS median_verification_hours
    """, [
        user_id, f.date_from, f.date_to,
        user_id, f.date_from, f.date_to,
        user_id, f.date_from, f.date_to,
        user_id, f.date_from, f.date_to,
    ]) or {}

    # Динамика за 6 мес — две линии (регистрации и проверки) по месяцам
    dynamics = _fetchall("""
        WITH months AS (
            SELECT TO_CHAR(DATE_TRUNC('month', CURRENT_DATE) - (n || ' months')::interval, 'YYYY-MM') AS month
            FROM generate_series(0, 5) AS n
        ),
        regs AS (
            SELECT TO_CHAR(DATE_TRUNC('month', registration_date), 'YYYY-MM') AS month,
                   COUNT(*) AS cnt
            FROM samples
            WHERE registered_by_id = %s
              AND registration_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
            GROUP BY month
        ),
        verifs AS (
            SELECT TO_CHAR(DATE_TRUNC('month', verified_at), 'YYYY-MM') AS month,
                   COUNT(*) AS cnt
            FROM samples
            WHERE verified_by = %s
              AND verified_at >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
            GROUP BY month
        )
        SELECT m.month,
               COALESCE(r.cnt, 0) AS registrations,
               COALESCE(v.cnt, 0) AS verifications
        FROM months m
        LEFT JOIN regs r   ON r.month = m.month
        LEFT JOIN verifs v ON v.month = m.month
        ORDER BY m.month
    """, [user_id, user_id])

    # Последние 15 образцов, где он был регистратором ИЛИ проверяющим
    recent = _fetchall("""
        SELECT
            s.id,
            s.sequence_number,
            s.cipher,
            s.status,
            s.registration_date,
            s.verified_at,
            (CASE WHEN s.registered_by_id = %s THEN 'registered' ELSE '' END) AS did_register,
            (CASE WHEN s.verified_by = %s THEN 'verified' ELSE '' END) AS did_verify,
            c.name AS client_name,
            l.code_display AS lab_code
        FROM samples s
        LEFT JOIN clients c ON c.id = s.client_id
        LEFT JOIN laboratories l ON l.id = s.laboratory_id
        WHERE (s.registered_by_id = %s OR s.verified_by = %s)
          AND (
              s.registration_date BETWEEN %s AND %s
              OR (s.verified_at BETWEEN %s AND %s::date + INTERVAL '1 day')
          )
        ORDER BY GREATEST(
            s.registration_date::timestamp,
            COALESCE(s.verified_at, '1900-01-01'::timestamp)
        ) DESC
        LIMIT 15
    """, [
        user_id, user_id, user_id, user_id,
        f.date_from, f.date_to, f.date_from, f.date_to,
    ])

    return _ok({
        'kind':             'client',
        'user':             user,
        'totals':           totals,
        'monthly_dynamics': dynamics,
        'recent_samples':   recent,
    }, meta=f.meta())
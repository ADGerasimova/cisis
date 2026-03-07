"""
maintenance_views.py — Техническое обслуживание оборудования
v3.25.0

Расположение: core/views/maintenance_views.py

Подключить в core/views/__init__.py:
    from . import maintenance_views

Маршруты в core/urls.py:
    path('workspace/maintenance/', maintenance_views.maintenance_view, name='maintenance'),
    path('workspace/maintenance/<int:plan_id>/', maintenance_views.maintenance_detail_view, name='maintenance_detail'),
"""

from datetime import date
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection
from django.http import HttpResponseForbidden
from urllib.parse import urlencode

from core.permissions import PermissionChecker
from core.models import Laboratory

MAINTENANCE_ITEMS_PER_PAGE = 50
LOG_ITEMS_PER_PAGE = 50

LOG_STATUS_CHOICES = [
    ('PLANNED',   'Запланировано'),
    ('COMPLETED', 'Выполнено'),
    ('OVERDUE',   'Просрочено'),
    ('CANCELLED', 'Отменено'),
]
LOG_STATUS_LABELS = dict(LOG_STATUS_CHOICES)


# ─────────────────────────────────────────────────────────────
# Утилиты
# ─────────────────────────────────────────────────────────────

def _fetchall(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [col[0] for col in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetchone(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        if row is None:
            return None
        cols = [col[0] for col in cur.description]
        return dict(zip(cols, row))


def _build_frequency_display(plan):
    """Склеивает три поля периодичности в одну строку."""
    parts = []
    count        = plan.get('frequency_count')
    period_value = plan.get('frequency_period_value')
    unit         = plan.get('frequency_unit') or ''
    if count is not None:
        parts.append(f"{count} раз в")
    if period_value is not None:
        parts.append(str(period_value))
    if unit:
        parts.append(unit)
    return ' '.join(parts) if parts else '—'


def _recalculate_next_due_date(plan_id):
    """
    Пересчитывает next_due_date на основе последнего выполненного обслуживания.
    Формула: performed_date + (interval / frequency_count)
    """
    with connection.cursor() as cur:
        cur.execute("""
            UPDATE equipment_maintenance_plans p
            SET next_due_date = l.performed_date + (
                CASE p.frequency_unit
                    WHEN 'DAY'   THEN make_interval(days  => p.frequency_period_value)
                    WHEN 'WEEK'  THEN make_interval(weeks => p.frequency_period_value)
                    WHEN 'MONTH' THEN make_interval(months => p.frequency_period_value)
                    WHEN 'YEAR'  THEN make_interval(years  => p.frequency_period_value)
                END / p.frequency_count
            ),
            updated_at = CURRENT_TIMESTAMP
            FROM equipment_maintenance_logs l
            WHERE l.plan_id = p.id
              AND p.id = %s
              AND l.status IN ('COMPLETED', 'OVERDUE')
              AND l.performed_date = (
                  SELECT MAX(l2.performed_date)
                  FROM equipment_maintenance_logs l2
                  WHERE l2.plan_id = p.id
                    AND l2.status IN ('COMPLETED', 'OVERDUE')
              )
        """, [plan_id])


# ─────────────────────────────────────────────────────────────
# Реестр планов ТО
# ─────────────────────────────────────────────────────────────

@login_required
def maintenance_view(request):
    if not PermissionChecker.can_view(request.user, 'MAINTENANCE', 'access'):
        messages.error(request, 'У вас нет доступа к разделу технического обслуживания')
        return redirect('workspace_home')

    can_edit = PermissionChecker.can_edit(request.user, 'MAINTENANCE', 'access')

    search       = request.GET.get('search', '').strip()
    lab_id       = request.GET.get('lab_id', '')
    overdue_only = request.GET.get('overdue_only', '')
    sort         = request.GET.get('sort', 'next_due_date')

    allowed_sorts = {
        'accounting_number', '-accounting_number',
        'equipment_type',    '-equipment_type',
        'name',              '-name',
        'next_due_date',     '-next_due_date',
    }
    if sort not in allowed_sorts:
        sort = 'next_due_date'

    sort_col = sort.lstrip('-')
    sort_dir = 'DESC' if sort.startswith('-') else 'ASC'
    sort_col_map = {
        'accounting_number': 'e.accounting_number',
        'equipment_type':    'e.equipment_type',
        'name':              'emp.name',
        'next_due_date':     'emp.next_due_date',
    }
    order_by = f"{sort_col_map.get(sort_col, 'emp.next_due_date')} {sort_dir}"

    where_clauses, params = [], []

    if search:
        where_clauses.append(
            "(e.accounting_number ILIKE %s OR emp.name ILIKE %s OR e.equipment_type ILIKE %s)"
        )
        like = f'%{search}%'
        params += [like, like, like]

    if lab_id:
        where_clauses.append("e.laboratory_id = %s")
        params.append(int(lab_id))

    if overdue_only:
        where_clauses.append("emp.next_due_date < CURRENT_DATE")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    rows = _fetchall(f"""
        SELECT
            emp.id,
            e.accounting_number,
            e.equipment_type,
            l.name          AS laboratory_name,
            emp.name,
            emp.frequency_count,
            emp.frequency_period_value,
            emp.frequency_unit,
            emp.frequency_condition,
            emp.next_due_date,
            emp.notes
        FROM equipment_maintenance_plans emp
        JOIN equipment e ON e.id = emp.equipment_id
        LEFT JOIN laboratories l ON l.id = e.laboratory_id
        {where_sql}
        ORDER BY {order_by}
    """, params)

    today = date.today()
    for row in rows:
        row['frequency_display'] = _build_frequency_display(row)
        nd = row.get('next_due_date')
        if nd:
            row['is_overdue'] = nd < today
            row['days_left']  = (nd - today).days
        else:
            row['is_overdue'] = False
            row['days_left']  = None

    paginator = Paginator(rows, MAINTENANCE_ITEMS_PER_PAGE)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    laboratories = Laboratory.objects.filter(is_active=True, department_type='LAB').order_by('name')

    filter_params = {}
    if search:       filter_params['search']       = search
    if lab_id:       filter_params['lab_id']       = lab_id
    if overdue_only: filter_params['overdue_only'] = overdue_only
    if sort != 'next_due_date': filter_params['sort'] = sort

    context = {
        'page_obj':             page_obj,
        'plans':                page_obj.object_list,
        'total_count':          len(rows),
        'laboratories':         laboratories,
        'can_edit':             can_edit,
        'current_search':       search,
        'current_lab_id':       lab_id,
        'current_overdue_only': overdue_only,
        'current_sort':         sort,
        'filter_query':         urlencode(filter_params),
        'sort_link_params':     urlencode({k: v for k, v in filter_params.items() if k != 'sort'}),
    }
    return render(request, 'core/maintenance.html', context)


# ─────────────────────────────────────────────────────────────
# Детальная страница плана ТО
# ─────────────────────────────────────────────────────────────

@login_required
def maintenance_detail_view(request, plan_id):
    if not PermissionChecker.can_view(request.user, 'MAINTENANCE', 'access'):
        messages.error(request, 'У вас нет доступа к разделу технического обслуживания')
        return redirect('workspace_home')

    can_edit = PermissionChecker.can_edit(request.user, 'MAINTENANCE', 'access')

    # Шапка плана
    plan = _fetchone("""
        SELECT
            emp.id,
            e.accounting_number,
            e.name              AS equipment_name,
            e.equipment_type,
            l.name              AS laboratory_name,
            emp.name,
            emp.frequency_count,
            emp.frequency_period_value,
            emp.frequency_unit,
            emp.frequency_condition,
            emp.next_due_date,
            emp.notes
        FROM equipment_maintenance_plans emp
        JOIN equipment e ON e.id = emp.equipment_id
        LEFT JOIN laboratories l ON l.id = e.laboratory_id
        WHERE emp.id = %s
    """, [plan_id])

    if plan is None:
        messages.error(request, 'План обслуживания не найден')
        return redirect('maintenance')

    plan['frequency_display'] = _build_frequency_display(plan)
    today = date.today()
    nd = plan.get('next_due_date')
    if nd:
        plan['is_overdue'] = nd < today
        plan['days_left']  = (nd - today).days
    else:
        plan['is_overdue'] = False
        plan['days_left']  = None

    # ── POST: добавление записи ───────────────────────────────
    if request.method == 'POST':
        if not can_edit:
            return HttpResponseForbidden()

        performed_date  = request.POST.get('performed_date', '').strip()
        performed_by_id = request.POST.get('performed_by_id', '').strip() or None
        verified_date   = request.POST.get('verified_date', '').strip()   or None
        verified_by_id  = request.POST.get('verified_by_id', '').strip()  or None
        status          = request.POST.get('status', 'COMPLETED')
        log_notes       = request.POST.get('notes', '').strip()           or None

        if not performed_date:
            messages.error(request, 'Укажите дату проведения обслуживания')
        else:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO equipment_maintenance_logs
                        (plan_id, performed_date, performed_by_id,
                         verified_date, verified_by_id, status, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, [
                    plan_id,
                    performed_date,
                    int(performed_by_id) if performed_by_id else None,
                    verified_date,
                    int(verified_by_id) if verified_by_id else None,
                    status,
                    log_notes,
                ])

            if status in ('COMPLETED', 'OVERDUE'):
                _recalculate_next_due_date(plan_id)

            messages.success(request, 'Запись об обслуживании добавлена')
            return redirect('maintenance_detail', plan_id=plan_id)

    # ── Журнал обслуживания ───────────────────────────────────
    logs = _fetchall("""
        SELECT
            ml.id,
            ml.performed_date,
            ml.verified_date,
            ml.status,
            ml.notes,
            pb.last_name  AS performed_last,
            pb.first_name AS performed_first,
            pb.sur_name   AS performed_sur,
            vb.last_name  AS verified_last,
            vb.first_name AS verified_first,
            vb.sur_name   AS verified_sur
        FROM equipment_maintenance_logs ml
        LEFT JOIN users pb ON pb.id = ml.performed_by_id
        LEFT JOIN users vb ON vb.id = ml.verified_by_id
        WHERE ml.plan_id = %s
        ORDER BY ml.performed_date DESC
    """, [plan_id])

    for log in logs:
        log['performed_by'] = ' '.join(filter(None, [
            log.get('performed_last'),
            log.get('performed_first'),
            log.get('performed_sur'),
        ])) or '—'
        log['verified_by'] = ' '.join(filter(None, [
            log.get('verified_last'),
            log.get('verified_first'),
            log.get('verified_sur'),
        ])) or '—'
        log['status_display'] = LOG_STATUS_LABELS.get(log.get('status'), log.get('status') or '—')

    # Список активных пользователей для формы
    users = _fetchall("""
        SELECT id, last_name, first_name, sur_name
        FROM users WHERE is_active = TRUE
        ORDER BY last_name, first_name
    """)
    for u in users:
        u['full_name'] = ' '.join(filter(None, [
            u.get('last_name'), u.get('first_name'), u.get('sur_name')
        ]))

    paginator = Paginator(logs, LOG_ITEMS_PER_PAGE)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'plan':               plan,
        'page_obj':           page_obj,
        'logs':               page_obj.object_list,
        'total_count':        len(logs),
        'can_edit':           can_edit,
        'log_status_choices': LOG_STATUS_CHOICES,
        'users':              users,
        'today':              today.isoformat(),
    }
    return render(request, 'core/maintenance_detail.html', context)
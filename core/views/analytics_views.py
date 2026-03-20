"""
analytics_views.py — Страница аналитики + все API-эндпоинты
v3.38.0

Расположение: core/views/analytics_views.py
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import connection

from core.permissions import PermissionChecker


# ──────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────
def _fetchall(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [col[0] for col in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetchval(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return row[0] if row else None


def _date_range_filter(request, date_column='registration_date'):
    """Конвертирует параметры date_from / date_to в SQL-условия.
    По умолчанию: с начала текущего месяца по сегодня.
    Возвращает (sql_fragment, params_list).
    """
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    sql_parts = []
    params = []

    if date_from:
        sql_parts.append(f"AND {date_column} >= %s")
        params.append(date_from)
    else:
        sql_parts.append(f"AND {date_column} >= DATE_TRUNC('month', CURRENT_DATE)")

    if date_to:
        sql_parts.append(f"AND {date_column} <= %s::date + INTERVAL '1 day'")
        params.append(date_to)

    return ' '.join(sql_parts), params


# ──────────────────────────────────────────────
# Главная страница аналитики
# GET /workspace/analytics/
# ──────────────────────────────────────────────
@login_required
def analytics_view(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return redirect('workspace_home')
    context = {
        'can_edit': PermissionChecker.can_edit(request.user, 'ANALYTICS', 'access'),
    }
    return render(request, 'core/analytics.html', context)


# ──────────────────────────────────────────────
# API: список лабораторий (только department_type = 'LAB')
# GET /workspace/analytics/api/laboratories
# ──────────────────────────────────────────────
@login_required
def api_laboratories(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse([], safe=False, status=403)
    rows = _fetchall("""
        SELECT id, name, code
        FROM laboratories
        WHERE is_active = TRUE AND department_type = 'LAB'
        ORDER BY name
    """)
    data = [{"id": 0, "name": "Все лаборатории", "code": "ALL"}] + rows
    return JsonResponse(data, safe=False)


# ──────────────────────────────────────────────
# API: KPI-карточки
# GET /workspace/analytics/api/kpi?date_from=...&date_to=...&lab_id=0
# ──────────────────────────────────────────────
@login_required
def api_kpi(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse({}, status=403)

    lab_id = int(request.GET.get('lab_id', 0))
    lab_f = "AND s.laboratory_id = %s" if lab_id else ""
    lab_p = [lab_id] if lab_id else []

    date_f, date_p = _date_range_filter(request, 's.registration_date')
    base_p = date_p + lab_p

    total     = _fetchval(f"SELECT COUNT(*) FROM samples s WHERE s.status != 'CANCELLED' {date_f} {lab_f}", base_p)
    active    = _fetchval(f"SELECT COUNT(*) FROM samples s WHERE s.status NOT IN ('COMPLETED','CANCELLED') {date_f} {lab_f}", base_p)
    overdue   = _fetchval(f"SELECT COUNT(*) FROM samples s WHERE s.deadline < CURRENT_DATE AND s.status NOT IN ('COMPLETED','CANCELLED') {date_f} {lab_f}", base_p)
    cancelled = _fetchval(f"SELECT COUNT(*) FROM samples s WHERE s.status = 'CANCELLED' {date_f} {lab_f}", base_p)

    avg_time = _fetchval(f"""
        SELECT COALESCE(ROUND(AVG(
            EXTRACT(DAY FROM (
                COALESCE(s.testing_end_datetime, CURRENT_TIMESTAMP) -
                COALESCE(s.testing_start_datetime, s.registration_date::timestamp)
            ))
        )::numeric, 1), 0)
        FROM samples s
        WHERE (s.testing_start_datetime IS NOT NULL OR s.testing_end_datetime IS NOT NULL)
        {date_f} {lab_f}
    """, base_p)

    if not avg_time:
        avg_time = _fetchval(f"""
            SELECT COALESCE(ROUND(AVG(s.deadline - s.registration_date)::numeric, 1), 0)
            FROM samples s
            WHERE s.deadline IS NOT NULL AND s.registration_date IS NOT NULL
            {date_f} {lab_f}
        """, base_p)

    if lab_id:
        employees = _fetchval(
            "SELECT COUNT(*) FROM users u JOIN laboratories l ON u.laboratory_id = l.id "
            "WHERE u.is_active = TRUE AND l.department_type = 'LAB' AND u.laboratory_id = %s", [lab_id])
        equipment = _fetchval(
            "SELECT COUNT(*) FROM equipment WHERE status = 'OPERATIONAL' AND laboratory_id = %s", [lab_id])
    else:
        employees = _fetchval(
            "SELECT COUNT(*) FROM users u JOIN laboratories l ON u.laboratory_id = l.id "
            "WHERE u.is_active = TRUE AND l.department_type = 'LAB'")
        equipment = _fetchval(
            "SELECT COUNT(*) FROM equipment WHERE status = 'OPERATIONAL'")

    completed = _fetchval(f"SELECT COUNT(*) FROM samples s WHERE s.status = 'COMPLETED' {date_f} {lab_f}", base_p)

    return JsonResponse({
        "total_samples":         int(total or 0),
        "active_samples":        int(active or 0),
        "overdue_samples":       int(overdue or 0),
        "cancelled_samples":     int(cancelled or 0),
        "avg_test_days":         float(avg_time or 0),
        "total_employees":       int(employees or 0),
        "active_equipment":      int(equipment or 0),
        "completed_this_period": int(completed or 0),
    })


# ──────────────────────────────────────────────
# API: трудоёмкость по месяцам
# ──────────────────────────────────────────────
@login_required
def api_monthly_labor(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse([], safe=False, status=403)

    lab_id = int(request.GET.get('lab_id', 0))
    lab_f = "AND laboratory_id = %s" if lab_id else ""
    lab_p = [lab_id] if lab_id else []
    date_f, date_p = _date_range_filter(request)

    rows = _fetchall(f"""
        SELECT TO_CHAR(registration_date, 'YYYY-MM') as month,
               COUNT(*) as samples_count
        FROM samples
        WHERE 1=1 {date_f} {lab_f}
        GROUP BY TO_CHAR(registration_date, 'YYYY-MM')
        ORDER BY month
    """, date_p + lab_p)
    return JsonResponse(rows, safe=False)


# ──────────────────────────────────────────────
# API: распределение по лабораториям (только LAB)
# ──────────────────────────────────────────────
@login_required
def api_laboratory_distribution(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse([], safe=False, status=403)

    date_f, date_p = _date_range_filter(request, 's.registration_date')

    rows = _fetchall(f"""
        SELECT COALESCE(l.name, 'Без лаборатории') as laboratory,
               COUNT(s.id) as samples_count
        FROM samples s
        LEFT JOIN laboratories l ON s.laboratory_id = l.id
        WHERE (l.department_type = 'LAB' OR l.id IS NULL)
        {date_f}
        GROUP BY l.id, l.name
        ORDER BY samples_count DESC
    """, date_p)
    return JsonResponse(rows, safe=False)


# ──────────────────────────────────────────────
# API: распределение по статусам
# ──────────────────────────────────────────────
@login_required
def api_status_distribution(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse([], safe=False, status=403)

    lab_id = int(request.GET.get('lab_id', 0))
    lab_f = "AND laboratory_id = %s" if lab_id else ""
    lab_p = [lab_id] if lab_id else []
    date_f, date_p = _date_range_filter(request)

    rows = _fetchall(f"""
        SELECT status, COUNT(*) as count
        FROM samples
        WHERE status IS NOT NULL {date_f} {lab_f}
        GROUP BY status ORDER BY count DESC
    """, date_p + lab_p)
    return JsonResponse(rows, safe=False)


# ──────────────────────────────────────────────
# API: динамика регистраций по дням
# ──────────────────────────────────────────────
@login_required
def api_daily_registrations(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse([], safe=False, status=403)

    lab_id = int(request.GET.get('lab_id', 0))
    lab_f = "AND laboratory_id = %s" if lab_id else ""
    lab_p = [lab_id] if lab_id else []
    date_f, date_p = _date_range_filter(request)

    rows = _fetchall(f"""
        SELECT TO_CHAR(registration_date, 'YYYY-MM-DD') as date,
               COUNT(*) as registrations
        FROM samples
        WHERE 1=1 {date_f} {lab_f}
        GROUP BY registration_date ORDER BY date
    """, date_p + lab_p)
    return JsonResponse(rows, safe=False)


# ──────────────────────────────────────────────
# API: статистика сотрудников (только department_type = 'LAB')
# ──────────────────────────────────────────────
@login_required
def api_employee_stats(request):
    if not PermissionChecker.can_view(request.user, 'ANALYTICS', 'access'):
        return JsonResponse([], safe=False, status=403)

    lab_id = int(request.GET.get('lab_id', 0))
    lab_filter = "AND u.laboratory_id = %s" if lab_id else ""
    p = [lab_id] if lab_id else []

    rows = _fetchall(f"""
        SELECT
            u.id,
            u.last_name,
            u.first_name,
            u.role,
            l.name as laboratory_name,
            COUNT(DISTINCT so.sample_id) as samples_tested,
            COUNT(DISTINCT s.id)         as protocols_made
        FROM users u
        JOIN laboratories l ON u.laboratory_id = l.id
        LEFT JOIN sample_operators so ON u.id = so.user_id
            AND so.sample_id IN (
                SELECT id FROM samples WHERE testing_end_datetime IS NOT NULL
            )
        LEFT JOIN samples s ON u.id = s.report_prepared_by_id
            AND s.testing_end_datetime IS NOT NULL
        WHERE u.is_active = TRUE
          AND l.department_type = 'LAB'
          {lab_filter}
        GROUP BY u.id, u.last_name, u.first_name, u.role, l.name
        ORDER BY samples_tested DESC, protocols_made DESC
    """, p)

    return JsonResponse(rows, safe=False)
"""
core/views/equipment_calendar_views.py — Календарь ТО и поверок оборудования
v3.40.0

Новый таб в оборудовании: Реестр / Планы ТО / Поверки / 📅 Календарь

Маршруты в core/urls.py:
    path('workspace/equipment/calendar/', equipment_calendar_views.equipment_calendar, name='equipment_calendar'),
    path('workspace/equipment/calendar/events/', equipment_calendar_views.equipment_calendar_events, name='equipment_calendar_events'),
"""

import json
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.http import JsonResponse

from core.permissions import PermissionChecker
from core.models import Laboratory


def _fetchall(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [col[0] for col in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
# Страница календаря (HTML)
# ─────────────────────────────────────────────────────────────

@login_required
def equipment_calendar(request):
    if not PermissionChecker.can_view(request.user, 'EQUIPMENT', 'access'):
        messages.error(request, 'У вас нет доступа к разделу оборудования')
        return redirect('workspace_home')

    laboratories = Laboratory.objects.filter(
        is_active=True, department_type='LAB'
    ).order_by('name')

    return render(request, 'core/equipment_calendar.html', {
        'laboratories': laboratories,
        'user': request.user,
    })


# ─────────────────────────────────────────────────────────────
# API: события для календаря (JSON)
# ─────────────────────────────────────────────────────────────

@login_required
def equipment_calendar_events(request):
    """
    GET /workspace/equipment/calendar/events/?start=2026-03-01&end=2026-03-31
        &event_type=all|verification|maintenance
        &equipment_type=all|СИ|ИО|ВО
        &lab_id=

    Возвращает JSON со списком событий.
    """
    if not PermissionChecker.can_view(request.user, 'EQUIPMENT', 'access'):
        return JsonResponse({'error': 'Нет доступа'}, status=403)

    start_str = request.GET.get('start', '')
    end_str = request.GET.get('end', '')
    event_type = request.GET.get('event_type', 'all')
    equipment_type = request.GET.get('equipment_type', 'all')
    lab_id = request.GET.get('lab_id', '')

    # По умолчанию — текущий месяц
    today = date.today()
    try:
        start_date = date.fromisoformat(start_str) if start_str else today.replace(day=1)
    except ValueError:
        start_date = today.replace(day=1)

    try:
        end_date = date.fromisoformat(end_str) if end_str else _last_day_of_month(start_date)
    except ValueError:
        end_date = _last_day_of_month(start_date)

    events = []

    # ── 1. Поверки / аттестации / калибровки ─────────────────
    if event_type in ('all', 'verification'):
        events += _get_verification_events(start_date, end_date, equipment_type, lab_id)

    # ── 2. Плановое ТО ──────────────────────────────────────
    if event_type in ('all', 'maintenance'):
        events += _get_maintenance_events(start_date, end_date, equipment_type, lab_id)

    # Сортировка по дате
    events.sort(key=lambda e: (e['date'], e['event_type'], e['equipment_name']))

    return JsonResponse({'events': events})


def _get_verification_events(start_date, end_date, equipment_type, lab_id):
    """
    Поверки/аттестации/калибровки:
    - Предстоящие: для каждого оборудования берём последнюю запись,
      next_due = valid_until (если есть) ИЛИ maintenance_date + metrology_interval
    - Выполненные: maintenance_date в диапазоне
    """
    events = []
    extra_where, extra_params = _build_extra_filters(equipment_type, lab_id)
    today = date.today()

    type_labels = {
        'VERIFICATION': 'Поверка',
        'ATTESTATION': 'Аттестация',
        'CALIBRATION': 'Калибровка',
    }

    # ── Предстоящие ──────────────────────────────────────────
    # Берём последнюю запись каждого типа (поверка/аттестация/калибровка)
    # для каждого оборудования и считаем next_due
    rows = _fetchall(f"""
        WITH last_records AS (
            SELECT DISTINCT ON (em.equipment_id, em.maintenance_type)
                em.id AS record_id,
                em.equipment_id,
                em.maintenance_type,
                em.maintenance_date,
                em.valid_until,
                em.certificate_number,
                em.verification_result
            FROM equipment_maintenance em
            WHERE em.maintenance_type IN ('VERIFICATION', 'ATTESTATION', 'CALIBRATION')
            ORDER BY em.equipment_id, em.maintenance_type, em.maintenance_date DESC
        )
        SELECT
            lr.record_id,
            lr.maintenance_type,
            lr.maintenance_date,
            lr.valid_until,
            lr.certificate_number,
            lr.verification_result,
            COALESCE(
                lr.valid_until,
                lr.maintenance_date + (e.metrology_interval || ' months')::interval
            )::date AS next_due,
            e.id AS equipment_id,
            e.name AS equipment_name,
            e.accounting_number,
            e.equipment_type,
            e.metrology_interval,
            l.name AS laboratory_name
        FROM last_records lr
        JOIN equipment e ON e.id = lr.equipment_id
        LEFT JOIN laboratories l ON l.id = e.laboratory_id
        WHERE e.status != 'RETIRED'
          AND (
              lr.valid_until IS NOT NULL
              OR (lr.maintenance_date IS NOT NULL AND e.metrology_interval IS NOT NULL AND e.metrology_interval > 0)
          )
          AND COALESCE(
              lr.valid_until,
              (lr.maintenance_date + (e.metrology_interval || ' months')::interval)::date
          ) BETWEEN %s AND %s
          {extra_where}
        ORDER BY next_due
    """, [start_date, end_date] + extra_params)

    for row in rows:
        d = row['next_due']
        if d < today:
            status = 'overdue'
        elif (d - today).days <= 7:
            status = 'soon'
        else:
            status = 'upcoming'

        detail = f"Годен до {d.strftime('%d.%m.%Y')}"
        if not row['valid_until'] and row['metrology_interval']:
            detail = f"Следующая: {d.strftime('%d.%m.%Y')} (интервал {row['metrology_interval']} мес.)"

        events.append({
            'date': d.isoformat(),
            'event_type': 'verification',
            'event_subtype': row['maintenance_type'],
            'label': type_labels.get(row['maintenance_type'], 'Поверка'),
            'status': status,
            'equipment_id': row['equipment_id'],
            'equipment_name': row['equipment_name'],
            'accounting_number': row['accounting_number'],
            'equipment_type': row['equipment_type'],
            'laboratory_name': row['laboratory_name'] or '',
            'detail': detail,
            'link': f"/workspace/equipment/{row['equipment_id']}/",
        })

    # ── Выполненные (maintenance_date в диапазоне) ───────────
    rows2 = _fetchall(f"""
        SELECT
            em.id AS record_id,
            em.maintenance_date,
            em.maintenance_type,
            em.valid_until,
            em.certificate_number,
            em.verification_result,
            e.id AS equipment_id,
            e.name AS equipment_name,
            e.accounting_number,
            e.equipment_type,
            l.name AS laboratory_name
        FROM equipment_maintenance em
        JOIN equipment e ON e.id = em.equipment_id
        LEFT JOIN laboratories l ON l.id = e.laboratory_id
        WHERE em.maintenance_date BETWEEN %s AND %s
          AND em.maintenance_type IN ('VERIFICATION', 'ATTESTATION', 'CALIBRATION')
          AND e.status != 'RETIRED'
          {extra_where}
        ORDER BY em.maintenance_date
    """, [start_date, end_date] + extra_params)

    result_labels = {
        'SUITABLE': 'пригоден',
        'UNSUITABLE': 'непригоден',
    }

    for row in rows2:
        d = row['maintenance_date']
        result_text = result_labels.get(row.get('verification_result'), '')
        detail = f"Выполнено {d.strftime('%d.%m.%Y')}"
        if result_text:
            detail += f" — {result_text}"

        events.append({
            'date': d.isoformat(),
            'event_type': 'verification',
            'event_subtype': row['maintenance_type'],
            'label': type_labels.get(row['maintenance_type'], 'Поверка'),
            'status': 'completed',
            'equipment_id': row['equipment_id'],
            'equipment_name': row['equipment_name'],
            'accounting_number': row['accounting_number'],
            'equipment_type': row['equipment_type'],
            'laboratory_name': row['laboratory_name'] or '',
            'detail': detail,
            'link': f"/workspace/equipment/{row['equipment_id']}/",
        })

    return events


def _get_maintenance_events(start_date, end_date, equipment_type, lab_id):
    """
    Плановое ТО:
    - Предстоящие: next_due_date в диапазоне
    - Выполненные: performed_date из equipment_maintenance_logs
    """
    events = []
    extra_where, extra_params = _build_extra_filters(equipment_type, lab_id)
    today = date.today()

    # Предстоящие (next_due_date)
    rows = _fetchall(f"""
        SELECT
            emp.id AS plan_id,
            emp.name AS plan_name,
            emp.next_due_date,
            e.id AS equipment_id,
            e.name AS equipment_name,
            e.accounting_number,
            e.equipment_type,
            l.name AS laboratory_name
        FROM equipment_maintenance_plans emp
        JOIN equipment e ON e.id = emp.equipment_id
        LEFT JOIN laboratories l ON l.id = e.laboratory_id
        WHERE emp.is_active = TRUE
          AND emp.next_due_date IS NOT NULL
          AND emp.next_due_date BETWEEN %s AND %s
          AND e.status != 'RETIRED'
          {extra_where}
        ORDER BY emp.next_due_date
    """, [start_date, end_date] + extra_params)

    for row in rows:
        d = row['next_due_date']
        if d < today:
            status = 'overdue'
        elif (d - today).days <= 7:
            status = 'soon'
        else:
            status = 'upcoming'

        events.append({
            'date': d.isoformat(),
            'event_type': 'maintenance',
            'event_subtype': 'TO',
            'label': row['plan_name'],
            'status': status,
            'equipment_id': row['equipment_id'],
            'equipment_name': row['equipment_name'],
            'accounting_number': row['accounting_number'],
            'equipment_type': row['equipment_type'],
            'laboratory_name': row['laboratory_name'] or '',
            'detail': f"Срок: {d.strftime('%d.%m.%Y')}",
            'link': f"/workspace/maintenance/{row['plan_id']}/",
        })

    # Выполненные (из логов)
    rows2 = _fetchall(f"""
        SELECT
            ml.performed_date,
            ml.status AS log_status,
            emp.id AS plan_id,
            emp.name AS plan_name,
            e.id AS equipment_id,
            e.name AS equipment_name,
            e.accounting_number,
            e.equipment_type,
            l.name AS laboratory_name
        FROM equipment_maintenance_logs ml
        JOIN equipment_maintenance_plans emp ON emp.id = ml.plan_id
        JOIN equipment e ON e.id = emp.equipment_id
        LEFT JOIN laboratories l ON l.id = e.laboratory_id
        WHERE ml.performed_date BETWEEN %s AND %s
          AND ml.status IN ('COMPLETED', 'OVERDUE')
          AND e.status != 'RETIRED'
          {extra_where}
        ORDER BY ml.performed_date
    """, [start_date, end_date] + extra_params)

    for row in rows2:
        d = row['performed_date']
        events.append({
            'date': d.isoformat(),
            'event_type': 'maintenance',
            'event_subtype': 'TO',
            'label': row['plan_name'],
            'status': 'completed',
            'equipment_id': row['equipment_id'],
            'equipment_name': row['equipment_name'],
            'accounting_number': row['accounting_number'],
            'equipment_type': row['equipment_type'],
            'laboratory_name': row['laboratory_name'] or '',
            'detail': f"Выполнено {d.strftime('%d.%m.%Y')}",
            'link': f"/workspace/maintenance/{row['plan_id']}/",
        })

    return events


# ─── Утилиты ────────────────────────────────────────────────

def _build_extra_filters(equipment_type, lab_id):
    """Формирует дополнительные WHERE-условия для фильтрации."""
    clauses = []
    params = []

    if equipment_type and equipment_type != 'all':
        clauses.append("AND e.equipment_type = %s")
        params.append(equipment_type)

    if lab_id:
        try:
            clauses.append("AND e.laboratory_id = %s")
            params.append(int(lab_id))
        except (ValueError, TypeError):
            pass

    return ' '.join(clauses), params


def _last_day_of_month(d):
    """Последний день месяца."""
    if d.month == 12:
        return d.replace(day=31)
    return d.replace(month=d.month + 1, day=1) - timedelta(days=1)
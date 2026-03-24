"""
core/services/metrology_checker.py — Автопроверка сроков МО оборудования
v3.39.0

Запускается автоматически при открытии рабочего стола (workspace_home).
Проверяет не чаще 1 раза в сутки (кеш в памяти процесса).
За 7 дней до истечения срока — создаёт задачу METROLOGY ответственным + СМК.
"""

import logging
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── Настройки ───────────────────────────────────────────────
WARN_DAYS_BEFORE = 7        # за сколько дней предупреждать
CHECK_INTERVAL_HOURS = 24   # не чаще раза в N часов

# Кеш последней проверки (в памяти процесса)
_last_checked = None


def maybe_check_metrology():
    """
    Вызывается из workspace_home.
    Если прошло больше CHECK_INTERVAL_HOURS — запускает проверку.
    """
    global _last_checked

    now = timezone.now()

    if _last_checked and (now - _last_checked).total_seconds() < CHECK_INTERVAL_HOURS * 3600:
        return  # ещё рано

    _last_checked = now

    try:
        _run_check()
    except Exception:
        logger.exception('Ошибка автопроверки МО оборудования')


def _run_check():
    """Основная логика проверки."""
    try:
        from core.models.equipment import Equipment, EquipmentMaintenance
        from core.models.tasks import Task, TaskAssignee

        today = date.today()
        warn_date = today + timedelta(days=WARN_DAYS_BEFORE)

        # Оборудование с интервалом МО, не выведенное из эксплуатации
        equipment_qs = Equipment.objects.filter(
            metrology_interval__gt=0,
        ).exclude(
            status='RETIRED',
        ).select_related('responsible_person', 'substitute_person', 'laboratory')

        created = 0

        # Работники СМК — получаем один раз
        from core.models import User
        qms_user_ids = set(User.objects.filter(
            role__in=('QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST'), is_active=True,
        ).values_list('id', flat=True))

        for eq in equipment_qs:
            next_due = _calc_next_due(eq)
            if next_due is None:
                continue

            # Срок ещё далеко
            if next_due > warn_date:
                continue

            # Собираем ответственных + отдел СМК
            assignee_ids = set()
            if eq.responsible_person_id:
                assignee_ids.add(eq.responsible_person_id)
            if eq.substitute_person_id:
                assignee_ids.add(eq.substitute_person_id)
            assignee_ids.update(qms_user_ids)

            if not assignee_ids:
                continue

            # Ищем открытую задачу по этому оборудованию
            existing = Task.objects.filter(
                task_type='METROLOGY',
                entity_type='equipment',
                entity_id=eq.id,
                status__in=['OPEN', 'IN_PROGRESS'],
            ).first()

            if existing:
                # Досинхронизируем исполнителей (добавляем недостающих)
                current_ids = set(
                    TaskAssignee.objects.filter(task=existing).values_list('user_id', flat=True)
                )
                for uid in assignee_ids - current_ids:
                    TaskAssignee.objects.get_or_create(task=existing, user_id=uid)
                continue

            days_left = (next_due - today).days

            # Заголовок
            if days_left < 0:
                title = f'Просрочено МО: {eq.name} ({eq.accounting_number})'
                priority = 'HIGH'
            elif days_left == 0:
                title = f'Сегодня истекает срок МО: {eq.name} ({eq.accounting_number})'
                priority = 'HIGH'
            else:
                title = f'Через {days_left} дн. МО: {eq.name} ({eq.accounting_number})'
                priority = 'MEDIUM' if days_left > 3 else 'HIGH'

            description = (
                f'Оборудование: {eq.name}\n'
                f'Учётный №: {eq.accounting_number}\n'
                f'Инвентарный №: {eq.inventory_number}\n'
                f'Срок МО: {next_due.strftime("%d.%m.%Y")}\n'
                f'Интервал: {eq.metrology_interval} мес.\n'
                f'Лаборатория: {eq.laboratory}'
            )

            task = Task.objects.create(
                task_type='METROLOGY',
                title=title,
                description=description,
                entity_type='equipment',
                entity_id=eq.id,
                created_by=None,  # система
                laboratory=eq.laboratory,
                deadline=next_due,
                priority=priority,
            )
            for uid in assignee_ids:
                TaskAssignee.objects.get_or_create(task=task, user_id=uid)

            created += 1

        if created:
            logger.info(f'Metrology checker: создано {created} задач')

    except Exception:
        logger.exception('Ошибка автопроверки МО оборудования')


def _calc_next_due(eq):
    """
    Дата следующего МО:
    1) valid_until из последней записи (если заполнено)
    2) maintenance_date + metrology_interval месяцев
    """
    from core.models.equipment import EquipmentMaintenance

    last = EquipmentMaintenance.objects.filter(
        equipment=eq,
        maintenance_type__in=['VERIFICATION', 'ATTESTATION', 'CALIBRATION'],
    ).order_by('-maintenance_date').first()

    if last is None:
        return None

    # Приоритет: valid_until
    if last.valid_until:
        return last.valid_until

    # Иначе: дата + интервал
    if last.maintenance_date and eq.metrology_interval:
        return _add_months(last.maintenance_date, eq.metrology_interval)

    return None


def _add_months(d, months):
    """Добавить N месяцев к дате (без dateutil)."""
    import calendar
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)
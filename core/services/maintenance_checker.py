"""
core/services/maintenance_checker.py — Автопроверка сроков планового ТО
v3.40.0

Запускается автоматически при открытии рабочего стола (workspace_home).
Проверяет не чаще 1 раза в сутки.
За 7 дней до next_due_date — создаёт задачу MAINTENANCE ответственным.

Подключить в core/views/views.py → workspace_home:
    from core.services.maintenance_checker import maybe_check_maintenance
    ...
    maybe_check_maintenance()   # после maybe_check_metrology()
"""

import logging
import threading
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── Настройки ───────────────────────────────────────────────
WARN_DAYS_BEFORE = 7        # за сколько дней предупреждать
CHECK_INTERVAL_HOURS = 24   # не чаще раза в N часов

# Потокобезопасный кеш последней проверки
_lock = threading.Lock()
_last_checked = None


def maybe_check_maintenance():
    """
    Вызывается из workspace_home.
    Если прошло больше CHECK_INTERVAL_HOURS — запускает проверку в фоне.
    """
    global _last_checked

    now = timezone.now()

    with _lock:
        if _last_checked and (now - _last_checked).total_seconds() < CHECK_INTERVAL_HOURS * 3600:
            return  # ещё рано
        _last_checked = now

    # Запускаем в отдельном потоке, чтобы не тормозить загрузку страницы
    t = threading.Thread(target=_run_check, daemon=True)
    t.start()


def _run_check():
    """Основная логика проверки планов ТО."""
    try:
        from core.models.equipment import EquipmentMaintenancePlan
        from core.models.tasks import Task, TaskAssignee

        today = date.today()
        warn_date = today + timedelta(days=WARN_DAYS_BEFORE)

        # Все активные планы с календарной периодичностью,
        # у которых next_due_date ≤ warn_date (включая просроченные)
        plans = (
            EquipmentMaintenancePlan.objects
            .filter(
                is_active=True,
                next_due_date__isnull=False,
                next_due_date__lte=warn_date,
            )
            .select_related(
                'equipment',
                'equipment__laboratory',
                'equipment__responsible_person',
                'equipment__substitute_person',
            )
        )

        created = 0

        for plan in plans:
            eq = plan.equipment

            # Пропускаем выведенное из эксплуатации оборудование
            if eq.status == 'RETIRED':
                continue

            # Проверяем: нет ли уже открытой задачи по этому плану ТО
            existing = Task.objects.filter(
                task_type='MAINTENANCE',
                entity_type='maintenance_plan',
                entity_id=plan.id,
                status__in=['OPEN', 'IN_PROGRESS'],
            ).exists()

            if existing:
                continue

            # ⭐ v3.73.0: Исполнители — через equipment_access.
            # Все сотрудники, допущенные к этому оборудованию (с учётом
            # доп. лаб, областей, исключений по стандартам, overrides).
            # Закрывать ТО смогут только не-стажёры — это гейтится в view.
            from core.services.equipment_access import get_equipment_allowed_users

            assignee_ids = set(
                get_equipment_allowed_users(eq, include_trainees=True)
                    .values_list('id', flat=True)
            )

            # Добавляем ответственных на всякий случай, даже если они
            # формально в другой лабе (метролог, замещающий с другой кафедры)
            # и не прошли по автонабору.
            if eq.responsible_person_id:
                assignee_ids.add(eq.responsible_person_id)
            if eq.substitute_person_id:
                assignee_ids.add(eq.substitute_person_id)

            if not assignee_ids:
                logger.warning(
                    f'Maintenance checker: план ТО #{plan.id} '
                    f'({plan.name}) для {eq.accounting_number} — '
                    f'нет допущенных сотрудников, задача не создана'
                )
                continue

            # Определяем приоритет
            days_left = (plan.next_due_date - today).days
            if days_left < 0:
                title = f'⚠ Просрочено ТО: {plan.name} — {eq.name} ({eq.accounting_number})'
                priority = 'HIGH'
            elif days_left <= 3:
                title = f'Срочно ТО: {plan.name} — {eq.name} ({eq.accounting_number})'
                priority = 'HIGH'
            else:
                title = f'Плановое ТО: {plan.name} — {eq.name} ({eq.accounting_number})'
                priority = 'MEDIUM'

            description = (
                f'Оборудование: {eq.name}\n'
                f'Учётный №: {eq.accounting_number}\n'
                f'Инвентарный №: {eq.inventory_number}\n'
                f'Вид ТО: {plan.name}\n'
                f'Срок: {plan.next_due_date.strftime("%d.%m.%Y")}\n'
                f'Периодичность: {plan.frequency_display()}\n'
                f'Лаборатория: {eq.laboratory}'
            )

            task = Task.objects.create(
                task_type='MAINTENANCE',
                title=title,
                description=description,
                entity_type='maintenance_plan',
                entity_id=plan.id,
                created_by=None,  # система
                laboratory=eq.laboratory,
                deadline=plan.next_due_date,
                priority=priority,
            )
            for uid in assignee_ids:
                TaskAssignee.objects.get_or_create(task=task, user_id=uid)

            created += 1

        if created:
            logger.info(f'Maintenance checker: создано {created} задач по ТО')

    except Exception:
        logger.exception('Ошибка автопроверки планового ТО оборудования')
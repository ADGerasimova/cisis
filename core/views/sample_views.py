"""
CISIS — Views для работы с образцами.

Содержит:
- sample_create: создание образца
- sample_detail: детальная карточка образца
- _build_fields_data: формирование полей для шаблона
- _handle_status_change: обработка смены статуса
- _get_status_actions: доступные кнопки действий
- unfreeze_registration_block: AJAX разморозка блока регистрации
- search_protocols / search_standards / search_moisture_samples / search_uzk_samples: AJAX endpoints

⭐ v3.15.0: Влагонасыщение (moisture conditioning)
  - accept_from_moisture в _handle_status_change
  - Автопереход MOISTURE_CONDITIONING после accept_sample (из мастерской)
  - Кнопка «💧 Принять из влагонасыщения» в _get_status_actions
  - moisture_conditioning / moisture_sample в _build_fields_data
  - Контекст moisture_sample + dependent_moisture_samples в sample_detail
  - Чекбокс + moisture_sample_id в sample_create
  - AJAX endpoint search_moisture_samples

⭐ v3.64.0: УЗК (uzk_sample) + приёмка в лаборатории
  - accept_from_uzk / accept_in_lab в _handle_status_change
  - Автопереход UZK_TESTING при верификации (если uzk_required)
  - Цепочка: УЗК → Влагонасыщение → Нарезка → Целевая лаба (⭐ v3.66.0: исправлен приоритет)
  - Кнопка «🔍 Принять из УЗК» / «✅ Принял образец» в _get_status_actions
  - AJAX endpoint search_uzk_samples
  - Статус ACCEPTED_IN_LAB — обязательная приёмка испытателем
"""

import logging
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import models, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.models import (
    Sample, Laboratory, Client, Contract,
    Standard, AccreditationArea, JournalColumn,
    SampleOperator, SampleStatus, WorkshopStatus,
    StandardLaboratory, StandardAccreditationArea,
    User, SampleStandard, AcceptanceAct, SampleGostR56762Params,
)
from core.services.gost_r_56762 import (
    GostR56762ParamsForm,
    is_gost_r_56762_standard,
    build_test_conditions_gost_r_56762,
    GOST_R_56762_CODE,
)


# v3.38.0: Импорт Invoice (может отсутствовать)
try:
    from core.models import Invoice
except ImportError:
    Invoice = None
from core.permissions import PermissionChecker
from .constants import (
    AUTO_FIELDS, DATETIME_AUTO_FIELDS, STATUS_CHANGE_ACTIONS,
    REGISTRATION_FIELDS, WORKSHOP_FIELDS, TESTER_FIELDS,
    QMS_ROLES, WORKSHOP_ROLES, REPEAT_FIELD_GROUPS,
)
from .field_utils import (
    get_field_info, is_readonly_for_user, get_allowed_statuses_for_role,
    _validate_latin_only,
)
from .freeze_logic import _is_field_frozen, _can_unfreeze_block
from .save_logic import (
    save_sample_fields, handle_sample_save, _validate_trainee_for_draft,
)
from core.views.audit import log_action
from core.models.parameters import StandardParameter, SampleParameter  # ⭐ v3.43.0

logger = logging.getLogger(__name__)

# ⭐ v3.34.0: Переименование полей для отображения в карточке образца
FIELD_NAME_OVERRIDES = {
    'notes': 'Примечания к образцу',
    'object_info': 'Информация об объекте (конфиденц.)',
    'admin_notes': 'Примечания регистратора',
    'contract': 'Договор / Счёт',  # ⭐ v3.38.0
}


# ─────────────────────────────────────────────────────────────
# Проверка доступа
# ─────────────────────────────────────────────────────────────

def _check_sample_access(user, sample):
    """
    Проверяет доступ пользователя к образцу.
    Возвращает None если доступ разрешён, иначе строку с причиной отказа.
    """
    if user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'SYSADMIN',
                     'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST', 'CTO', 'CEO'):
        return None

    if user.role == 'WORKSHOP_HEAD':
        if sample.manufacturing and sample.status != 'PENDING_VERIFICATION':
            return None
        return 'У вас нет доступа к этому образцу'

    if user.role == 'WORKSHOP':
        if not sample.workshop_status or sample.status == 'PENDING_VERIFICATION':
            return 'У вас нет доступа к этому образцу'
        return None

    if user.role == 'LAB_HEAD':
        if not user.laboratory:
            return 'У вас нет доступа к этому образцу'
        if user.has_laboratory(sample.laboratory):
            return None
        return 'У вас нет доступа к этому образцу'

    if not user.has_laboratory(sample.laboratory):
        return 'У вас нет доступа к этому образцу'

    return None


# ─────────────────────────────────────────────────────────────
# Обработка статусов
# ─────────────────────────────────────────────────────────────

def _handle_status_change(request, sample, action):
    """Обрабатывает изменение статуса образца по action."""
    if not PermissionChecker.can_edit(request.user, 'SAMPLES', 'status'):
        # Исключения: accept_sample и accept_from_moisture для регистраторов
        allow_without_permission = False
        if action == 'accept_sample' and request.user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD') and sample.status in ('TRANSFERRED', 'MANUFACTURED'):
            allow_without_permission = True
        if action == 'accept_from_moisture' and request.user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD') and sample.status in ('MOISTURE_CONDITIONING', 'MOISTURE_READY'):
            allow_without_permission = True
        # ⭐ v3.64.0: accept_from_uzk для регистраторов
        if action == 'accept_from_uzk' and request.user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD') and sample.status in ('UZK_TESTING', 'UZK_READY'):
            allow_without_permission = True
        # ⭐ v3.64.0: accept_in_lab для испытателей и завлабов
        if action == 'accept_in_lab' and request.user.role in ('TESTER', 'LAB_HEAD') and sample.status == 'REGISTERED':
            allow_without_permission = True
        if not allow_without_permission:
            messages.error(request, 'У вас нет прав на изменение статуса')
            return redirect('sample_detail', sample_id=sample.id)

    now = timezone.now()
    now_local_str = timezone.localtime(now).strftime('%H:%M')

    old_status = sample.status  # ⭐ v3.14.0: запоминаем для аудита

    # ⭐ v3.34.0: Серверная валидация последовательности статусов для TESTER
    # ⭐ v3.64.0: Добавлен accept_in_lab и ACCEPTED_IN_LAB
    if request.user.role == 'TESTER':
        allowed_transitions = {
            'accept_in_lab': ('REGISTERED', 'TRANSFERRED'),
            'start_conditioning': ('ACCEPTED_IN_LAB', 'REPLACEMENT_PROTOCOL'),
            'ready_for_test': ('CONDITIONING',),
            'start_testing': ('ACCEPTED_IN_LAB', 'REPLACEMENT_PROTOCOL', 'READY_FOR_TEST'),
            'complete_test': ('IN_TESTING',),
            'draft_ready': ('TESTED',),
            'results_uploaded': ('TESTED',),
        }
        required_statuses = allowed_transitions.get(action)
        if required_statuses and sample.status not in required_statuses:
            messages.error(request, f'Нельзя выполнить это действие из текущего статуса')
            return redirect('sample_detail', sample_id=sample.id)

    if action in ('draft_ready', 'results_uploaded'):
        is_valid, error_msg = _validate_trainee_for_draft(sample)
        if not is_valid:
            messages.error(request, error_msg)
            return redirect('sample_detail', sample_id=sample.id)

    if action == 'complete_manufacturing':
        sample.status = SampleStatus.MANUFACTURED
        sample.workshop_status = WorkshopStatus.COMPLETED
        sample.manufacturing_completion_date = now
        sample.save()
        # ⭐ v3.14.0: аудит
        log_action(request, 'sample', sample.id, 'sample_status_change',
                   field_name='status', old_value=old_status, new_value=sample.status)
        # ⭐ v3.82.0: Синхронизируем статусы автозадач (MANUFACTURING → DONE,
        # т.к. образец стал MANUFACTURED)
        from core.views.task_views import sync_auto_task_from_sample, create_auto_task
        sync_auto_task_from_sample(sample, request)

        # ⭐ v3.39.0: Задача ACCEPT_SAMPLE — регистраторам
        try:
            registrar_ids = list(
                User.objects.filter(
                    role__in=('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'),
                    is_active=True,
                ).values_list('id', flat=True)
            )
            if registrar_ids:
                create_auto_task('ACCEPT_SAMPLE', sample, registrar_ids, created_by=None)
        except Exception:
            logger.exception('Ошибка создания задачи ACCEPT_SAMPLE')

        is_workshop_only = (
            sample.laboratory and sample.laboratory.code == 'WORKSHOP'
        )
        if is_workshop_only:
            messages.success(
                request,
                f'Изготовление завершено в {now_local_str}. '
                f'Образец ожидает приёмки регистратором (только нарезка).'
            )
        else:
            lab_name = sample.laboratory.name if sample.laboratory else 'лабораторию'
            messages.success(
                request,
                f'Изготовление завершено в {now_local_str}. '
                f'Образец ожидает приёмки регистратором для передачи в {lab_name}.'
            )
        return redirect('sample_detail', sample_id=sample.id)

    elif action == 'accept_sample':
        if sample.status not in ('TRANSFERRED', 'MANUFACTURED'):
            messages.error(request, 'Образец не в статусе "Передан" или "Изготовлено"')
            return redirect('sample_detail', sample_id=sample.id)
        # ⭐ v3.32.0: Только регистраторы и LAB_HEAD могут принимать образцы
        if request.user.role not in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'SYSADMIN'):
            messages.error(request, 'Принять образец может только регистратор или заведующий лабораторией')
            return redirect('sample_detail', sample_id=sample.id)

        # ⭐ v3.33.0: Определяем сценарий по целевой лаборатории
        is_workshop_only = (
            sample.laboratory and sample.laboratory.code == 'WORKSHOP'
        )

        if is_workshop_only:
            # Лаборатория = Мастерская → только нарезка → завершить
            sample.status = SampleStatus.COMPLETED
            messages.success(request, f'Образец принят и завершён (только нарезка)')
        elif sample.manufacturing:
            # Лаборатория = другая + нарезка в мастерской → передать в целевую лабу
            sample.status = SampleStatus.REGISTERED
            lab_name = sample.laboratory.name if sample.laboratory else 'лабораторию'
            messages.success(
                request,
                f'Образец принят из мастерской и передан в {lab_name} в {now_local_str}'
            )
        else:
            # Обычный приём без мастерской
            sample.status = SampleStatus.REGISTERED
            messages.success(request, f'Образец принят в лабораторию в {now_local_str}')
        sample.save()
        # ⭐ v3.14.0: аудит
        log_action(request, 'sample', sample.id, 'sample_status_change',
                   field_name='status', old_value=old_status, new_value=sample.status)

        # ⭐ v3.15.0: Автопереход в MOISTURE_CONDITIONING после приёма
        # ⭐ v3.66.0: НЕ переводить, если образец пришёл из мастерской (MANUFACTURED),
        # т.к. влагонасыщение уже пройдено ДО нарезки (accept_from_moisture → MANUFACTURING)
        # ⭐ v3.39.0: Закрываем задачу приёмки
        from core.views.task_views import close_auto_tasks
        close_auto_tasks('ACCEPT_SAMPLE', 'sample', sample.id)

        if (sample.status == SampleStatus.REGISTERED
                and old_status != 'MANUFACTURED'
                and sample.moisture_conditioning
                and sample.moisture_sample_id):
            prev_status = sample.status
            sample.status = SampleStatus.MOISTURE_CONDITIONING
            sample.save()
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status', old_value=prev_status,
                       new_value='MOISTURE_CONDITIONING')
            messages.info(
                request,
                'Образец автоматически переведён на влагонасыщение.'
            )

        # ⭐ v3.67.0: Задача TESTING создаётся через cron за 2 дня до дедлайна
        # (management command: create_testing_tasks)

        return redirect('sample_detail', sample_id=sample.id)

    # ⭐ v3.64.0: Приёмка образца в лаборатории (испытатель/завлаб подтверждает)
    elif action == 'accept_in_lab':
        if sample.status not in ('REGISTERED', 'TRANSFERRED'):
            messages.error(request, 'Образец не в статусе для приёмки в лаборатории')
            return redirect('sample_detail', sample_id=sample.id)
        if request.user.role not in ('TESTER', 'LAB_HEAD', 'SYSADMIN'):
            messages.error(request, 'Принять образец может только испытатель или заведующий лабораторией')
            return redirect('sample_detail', sample_id=sample.id)
        if request.user.role == 'LAB_HEAD' and not request.user.has_laboratory(sample.laboratory):
            messages.error(request, 'Это образец другой лаборатории')
            return redirect('sample_detail', sample_id=sample.id)
        sample.status = SampleStatus.ACCEPTED_IN_LAB
        sample.save()
        log_action(request, 'sample', sample.id, 'sample_status_change',
                   field_name='status', old_value=old_status, new_value=sample.status)
        messages.success(request, f'Образец принят в лаборатории в {now_local_str}')
        return redirect('sample_detail', sample_id=sample.id)

    # ⭐ v3.64.0: Приём из УЗК
    elif action == 'accept_from_uzk':
        if sample.status not in ('UZK_TESTING', 'UZK_READY'):
            messages.error(request, 'Образец не в статусе УЗК')
            return redirect('sample_detail', sample_id=sample.id)

        # Определяем следующий этап: УЗК → Влагонасыщение → Нарезка → Лаба
        # ⭐ v3.66.0: Влагонасыщение проверяется ПЕРЕД нарезкой (фикс приоритета)

        # ⭐ v3.67.0: Закрываем задачу «Принять из УЗК»
        try:
            from core.views.task_views import close_auto_tasks
            close_auto_tasks('ACCEPT_FROM_UZK', 'sample', sample.id)
        except Exception:
            logger.exception('Ошибка закрытия задачи ACCEPT_FROM_UZK')

        if sample.moisture_conditioning and sample.moisture_sample_id:
            # Влагонасыщение (нарезка, если нужна, произойдёт после)
            sample.status = SampleStatus.MOISTURE_CONDITIONING
            sample.save()
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status', old_value=old_status, new_value=sample.status)
            messages.success(request, f'Образец принят из УЗК и переведён на влагонасыщение в {now_local_str}')

        elif sample.manufacturing:
            # Нарезка в мастерской (без влагонасыщения)
            sample.status = SampleStatus.MANUFACTURING
            sample.workshop_status = WorkshopStatus.IN_WORKSHOP
            sample.save()
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status', old_value=old_status, new_value=sample.status)
            messages.success(request, f'Образец принят из УЗК и передан в мастерскую в {now_local_str}')

            # Автозадача MANUFACTURING
            try:
                from core.views.task_views import create_auto_task, sync_auto_task_from_sample
                workshop_user_ids = list(
                    User.objects.filter(
                        role__in=('WORKSHOP', 'WORKSHOP_HEAD'), is_active=True,
                    ).values_list('id', flat=True)
                )
                if workshop_user_ids:
                    create_auto_task('MANUFACTURING', sample, workshop_user_ids, created_by=None)
                # ⭐ v3.82.0: Образец уже в статусе MANUFACTURING — переводим
                # только что созданную задачу сразу в IN_PROGRESS
                sync_auto_task_from_sample(sample, request)
            except Exception:
                logger.exception('Ошибка создания задачи MANUFACTURING (accept_from_uzk)')

        else:
            # Целевая лаборатория
            sample.status = SampleStatus.REGISTERED
            sample.save()
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status', old_value=old_status, new_value=sample.status)
            lab_name = sample.laboratory.name if sample.laboratory else 'лабораторию'
            messages.success(request, f'Образец принят из УЗК и передан в {lab_name} в {now_local_str}')

            # ⭐ v3.67.0: Задача TESTING создаётся через cron за 2 дня до дедлайна

        return redirect('sample_detail', sample_id=sample.id)

    # ⭐ v3.15.0: Приём из влагонасыщения
    # ⭐ v3.66.0: После влагонасыщения — нарезка (если нужна), иначе лаборатория
    elif action == 'accept_from_moisture':
        if sample.status not in ('MOISTURE_CONDITIONING', 'MOISTURE_READY'):
            messages.error(request, 'Образец не в статусе влагонасыщения')
            return redirect('sample_detail', sample_id=sample.id)

        if sample.manufacturing:
            # ⭐ v3.66.0: После влагонасыщения → нарезка в мастерской
            sample.status = SampleStatus.MANUFACTURING
            sample.workshop_status = WorkshopStatus.IN_WORKSHOP
            sample.save()
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status', old_value=old_status, new_value=sample.status)
            messages.success(request, f'Образец принят из влагонасыщения и передан в мастерскую в {now_local_str}')

            # Автозадача MANUFACTURING
            try:
                from core.views.task_views import create_auto_task, sync_auto_task_from_sample
                workshop_user_ids = list(
                    User.objects.filter(
                        role__in=('WORKSHOP', 'WORKSHOP_HEAD'), is_active=True,
                    ).values_list('id', flat=True)
                )
                if workshop_user_ids:
                    create_auto_task('MANUFACTURING', sample, workshop_user_ids, created_by=None)
                # ⭐ v3.82.0: Образец уже в статусе MANUFACTURING — переводим
                # только что созданную задачу сразу в IN_PROGRESS
                sync_auto_task_from_sample(sample, request)
            except Exception:
                logger.exception('Ошибка создания задачи MANUFACTURING (accept_from_moisture)')
        else:
            # Без нарезки → целевая лаборатория
            sample.status = SampleStatus.REGISTERED
            sample.save()
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status', old_value=old_status, new_value=sample.status)
            messages.success(request, f'Образец принят из влагонасыщения в {now_local_str}')

            # ⭐ v3.67.0: Задача TESTING создаётся через cron за 2 дня до дедлайна

        return redirect('sample_detail', sample_id=sample.id)

    elif action == 'complete_cutting_only':
        sample.status = SampleStatus.COMPLETED
        sample.save()
        # ⭐ v3.14.0: аудит
        log_action(request, 'sample', sample.id, 'sample_status_change',
                   field_name='status', old_value=old_status, new_value=sample.status)
        messages.success(request, 'Нарезка завершена. Образец готов к выдаче заказчику.')
        return redirect('sample_detail', sample_id=sample.id)

    elif action == 'start_conditioning':
        old_cond_start = sample.conditioning_start_datetime  # ⭐ v3.16.0
        sample.status = 'CONDITIONING'
        sample.conditioning_start_datetime = now
        messages.success(request, f'Кондиционирование начато в {now_local_str}')

    elif action == 'ready_for_test':
        old_cond_end = sample.conditioning_end_datetime  # ⭐ v3.16.0
        sample.status = 'READY_FOR_TEST'
        sample.conditioning_end_datetime = now
        if sample.conditioning_start_datetime:
            duration = (now - sample.conditioning_start_datetime).total_seconds() / 3600
            messages.success(
                request,
                f'Кондиционирование завершено в {now_local_str}. '
                f'Длительность: {duration:.1f} часов'
            )
        else:
            messages.success(request, f'Кондиционирование завершено в {now_local_str}')

    elif action == 'start_testing':
        old_test_start = sample.testing_start_datetime  # ⭐ v3.16.0
        sample.status = 'IN_TESTING'
        sample.testing_start_datetime = now
        messages.success(request, f'Испытание начато в {now_local_str}')

        # ⭐ v3.82.0: Задача TESTING не закрывается при start_testing,
        # а переводится в IN_PROGRESS — делается ниже через
        # sync_auto_task_from_sample после общего sample.save().

    elif action == 'complete_test':
        old_test_end = sample.testing_end_datetime  # ⭐ v3.16.0
        sample.status = 'TESTED'
        sample.testing_end_datetime = now
        if sample.testing_start_datetime:
            duration = (now - sample.testing_start_datetime).total_seconds() / 3600
            messages.success(
                request,
                f'Испытание завершено в {now_local_str}. '
                f'Длительность: {duration:.1f} часов'
            )
        else:
            messages.success(request, f'Испытание завершено в {now_local_str}')

        # ⭐ v3.15.0: Автообновление зависимых образцов B при завершении испытания Образца A
        dependent_count = Sample.objects.filter(
            moisture_sample_id=sample.id,
            status='MOISTURE_CONDITIONING',
        ).update(status='MOISTURE_READY')
        if dependent_count:
            messages.info(
                request,
                f'Обновлено {dependent_count} связанных образцов → «Готово к передаче из УКИ»'
            )

        # ⭐ v3.64.0: Автообновление зависимых УЗК-образцов
        uzk_dependent_count = Sample.objects.filter(
            uzk_sample_id=sample.id,
            status='UZK_TESTING',
        ).update(status='UZK_READY')
        if uzk_dependent_count:
            messages.info(
                request,
                f'Обновлено {uzk_dependent_count} связанных образцов → «Готово к передаче из МИ (УЗК)»'
            )

        # ⭐ v3.82.0: Задача TESTING НЕ закрывается при complete_test (TESTED).
        # Она закрывается только при draft_ready или results_uploaded —
        # см. хук sync_auto_task_from_sample после общего sample.save().

    elif action == 'draft_ready':
        # ⭐ v3.84.0: Больше НЕ автоподставляем report_prepared_by / date.
        # Подготовившие — M2M report_preparers, заполняется в форме.
        # Дата подготовки — вручную, валидируется в _validate_trainee_for_draft
        # (вызван выше в этой же функции через _validate_trainee_for_draft).
        sample.status = 'DRAFT_READY'
        now_date_str = timezone.localtime(now).strftime('%d.%m.%Y %H:%M')
        messages.success(request, f'Черновик протокола готов. Время перехода: {now_date_str}')

    elif action == 'results_uploaded':
        # ⭐ v3.84.0: см. комментарий выше — автоподстановка убрана.
        sample.status = 'RESULTS_UPLOADED'
        now_date_str = timezone.localtime(now).strftime('%d.%m.%Y %H:%M')
        messages.success(request, f'Результаты выложены. Время перехода: {now_date_str}')

    elif action == 'protocol_issued':
        sample.status = 'PROTOCOL_ISSUED'
        messages.success(request, 'Статус изменён на "Протокол готов"')

    elif action == 'complete_sample':
        sample.status = 'COMPLETED'
        messages.success(request, 'Образец завершён')

    sample.save()

    # ⭐ v3.14.0: аудит (для всех веток, которые доходят до этого save)
    log_action(request, 'sample', sample.id, 'sample_status_change',
               field_name='status', old_value=old_status, new_value=sample.status)

    # ⭐ v3.16.0: аудит автозаполненных datetime-полей
    if action == 'start_conditioning':
        log_action(request, 'sample', sample.id, 'sample_updated',
                   field_name='conditioning_start_datetime',
                   old_value=old_cond_start, new_value=now)
    elif action == 'ready_for_test':
        log_action(request, 'sample', sample.id, 'sample_updated',
                   field_name='conditioning_end_datetime',
                   old_value=old_cond_end, new_value=now)
    elif action == 'start_testing':
        log_action(request, 'sample', sample.id, 'sample_updated',
                   field_name='testing_start_datetime',
                   old_value=old_test_start, new_value=now)
    elif action == 'complete_test':
        log_action(request, 'sample', sample.id, 'sample_updated',
                   field_name='testing_end_datetime',
                   old_value=old_test_end, new_value=now)
    # ⭐ v3.84.0: явный аудит report_prepared_date/by для draft_ready/results_uploaded
    # убран — теперь эти поля заполняются вручную через обычную форму,
    # аудит идёт автоматически через save_sample_fields → log_field_changes
    # (для report_prepared_date) и log_m2m_changes (для report_preparers).

    # ⭐ v3.82.0: Синхронизация статусов автозадач после смены статуса образца.
    # Покрывает переходы, обрабатываемые через общий sample.save() в конце функции:
    #   start_testing      → IN_TESTING      → TESTING task → IN_PROGRESS
    #   draft_ready        → DRAFT_READY     → TESTING task → DONE
    #   results_uploaded   → RESULTS_UPLOADED → TESTING task → DONE
    # Остальные action'ы (complete_manufacturing, accept_from_uzk,
    # accept_from_moisture) делают свой save() и вызывают хелпер локально,
    # до return redirect в собственной ветке.
    if action in ('start_testing', 'draft_ready', 'results_uploaded'):
        from core.views.task_views import sync_auto_task_from_sample
        sync_auto_task_from_sample(sample, request)

    return redirect('sample_detail', sample_id=sample.id)


def _get_status_actions(user, sample):
    """Определяет доступные кнопки действий со статусом."""
    actions = []
    user_role = user.role

    if user_role == 'WORKSHOP_HEAD':
        if sample.status == 'MANUFACTURING':
            actions.append({
                'action': 'complete_manufacturing',
                'label': '✅ Завершить изготовление и передать',
                'class': 'btn-success',
                'new_status': 'MANUFACTURED',
            })
        return actions

    if user_role == 'WORKSHOP':
        if sample.status == 'MANUFACTURING':
            actions.append({
                'action': 'complete_manufacturing',
                'label': '✅ Завершить изготовление и передать',
                'class': 'btn-success',
                'new_status': 'MANUFACTURED',
            })
        return actions

    if user_role in ('TESTER', 'LAB_HEAD'):
        # ⭐ v3.32.0: Принять образец — только LAB_HEAD (не TESTER)
        if user_role == 'LAB_HEAD' and sample.status == 'TRANSFERRED':
            is_own_lab = user.has_laboratory(sample.laboratory)
            if is_own_lab:
                actions.append({
                    'action': 'accept_sample',
                    'label': '📥 Принять образец',
                    'class': 'btn-success',
                    'new_status': 'REGISTERED',
                })

        is_own_lab = user.has_laboratory(sample.laboratory)
        if not is_own_lab and user_role == 'LAB_HEAD':
            return actions

        # ⭐ v3.64.0: Приёмка в лаборатории — первый шаг перед работой
        if sample.status in ('REGISTERED', 'TRANSFERRED'):
            actions.append({
                'action': 'accept_in_lab',
                'label': '✅ Принял образец в лабораторию',
                'class': 'btn-success',
                'new_status': 'ACCEPTED_IN_LAB',
            })

        working_statuses = (
            'ACCEPTED_IN_LAB', 'REPLACEMENT_PROTOCOL',
            'CONDITIONING', 'READY_FOR_TEST', 'IN_TESTING',
        )
        if sample.status in working_statuses:
            # ⭐ v3.34.0: TESTER видит только следующий шаг, LAB_HEAD — все
            # ⭐ v3.64.0: Кондиционирование/испытание — только после ACCEPTED_IN_LAB
            if user_role == 'TESTER':
                # Строгая последовательность: только следующее действие
                if sample.status in ('ACCEPTED_IN_LAB', 'REPLACEMENT_PROTOCOL'):
                    actions.append({
                        'action': 'start_conditioning',
                        'label': '🌡️ Начать кондиционирование',
                        'class': 'btn-primary',
                        'new_status': 'CONDITIONING',
                    })

                    actions.append({
                        'action': 'start_testing',
                        'label': '▶️ Начать испытание',
                        'class': 'btn-primary',
                        'new_status': 'IN_TESTING',
                    })

                elif sample.status == 'CONDITIONING':
                    actions.append({
                        'action': 'ready_for_test',
                        'label': '✓ Кондиционирование завершено',
                        'class': 'btn-success',
                        'new_status': 'READY_FOR_TEST',
                    })
                elif sample.status == 'READY_FOR_TEST':
                    actions.append({
                        'action': 'start_testing',
                        'label': '▶️ Начать испытание',
                        'class': 'btn-primary',
                        'new_status': 'IN_TESTING',
                    })
                elif sample.status == 'IN_TESTING':
                    actions.append({
                        'action': 'complete_test',
                        'label': '✓ Завершить испытание',
                        'class': 'btn-warning',
                        'new_status': 'TESTED',
                    })
            else:
                # LAB_HEAD — все кнопки (может перескакивать, но после приёмки)
                actions.extend([
                    {
                        'action': 'start_conditioning',
                        'label': '🌡️ Начать кондиционирование',
                        'class': 'btn-primary',
                        'new_status': 'CONDITIONING',
                    },
                    {
                        'action': 'ready_for_test',
                        'label': '✓ Кондиционирование завершено',
                        'class': 'btn-success',
                        'new_status': 'READY_FOR_TEST',
                    },
                    {
                        'action': 'start_testing',
                        'label': '▶️ Начать испытание',
                        'class': 'btn-primary',
                        'new_status': 'IN_TESTING',
                    },
                    {
                        'action': 'complete_test',
                        'label': '✓ Завершить испытание',
                        'class': 'btn-warning',
                        'new_status': 'TESTED',
                    },
                ])

        elif sample.status == 'TESTED':
            actions.extend([
                {
                    'action': 'draft_ready',
                    'label': '📝 Черновик протокола готов',
                    'class': 'btn-success',
                    'new_status': 'DRAFT_READY',
                },
                {
                    'action': 'results_uploaded',
                    'label': '📤 Результаты выложены (без протокола)',
                    'class': 'btn-warning',
                    'new_status': 'RESULTS_UPLOADED',
                },
            ])

    elif user_role in ('QMS_HEAD', 'QMS_ADMIN'):
        if sample.status == 'PROTOCOL_ISSUED':
            actions.append({
                'action': 'complete_sample',
                'label': '✅ Завершить работу (печать выполнена)',
                'class': 'btn-success',
                'new_status': 'COMPLETED',
            })

    if (user_role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD')
            and sample.status in ('TRANSFERRED', 'MANUFACTURED')):
        # ⭐ v3.33.0: Определяем по целевой лаборатории
        is_workshop_only = (
            sample.laboratory and sample.laboratory.code == 'WORKSHOP'
        )
        if is_workshop_only:
            actions.append({
                'action': 'accept_sample',
                'label': '📥 Принять и завершить (нарезка)',
                'class': 'btn-success',
                'new_status': 'COMPLETED',
            })
        elif sample.manufacturing:
            lab_name = sample.laboratory.name if sample.laboratory else 'лабораторию'
            actions.append({
                'action': 'accept_sample',
                'label': f'📥 Принять и передать в {lab_name}',
                'class': 'btn-success',
                'new_status': 'REGISTERED',
            })
        else:
            actions.append({
                'action': 'accept_sample',
                'label': '📥 Принять образец',
                'class': 'btn-success',
                'new_status': 'REGISTERED',
            })

    # ⭐ v3.15.0: Приём из влагонасыщения
    # Кнопка доступна при MOISTURE_READY (автоматический переход)
    # или при MOISTURE_CONDITIONING если Образец A уже TESTED+
    if (user_role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'SYSADMIN')
            and sample.status in ('MOISTURE_CONDITIONING', 'MOISTURE_READY')):
        show_button = False
        if sample.status == 'MOISTURE_READY':
            # Образец A уже завершён — кнопка всегда доступна
            show_button = True
        elif sample.moisture_sample_id:
            # Проверяем статус Образца A вручную (на случай если автообновление не сработало)
            MOISTURE_READY_STATUSES = frozenset([
                'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
                'PROTOCOL_ISSUED', 'COMPLETED',
            ])
            moisture_sample_status = (
                Sample.objects.filter(id=sample.moisture_sample_id)
                .values_list('status', flat=True)
                .first()
            )
            show_button = (moisture_sample_status in MOISTURE_READY_STATUSES)
        else:
            # Без привязки — кнопка доступна (ручной режим)
            show_button = True

        if show_button:
            # ⭐ v3.66.0: После влагонасыщения → нарезка или лаборатория
            if sample.manufacturing:
                moisture_next_label = '💧 Принять из влагонасыщения → мастерская'
                moisture_next_status = 'MANUFACTURING'
            else:
                moisture_next_label = '💧 Принять из влагонасыщения'
                moisture_next_status = 'REGISTERED'
            actions.append({
                'action': 'accept_from_moisture',
                'label': moisture_next_label,
                'class': 'btn-info',
                'new_status': moisture_next_status,
            })

    # ⭐ v3.64.0: Приём из УЗК
    # Кнопка доступна при UZK_READY или UZK_TESTING если УЗК-образец уже TESTED+
    if (user_role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'SYSADMIN')
            and sample.status in ('UZK_TESTING', 'UZK_READY')):
        show_uzk_button = False
        if sample.status == 'UZK_READY':
            show_uzk_button = True
        elif sample.uzk_sample_id:
            UZK_READY_STATUSES = frozenset([
                'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
                'PROTOCOL_ISSUED', 'COMPLETED',
            ])
            uzk_sample_status = (
                Sample.objects.filter(id=sample.uzk_sample_id)
                .values_list('status', flat=True)
                .first()
            )
            show_uzk_button = (uzk_sample_status in UZK_READY_STATUSES)
        else:
            show_uzk_button = True

        if show_uzk_button:
            # ⭐ v3.66.0: Определяем следующий этап для label (влагонасыщение приоритетнее нарезки)
            if sample.moisture_conditioning and sample.moisture_sample_id:
                uzk_next_label = '🔍 Принять из УЗК → влагонасыщение'
                uzk_next_status = 'MOISTURE_CONDITIONING'
            elif sample.manufacturing:
                uzk_next_label = '🔍 Принять из УЗК → мастерская'
                uzk_next_status = 'MANUFACTURING'
            else:
                lab_name = sample.laboratory.name if sample.laboratory else 'лабораторию'
                uzk_next_label = f'🔍 Принять из УЗК → {lab_name}'
                uzk_next_status = 'REGISTERED'
            actions.append({
                'action': 'accept_from_uzk',
                'label': uzk_next_label,
                'class': 'btn-info',
                'new_status': uzk_next_status,
            })

    if user.is_trainee:
        actions = [a for a in actions if a['action'] != 'protocol_issued']

    return actions


# ─────────────────────────────────────────────────────────────
# Построение данных для шаблона
# ─────────────────────────────────────────────────────────────

def _build_fields_data(request, sample):
    """Формирует структуру полей для отображения в шаблоне."""
    all_columns = JournalColumn.objects.filter(
        journal__code='SAMPLES', is_active=True
    ).order_by('display_order')

    # ⭐ v3.57.0: Блок «Регистрация» разбит на 4 логических группы:
    # Основная информация → Объект испытаний → Испытание → Хранение.
    # Статус вынесен в отдельный блок «Статусы» в самом конце.
    field_groups = {
        'Основная информация': [
            'sequence_number', 'cipher', 'registration_date',
            'client', 'contract', 'contract_date', 'laboratory',
            'acceptance_act',  # ⭐ v3.85.0 (1б): селект акта — источник для accompanying_doc_*
            'accompanying_doc_number', 'accompanying_doc_full_name',
            'test_code', 'test_type',
            'sample_received_date',
            'registered_by', 'verified_by', 'verified_at',
        ],
        'Информация об объекте испытаний': [
            'object_id', 'panel_id',
            'object_info',
            'material',
        ],
        'Испытание': [
            'accreditation_area', 'standards',
            'determined_parameters',
            'sample_count', 'additional_sample_count',
            'cutting_direction', 'test_conditions',
            'preparation',
            'notes',
            'deadline',
            'report_type', 'pi_number',
            'uzk_required',
            'replacement_protocol_required', 'replacement_pi_number',
            'admin_notes',
            # ⭐ v3.20.0: manufacturing/moisture поля вынесены в кастомный блок шаблона
            # 'manufacturing', 'manufacturing_deadline', 'workshop_notes', 'further_movement',
            # 'cutting_standard', 'moisture_conditioning', 'moisture_sample',
        ],
        'Хранение': [
            'storage_location', 'storage_conditions',
        ],
        'Изготовление (Мастерская)': [
            'workshop_status',
            'manufacturing_completion_date',
            'manufacturing_measuring_instruments',
            'manufacturing_testing_equipment',
            'manufacturing_auxiliary_equipment',
            'manufacturing_operators',
        ],
        'Испытатель': [
            # ⭐ v3.84.0: новый порядок — datetime-блоки сверху, M2M ширинами снизу
            'conditioning_start_datetime',
            'conditioning_end_datetime',
            'testing_start_datetime',
            'testing_end_datetime',
            'measuring_instruments',
            'testing_equipment',
            'auxiliary_equipment',
            'operators',
            'operator_notes',
            'report_prepared_date',
            'report_preparers',
        ],
        'СМК': [
            'protocol_checked_by',
            'protocol_issued_date',
            'protocol_printed_date',
            'replacement_protocol_issued_date',
        ],
        'Статусы': [
            'status',
        ],
    }

    user = request.user

    # Мастерская и WORKSHOP_HEAD не видят поле status
    if user.role in WORKSHOP_ROLES:
        for group_name in field_groups:
            field_groups[group_name] = [
                f for f in field_groups[group_name] if f != 'status'
            ]

    fields_data = {}
    for group_name, field_codes in field_groups.items():
        group_fields = []

        for field_code in field_codes:
            column = all_columns.filter(code=field_code).first()
            if not column:
                continue

            permission = PermissionChecker.get_user_permission(user, 'SAMPLES', field_code)
            if permission == 'NONE':
                continue

            field_info = get_field_info(sample, field_code, user)

            # ⭐ v3.85.0 (1б): Initial рендер dropdown'а «Акт приёма-передачи»
            # должен содержать только акты, релевантные текущей привязке
            # образца (симметрично AJAX-endpoints, которые используются для
            # каскада при смене client/contract/invoice):
            #   - есть contract → акты этого контракта
            #   - есть invoice  → акты этого счёта
            #   - только client → акты с client_direct = client (прямые)
            #   - ничего нет    → пустой список
            # Без этой фильтрации field.options возвращает ВСЕ акты системы
            # (generic-FK поведение), и dropdown показывает чужих заказчиков.
            if field_code == 'acceptance_act':
                from core.models import AcceptanceAct
                qs = AcceptanceAct.objects.all()
                if sample.contract_id:
                    qs = qs.filter(contract_id=sample.contract_id)
                elif getattr(sample, 'invoice_id', None):
                    qs = qs.filter(invoice_id=sample.invoice_id)
                elif sample.client_id:
                    qs = qs.filter(client_direct_id=sample.client_id)
                else:
                    qs = qs.none()
                # Гарантированно включаем текущее значение, даже если оно
                # не проходит по фильтру (старые данные / рассинхрон).
                if sample.acceptance_act_id:
                    qs = qs | AcceptanceAct.objects.filter(id=sample.acceptance_act_id)
                field_info['options'] = list(qs.distinct().order_by('-id'))

            is_editable = False
            frozen_reason = None

            if field_code == 'status':
                if user.role in ('TESTER', 'OPERATOR') or user.role in WORKSHOP_ROLES:
                    continue
                is_editable = (permission == 'EDIT')

            elif field_code in AUTO_FIELDS:
                is_editable = False

            elif field_code in DATETIME_AUTO_FIELDS:
                is_editable = (
                    permission == 'EDIT'
                    and user.role in ('SYSADMIN', 'LAB_HEAD', 'QMS_HEAD', 'QMS_ADMIN', 'WORKSHOP_HEAD')
                )

            else:
                is_editable = (permission == 'EDIT')

            if is_editable:
                is_frozen, reason = _is_field_frozen(field_code, user, sample, request=request)
                if is_frozen:
                    is_editable = False
                    frozen_reason = reason

            group_fields.append({
                'code': field_code,
                'name': FIELD_NAME_OVERRIDES.get(field_code, column.name),
                'value': field_info['value'],
                'display_value': field_info['display_value'],
                'field_type': field_info['field_type'],
                'choices': field_info.get('choices'),
                'options': field_info.get('options'),
                'is_editable': is_editable,
                'is_auto': field_code in AUTO_FIELDS or field_code in DATETIME_AUTO_FIELDS,
                'is_frozen': frozen_reason is not None,
                'frozen_reason': frozen_reason,
                'permission': permission,
                'help_text': field_info.get('help_text'),
            })

        if group_fields:
            fields_data[group_name] = group_fields

    # ⭐ v3.65.0: cut_maximum → «Макс.» вместо числового значения sample_count
    if sample.cut_maximum:
        for group_name, group_fields in fields_data.items():
            for field in group_fields:
                if field['code'] == 'sample_count':
                    field['display_value'] = '✂️ Максимальное'
                    field['is_editable'] = False  # readonly при cut_maximum
                    break
                elif field['code'] == 'additional_sample_count':
                    field['display_value'] = '—'
                    field['is_editable'] = False
                    break

    return fields_data


# ─────────────────────────────────────────────────────────────
# Verification contexts
# ─────────────────────────────────────────────────────────────

def _get_verification_context(request, sample):
    """Формирует контекст для блока проверки регистрации."""
    can_verify = False
    verification_message = ''
    verification_info = None

    if sample.status == 'PENDING_VERIFICATION':
        if sample.registered_by != request.user:
            if request.user.role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'SYSADMIN'):
                can_verify = True
                verification_message = (
                    f'Образец зарегистрирован {sample.registered_by.full_name}. '
                    f'Вы можете проверить и подтвердить регистрацию.'
                )
            elif (request.user.role == 'LAB_HEAD'
                  and request.user.has_laboratory(sample.laboratory)):
                can_verify = True
                verification_message = (
                    f'Образец зарегистрирован {sample.registered_by.full_name}. '
                    f'Вы можете проверить и подтвердить регистрацию.'
                )
            else:
                verification_message = 'Образец ожидает проверки.'
        else:
            verification_message = (
                'Вы зарегистрировали этот образец. '
                'Проверку должен выполнить другой сотрудник.'
            )

    if sample.verified_by:
        verification_info = {
            'verified_by': sample.verified_by.full_name,
            'verified_at': sample.verified_at,
            'registered_by': sample.registered_by.full_name,
        }

    return can_verify, verification_message, verification_info


def _get_protocol_verification_context(request, sample):
    """Формирует контекст для блока проверки протокола."""
    can_verify_protocol = False
    message = ''
    info = None

    if sample.status in ('DRAFT_READY', 'RESULTS_UPLOADED'):
        can_check = False

        if request.user.role in ('QMS_HEAD', 'QMS_ADMIN', 'SYSADMIN'):
            can_check = True
        elif (request.user.role == 'LAB_HEAD'
              and request.user.has_laboratory(sample.laboratory)):
            can_check = True

        if can_check:
            can_verify_protocol = True
            if sample.status == 'DRAFT_READY':
                message = (
                    f'Черновик протокола готов. Проверьте и подтвердите '
                    f'выпуск протокола {sample.pi_number}.'
                )
            else:
                message = (
                    'Результаты испытаний выложены. '
                    'Проверьте и подтвердите завершение работы.'
                )
        else:
            if sample.status == 'DRAFT_READY':
                message = 'Черновик протокола ожидает проверки.'
            else:
                message = 'Результаты ожидают проверки.'

    if sample.protocol_checked_by:
        info = {
            'checked_by': sample.protocol_checked_by.full_name,
            'checked_at': sample.protocol_checked_at,
            'issued_date': sample.protocol_issued_date,
            'pi_number': sample.pi_number,
        }

    return can_verify_protocol, message, info


# ─────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────

@login_required
def sample_create(request):
    """Создание нового образца."""

    allowed_roles = ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'SYSADMIN')
    if request.user.role not in allowed_roles:
        messages.error(request, 'У вас нет прав на создание образцов')
        return redirect('journal_samples')

    if request.method == 'POST':
        # ═══ Шаг 1: Парсинг и валидация (ДО транзакции — не тратим ID) ═══
        try:
            data = {}
            data['laboratory_id'] = request.POST.get('laboratory')
            data['client_id'] = request.POST.get('client')
            data['accompanying_doc_number'] = request.POST.get('accompanying_doc_number', '')
            data['accompanying_doc_full_name'] = request.POST.get('accompanying_doc_full_name', '')
            data['accreditation_area_id'] = request.POST.get('accreditation_area')
            # ⭐ v3.86.0: принимаем ЛИБО deadline, ЛИБО working_days — что не
            # прислали, добираем через Sample.calculate_* (с учётом ACT/ChA).
            deadline_str = (request.POST.get('deadline') or '').strip()
            working_days_str = (request.POST.get('working_days') or '').strip()

            deadline_value = None
            working_days_value = None

            if deadline_str:
                try:
                    deadline_value = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                except ValueError:
                    messages.error(request, 'Неверный формат срока выполнения')
                    return redirect('sample_create')

            if working_days_str:
                try:
                    working_days_value = int(working_days_str)
                except ValueError:
                    messages.error(request, 'Неверный формат количества рабочих дней')
                    return redirect('sample_create')
                if working_days_value < 1:
                    messages.error(request, 'Количество рабочих дней должно быть не меньше 1')
                    return redirect('sample_create')

            if deadline_value is None and working_days_value is None:
                messages.error(request, 'Укажите срок выполнения или количество рабочих дней')
                return redirect('sample_create')

            data['deadline'] = deadline_value
            data['working_days'] = working_days_value
            # (фактический расчёт недостающего поля — ниже, после того как
            #  станут известны sample_received_date и laboratory_id)
            data['determined_parameters'] = request.POST.get('determined_parameters', '')
            data['preparation'] = request.POST.get('preparation', '')
            data['notes'] = request.POST.get('notes', '')
            data['workshop_notes'] = request.POST.get('workshop_notes', '')
            data['admin_notes'] = request.POST.get('admin_notes', '')
            data['storage_location'] = request.POST.get('storage_location', '')  # ⭐ v3.54.0
            data['storage_conditions'] = request.POST.get('storage_conditions', '')  # ⭐ v3.54.0
            data['sample_count'] = int(request.POST.get('sample_count', 1))
            data['additional_sample_count'] = int(request.POST.get('additional_sample_count', 0))

            # v3.38.0: Договор / Счёт
            data['contract_id'] = None
            data['contract_date'] = None
            data['invoice_id'] = None
            bind_value = request.POST.get('contract', '')
            if bind_value.startswith('contract_'):
                contract_id = bind_value.replace('contract_', '')
                if contract_id:
                    data['contract_id'] = int(contract_id)
                    contract = Contract.objects.get(id=contract_id)
                    data['contract_date'] = contract.date
            elif bind_value.startswith('invoice_'):
                invoice_id = bind_value.replace('invoice_', '')
                if invoice_id:
                    data['invoice_id'] = int(invoice_id)
            elif bind_value:
                data['contract_id'] = int(bind_value)
                contract = Contract.objects.get(id=bind_value)
                data['contract_date'] = contract.date

            # ⭐ v3.19.0: Акт приёма-передачи
            acceptance_act_id = request.POST.get('acceptance_act')
            data['acceptance_act_id'] = int(acceptance_act_id) if acceptance_act_id else None

            sample_received_date_str = request.POST.get('sample_received_date')
            if sample_received_date_str:
                data['sample_received_date'] = datetime.strptime(
                    sample_received_date_str, '%Y-%m-%d'
                ).date()
            else:
                data['sample_received_date'] = timezone.now().date()

            # ⭐ v3.86.0: доделываем пару deadline ↔ working_days.
            # Любое из полей могло быть не заполнено — добираем через модель.
            if data['deadline'] is None or data['working_days'] is None:
                stub = Sample(sample_received_date=data['sample_received_date'])
                if data.get('laboratory_id'):
                    try:
                        stub.laboratory = Laboratory.objects.only('id', 'code').get(
                            id=data['laboratory_id']
                        )
                    except Laboratory.DoesNotExist:
                        pass

                if data['deadline'] is None:
                    stub.working_days = data['working_days']
                    calculated_deadline = stub.calculate_deadline()
                    if calculated_deadline is None:
                        messages.error(request, 'Не удалось рассчитать срок выполнения')
                        return redirect('sample_create')
                    data['deadline'] = calculated_deadline
                else:
                    stub.deadline = data['deadline']
                    calculated_wd = stub.calculate_working_days()
                    if calculated_wd is None:
                        messages.error(
                            request,
                            'Не удалось рассчитать количество рабочих дней '
                            '(проверьте, что срок позже даты поступления)'
                        )
                        return redirect('sample_create')
                    data['working_days'] = calculated_wd

            # ⭐ Серверная валидация: deadline должен быть позже даты поступления
            if data['deadline'] <= data['sample_received_date']:
                messages.error(request, 'Срок выполнения должен быть позже даты поступления образца')
                return redirect('sample_create')

            data['registration_date'] = timezone.now().date()
            data['object_info'] = request.POST.get('object_info', '')

            # Валидация латиницы — ДО транзакции
            object_id_value = request.POST.get('object_id', '')
            is_valid, error_msg = _validate_latin_only('object_id', object_id_value)
            if not is_valid:
                messages.error(request, f'ID объекта испытаний: {error_msg}')
                return redirect('sample_create')
            data['object_id'] = object_id_value

            data['cutting_direction'] = request.POST.get('cutting_direction', '')
            data['test_conditions'] = request.POST.get('test_conditions', '')
            data['material'] = request.POST.get('material', '')
            data['manufacturing'] = request.POST.get('manufacturing') == 'on'
            data['uzk_required'] = request.POST.get('uzk_required') == 'on'
            data['cut_maximum'] = request.POST.get('cut_maximum') == 'on'  # ⭐ v3.64.0

            # ⭐ v3.15.0: Стандарт на нарезку
            cutting_standard_id = request.POST.get('cutting_standard')
            data['cutting_standard_id'] = int(cutting_standard_id) if cutting_standard_id else None

            # ⭐ v3.15.0: Влагонасыщение
            data['moisture_conditioning'] = request.POST.get('moisture_conditioning') == 'on'
            moisture_sample_id = request.POST.get('moisture_sample_id')
            if data['moisture_conditioning'] and moisture_sample_id:
                data['moisture_sample_id'] = int(moisture_sample_id)
            else:
                data['moisture_sample_id'] = None

            # ⭐ v3.64.0: УЗК — привязка к образцу МИ
            uzk_sample_id = request.POST.get('uzk_sample_id')
            if data['uzk_required'] and uzk_sample_id:
                data['uzk_sample_id'] = int(uzk_sample_id)
            else:
                data['uzk_sample_id'] = None

            data['replacement_protocol_required'] = (
                request.POST.get('replacement_protocol_required') == 'on'
            )
            data['workshop_status'] = (
                WorkshopStatus.IN_WORKSHOP if data['manufacturing'] else None
            )

            # ⭐ v3.32.0: report_type
            report_types = request.POST.getlist('report_type')
            data['report_type'] = ','.join(report_types) if report_types else 'PROTOCOL'
            data['existing_pi'] = request.POST.get('existing_pi_number', '').strip()
            report_set = set(data['report_type'].split(','))
            data['_use_existing_pi_number'] = None

            # ⭐ Если протокол не выбран — pi_number = '-', генерация не нужна
            if 'PROTOCOL' not in report_set:
                data['_force_pi_number'] = '-'
            elif data['existing_pi'] and (report_set - {'WITHOUT_REPORT'}):
                if Sample.objects.filter(pi_number=data['existing_pi']).exists():
                    data['_use_existing_pi_number'] = data['existing_pi']
                else:
                    messages.warning(
                        request,
                        f'Указанный номер протокола «{data["existing_pi"]}» не найден. '
                        f'Будет сгенерирован новый номер.'
                    )

            manufacturing_deadline_str = request.POST.get('manufacturing_deadline')
            data['manufacturing_deadline'] = (
                datetime.strptime(manufacturing_deadline_str, '%Y-%m-%d').date()
                if manufacturing_deadline_str else None
            )
            data['further_movement'] = request.POST.get('further_movement', '')

            status_choice = request.POST.get('status', 'PENDING_VERIFICATION')
            data['status'] = (
                'CANCELLED' if status_choice == 'CANCELLED'
                else 'PENDING_VERIFICATION'
            )

            data['standard_ids'] = [
                int(sid) for sid in request.POST.getlist('standards') if sid
            ]
            # ═══ ГОСТ Р 56762: парсинг параметров из модалки ═══
            has_gost_r_56762 = False
            gost_form = None

            if data['standard_ids']:
                gost_standard = Standard.objects.filter(
                    id__in=data['standard_ids'],
                    code=GOST_R_56762_CODE,
                ).first()

                if gost_standard:
                    has_gost_r_56762 = True
                    gost_form = GostR56762ParamsForm(
                        request.POST,
                        prefix='gost56762',
                    )
                    if not gost_form.is_valid():
                        for field, errors in gost_form.errors.items():
                            for error in errors:
                                field_label = gost_form.fields[field].label or field
                                messages.error(
                                    request,
                                    f'ГОСТ Р 56762 — {field_label}: {error}'
                                )
                        return redirect('sample_create')

                    # Перезаписываем test_conditions сгенерированным значением
                    try:
                        data['test_conditions'] = gost_form.build_test_conditions()
                    except Exception as e:
                        messages.error(request, f'Ошибка генерации условий испытания: {e}')
                        return redirect('sample_create')
            # ⭐ v3.43.0: Показатели (из пула стандартов)
            data['sp_ids'] = [
                int(pid) for pid in request.POST.getlist('param_sp_ids') if pid
            ]

        except Exception as e:
            logger.exception('Ошибка при разборе данных формы')
            messages.error(request, f'Ошибка при создании образца: {e}')
            return redirect('sample_create')

        # ═══ Шаг 2: Сохранение в транзакции (ID тратится только здесь) ═══
        try:
            with transaction.atomic():
                sample = Sample()
                sample.laboratory_id = data['laboratory_id']
                sample.client_id = data['client_id']
                sample.accompanying_doc_number = data['accompanying_doc_number']
                sample.accompanying_doc_full_name = data['accompanying_doc_full_name']
                sample.accreditation_area_id = data['accreditation_area_id']
                sample.deadline = data['deadline']
                sample.working_days = data['working_days']  # ⭐ v3.86.0
                sample.determined_parameters = data['determined_parameters']
                sample.preparation = data['preparation']
                sample.notes = data['notes']
                sample.workshop_notes = data['workshop_notes']
                sample.admin_notes = data['admin_notes']
                sample.storage_location = data['storage_location']  # ⭐ v3.54.0
                sample.storage_conditions = data['storage_conditions']  # ⭐ v3.54.0
                sample.sample_count = data['sample_count']
                sample.additional_sample_count = data['additional_sample_count']
                sample.registered_by = request.user
                sample.contract_id = data['contract_id']
                sample.contract_date = data['contract_date']
                sample.invoice_id = data['invoice_id']
                sample.acceptance_act_id = data['acceptance_act_id']
                sample.sample_received_date = data['sample_received_date']
                sample.registration_date = data['registration_date']
                sample.object_info = data['object_info']
                sample.object_id = data['object_id']
                sample.cutting_direction = data['cutting_direction']
                sample.test_conditions = data['test_conditions']
                sample.material = data['material']
                sample.manufacturing = data['manufacturing']
                sample.uzk_required = data['uzk_required']
                sample.cut_maximum = data['cut_maximum']  # ⭐ v3.64.0
                sample.uzk_sample_id = data['uzk_sample_id']  # ⭐ v3.64.0
                sample.cutting_standard_id = data['cutting_standard_id']
                sample.moisture_conditioning = data['moisture_conditioning']
                sample.moisture_sample_id = data['moisture_sample_id']
                sample.replacement_protocol_required = data['replacement_protocol_required']
                sample.workshop_status = data['workshop_status']
                sample.report_type = data['report_type']
                sample.manufacturing_deadline = data['manufacturing_deadline']
                sample.further_movement = data['further_movement']
                sample.status = data['status']

                if data.get('_force_pi_number'):
                    sample.pi_number = data['_force_pi_number']
                elif data['_use_existing_pi_number']:
                    sample._use_existing_pi_number = data['_use_existing_pi_number']

                sample.save()

                # ⭐ v3.13.0: Добавляем стандарты (M2M — после save)
                for std_id in data['standard_ids']:
                    SampleStandard.objects.create(
                        sample=sample, standard_id=std_id
                    )
                    # ═══ ГОСТ Р 56762: сохранение параметров ═══
                if has_gost_r_56762 and gost_form is not None:
                    gost_form.save(sample=sample)

                # ⭐ v3.43.0: Сохраняем показатели образца
                param_order = 0
                for sp_id in data['sp_ids']:
                    try:
                        sp = StandardParameter.objects.get(id=sp_id, is_active=True)
                        SampleParameter.objects.create(
                            sample=sample,
                            standard_parameter=sp,
                            is_selected=True,
                            display_order=param_order,
                        )
                        param_order += 1
                    except StandardParameter.DoesNotExist:
                        pass

                # Копируем test_code/test_type из первого стандарта
                if data['standard_ids']:
                    first_std = Standard.objects.filter(id=data['standard_ids'][0]).first()
                    if first_std:
                        sample.test_code = first_std.test_code
                        sample.test_type = first_std.test_type
                        sample.cipher = sample.generate_cipher()
                        # ⭐ v3.32.0: report_type
                        rt_set = set(sample.report_type.split(',')) if sample.report_type else set()
                        if ('PROTOCOL' in rt_set
                                and not getattr(sample, '_use_existing_pi_number', None)
                                and sample.pi_number != '-'):
                            sample.pi_number = sample.generate_pi_number()
                        sample.save()

                log_action(request, 'sample', sample.id, 'sample_created', extra_data={
                    'cipher': sample.cipher,
                })

                # ⭐ v3.39.0: Задачи MANUFACTURING и TESTING создаются при верификации
                # (verification_views.py), а не при создании образца

                # ⭐ v3.39.0: Задача VERIFY_REGISTRATION — другим регистраторам
                if sample.status == 'PENDING_VERIFICATION':
                    try:
                        from core.views.task_views import create_auto_task
                        registrar_ids = list(
                            User.objects.filter(
                                role__in=('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'),
                                is_active=True,
                            ).exclude(id=request.user.id)
                            .values_list('id', flat=True)
                        )
                        if registrar_ids:
                            create_auto_task(
                                'VERIFY_REGISTRATION', sample, registrar_ids,
                                created_by=None,
                            )
                    except Exception:
                        logger.exception('Ошибка создания задачи VERIFY_REGISTRATION')

                if sample.status == 'PENDING_VERIFICATION':
                    messages.success(
                        request,
                        f'Образец {sample.cipher} создан (№ {sample.sequence_number}). '
                        f'Ожидает проверки.'
                    )
                else:
                    messages.warning(
                        request,
                        f'Образец {sample.cipher} создан со статусом "Отменено"'
                    )

                # «Создать + такой же»
                is_repeat = request.POST.get('action') == 'create_and_repeat'
                if is_repeat:
                    selected_groups = request.POST.getlist('repeat_groups')
                    if selected_groups:
                        prefs = request.user.ui_preferences or {}
                        prefs['repeat_sample_groups'] = selected_groups
                        request.user.ui_preferences = prefs
                        request.user.save(update_fields=['ui_preferences'])

                    all_sample_data = {
                        'laboratory': sample.laboratory_id,
                        'client': sample.client_id,
                        # v3.38.0: сохраняем с префиксом для повторного создания
                        'contract': (f'contract_{sample.contract_id}' if sample.contract_id
                                     else (f'invoice_{sample.invoice_id}' if getattr(sample, 'invoice_id', None)
                                           else '')),
                        'deadline': sample.deadline.strftime('%Y-%m-%d') if sample.deadline else '',
                        'accompanying_doc_number': sample.accompanying_doc_number or '',
                        'acceptance_act': sample.acceptance_act_id or '',
                        'accreditation_area': sample.accreditation_area_id,
                        'standards': list(SampleStandard.objects.filter(sample=sample).values_list('standard_id', flat=True)),
                        'report_type': sample.report_type or 'PROTOCOL',
                        'determined_parameters': sample.determined_parameters or '',
                        'sample_count': sample.sample_count,
                        'additional_sample_count': sample.additional_sample_count,
                        'object_id': sample.object_id or '',
                        'cutting_direction': sample.cutting_direction or '',
                        'test_conditions': sample.test_conditions or '',
                        'material': sample.material or '',
                        'preparation': sample.preparation or '',
                        'notes': sample.notes or '',
                        'object_info': sample.object_info or '',
                        'workshop_notes': sample.workshop_notes or '',
                        'admin_notes': sample.admin_notes or '',
                        'storage_location': sample.storage_location or '',  # ⭐ v3.54.0
                        'storage_conditions': sample.storage_conditions or '',  # ⭐ v3.54.0
                        'manufacturing': sample.manufacturing,
                        'moisture_conditioning': sample.moisture_conditioning,  # ⭐ v3.15.0
                        'further_movement': sample.further_movement or '',
                    }

                    repeat_data = {}
                    for group_code in selected_groups:
                        group = REPEAT_FIELD_GROUPS.get(group_code)
                        if group:
                            for field in group['fields']:
                                if field in all_sample_data:
                                    repeat_data[field] = all_sample_data[field]

                    warn_fields = []
                    for group_code in selected_groups:
                        group = REPEAT_FIELD_GROUPS.get(group_code)
                        if group and group.get('warn'):
                            warn_fields.extend(group['fields'])
                    if warn_fields:
                        repeat_data['_warn_fields'] = warn_fields

                    request.session['last_sample_data'] = repeat_data
                    return redirect('sample_create')
                else:
                    if 'last_sample_data' in request.session:
                        del request.session['last_sample_data']
                    return redirect('sample_detail', sample_id=sample.id)

        except Exception as e:
            logger.exception('Ошибка при создании образца')
            messages.error(request, f'Ошибка при создании образца: {e}')
            return redirect('sample_create')

    # ─── GET: показываем форму ───
    laboratories = Laboratory.objects.filter(is_active=True, department_type='LAB').order_by('name')
    clients = Client.objects.filter(is_active=True).order_by('name')
    accreditation_areas = AccreditationArea.objects.filter(is_active=True).order_by('name')
    standards = Standard.objects.filter(is_active=True).order_by('code')

    last_data = request.session.pop('last_sample_data', {})

    # ⭐ v3.51.0: «Создать такой же» из карточки образца (?from=ID)
    copy_from_id = request.GET.get('from')
    if copy_from_id and not last_data:
        try:
            src = Sample.objects.select_related('laboratory', 'client').get(id=int(copy_from_id))
            last_data = {
                'laboratory': src.laboratory_id,
                'client': src.client_id,
                'contract': (f'contract_{src.contract_id}' if src.contract_id
                             else (f'invoice_{src.invoice_id}' if getattr(src, 'invoice_id', None)
                                   else '')),
                'deadline': src.deadline.strftime('%Y-%m-%d') if src.deadline else '',
                'accompanying_doc_number': src.accompanying_doc_number or '',
                'acceptance_act': src.acceptance_act_id or '',
                'accreditation_area': src.accreditation_area_id,
                'standards': list(SampleStandard.objects.filter(sample=src).values_list('standard_id', flat=True)),
                'report_type': src.report_type or 'PROTOCOL',
                'determined_parameters': src.determined_parameters or '',
                'sample_count': src.sample_count,
                'additional_sample_count': src.additional_sample_count,
                'object_id': src.object_id or '',
                'cutting_direction': src.cutting_direction or '',
                'test_conditions': src.test_conditions or '',
                'material': src.material or '',
                'preparation': src.preparation or '',
                'notes': src.notes or '',
                'object_info': src.object_info or '',
                'workshop_notes': src.workshop_notes or '',
                'admin_notes': src.admin_notes or '',
                'storage_location': src.storage_location or '',  # ⭐ v3.54.0
                'storage_conditions': src.storage_conditions or '',  # ⭐ v3.54.0
                'manufacturing': src.manufacturing,
                'moisture_conditioning': src.moisture_conditioning,
                'further_movement': src.further_movement or '',
            }
            # Подсветка полей объекта как предупреждение
            last_data['_warn_fields'] = ['object_id', 'cutting_direction', 'test_conditions',
                                         'material', 'preparation', 'notes', 'object_info']
        except (Sample.DoesNotExist, ValueError):
            pass

    for key in ('laboratory', 'client', 'contract', 'accreditation_area'):
        if key in last_data and last_data[key]:
            try:
                last_data[key] = int(last_data[key])
            except (ValueError, TypeError):
                pass
        if 'standards' in last_data and last_data['standards']:
            try:
                last_data['standards'] = [int(x) for x in last_data['standards']]
            except (ValueError, TypeError):
                pass

    contracts = []
    if last_data.get('client'):
        contracts = Contract.objects.filter(
            client_id=last_data['client'], status='ACTIVE'
        ).order_by('-date')

    prefs = request.user.ui_preferences or {}
    saved_repeat_groups = prefs.get('repeat_sample_groups', ['basic', 'doc', 'testing'])

    return render(request, 'core/sample_create.html', {
        'laboratories': laboratories,
        'clients': clients,
        'accreditation_areas': accreditation_areas,
        'standards': standards,
        'contracts': contracts,
        'last_data': last_data,
        'warn_fields': last_data.get('_warn_fields', []),
        'user': request.user,
        'current_user_fullname': request.user.full_name,
        'repeat_field_groups': REPEAT_FIELD_GROUPS,
        'saved_repeat_groups': saved_repeat_groups,
        'gost_form': GostR56762ParamsForm(prefix='gost56762'),
        'GOST_R_56762_CODE': GOST_R_56762_CODE,
    })


def _preprocess_deadline_pair(request, sample):
    """
    ⭐ v3.86.0: нормализация пары «deadline ↔ working_days» в request.POST
    и in-memory sample ПЕРЕД save_sample_fields / handle_sample_save.

    - Если пришло только одно — добираем второе через Sample.calculate_*.
    - Если оба — доверяем как есть (пользователь видел расчёт в UI).
    - Если ничего не пришло — не трогаем.

    Мутирует:
      - request.POST (mutable copy) — чтобы save_sample_fields провёл
        deadline через свой аудит.
      - sample.working_days в памяти — чтобы любой sample.save() внутри
        цепочки сохранил актуальное значение (save_sample_fields и
        handle_sample_save могут не знать про это поле явно).
    """
    post = request.POST
    wd_str = (post.get('working_days') or '').strip()
    dl_str = (post.get('deadline') or '').strip()

    if not wd_str and not dl_str:
        return
    if not sample.sample_received_date:
        return

    wd = None
    dl = None
    try:
        if wd_str:
            wd = int(wd_str)
            if wd < 1:
                return
    except ValueError:
        return
    try:
        if dl_str:
            dl = datetime.strptime(dl_str, '%Y-%m-%d').date()
    except ValueError:
        return

    if wd is not None and dl is None:
        stub = Sample(
            sample_received_date=sample.sample_received_date,
            laboratory=sample.laboratory,
            working_days=wd,
        )
        dl = stub.calculate_deadline()
    elif dl is not None and wd is None:
        stub = Sample(
            sample_received_date=sample.sample_received_date,
            laboratory=sample.laboratory,
            deadline=dl,
        )
        wd = stub.calculate_working_days()

    # Mutable copy request.POST — чтобы save_sample_fields увидел deadline.
    new_post = request.POST.copy()
    if dl is not None:
        new_post['deadline'] = dl.strftime('%Y-%m-%d')
    if wd is not None:
        new_post['working_days'] = str(wd)
    request.POST = new_post

    # Страховка: кладём working_days прямо в sample.
    # Следующий же sample.save() внутри цепочки сохранит значение.
    if wd is not None:
        sample.working_days = wd


@login_required
def sample_detail(request, sample_id):
    """Просмотр и редактирование образца."""

    sample = get_object_or_404(
        Sample.objects.select_related(
            'laboratory', 'client', 'contract', 'invoice',  # ⭐ v3.38.0: invoice
            'accreditation_area', 'registered_by',
            # ⭐ v3.84.0: report_prepared_by (FK) удалён, заменён M2M report_preparers
            # (prefetch_related ниже).
            'protocol_checked_by', 'verified_by',
            'moisture_sample', 'cutting_standard',  # ⭐ v3.15.0
            'uzk_sample',  # ⭐ v3.64.0
        ).prefetch_related(
            'measuring_instruments', 'testing_equipment', 'operators',
            'report_preparers',  # ⭐ v3.84.0
            'standards',
        ),
        id=sample_id
    )

    if not PermissionChecker.has_journal_access(request.user, 'SAMPLES'):
        messages.error(request, 'У вас нет доступа к журналу образцов')
        return redirect('workspace_home')

    access_error = _check_sample_access(request.user, sample)
    if access_error:
        messages.error(request, access_error)
        return redirect('journal_samples')

    # --- POST ---
    if request.method == 'POST':
        action = request.POST.get('action')

        if action in STATUS_CHANGE_ACTIONS:
            try:
                with transaction.atomic():
                    _preprocess_deadline_pair(request, sample)
                    updated_fields = save_sample_fields(request, sample)
                    if updated_fields:
                        messages.info(
                            request,
                            f'Сохранены изменения: {", ".join(updated_fields)}'
                        )
            except Exception as e:
                logger.exception('Ошибка при сохранении полей перед сменой статуса')
                messages.error(request, f'Ошибка при сохранении полей: {e}')
                return redirect('sample_detail', sample_id=sample.id)

        if action == 'save':
            # ⭐ v3.86.0: нормализуем пару deadline ↔ working_days до save
            _preprocess_deadline_pair(request, sample)
            # ⭐ v3.85.0 (1г): если клиент прислал issue_replacement=1,
            # идём через wrapper, который после сохранения полей вызовет
            # sample.initiate_replacement_protocol. Safety: роль проверяется
            # здесь (дублирует preflight в api_validate_sample_fk_change).
            if request.POST.get('issue_replacement') == '1':
                user_role = getattr(request.user, 'role', '') or ''
                if user_role in CASCADE_REPLACEMENT_ROLES:
                    return _handle_sample_save_with_replacement(request, sample)
                # Нет прав — предупреждаем и сохраняем без выпуска ЗАМа
                messages.warning(
                    request,
                    'У вас нет прав на выпуск замещающего протокола. '
                    'Сохранение выполнено без выпуска ЗАМа.'
                )
            return handle_sample_save(request, sample)
        elif action in STATUS_CHANGE_ACTIONS:
            return _handle_status_change(request, sample, action)

    # --- GET: формирование контекста ---
    fields_data = _build_fields_data(request, sample)

    can_edit_any = any(
        field['is_editable']
        for group in fields_data.values()
        for field in group
    )

    can_change_status = PermissionChecker.can_edit(request.user, 'SAMPLES', 'status')
    status_actions = _get_status_actions(request.user, sample)

    can_verify, verification_message, verification_info = (
        _get_verification_context(request, sample)
    )

    can_verify_protocol, protocol_verification_message, protocol_verification_info = (
        _get_protocol_verification_context(request, sample)
    )

    sample_files = sample.files.all().order_by('-uploaded_at')
    can_upload_files = PermissionChecker.can_edit(request.user, 'SAMPLES', 'files_path')
    can_delete_files = request.user.role in (
        'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
        'LAB_HEAD', 'QMS_HEAD', 'QMS_ADMIN',
        'SYSADMIN',
        'WORKSHOP_HEAD', 'WORKSHOP',
    )

    freezing_actions = []
    for act in status_actions:
        if act['action'] in ('draft_ready', 'results_uploaded'):
            freezing_actions.append(act['action'])
        elif act['action'] == 'complete_manufacturing':
            freezing_actions.append(act['action'])

    is_workshop_head_view = (
        request.user.role in WORKSHOP_ROLES
        and not request.user.has_laboratory(sample.laboratory)
    )

    # ⭐ v3.51.0: Заморозка регистрации убрана — поля всегда редактируемы
    # по правам ролей (все изменения логгируются)
    registration_is_frozen = False
    registration_unfrozen = False
    can_unfreeze_registration = False

    # ⭐ v3.14.0: Доступ к журналу аудита
    can_view_audit = request.user.role in (
        'SYSADMIN', 'QMS_HEAD', 'QMS_ADMIN', 'CTO', 'CEO',
        'CLIENT_DEPT_HEAD', 'LAB_HEAD', 'WORKSHOP_HEAD',
    )

    # ⭐ v3.15.0: Контекст влагонасыщения
    moisture_sample = None
    moisture_sample_ready = False
    can_view_moisture_sample = False
    if sample.moisture_sample_id:
        moisture_sample = sample.moisture_sample  # уже в select_related

        # Автопереход: если Образец A достиг TESTED+ — перевести Образец B
        # из MOISTURE_CONDITIONING в MOISTURE_READY
        MOISTURE_DONE_STATUSES = frozenset([
            'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
            'PROTOCOL_ISSUED', 'COMPLETED',
        ])
        if (sample.status == 'MOISTURE_CONDITIONING'
                and moisture_sample.status in MOISTURE_DONE_STATUSES):
            sample.status = 'MOISTURE_READY'
            sample.save(update_fields=['status', 'updated_at'])
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status',
                       old_value='MOISTURE_CONDITIONING',
                       new_value='MOISTURE_READY')

        moisture_sample_ready = (
            sample.status == 'MOISTURE_READY'
            or moisture_sample.status in MOISTURE_DONE_STATUSES
        )
        # Проверяем, есть ли у пользователя доступ к образцу УКИ
        if request.user.role in ('WORKSHOP', 'WORKSHOP_HEAD'):
            can_view_moisture_sample = False
        else:
            can_view_moisture_sample = (_check_sample_access(request.user, moisture_sample) is None)

    # Обратная связь: образцы, привязанные к данному (если это Образец A)
    dependent_moisture_samples = Sample.objects.filter(
        moisture_sample_id=sample.id
    ).select_related('laboratory').only(
        'id', 'cipher', 'sequence_number', 'status', 'laboratory'
    )

    # Проверяем доступ к каждому зависимому образцу
    for dep in dependent_moisture_samples:
        # Мастерская не должна видеть ссылки на образцы других лабораторий
        if request.user.role in ('WORKSHOP', 'WORKSHOP_HEAD'):
            dep.is_accessible = False
        else:
            dep.is_accessible = (_check_sample_access(request.user, dep) is None)

    _mfg_perm = PermissionChecker.get_user_permission(request.user, 'SAMPLES', 'manufacturing')
    _mfg_frozen, _ = _is_field_frozen('manufacturing', request.user, sample, request=request)
    can_edit_manufacturing = (_mfg_perm == 'EDIT' and not _mfg_frozen)

    _mc_perm = PermissionChecker.get_user_permission(request.user, 'SAMPLES', 'moisture_conditioning')
    _mc_frozen, _ = _is_field_frozen('moisture_conditioning', request.user, sample, request=request)
    can_edit_moisture = (_mc_perm == 'EDIT' and not _mc_frozen)

    show_manufacturing_block = _mfg_perm in ('VIEW', 'EDIT')
    show_moisture_block = _mc_perm in ('VIEW', 'EDIT')

    # ⭐ v3.64.0: Контекст УЗК
    uzk_sample = None
    uzk_sample_ready = False
    can_view_uzk_sample = False
    if sample.uzk_sample_id:
        uzk_sample = sample.uzk_sample  # уже в select_related

        UZK_DONE_STATUSES = frozenset([
            'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
            'PROTOCOL_ISSUED', 'COMPLETED',
        ])
        if (sample.status == 'UZK_TESTING'
                and uzk_sample.status in UZK_DONE_STATUSES):
            sample.status = 'UZK_READY'
            sample.save(update_fields=['status', 'updated_at'])
            log_action(request, 'sample', sample.id, 'sample_status_change',
                       field_name='status',
                       old_value='UZK_TESTING',
                       new_value='UZK_READY')

        uzk_sample_ready = (
            sample.status == 'UZK_READY'
            or uzk_sample.status in UZK_DONE_STATUSES
        )
        if request.user.role in ('WORKSHOP', 'WORKSHOP_HEAD'):
            can_view_uzk_sample = False
        else:
            can_view_uzk_sample = (_check_sample_access(request.user, uzk_sample) is None)

    # Обратная связь: образцы, привязанные к данному УЗК-образцу
    dependent_uzk_samples = Sample.objects.filter(
        uzk_sample_id=sample.id
    ).select_related('laboratory').only(
        'id', 'cipher', 'sequence_number', 'status', 'laboratory'
    )
    for dep in dependent_uzk_samples:
        if request.user.role in ('WORKSHOP', 'WORKSHOP_HEAD'):
            dep.is_accessible = False
        else:
            dep.is_accessible = (_check_sample_access(request.user, dep) is None)

    # Permissions для УЗК-блока
    _uzk_perm = PermissionChecker.get_user_permission(request.user, 'SAMPLES', 'uzk_required')
    _uzk_frozen, _ = _is_field_frozen('uzk_required', request.user, sample, request=request)
    can_edit_uzk = (_uzk_perm == 'EDIT' and not _uzk_frozen)
    show_uzk_block = _uzk_perm in ('VIEW', 'EDIT')

    # ⭐ v3.64.0: Цепочка связанных образцов (для информационного блока)
    sample_chain = []
    _chain_fields = ('id', 'cipher', 'sequence_number', 'status', 'laboratory__name',
                     'uzk_sample_id', 'moisture_sample_id', 'uzk_required', 'moisture_conditioning')

    # Вверх по цепочке: от чего зависит этот образец
    if uzk_sample:
        sample_chain.append({
            'sample': uzk_sample, 'type': 'uzk', 'direction': 'up',
            'label': '🔍 УЗК (МИ)', 'accessible': can_view_uzk_sample,
        })
    if moisture_sample:
        sample_chain.append({
            'sample': moisture_sample, 'type': 'moisture', 'direction': 'up',
            'label': '💧 Влагонасыщение (УКИ)', 'accessible': can_view_moisture_sample,
        })
        # Глубже: у влагонасыщения есть УЗК?
        if getattr(moisture_sample, 'uzk_sample_id', None):
            try:
                _m_uzk = Sample.objects.select_related('laboratory').get(id=moisture_sample.uzk_sample_id)
                sample_chain.append({
                    'sample': _m_uzk, 'type': 'uzk', 'direction': 'up',
                    'label': '🔍 УЗК влагонасыщения',
                    'accessible': _check_sample_access(request.user, _m_uzk) is None,
                })
            except Sample.DoesNotExist:
                pass

    # Вниз по цепочке: кто зависит от этого образца
    for dep in dependent_uzk_samples:
        sample_chain.append({
            'sample': dep, 'type': 'uzk_dep', 'direction': 'down',
            'label': '→ Ожидает УЗК', 'accessible': dep.is_accessible,
        })
        # Глубже: у зависимого есть ещё зависимые (влагонасыщение → целевая лаба)?
        _deeper = Sample.objects.filter(
            moisture_sample_id=dep.id
        ).select_related('laboratory').only(*_chain_fields)[:5]
        for dd in _deeper:
            dd.is_accessible = _check_sample_access(request.user, dd) is None if request.user.role not in ('WORKSHOP', 'WORKSHOP_HEAD') else False
            sample_chain.append({
                'sample': dd, 'type': 'moisture_dep', 'direction': 'down',
                'label': '→→ Ожидает влагонасыщение', 'accessible': dd.is_accessible,
            })

    for dep in dependent_moisture_samples:
        sample_chain.append({
            'sample': dep, 'type': 'moisture_dep', 'direction': 'down',
            'label': '→ Ожидает влагонасыщение', 'accessible': dep.is_accessible,
        })

    has_chain = bool(sample_chain)

    # ⭐ v3.38.0: Счета заказчика для поля «Договор / Счёт»
    client_invoices = []
    sample_invoice = sample.invoice  # уже в select_related
    if Invoice and sample.client_id:
        client_invoices = list(Invoice.objects.filter(
            client_id=sample.client_id,
        ).order_by('-date'))

    # ⭐ v3.43.0: Показатели образца для отображения бейджами
    sample_params_qs = list(
        SampleParameter.objects.filter(sample=sample, is_selected=True)
        .select_related('standard_parameter__parameter')
        .order_by('display_order', 'id')
    )
    sample_params_data = []
    for _sp in sample_params_qs:
        sample_params_data.append({
            'id': _sp.id,
            'name': _sp.effective_name,
            'unit': _sp.effective_unit,
            'display_name': _sp.display_name,
            'role': _sp.effective_role,
        })

    return render(request, 'core/sample_detail.html', {
        'sample': sample,
        'fields_data': fields_data,
        'can_edit_any': can_edit_any,
        'can_change_status': can_change_status,
        'status_actions': status_actions,
        'freezing_actions': freezing_actions,
        'is_workshop_head_view': is_workshop_head_view,
        'can_unfreeze_registration': can_unfreeze_registration,
        'registration_unfrozen': registration_unfrozen,
        'sample_files': sample_files,
        'can_upload_files': can_upload_files,
        'can_delete_files': can_delete_files,
        'can_verify': can_verify,
        'verification_message': verification_message,
        'verification_info': verification_info,
        'can_verify_protocol': can_verify_protocol,
        'protocol_verification_message': protocol_verification_message,
        'protocol_verification_info': protocol_verification_info,
        'can_view_audit': can_view_audit,
        'moisture_sample': moisture_sample,
        'moisture_sample_ready': moisture_sample_ready,
        'can_view_moisture_sample': can_view_moisture_sample,
        'dependent_moisture_samples': dependent_moisture_samples,
        'can_edit_manufacturing': can_edit_manufacturing,  # ⭐ v3.20.0
        'can_edit_moisture': can_edit_moisture,  # ⭐ v3.20.0
        'show_manufacturing_block': show_manufacturing_block,  # ⭐ v3.20.0
        'show_moisture_block': show_moisture_block,  # ⭐ v3.20.0
        'uzk_sample': uzk_sample,  # ⭐ v3.64.0
        'uzk_sample_ready': uzk_sample_ready,  # ⭐ v3.64.0
        'can_view_uzk_sample': can_view_uzk_sample,  # ⭐ v3.64.0
        'dependent_uzk_samples': dependent_uzk_samples,  # ⭐ v3.64.0
        'can_edit_uzk': can_edit_uzk,  # ⭐ v3.64.0
        'show_uzk_block': show_uzk_block,  # ⭐ v3.64.0
        'sample_chain': sample_chain,  # ⭐ v3.64.0
        'has_chain': has_chain,  # ⭐ v3.64.0
        'client_invoices': client_invoices,  # ⭐ v3.38.0
        'sample_invoice': sample_invoice,  # ⭐ v3.38.0
        'sample_params': sample_params_data,  # ⭐ v3.43.0
    })

# ─────────────────────────────────────────────────────────────
# AJAX endpoints
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def unfreeze_registration_block(request, sample_id):
    """
    AJAX endpoint — разморозка блока регистрации.
    POST /workspace/samples/<id>/unfreeze-registration/
    """
    sample = get_object_or_404(Sample, id=sample_id)
    user = request.user

    access_error = _check_sample_access(user, sample)
    if access_error:
        return JsonResponse({'error': access_error}, status=403)

    if not _can_unfreeze_block(user, sample, 'registration'):
        return JsonResponse({'error': 'Нет прав на разморозку блока регистрации'}, status=403)

    if sample.status == 'PENDING_VERIFICATION':
        return JsonResponse({'error': 'Блок регистрации не заморожен'}, status=400)

    now = timezone.now()
    now_str = timezone.localtime(now).strftime('%d.%m.%Y %H:%M')
    unfreeze_note = (
        f"[{now_str}] 🔓 Разморозка блока регистрации — "
        f"{user.full_name} ({user.role})"
    )

    if sample.admin_notes:
        sample.admin_notes = f"{sample.admin_notes}\n{unfreeze_note}"
    else:
        sample.admin_notes = unfreeze_note

    sample.save(update_fields=['admin_notes', 'updated_at'])

    unfrozen_key = f'unfrozen_registration_{sample.id}'
    request.session[unfrozen_key] = True
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'message': 'Блок регистрации разморожен',
    })


@login_required
def search_protocols(request):
    """
    AJAX endpoint: поиск существующих номеров протоколов.
    GET: ?laboratory=ID&client=ID&q=search&limit=10
    """
    laboratory_id = request.GET.get('laboratory')
    if not laboratory_id:
        return JsonResponse({'protocols': []})

    qs = Sample.objects.filter(
        laboratory_id=laboratory_id,
        report_type__contains='PROTOCOL',  # ⭐ v3.32.0: report_type через запятую
    ).exclude(
        pi_number=''
    ).exclude(
        pi_number__isnull=True
    )

    client_id = request.GET.get('client')
    if client_id:
        qs = qs.filter(client_id=client_id)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(pi_number__icontains=q)

    limit = int(request.GET.get('limit', 10))
    protocols = (
        qs.values('pi_number')
        .annotate(
            last_date=models.Max('registration_date'),
            sample_count=models.Count('id'),
        )
        .order_by('-last_date')[:limit]
    )

    return JsonResponse({
        'protocols': [
            {
                'pi_number': p['pi_number'],
                'sample_count': p['sample_count'],
            }
            for p in protocols
        ]
    })

@login_required
def api_sample_schedule_calc(request):
    """
    ⭐ v3.86.0: AJAX — расчёт пары «deadline ↔ working_days» по коду лаборатории.

    GET-параметры:
        sample_received_date (YYYY-MM-DD, обязательно)
        laboratory_id        (ID лаборатории или пусто)
        mode                 'deadline' | 'working_days' — что вычислять
        working_days         int (если mode='deadline')
        deadline             YYYY-MM-DD (если mode='working_days')

    Ответ: {ok: true, working_days: N, deadline: 'YYYY-MM-DD'}
    В случае ошибки: {ok: false, error: '…'}
    """
    received_str = (request.GET.get('sample_received_date') or '').strip()
    laboratory_id = (request.GET.get('laboratory_id') or '').strip()
    mode = (request.GET.get('mode') or '').strip()

    if not received_str:
        return JsonResponse({'ok': False, 'error': 'sample_received_date required'})

    try:
        received_date = datetime.strptime(received_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'invalid sample_received_date'})

    # In-memory Sample — чтобы переиспользовать методы модели без записи в БД
    stub = Sample(sample_received_date=received_date)
    if laboratory_id:
        try:
            stub.laboratory = Laboratory.objects.only('id', 'code').get(id=int(laboratory_id))
        except (Laboratory.DoesNotExist, ValueError):
            pass

    if mode == 'deadline':
        wd_str = (request.GET.get('working_days') or '').strip()
        if not wd_str:
            return JsonResponse({'ok': False, 'error': 'working_days required'})
        try:
            wd = int(wd_str)
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'invalid working_days'})
        if wd < 1:
            return JsonResponse({'ok': False, 'error': 'working_days must be >= 1'})
        stub.working_days = wd
        deadline = stub.calculate_deadline()
        if deadline is None:
            return JsonResponse({'ok': False, 'error': 'calc failed'})
        return JsonResponse({
            'ok': True,
            'working_days': wd,
            'deadline': deadline.strftime('%Y-%m-%d'),
        })

    if mode == 'working_days':
        dl_str = (request.GET.get('deadline') or '').strip()
        if not dl_str:
            return JsonResponse({'ok': False, 'error': 'deadline required'})
        try:
            dl = datetime.strptime(dl_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'invalid deadline'})
        if dl <= received_date:
            return JsonResponse({'ok': False, 'error': 'deadline must be later than sample_received_date'})
        stub.deadline = dl
        wd = stub.calculate_working_days()
        if wd is None:
            return JsonResponse({'ok': False, 'error': 'calc failed'})
        return JsonResponse({
            'ok': True,
            'working_days': wd,
            'deadline': dl.strftime('%Y-%m-%d'),
        })

    return JsonResponse({'ok': False, 'error': "mode must be 'deadline' or 'working_days'"})


@login_required
def api_protocol_sample_data(request):
    """
    ⭐ v3.50.x: API — данные образца-источника для автозаполнения формы при выборе
    существующего протокола.

    GET: ?pi_number=PI-2024-001&laboratory=ID

    Возвращает поля образца с НАИМЕНЬШИМ id среди всех образцов с данным pi_number
    (и данной лабораторией, если передана).

    Возвращаемые поля:
        client_id, contract_value (contract_N / invoice_N), contract_date,
        acceptance_act_id, accompanying_doc_number,
        accreditation_area_id,
        standards: [{id, code, name}, ...],
        parameters: [{sp_id, parameter_id, name, unit, display_name, role, standard_id}, ...],
        object_id, cutting_direction, test_conditions, material,
        preparation, notes, object_info
    """
    pi_number = request.GET.get('pi_number', '').strip()
    laboratory_id = request.GET.get('laboratory', '').strip()

    if not pi_number:
        return JsonResponse({'error': 'pi_number required'}, status=400)

    qs = Sample.objects.filter(pi_number=pi_number)
    if laboratory_id:
        qs = qs.filter(laboratory_id=laboratory_id)

    sample = qs.order_by('id').first()
    if not sample:
        return JsonResponse({'error': 'not found'}, status=404)

    # ── Contract / Invoice ──────────────────────────────────────────
    contract_id = getattr(sample, 'contract_id', None)
    invoice_id = getattr(sample, 'invoice_id', None) if Invoice else None
    contract_value = ''
    contract_date = ''

    if contract_id:
        contract_value = f'contract_{contract_id}'
        try:
            contract_obj = Contract.objects.get(id=contract_id)
            contract_date = str(contract_obj.date) if getattr(contract_obj, 'date', None) else ''
        except Contract.DoesNotExist:
            pass
    elif invoice_id:
        contract_value = f'invoice_{invoice_id}'

    # ── Standards ───────────────────────────────────────────────────
    standards_qs = (
        SampleStandard.objects
        .filter(sample=sample)
        .select_related('standard')
        .order_by('id')
    )
    standards = [
        {'id': ss.standard_id, 'code': ss.standard.code, 'name': ss.standard.name}
        for ss in standards_qs
    ]

    # ── Parameters (SampleParameter → StandardParameter) ────────────
    params_qs = (
        SampleParameter.objects
        .filter(sample=sample)
        .select_related('standard_parameter__parameter', 'standard_parameter__standard')
        .order_by('id')
    )
    parameters = []
    for sp_record in params_qs:
        sp = getattr(sp_record, 'standard_parameter', None)
        if not sp:
            continue
        param = getattr(sp, 'parameter', None)
        if not param:
            continue
        parameters.append({
            'sp_id': sp.id,
            'parameter_id': sp.parameter_id,
            'name': param.name,
            'unit': sp.effective_unit if hasattr(sp, 'effective_unit') else getattr(param, 'unit', ''),
            'display_name': sp.display_name if hasattr(sp, 'display_name') else param.name,
            'role': sp.parameter_role if hasattr(sp, 'parameter_role') else '',
            'standard_id': sp.standard_id,
        })

    return JsonResponse({
        'client_id': sample.client_id,
        'contract_value': contract_value,
        'contract_date': contract_date,
        'acceptance_act_id': sample.acceptance_act_id,
        'accompanying_doc_number': sample.accompanying_doc_number or '',
        'accreditation_area_id': sample.accreditation_area_id,
        'standards': standards,
        'parameters': parameters,
        'object_id': sample.object_id or '',
        'cutting_direction': sample.cutting_direction or '',
        'test_conditions': sample.test_conditions or '',
        'material': sample.material or '',
        'preparation': sample.preparation or '',
        'notes': sample.notes or '',
        'object_info': sample.object_info or '',
    })
@login_required
def search_standards(request):
    """
    AJAX endpoint: стандарты, отфильтрованные по лаборатории и/или области.
    GET: ?laboratory=ID&accreditation_area=ID
    """
    qs = Standard.objects.filter(is_active=True)

    laboratory_id = request.GET.get('laboratory')
    accreditation_area_id = request.GET.get('accreditation_area')

    if laboratory_id:
        standard_ids = StandardLaboratory.objects.filter(
            laboratory_id=laboratory_id
        ).values_list('standard_id', flat=True)
        qs = qs.filter(id__in=standard_ids)

    if accreditation_area_id:
        standard_ids = StandardAccreditationArea.objects.filter(
            accreditation_area_id=accreditation_area_id
        ).values_list('standard_id', flat=True)
        qs = qs.filter(id__in=standard_ids)

    standards = qs.order_by('code').values('id', 'code', 'name', 'test_code', 'test_type')

    return JsonResponse({'standards': list(standards)})


@login_required
def api_standard_parameters(request):
    """
    ⭐ v3.43.0: API — показатели для выбранных стандартов.
    GET: ?standard_ids=1,2,3
    Возвращает показатели из standard_parameters (is_default=True, is_active=True).
    Дедупликация по parameter_id (если один показатель в нескольких стандартах).
    """
    standard_ids_str = request.GET.get('standard_ids', '')
    if not standard_ids_str:
        return JsonResponse({'parameters': []})

    try:
        standard_ids = [int(x) for x in standard_ids_str.split(',') if x.strip()]
    except (ValueError, TypeError):
        return JsonResponse({'parameters': []})

    if not standard_ids:
        return JsonResponse({'parameters': []})

    sp_qs = (
        StandardParameter.objects
        .filter(
            standard_id__in=standard_ids,
            is_active=True,
            is_default=True,
        )
        .select_related('parameter', 'standard')
        .order_by('display_order', 'parameter__name')
    )

    # Дедупликация: один parameter_id → один показатель
    seen_param_ids = set()
    params = []
    for sp in sp_qs:
        if sp.parameter_id in seen_param_ids:
            continue
        seen_param_ids.add(sp.parameter_id)
        params.append({
            'sp_id': sp.id,
            'parameter_id': sp.parameter_id,
            'name': sp.parameter.name,
            'unit': sp.effective_unit,
            'display_name': sp.display_name,
            'role': sp.parameter_role,
            'standard_id': sp.standard_id,
        })

    return JsonResponse({'parameters': params})


@login_required
def search_moisture_samples(request):
    """
    ⭐ v3.15.0: AJAX endpoint — поиск образцов УКИ для привязки влагонасыщения.
    GET: ?q=search_query&limit=10
    Возвращает образцы лаборатории ACT (УКИ), кроме отменённых.
    """
    q = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))

    # Находим лабораторию УКИ (code='ACT')
    act_lab = Laboratory.objects.filter(code='ACT').first()
    if not act_lab:
        return JsonResponse({'samples': []})

    qs = Sample.objects.filter(
        laboratory=act_lab,
    ).exclude(
        status='CANCELLED',
    ).select_related('laboratory')

    if q:
        qs = qs.filter(
            models.Q(cipher__icontains=q) |
            models.Q(sequence_number__icontains=q)
        )

    samples = qs.order_by('-registration_date', '-sequence_number')[:limit]

    return JsonResponse({
        'samples': [
            {
                'id': s.id,
                'cipher': s.cipher,
                'sequence_number': s.sequence_number,
                'status': s.get_status_display(),
                'status_code': s.status,
            }
            for s in samples
        ]
    })
@login_required
def search_uzk_samples(request):
    """
    ⭐ v3.64.0: AJAX endpoint — поиск образцов МИ для привязки УЗК.
    GET: ?q=search_query&limit=10
    Возвращает образцы лаборатории МИ (code='MI'), кроме отменённых.
    """
    q = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))

    mi_lab = Laboratory.objects.filter(code='MI').first()
    if not mi_lab:
        return JsonResponse({'samples': []})

    qs = Sample.objects.filter(
        laboratory=mi_lab,
    ).exclude(
        status='CANCELLED',
    ).select_related('laboratory')

    if q:
        qs = qs.filter(
            models.Q(cipher__icontains=q) |
            models.Q(sequence_number__icontains=q)
        )

    samples = qs.order_by('-registration_date', '-sequence_number')[:limit]

    return JsonResponse({
        'samples': [
            {
                'id': s.id,
                'cipher': s.cipher,
                'sequence_number': s.sequence_number,
                'status': s.get_status_display(),
                'status_code': s.status,
            }
            for s in samples
        ]
    })


@login_required
def api_check_operator_accreditation(request):
    """
    ⭐ v3.28.0: AJAX — проверка допуска операторов к областям аккредитации.

    GET: ?operator_ids=1,2,3&standard_ids=4,5,6
    Возвращает JSON со списком предупреждений.

    Учитывает:
    - user_accreditation_areas (допуск к области)
    - user_standard_exclusions (исключения по конкретным стандартам)
    """
    operator_ids_raw = request.GET.get('operator_ids', '')
    standard_ids_raw = request.GET.get('standard_ids', '')

    if not operator_ids_raw or not standard_ids_raw:
        return JsonResponse({'warnings': []})

    try:
        operator_ids = [int(x) for x in operator_ids_raw.split(',') if x.strip()]
        standard_ids = [int(x) for x in standard_ids_raw.split(',') if x.strip()]
    except (ValueError, TypeError):
        return JsonResponse({'warnings': []})

    if not operator_ids or not standard_ids:
        return JsonResponse({'warnings': []})

    from django.db import connection

    # 1. Для каждого стандарта — его НЕ-дефолтные области
    with connection.cursor() as cur:
        cur.execute("""
            SELECT saa.standard_id, aa.id AS area_id, aa.name AS area_name
            FROM standard_accreditation_areas saa
            JOIN accreditation_areas aa ON aa.id = saa.accreditation_area_id
            WHERE saa.standard_id = ANY(%s)
              AND aa.is_default = FALSE
              AND aa.is_active = TRUE
        """, [standard_ids])
        # {standard_id: {area_id: area_name, ...}}
        standard_areas = {}
        for row in cur.fetchall():
            standard_areas.setdefault(row[0], {})[row[1]] = row[2]

    # Если все стандарты только «Вне области» — проверка не нужна
    if not standard_areas:
        return JsonResponse({'warnings': []})

    # 2. Допуски операторов к областям
    all_area_ids = set()
    for areas in standard_areas.values():
        all_area_ids.update(areas.keys())

    with connection.cursor() as cur:
        cur.execute("""
            SELECT user_id, accreditation_area_id
            FROM user_accreditation_areas
            WHERE user_id = ANY(%s)
              AND accreditation_area_id = ANY(%s)
        """, [operator_ids, list(all_area_ids)])
        # set of (user_id, area_id)
        operator_area_set = {(row[0], row[1]) for row in cur.fetchall()}

    # 3. Исключения по стандартам
    with connection.cursor() as cur:
        cur.execute("""
            SELECT user_id, standard_id
            FROM user_standard_exclusions
            WHERE user_id = ANY(%s)
              AND standard_id = ANY(%s)
        """, [operator_ids, list(standard_areas.keys())])
        # set of (user_id, standard_id)
        exclusion_set = {(row[0], row[1]) for row in cur.fetchall()}

    # 4. Имена операторов
    operators = User.objects.filter(id__in=operator_ids).values(
        'id', 'last_name', 'first_name', 'sur_name'
    )
    operator_names = {}
    for op in operators:
        name = f"{op['last_name']} {op['first_name']}"
        if op.get('sur_name'):
            name += f" {op['sur_name']}"
        operator_names[op['id']] = name

    # 5. Формируем предупреждения
    warnings = []
    for op_id in operator_ids:
        issues = []  # [(standard_code, reason), ...]

        for std_id, areas in standard_areas.items():
            # Проверяем исключение по стандарту
            if (op_id, std_id) in exclusion_set:
                issues.append({
                    'standard_id': std_id,
                    'reason': 'excluded',  # исключён из допуска
                })
                continue

            # Проверяем допуск к хотя бы одной области этого стандарта
            has_area = any(
                (op_id, area_id) in operator_area_set
                for area_id in areas.keys()
            )
            if not has_area:
                area_names = list(areas.values())
                issues.append({
                    'standard_id': std_id,
                    'reason': 'no_area',
                    'missing_areas': area_names,
                })

        if issues:
            # Получаем коды стандартов для отображения
            std_codes = dict(
                Standard.objects.filter(id__in=[i['standard_id'] for i in issues])
                .values_list('id', 'code')
            )

            details = []
            for issue in issues:
                std_code = std_codes.get(issue['standard_id'], f"ID {issue['standard_id']}")
                if issue['reason'] == 'excluded':
                    details.append(f'{std_code} (исключён)')
                else:
                    areas_str = ', '.join(issue['missing_areas'])
                    details.append(f'{std_code} (нет допуска: {areas_str})')

            warnings.append({
                'operator_id': op_id,
                'operator_name': operator_names.get(op_id, f'ID {op_id}'),
                'details': details,
            })

    return JsonResponse({'warnings': warnings})


# ─────────────────────────────────────────────────────────────
# v3.38.0: API — Счета заказчика (для каскада в sample_create)
# ─────────────────────────────────────────────────────────────

@login_required
def api_client_invoices_for_sample(request, client_id):
    """Возвращает JSON список счетов заказчика для выпадающего списка."""
    if not Invoice:
        return JsonResponse({'invoices': []})
    invoices = Invoice.objects.filter(
        client_id=client_id,
    ).order_by('-date')
    result = []
    for inv in invoices:
        result.append({
            'id': inv.id,
            'number': inv.number,
            'date': str(inv.date) if inv.date else '',
        })
    return JsonResponse({'invoices': result})


@login_required
def api_invoice_acts(request, invoice_id):
    """v3.38.0: Возвращает JSON список актов для данного счёта."""
    acts = AcceptanceAct.objects.filter(invoice_id=invoice_id).order_by('-created_at')
    result = []
    for act in acts:
        labs = list(act.act_laboratories.values_list('laboratory__code_display', flat=True))
        result.append({
            'id': act.id,
            'doc_number': act.doc_number,
            'document_name': act.document_name,
            'work_deadline': str(act.work_deadline) if act.work_deadline else None,
            'samples_received_date': str(act.samples_received_date) if act.samples_received_date else None,
            'laboratories': labs,
            'work_status': act.work_status,
        })
    return JsonResponse(result, safe=False)


@login_required
def api_sample_field_changes(request, sample_id):
    """
    ⭐ v3.58.0: Последнее изменение каждого поля образца из audit_log.
    Используется для подсветки изменённых полей в карточке образца.
    Подсветка хранится навсегда — показывает кто последний менял поле.

    GET /api/samples/<sample_id>/field-changes/
    """
    sample = get_object_or_404(Sample, id=sample_id)
    access_error = _check_sample_access(request.user, sample)
    if access_error:
        return JsonResponse({'error': access_error}, status=403)

    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (al.field_name)
                al.field_name,
                al.new_value,
                al.old_value,
                al.timestamp,
                u.last_name,
                u.first_name,
                u.sur_name
            FROM audit_log al
            JOIN users u ON u.id = al.user_id
            WHERE al.entity_type = 'sample'
            AND al.entity_id = %s
            AND al.action = 'sample_updated'
            AND al.field_name IS NOT NULL
            ORDER BY al.field_name, al.timestamp DESC
        """, [sample_id])
        rows = cur.fetchall()

    result = {}
    for row in rows:
        field_name, new_value, old_value, timestamp, last_name, first_name, sur_name = row
        initials = f"{first_name[0]}." if first_name else ""
        sur_initials = f"{sur_name[0]}." if sur_name else ""
        full_short = f"{last_name} {initials}{sur_initials}".strip()
        result[field_name] = {
            'changed_by': full_short,
            'changed_at': timezone.localtime(timestamp).strftime('%d.%m.%Y %H:%M'),
            'is_new': not old_value,
        }

    return JsonResponse(result)


# ─────────────────────────────────────────────────────────────
# ⭐ v3.84.0: AJAX — preflight-валидация перед draft_ready/results_uploaded
# ─────────────────────────────────────────────────────────────

@login_required
def api_validate_draft_ready(request):
    """
    ⭐ v3.84.0: Клиентский preflight перед нажатием «Черновик готов» /
    «Результаты выложены». Принимает текущие значения из формы (ещё не
    сохранённые) и возвращает список ошибок для отображения в модалке.
    Сервер повторит ту же проверку в _validate_trainee_for_draft как safety net.

    GET: ?operator_ids=1,2,3&preparer_ids=4,5&report_prepared_date=YYYY-MM-DDTHH:MM
    Ответ: {ok: bool, errors: [str, ...]}
    """
    def _parse_ids(raw):
        try:
            return [int(x) for x in (raw or '').split(',') if x.strip()]
        except (ValueError, TypeError):
            return []

    operator_ids = _parse_ids(request.GET.get('operator_ids', ''))
    preparer_ids = _parse_ids(request.GET.get('preparer_ids', ''))
    date_str = (request.GET.get('report_prepared_date', '') or '').strip()

    errors = []

    # 1. Операторы
    if not operator_ids:
        errors.append('Поле «Операторы» пусто.')
    else:
        has_non_trainee_op = User.objects.filter(
            id__in=operator_ids, is_active=True, is_trainee=False
        ).exists()
        if not has_non_trainee_op:
            errors.append(
                'Среди операторов нет аттестованного сотрудника — все стажёры. '
                'Добавьте не-стажёра в поле «Операторы».'
            )

    # 2. Подготовившие отчёт
    if not preparer_ids:
        errors.append('Поле «Отчёт подготовили» пусто.')
    else:
        has_non_trainee_prep = User.objects.filter(
            id__in=preparer_ids, is_active=True, is_trainee=False
        ).exists()
        if not has_non_trainee_prep:
            errors.append(
                'Среди подготовивших отчёт нет аттестованного сотрудника — все стажёры. '
                'Добавьте не-стажёра в поле «Отчёт подготовили».'
            )

    # 3. Дата подготовки отчёта
    if not date_str:
        errors.append('Не заполнено поле «Дата и время подготовки отчёта».')

    return JsonResponse({'ok': len(errors) == 0, 'errors': errors})


# ─────────────────────────────────────────────────────────────
# ⭐ v3.85.0 (1б + 1г): Preflight при смене FK на карточке образца.
#
# Когда пользователь меняет client/contract/invoice/acceptance_act на
# уже существующем образце и образец в финальном статусе (COMPLETED или
# REPLACEMENT_PROTOCOL) — показываем модалку «хотите выпустить ЗАМ с
# новыми реквизитами?». Эндпоинт ниже — источник данных для этой модалки.
#
# Роли, которым можно инициировать выпуск ЗАМа через смену FK.
# Дублирует act_views.CASCADE_REPLACEMENT_ROLES (см. каскад 1а/1г).
# ─────────────────────────────────────────────────────────────
CASCADE_REPLACEMENT_ROLES = frozenset({
    'LAB_HEAD', 'CTO', 'CEO', 'SYSADMIN',
    'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
})

FK_CHANGE_REPLACEABLE_STATUSES = frozenset({
    'COMPLETED', 'REPLACEMENT_PROTOCOL',
})

FK_CHANGE_LABELS = {
    'client':         'Заказчик',
    'contract':       'Договор',
    'invoice':        'Счёт',
    'acceptance_act': 'Акт приёма-передачи',
}


def _handle_sample_save_with_replacement(request, sample):
    """⭐ v3.85.0 (1г): Обёртка над handle_sample_save, которая после
    сохранения полей образца вызывает sample.initiate_replacement_protocol
    для выпуска ЗАМа с новыми реквизитами.

    Вызывается из sample_detail POST-handler'а, когда пользователь:
      1. Изменил client/contract/invoice/acceptance_act
      2. Образец в финальном статусе (COMPLETED / REPLACEMENT_PROTOCOL)
      3. В preflight-модалке поставил галку «Выпустить ЗАМ»
      4. В POST прислано issue_replacement=1 + confirm_fk_change=1

    Всё выполняется в одной transaction.atomic — если выпуск ЗАМа упал,
    изменения полей тоже откатываются.
    """
    try:
        with transaction.atomic():
            _preprocess_deadline_pair(request, sample)
            updated_fields = save_sample_fields(request, sample)

            # После save_sample_fields sample в памяти имеет актуальное
            # состояние (save уже прошёл внутри). Проверяем, что статус
            # позволяет выпуск ЗАМа.
            if sample.status not in FK_CHANGE_REPLACEABLE_STATUSES:
                # Теоретически не должно происходить, т.к. preflight
                # проверяет статус ДО submit'а. Но если кто-то умудрился
                # поменять статус параллельно — не ломаемся, просто
                # пропускаем выпуск.
                messages.warning(
                    request,
                    f'Образец не в финальном статусе — выпуск ЗАМа пропущен.'
                )
            else:
                sample.initiate_replacement_protocol(
                    request=request,
                    reason='sample_fk_change',
                )
                sample.save()
                messages.success(
                    request,
                    f'Выпущен замещающий протокол № {sample.replacement_pi_number} '
                    f'от {sample.replacement_protocol_issued_date:%d.%m.%Y}.'
                )

            if updated_fields:
                messages.info(
                    request,
                    f'Изменены поля: {", ".join(updated_fields)}'
                )

    except Exception as e:
        logger.exception(
            'Ошибка при сохранении образца %s с выпуском ЗАМа', sample.id
        )
        messages.error(request, f'Ошибка при сохранении: {e}')

    return redirect('sample_detail', sample_id=sample.id)


@login_required
def api_validate_sample_fk_change(request, sample_id):
    """
    ⭐ v3.85.0 (1б + 1г): Клиентский preflight перед сохранением образца,
    когда меняются FK client/contract/invoice/acceptance_act.

    Возвращает, нужно ли показать модалку «выпустить ЗАМ»: да, если
      - образец в статусе COMPLETED или REPLACEMENT_PROTOCOL
      - хотя бы один из FK реально меняется относительно БД

    can_replace — решается здесь (UX), и дополнительно проверяется в
    save-handler'е (safety).

    GET: ?client=<id>&contract=<contract_X|invoice_Y|пусто>&acceptance_act=<id>
    Ответ:
      {
        needs_prompt: bool,
        changed_fk_labels: [str, ...],
        can_replace: bool,
        status: str,
        status_display: str,
      }
    """
    sample = get_object_or_404(Sample, id=sample_id)
    access_error = _check_sample_access(request.user, sample)
    if access_error:
        return JsonResponse({'error': access_error}, status=403)

    # Парсим новые значения из GET
    def _parse_int(raw):
        raw = (raw or '').strip()
        try:
            return int(raw) if raw else None
        except ValueError:
            return None

    new_client_id = _parse_int(request.GET.get('client', ''))
    

    # contract приходит с префиксом contract_X / invoice_Y, либо пусто
    contract_raw = (request.GET.get('contract', '') or '').strip()
    new_contract_id = None
    new_invoice_id = None
    if contract_raw.startswith('contract_'):
        new_contract_id = _parse_int(contract_raw.replace('contract_', ''))
    elif contract_raw.startswith('invoice_'):
        new_invoice_id = _parse_int(contract_raw.replace('invoice_', ''))
    elif contract_raw:
        # Обратная совместимость — голый id трактуем как contract_id
        new_contract_id = _parse_int(contract_raw)

    new_act_id = _parse_int(request.GET.get('acceptance_act', ''))

    # Сравниваем с БД
    changed = []
    if new_client_id != sample.client_id:
        changed.append('client')
    if new_contract_id != sample.contract_id:
        changed.append('contract')
    if new_invoice_id != sample.invoice_id:
        changed.append('invoice')
    if new_act_id != sample.acceptance_act_id:
        changed.append('acceptance_act')

    in_replaceable_status = sample.status in FK_CHANGE_REPLACEABLE_STATUSES
    user_role = getattr(request.user, 'role', '') or ''
    can_replace = user_role in CASCADE_REPLACEMENT_ROLES

    needs_prompt = bool(changed) and in_replaceable_status

    status_labels = dict(SampleStatus.choices)
    return JsonResponse({
        'needs_prompt': needs_prompt,
        'changed_fk_labels': [FK_CHANGE_LABELS.get(f, f) for f in changed],
        'can_replace': can_replace,
        'status': sample.status,
        'status_display': status_labels.get(sample.status, sample.status),
    })
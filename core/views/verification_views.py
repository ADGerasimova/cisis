from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import date

from core.models import Sample, SampleStatus
from core.permissions import PermissionChecker

@login_required
def verify_sample(request, sample_id):
    """Проверка и подтверждение регистрации образца"""

    if request.method != 'POST':
        return redirect('sample_detail', sample_id=sample_id)

    # Получаем образец
    sample = get_object_or_404(Sample, id=sample_id)

    # Проверяем, что это НЕ тот кто зарегистрировал
    if sample.registered_by == request.user:
        messages.error(request, 'Вы не можете проверить образец, который зарегистрировали сами')
        return redirect('sample_detail', sample_id=sample_id)

    # Проверяем статус
    if sample.status != SampleStatus.PENDING_VERIFICATION:
        messages.warning(request, 'Этот образец уже проверен или имеет другой статус')
        return redirect('sample_detail', sample_id=sample_id)

    # НОВАЯ ЛОГИКА ПРАВ:
    # Могут проверять:
    # 1. Другой специалист отдела заказчиков (CLIENT_MANAGER)
    # 2. Руководитель отдела заказчиков (CLIENT_DEPT_HEAD)
    # 3. Заведующий лаборатории, к которой относится образец (LAB_HEAD)
    # 4. Системный администратор (SYSADMIN)

    can_verify = False

    if request.user.role == 'SYSADMIN':
        can_verify = True
    elif request.user.role == 'CLIENT_MANAGER':
        # Другой специалист отдела заказчиков
        can_verify = True
    elif request.user.role == 'CLIENT_DEPT_HEAD':
        # Руководитель отдела заказчиков
        can_verify = True
    elif request.user.role == 'LAB_HEAD':
        # ⭐ v3.8.0: Заведующий может проверять образцы своей лаборатории (основная + доп.)
        if request.user.has_laboratory(sample.laboratory):
            can_verify = True
        else:
            messages.error(request, 'Вы можете проверять только образцы своей лаборатории')
            return redirect('sample_detail', sample_id=sample_id)

    if not can_verify:
        messages.error(request, 'У вас нет прав для проверки регистрации')
        return redirect('sample_detail', sample_id=sample_id)

    # Получаем действие
    action = request.POST.get('verify_action')


    if action == 'approve':
        sample.verified_by = request.user
        sample.verified_at = timezone.now()

        # Автоматически переводим в нужный статус:
        # ⭐ v3.66.0: Исправлен приоритет: зависимость от влагонасыщения проверяется ДО нарезки
        # 0. uzk_required=True → UZK_TESTING (УЗК до всего)
        # 1. moisture_conditioning + moisture_sample_id → MOISTURE_CONDITIONING (ждёт другой образец)
        # 2. manufacturing=True → MANUFACTURING (нарезка)
        # 3. moisture_conditioning (без зависимости) → MOISTURE_CONDITIONING
        # 4. Иначе → REGISTERED
        if sample.uzk_required and sample.uzk_sample_id:
            sample.status = SampleStatus.UZK_TESTING
            messages.success(
                request,
                f'Образец {sample.cipher} проверен. '
                f'Статус: «На УЗК» — ожидает завершения ультразвукового контроля в МИ.'
            )
        elif sample.uzk_required and not sample.uzk_sample_id:
            # УЗК включён, но образец МИ не привязан — ставим UZK_TESTING
            # (регистратор привяжет позже)
            sample.status = SampleStatus.UZK_TESTING
            messages.success(
                request,
                f'Образец {sample.cipher} проверен. '
                f'Статус: «На УЗК» — образец МИ ещё не привязан.'
            )
        elif sample.moisture_conditioning and sample.moisture_sample_id:
            # ⭐ v3.66.0: Зависит от образца влагонасыщения → ждём его
            # (нарезка, если нужна, произойдёт после приёма из влагонасыщения)
            sample.status = SampleStatus.MOISTURE_CONDITIONING
            messages.success(
                request,
                f'Образец {sample.cipher} проверен. '
                f'Статус: «На влагонасыщении» — ожидает завершения работ в УКИ.'
            )
        elif sample.manufacturing:
            sample.status = SampleStatus.MANUFACTURING
            messages.success(
                request,
                f'Образец {sample.cipher} проверен и передан в мастерскую для изготовления.'
            )
        elif sample.moisture_conditioning:
            # ⭐ v3.15.0: Влагонасыщение без зависимости от другого образца
            sample.status = SampleStatus.MOISTURE_CONDITIONING
            messages.success(
                request,
                f'Образец {sample.cipher} проверен. '
                f'Статус: «На влагонасыщении» — ожидает завершения работ в УКИ.'
            )
        else:
            sample.status = SampleStatus.REGISTERED
            messages.success(
                request,
                f'Образец {sample.cipher} проверен и подтверждён. '
                f'Теперь он доступен испытателям.'
            )

        sample.save()

        # ⭐ v3.39.0: Закрываем задачу проверки регистрации
        try:
            from core.views.task_views import create_auto_task, close_auto_tasks
            from core.models import User as TaskUser
            close_auto_tasks('VERIFY_REGISTRATION', 'sample', sample.id)

            # Создаём следующие задачи
            # ⭐ v3.64.0: UZK_TESTING → задачу регистраторам (для отслеживания)
            if sample.status == SampleStatus.UZK_TESTING:
                registrar_ids = list(TaskUser.objects.filter(
                    role__in=('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD'), is_active=True,
                ).values_list('id', flat=True))
                if registrar_ids:
                    create_auto_task('ACCEPT_FROM_UZK', sample, registrar_ids, created_by=None)

            # MANUFACTURING → мастерской
            elif sample.status == SampleStatus.MANUFACTURING:
                workshop_ids = list(TaskUser.objects.filter(
                    role__in=('WORKSHOP', 'WORKSHOP_HEAD'), is_active=True,
                ).values_list('id', flat=True))
                if workshop_ids:
                    create_auto_task('MANUFACTURING', sample, workshop_ids, created_by=None)

            # ⭐ v3.67.0: TESTING создаётся через cron за 2 дня до дедлайна

        except Exception:
            import logging
            logging.getLogger(__name__).exception('Ошибка обработки автозадач')

    elif action == 'reject':
        # Отклоняем регистрацию - возвращаем на доработку
        rejection_reason = request.POST.get('rejection_reason', '').strip()

        if rejection_reason:
            # Сохраняем причину отклонения в примечаниях администратора
            if sample.admin_notes:
                sample.admin_notes += f"\n\n--- ОТКЛОНЕНО {timezone.now().strftime('%d.%m.%Y %H:%M')} ---\n"
                sample.admin_notes += f"Проверяющий: {request.user.full_name}\n"
                sample.admin_notes += f"Причина: {rejection_reason}"
            else:
                sample.admin_notes = f"ОТКЛОНЕНО: {rejection_reason}"

        # Оставляем в статусе PENDING - чтобы регистратор мог исправить
        sample.save()

        # ⭐ v3.39.0: Закрываем задачу проверки
        try:
            from core.views.task_views import close_auto_tasks
            close_auto_tasks('VERIFY_REGISTRATION', 'sample', sample.id)
        except Exception:
            pass

        messages.warning(
            request,
            f'Регистрация образца {sample.cipher} отклонена. '
            f'Причина сохранена в примечаниях.'
        )

    elif action == 'cancel':
        # Полная отмена образца
        sample.status = SampleStatus.CANCELLED
        sample.verified_by = request.user
        sample.verified_at = timezone.now()
        sample.save()

        # ⭐ v3.39.0: Закрываем задачу проверки
        try:
            from core.views.task_views import close_auto_tasks
            close_auto_tasks('VERIFY_REGISTRATION', 'sample', sample.id)
        except Exception:
            pass

        messages.info(
            request,
            f'Образец {sample.cipher} отменён'
        )

    return redirect('sample_detail', sample_id=sample_id)

@login_required
def verify_protocol(request, sample_id):
    """Проверка и подтверждение протокола СМК или заведующим лаборатории"""

    if request.method != 'POST':
        messages.error(request, 'Неверный метод запроса')
        return redirect('sample_detail', sample_id=sample_id)

    # Получаем образец
    sample = get_object_or_404(Sample, id=sample_id)

    # ═══════════════════════════════════════════════════════════════
    # ПРОВЕРКА ПРАВ
    # ═══════════════════════════════════════════════════════════════

    # Могут проверять протоколы:
    # 1. Руководитель СМК (QMS_HEAD)
    # 2. Администратор СМК (QMS_ADMIN)
    # 3. Заведующий лаборатории (LAB_HEAD) - своей лаборатории (основная + доп.)
    # 4. Системный администратор (SYSADMIN)

    can_verify = False

    if request.user.role == 'SYSADMIN':
        can_verify = True
    elif request.user.role in ['QMS_HEAD', 'QMS_ADMIN']:
        can_verify = True
    elif request.user.role == 'LAB_HEAD':
        # ⭐ v3.8.0: Заведующий может проверять протоколы своей лаборатории (основная + доп.)
        if request.user.has_laboratory(sample.laboratory):
            can_verify = True
        else:
            messages.error(request, 'Вы можете проверять только протоколы своей лаборатории')
            return redirect('sample_detail', sample_id=sample_id)

    if not can_verify:
        messages.error(request, 'У вас нет прав для проверки протоколов')
        return redirect('sample_detail', sample_id=sample_id)

    # ═══════════════════════════════════════════════════════════════
    # ПРОВЕРКА СТАТУСА
    # ═══════════════════════════════════════════════════════════════

    # Проверять можно только образцы со статусами DRAFT_READY или RESULTS_UPLOADED
    if sample.status not in ['DRAFT_READY', 'RESULTS_UPLOADED']:
        messages.warning(
            request,
            f'Протокол не готов к проверке. Текущий статус: {sample.get_status_display()}'
        )
        return redirect('sample_detail', sample_id=sample_id)

    # ═══════════════════════════════════════════════════════════════
    # ОБРАБОТКА ДЕЙСТВИЯ
    # ═══════════════════════════════════════════════════════════════

    action = request.POST.get('verify_action')

    if action == 'approve':
        # Подтверждаем протокол/результаты
        from django.utils import timezone

        old_status = sample.status

        # РАЗНАЯ ЛОГИКА ДЛЯ РАЗНЫХ СТАТУСОВ:
        if sample.status == 'DRAFT_READY':
            # Черновик протокола → Протокол выпущен
            sample.status = 'PROTOCOL_ISSUED'

            # Автоматически проставляем дату выпуска протокола
            if not sample.protocol_issued_date:
                sample.protocol_issued_date = timezone.now().date()

            success_message = (
                f'✅ Протокол {sample.pi_number} проверен и одобрен! '
                f'Дата выпуска: {sample.protocol_issued_date.strftime("%d.%m.%Y")}. '
                f'Следующий шаг: после печати установите дату печати и статус "Готово".'
            )

        else:  # RESULTS_UPLOADED
            # Результаты выложены → Готово (без протокола)
            sample.status = 'COMPLETED'

            # Дату выпуска НЕ устанавливаем (нет протокола)

            success_message = (
                f'✅ Результаты проверены и одобрены! '
                f'Работа по образцу {sample.cipher} завершена.'
            )

        # Записываем кто и когда проверил
        sample.protocol_checked_by = request.user
        sample.protocol_checked_at = timezone.now()

        sample.save()

        messages.success(request, success_message)

    elif action == 'reject':
        # Отклоняем протокол/результаты - возвращаем испытателю на доработку
        from django.utils import timezone

        rejection_reason = request.POST.get('rejection_reason', '').strip()

        if rejection_reason:
            # Сохраняем причину отклонения в примечаниях оператора
            timestamp = timezone.now().strftime('%d.%m.%Y %H:%M')

            if sample.status == 'DRAFT_READY':
                note_header = f"\n\n--- ПРОТОКОЛ ОТКЛОНЁН {timestamp} ---\n"
            else:  # RESULTS_UPLOADED
                note_header = f"\n\n--- РЕЗУЛЬТАТЫ ОТКЛОНЕНЫ {timestamp} ---\n"

            if sample.operator_notes:
                sample.operator_notes += note_header
                sample.operator_notes += f"Проверяющий: {request.user.full_name}\n"
                sample.operator_notes += f"Причина: {rejection_reason}"
            else:
                sample.operator_notes = f"{note_header}Проверяющий: {request.user.full_name}\nПричина: {rejection_reason}"

        # Возвращаем статус в TESTED
        sample.status = 'TESTED'
        sample.save()

        if sample.status == 'DRAFT_READY':
            warning_message = (
                f'⚠️ Протокол {sample.pi_number} отклонён и возвращён испытателю на доработку. '
                f'Причина сохранена в примечаниях.'
            )
        else:
            warning_message = (
                f'⚠️ Результаты отклонены и возвращены испытателю на доработку. '
                f'Причина сохранена в примечаниях.'
            )

        messages.warning(request, warning_message)

    else:
        messages.error(request, f'Неизвестное действие: {action}')

    return redirect('sample_detail', sample_id=sample_id)
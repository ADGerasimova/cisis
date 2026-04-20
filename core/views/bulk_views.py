"""
CISIS v3.16.0 — Массовые операции для испытателей.

Содержит:
- bulk_operations: страница массовых операций (GET + POST)
- _get_bulk_actions: доступные массовые действия для роли
- _get_m2m_options_for_lab: варианты M2M (СИ, ИО, ВО, операторы) для лаборатории
- _apply_bulk_status_change: массовая смена статуса с автозаполнением datetime
- _apply_bulk_m2m_add: массовое добавление M2M (без замены)
"""

import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from core.models import (
    Sample, Laboratory, Equipment, EquipmentAccreditationArea, User,
    SampleMeasuringInstrument, SampleTestingEquipment,
    SampleAuxiliaryEquipment, SampleOperator,
    SampleStatus,
)
from core.permissions import PermissionChecker
from core.views.audit import log_action, log_m2m_changes
from .save_logic import _validate_trainee_for_draft

logger = logging.getLogger(__name__)

# Роли с доступом к массовым операциям
BULK_ALLOWED_ROLES = frozenset(['TESTER', 'LAB_HEAD', 'SYSADMIN'])

# ─────────────────────────────────────────────────────────────
# Конфигурация массовых действий
# ─────────────────────────────────────────────────────────────

# Какие исходные статусы допустимы для каждого действия
BULK_ACTIONS = {
    'start_conditioning': {
        'label': '🌡️ Начать кондиционирование',
        'new_status': 'CONDITIONING',
        'allowed_from': frozenset([
            'REGISTERED', 'MANUFACTURED', 'TRANSFERRED',
            'REPLACEMENT_PROTOCOL', 'READY_FOR_TEST',
        ]),
        'datetime_field': 'conditioning_start_datetime',
    },
    'ready_for_test': {
        'label': '✓ Кондиционирование завершено',
        'new_status': 'READY_FOR_TEST',
        'allowed_from': frozenset([
            'CONDITIONING', 'REGISTERED', 'MANUFACTURED',
            'TRANSFERRED', 'REPLACEMENT_PROTOCOL',
        ]),
        'datetime_field': 'conditioning_end_datetime',
    },
    'start_testing': {
        'label': '▶️ Начать испытание',
        'new_status': 'IN_TESTING',
        'allowed_from': frozenset([
            'READY_FOR_TEST', 'CONDITIONING', 'REGISTERED',
            'MANUFACTURED', 'TRANSFERRED', 'REPLACEMENT_PROTOCOL',
        ]),
        'datetime_field': 'testing_start_datetime',
    },
    'complete_test': {
        'label': '✓ Завершить испытание',
        'new_status': 'TESTED',
        'allowed_from': frozenset(['IN_TESTING']),
        'datetime_field': 'testing_end_datetime',
    },
    'draft_ready': {
        'label': '📝 Черновик протокола готов',
        'new_status': 'DRAFT_READY',
        'allowed_from': frozenset(['TESTED']),
        'datetime_field': 'report_prepared_date',
        'set_user_field': 'report_prepared_by',
    },
    'results_uploaded': {
        'label': '📤 Результаты выложены',
        'new_status': 'RESULTS_UPLOADED',
        'allowed_from': frozenset(['TESTED']),
        'datetime_field': 'report_prepared_date',
        'set_user_field': 'report_prepared_by',
    },
}

# M2M поля испытателя для массового добавления
BULK_M2M_FIELDS = {
    'measuring_instruments': {
        'label': 'Средства измерений (СИ)',
        'through_model': SampleMeasuringInstrument,
        'id_field': 'equipment_id',
        'equipment_type': 'СИ',
        'badge_class': 'blue',
    },
    'testing_equipment': {
        'label': 'Испытательное оборудование (ИО)',
        'through_model': SampleTestingEquipment,
        'id_field': 'equipment_id',
        'equipment_type': 'ИО',
        'badge_class': 'blue',
    },
    'auxiliary_equipment': {
        'label': 'Вспомогательное оборудование (ВО)',
        'through_model': SampleAuxiliaryEquipment,
        'id_field': 'equipment_id',
        'equipment_type': 'ВО',
        'badge_class': 'blue',
    },
    'operators': {
        'label': 'Операторы',
        'through_model': SampleOperator,
        'id_field': 'user_id',
        'equipment_type': None,  # не оборудование
        'badge_class': 'green',
    },
}


# ─────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────

def _get_bulk_actions_for_role(user_role):
    """Возвращает список доступных массовых действий для роли."""
    # Все роли с доступом получают все действия испытателя
    return [
        {'action': key, **config}
        for key, config in BULK_ACTIONS.items()
    ]


def _get_m2m_options_for_lab(laboratory, field_code):
    """Возвращает queryset вариантов M2M для данной лаборатории."""
    config = BULK_M2M_FIELDS.get(field_code)
    if not config:
        return []

    if field_code == 'operators':
        if not laboratory:
            return User.objects.none()
        return User.objects.filter(
            laboratory=laboratory, is_active=True
        ).order_by('last_name', 'first_name')
    else:
        if not laboratory:
            return Equipment.objects.none()
        return Equipment.objects.filter(
            laboratory=laboratory,
            status='OPERATIONAL',
            equipment_type=config['equipment_type'],
        ).order_by('accounting_number')


def _get_samples_for_bulk(user):
    """Возвращает queryset образцов, доступных для массовых операций."""
    if user.role == 'SYSADMIN':
        return Sample.objects.all().exclude(status='PENDING_VERIFICATION')

    if user.role == 'LAB_HEAD':
        if not user.laboratory:
            return Sample.objects.none()
        return Sample.objects.filter(
            laboratory_id__in=user.all_laboratory_ids
        ).exclude(status='PENDING_VERIFICATION')

    # TESTER, OPERATOR
    if not user.laboratory:
        return Sample.objects.none()
    return Sample.objects.filter(
        laboratory_id__in=user.all_laboratory_ids
    ).exclude(status='PENDING_VERIFICATION')


# ─────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────

@login_required
def bulk_operations(request):
    """
    Страница массовых операций для испытателей.

    GET: отображает таблицу образцов с чекбоксами + панель действий.
    POST: выполняет выбранное действие над отмеченными образцами.
    """
    user = request.user

    if user.role not in BULK_ALLOWED_ROLES:
        messages.error(request, 'У вас нет доступа к массовым операциям')
        return redirect('journal_samples')

    if not PermissionChecker.has_journal_access(user, 'SAMPLES'):
        messages.error(request, 'У вас нет доступа к журналу образцов')
        return redirect('workspace_home')

    # ─── Queryset образцов ───
    samples_qs = _get_samples_for_bulk(user)
    samples_qs = samples_qs.select_related(
        'laboratory', 'accreditation_area', 'client',
    ).prefetch_related(
        'standards', 'operators',
        'measuring_instruments', 'testing_equipment', 'auxiliary_equipment',
    ).order_by('-registration_date', '-sequence_number')

    # Фильтр по статусу (GET-параметр)
    status_filter = request.GET.get('status', '')
    if status_filter:
        samples_qs = samples_qs.filter(status=status_filter)

    samples = list(samples_qs[:200])  # Лимит для производительности

    # ─── Доступные действия ───
    bulk_actions = _get_bulk_actions_for_role(user.role)

    # ─── M2M варианты ───
    lab = user.laboratory
    m2m_options = {}
    for field_code, config in BULK_M2M_FIELDS.items():
        options = _get_m2m_options_for_lab(lab, field_code)
        m2m_options[field_code] = {
            'label': config['label'],
            'badge_class': config['badge_class'],
            'options': list(options),
            'is_users': field_code == 'operators',
        }

    # ─── POST: выполнение массовой операции ───
    report = None
    if request.method == 'POST':
        selected_ids = request.POST.getlist('sample_ids')
        if not selected_ids:
            messages.warning(request, 'Не выбрано ни одного образца')
        else:
            selected_ids = [int(sid) for sid in selected_ids if sid]
            action = request.POST.get('bulk_action', '')
            report = _execute_bulk_operation(request, user, selected_ids, action)

            # Перезагружаем образцы после изменений
            samples_qs = _get_samples_for_bulk(user)
            samples_qs = samples_qs.select_related(
                'laboratory', 'accreditation_area', 'client',
            ).prefetch_related(
                'standards', 'operators',
                'measuring_instruments', 'testing_equipment', 'auxiliary_equipment',
            ).order_by('-registration_date', '-sequence_number')
            if status_filter:
                samples_qs = samples_qs.filter(status=status_filter)
            samples = list(samples_qs[:200])

    # ─── Статусы для фильтра ───
    all_statuses = [
        ('REGISTERED', 'Зарегистрирован'),
        ('CONDITIONING', 'Кондиционирование'),
        ('READY_FOR_TEST', 'Готов к испытанию'),
        ('IN_TESTING', 'Испытание'),
        ('TESTED', 'Испытан'),
        ('MANUFACTURED', 'Изготовлен'),
        ('TRANSFERRED', 'Передан'),
        ('REPLACEMENT_PROTOCOL', 'Замещающий протокол'),
        ('DRAFT_READY', 'Черновик готов'),
        ('RESULTS_UPLOADED', 'Результаты выложены'),
    ]

    return render(request, 'core/bulk_operations.html', {
        'samples': samples,
        'bulk_actions': bulk_actions,
        'm2m_options': m2m_options,
        'report': report,
        'status_filter': status_filter,
        'all_statuses': all_statuses,
        'user': user,
    })


def _execute_bulk_operation(request, user, selected_ids, action):
    """
    Выполняет массовую операцию: смена статуса + добавление M2M.
    Возвращает отчёт: {success: [], skipped: [], errors: []}.
    """
    report = {
        'success': [],
        'skipped': [],
        'errors': [],
        'action_label': '',
        'm2m_added': [],
    }

    now = timezone.now()

    # ─── 1. Смена статуса ───
    action_config = BULK_ACTIONS.get(action)
    if action_config:
        report['action_label'] = action_config['label']

        samples = Sample.objects.filter(
            id__in=selected_ids
        ).select_related('laboratory')

        for sample in samples:
            # Проверяем доступ
            if user.role not in ('SYSADMIN',):
                if user.role == 'LAB_HEAD':
                    if not user.has_laboratory(sample.laboratory):
                        report['skipped'].append({
                            'cipher': sample.cipher,
                            'reason': 'Образец не из вашей лаборатории',
                        })
                        continue
                elif not user.has_laboratory(sample.laboratory):
                    report['skipped'].append({
                        'cipher': sample.cipher,
                        'reason': 'Образец не из вашей лаборатории',
                    })
                    continue

            # Проверяем допустимость перехода
            if sample.status not in action_config['allowed_from']:
                report['skipped'].append({
                    'cipher': sample.cipher,
                    'reason': f'Статус «{sample.get_status_display()}» не подходит для этого действия',
                })
                continue

            # Валидация стажёров для draft_ready / results_uploaded
            if action in ('draft_ready', 'results_uploaded'):
                is_valid, error_msg = _validate_trainee_for_draft(sample)
                if not is_valid:
                    report['skipped'].append({
                        'cipher': sample.cipher,
                        'reason': error_msg,
                    })
                    continue

            try:
                with transaction.atomic():
                    old_status = sample.status
                    sample.status = action_config['new_status']

                    # Автозаполнение datetime
                    dt_field = action_config.get('datetime_field')
                    if dt_field:
                        setattr(sample, dt_field, now)

                    # Автозаполнение user (report_prepared_by)
                    user_field = action_config.get('set_user_field')
                    if user_field:
                        setattr(sample, user_field, user)

                    sample.save()

                    # Аудит
                    log_action(
                        request, 'sample', sample.id, 'status_change',
                        field_name='status',
                        old_value=old_status,
                        new_value=sample.status,
                        extra_data={'bulk_operation': True},
                    )

                    # complete_test: обновляем зависимые образцы (moisture)
                    if action == 'complete_test':
                        dep_count = Sample.objects.filter(
                            moisture_sample_id=sample.id,
                            status='MOISTURE_CONDITIONING',
                        ).update(status='MOISTURE_READY')
                        if dep_count:
                            report['success'].append({
                                'cipher': sample.cipher,
                                'note': f'+ {dep_count} связанных образцов → «Готово к передаче из УКИ»',
                            })
                            continue

                    report['success'].append({'cipher': sample.cipher})

            except Exception as e:
                logger.exception('Ошибка массовой смены статуса для %s', sample.cipher)
                report['errors'].append({
                    'cipher': sample.cipher,
                    'reason': str(e),
                })

    # ─── 2. Добавление M2M ───
    for field_code, config in BULK_M2M_FIELDS.items():
        m2m_ids = request.POST.getlist(f'bulk_{field_code}')
        if not m2m_ids:
            continue

        m2m_ids = set(int(mid) for mid in m2m_ids if mid)
        if not m2m_ids:
            continue

        through_model = config['through_model']
        id_field = config['id_field']
        added_count = 0

        samples = Sample.objects.filter(id__in=selected_ids)

        for sample in samples:
            # Проверяем доступ
            if user.role not in ('SYSADMIN',):
                if not user.has_laboratory(sample.laboratory):
                    continue

            try:
                # Получаем текущие ID
                current_ids = set(
                    through_model.objects.filter(sample=sample)
                    .values_list(id_field, flat=True)
                )
                # Добавляем только новые (без замены)
                new_ids = m2m_ids - current_ids
                if not new_ids:
                    continue

                for obj_id in new_ids:
                    through_model.objects.create(
                        sample=sample, **{id_field: obj_id}
                    )

                # Аудит
                log_m2m_changes(
                    request=request,
                    entity_type='sample',
                    entity_id=sample.id,
                    field_name=field_code,
                    old_ids=current_ids,
                    new_ids=current_ids | new_ids,
                )

                added_count += 1

            except Exception as e:
                logger.exception(
                    'Ошибка массового добавления M2M %s для %s',
                    field_code, sample.id,
                )
                report['errors'].append({
                    'cipher': getattr(sample, 'cipher', f'ID {sample.id}'),
                    'reason': f'{config["label"]}: {e}',
                })

        if added_count:
            report['m2m_added'].append({
                'field': config['label'],
                'count': added_count,
                'items': len(m2m_ids),
            })

    return report
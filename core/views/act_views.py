"""
CISIS v3.37.0 — Акты приёма-передачи: views

Файл: core/views/act_views.py
Действие: ПОЛНАЯ ЗАМЕНА файла

Изменения v3.37.0:
- contract_id теперь необязателен (nullable)
- Поддержка invoice_id (работа без договора)
- Поддержка specification_id (спецификация/ТЗ к договору)
- Наследование финансов из спецификации/счёта
- API: api_client_invoices — AJAX-каскад счетов по заказчику
- API: api_contract_specifications — AJAX-каскад спецификаций по договору
"""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, F

from core.models import (
    AcceptanceAct, AcceptanceActLaboratory,
    Client, Contract, Laboratory,
)
from core.views.audit import log_action, log_field_changes
from core.views.file_views import get_files_for_entity
from core.permissions import PermissionChecker

logger = logging.getLogger(__name__)

# Пробуем импортировать новые модели (v3.37.0)
try:
    from core.models import Invoice, Specification
except ImportError:
    Invoice = None
    Specification = None


# ─────────────────────────────────────────────────────────────
# Проверки доступа
# ─────────────────────────────────────────────────────────────

def _check_acts_access(user):
    return PermissionChecker.can_view(user, 'CLIENTS', 'access')

def _can_edit_acts(user):
    return PermissionChecker.can_edit(user, 'CLIENTS', 'access')


# ─────────────────────────────────────────────────────────────
# Выпадающие списки
# ─────────────────────────────────────────────────────────────

ACT_CHOICES = {
    'document_status': [
        ('', '—'),
        ('SCANS_RECEIVED', 'Получены сканы'),
        ('ORIGINALS_RECEIVED', 'Получены оригиналы'),
    ],
    'payment_terms': [
        ('', '—'),
        ('PREPAID', 'Предоплата'),
        ('POSTPAID', 'Постоплата'),
        ('ADVANCE_50', 'Аванс 50%'),
        ('ADVANCE_30', 'Аванс 30%'),
        ('OTHER', 'Другое'),
    ],
    'document_flow': [
        ('', '—'),
        ('PAPER', 'Бумажный'),
        ('EDO', 'ЭДО'),
    ],
    'closing_status': [
        ('', '—'),
        ('PREPARED', 'Подготовлено'),
        ('SENT_TO_CLIENT', 'Передано заказчику'),
        ('RECEIVED', 'Получено'),
        ('CANCELLED', 'Отмена'),
    ],
    'work_status': [
        ('IN_PROGRESS', 'В работе'),
        ('CLOSED', 'Работы закрыты'),
        ('CANCELLED', 'Отмена'),
    ],
    'sending_method': [
        ('', '—'),
        ('COURIER', 'Курьер'),
        ('EMAIL', 'Отправлены по электронной почте'),
        ('RUSSIAN_POST', 'Отправлены Почтой России'),
        ('GARANTPOST', 'Отправлены Гарантпост'),
        ('IN_PERSON', 'Переданы нарочно'),
    ],
}

ACT_DISPLAY = {}
for field, choices in ACT_CHOICES.items():
    ACT_DISPLAY[field] = dict(choices)


# ─────────────────────────────────────────────────────────────
# ⭐ v3.85.0: Каскадное наследование АПП → образцы (задачи 1а + 1г)
#
# При редактировании акта три поля должны каскадно распространяться
# на все привязанные к нему образцы: doc_number, document_name,
# samples_received_date. Имена зеркальных полей на Sample отличаются
# исторически — см. CASCADE_FIELDS_MAP.
#
# Образцы делятся на три группы по статусу:
#
#   1. UPDATABLE — активные (не в финальном статусе). Обновляются
#      каскадом автоматически, без подтверждения.
#
#   2. REPLACEABLE — COMPLETED или REPLACEMENT_PROTOCOL. Ретроактивно
#      менять данные выпущенного протокола нельзя, но можно выпустить
#      замещающий (ЗАМ / ЗАМ-ЗАМ / ЗАМ-ЗАМ-ЗАМ) с обновлёнными
#      реквизитами. В баннере подтверждения каждый такой образец
#      получает чекбокс «выпустить ЗАМ» (только для ролей из
#      CASCADE_REPLACEMENT_ROLES). По умолчанию галка снята.
#
#   3. NON_REPLACEABLE — CANCELLED. Образец отменён, никакие действия
#      не применяются. В баннере отображается как информация.
#
# Если есть образцы в REPLACEABLE или NON_REPLACEABLE — форма
# перерисовывается с баннером подтверждения, и применение требует
# повторного нажатия «Сохранить» с confirm_cascade=1.
# ─────────────────────────────────────────────────────────────

CASCADE_FIELDS_MAP = {
    # поле AcceptanceAct        →  поле Sample
    'doc_number':               'accompanying_doc_number',
    'document_name':            'accompanying_doc_full_name',
    'samples_received_date':    'sample_received_date',
}

CASCADE_FIELDS_LABELS = {
    'doc_number':               'Код документа',
    'document_name':            'Наименование документа',
    'samples_received_date':    'Дата получения образцов',
}

# Статусы образцов с выпущенным протоколом — можно выпустить ЗАМ.
CASCADE_REPLACEABLE_STATUSES = frozenset({
    'COMPLETED', 'REPLACEMENT_PROTOCOL',
})

# Статусы, в которых образец не трогается вообще (отменён).
CASCADE_NON_REPLACEABLE_STATUSES = frozenset({
    'CANCELLED',
})

# Объединение — все статусы, исключаемые из обычного каскада.
# Для замещаемых дополнительно применяется логика ЗАМ (_apply_cascade
# при наличии replace_sample_ids).
CASCADE_SKIP_STATUSES = (
    CASCADE_REPLACEABLE_STATUSES | CASCADE_NON_REPLACEABLE_STATUSES
)

# Роли, которым можно инициировать выпуск ЗАМа через каскад.
# Регистраторы и завлабы + CTO/CEO/SYSADMIN. Выпуск ЗАМа — новый
# официальный документ, поэтому право закреплено явно по ролям,
# а не через общий can_edit для актов.
CASCADE_REPLACEMENT_ROLES = frozenset({
    'LAB_HEAD', 'CTO', 'CEO', 'SYSADMIN',
    'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
})


def _get_cascade_changes(act, new_values):
    """Возвращает {act_field: new_value} только для реально изменённых
    полей из CASCADE_FIELDS_MAP.

    Особое правило: sample_received_date на Sample — NOT NULL, поэтому если
    в акте очистили samples_received_date (новое значение None), в каскад
    это поле не включаем — у образцов оно остаётся как было.
    """
    changes = {}
    for act_field in CASCADE_FIELDS_MAP:
        old = getattr(act, act_field, None)
        new = new_values.get(act_field)
        # Нормализация '' vs None для строковых полей
        if act_field in ('doc_number', 'document_name'):
            old = old or ''
            new = new or ''
        if old != new:
            if act_field == 'samples_received_date' and new is None:
                continue
            changes[act_field] = new
    return changes


def _preview_cascade(act, cascade_changes):
    """Считает, какие образцы акта будут затронуты каскадом, и разбивает
    их на три группы. Ничего не пишет в БД.

    Возвращает (update_count, replaceable, non_replaceable), где:
      - update_count: сколько активных образцов реально обновится
      - replaceable: список dict'ов про образцы с выпущенным протоколом —
        для них возможен выпуск ЗАМа. Ключи: id, sequence_number, cipher,
        status, status_display, pi_number, replacement_pi_number,
        replacement_count, effective_pi (номер последнего выпущенного
        документа — оригинал или последний ЗАМ).
      - non_replaceable: список dict'ов про CANCELLED. Ключи: id,
        sequence_number, cipher, status, status_display.
    """
    from core.models import Sample, SampleStatus
    if not cascade_changes:
        return 0, [], []

    all_samples = Sample.objects.filter(
        acceptance_act_id=act.id
    ).order_by('sequence_number')

    update_count = all_samples.exclude(status__in=CASCADE_SKIP_STATUSES).count()

    status_labels = dict(SampleStatus.choices)

    replaceable = []
    for s in all_samples.filter(status__in=CASCADE_REPLACEABLE_STATUSES):
        # Последний фактически выпущенный номер документа — для показа в UI.
        # Если уже был ЗАМ — это replacement_pi_number, иначе оригинальный pi_number.
        effective_pi = s.replacement_pi_number or s.pi_number
        replaceable.append({
            'id': s.id,
            'sequence_number': s.sequence_number,
            'cipher': s.cipher,
            'status': s.status,
            'status_display': status_labels.get(s.status, s.status),
            'pi_number': s.pi_number,
            'replacement_pi_number': s.replacement_pi_number,
            'replacement_count': s.replacement_count or 0,
            'effective_pi': effective_pi,
        })

    non_replaceable = [
        {
            'id': s.id,
            'sequence_number': s.sequence_number,
            'cipher': s.cipher,
            'status': s.status,
            'status_display': status_labels.get(s.status, s.status),
        }
        for s in all_samples.filter(status__in=CASCADE_NON_REPLACEABLE_STATUSES)
    ]

    return update_count, replaceable, non_replaceable


def _apply_cascade(act, cascade_changes, request, replace_sample_ids=None):
    """Применяет каскад. Возвращает (updated_count, replaced_count).

    Для активных образцов: обновляет зеркальные поля + при необходимости
    сбрасывает собственный pi_number для пересчёта. cipher пересчитается
    автоматически в Sample.save().

    Для образцов из replace_sample_ids (COMPLETED / REPLACEMENT_PROTOCOL):
    сначала обновляются зеркальные поля (включая accompanying_doc_number —
    это нужно для правильной генерации номера нового ЗАМа), затем вызывается
    sample.initiate_replacement_protocol(request, reason='cascade_from_act',
    source_act_id=act.id) — она инкрементирует replacement_count, генерит
    новый replacement_pi_number от свежих реквизитов и пишет запись в
    audit_log с action='replacement_issued' (там же хранится история,
    которую будет читать шапка протокола).

    ВАЖНО: pi_number замещаемых образцов НЕ трогается — это исторически
    зафиксированный номер выпущенного документа. Новый номер пишется
    только в replacement_pi_number.
    """
    from core.models import Sample

    if not cascade_changes:
        return 0, 0

    replace_sample_ids = set(replace_sample_ids or [])

    # {sample_field: new_value} — только для полей из каскада
    field_updates = {
        CASCADE_FIELDS_MAP[act_field]: new_value
        for act_field, new_value in cascade_changes.items()
    }

    doc_number_changed = 'doc_number' in cascade_changes
    audit_extra = {'act_id': act.id, 'source': 'cascade_from_act'}

    # ─── 1) Активные образцы: обычный каскад ───
    active_samples = (
        Sample.objects.filter(acceptance_act_id=act.id)
        .exclude(status__in=CASCADE_SKIP_STATUSES)
    )

    updated_count = 0
    for sample in active_samples:
        per_sample_changes = {}

        for sample_field, new_value in field_updates.items():
            old_value = getattr(sample, sample_field)
            if old_value != new_value:
                per_sample_changes[sample_field] = (old_value, new_value)
                setattr(sample, sample_field, new_value)

        # pi_number: сбрасываем ТОЛЬКО если accompanying_doc_number меняется
        # И pi_number сейчас собственный (содержит паттерн "/<sequence>-").
        # Паттерн согласован с save_logic.py (строки 191, 317, 666-668).
        if doc_number_changed and sample.pi_number and sample.sequence_number:
            own_pattern = f"/{sample.sequence_number}-"
            if own_pattern in sample.pi_number:
                old_pi = sample.pi_number
                sample.pi_number = ''  # Sample.save() перегенерирует
                per_sample_changes['pi_number'] = (old_pi, '(пересчёт)')

        if not per_sample_changes:
            continue

        sample.save()  # cipher и pi_number пересчитаются автоматически

        log_field_changes(
            request, 'sample', sample.id, per_sample_changes,
            action='cascade_from_act',
            extra_data=audit_extra,
        )
        updated_count += 1

    # ─── 2) Замещаемые образцы: обновляем поля + инициируем ЗАМ ───
    replaced_count = 0
    if replace_sample_ids:
        replace_samples = Sample.objects.filter(
            acceptance_act_id=act.id,
            id__in=replace_sample_ids,
            status__in=CASCADE_REPLACEABLE_STATUSES,
        )

        for sample in replace_samples:
            per_sample_changes = {}

            # 2.1 Обновляем зеркальные поля (accompanying_doc_number и др.)
            # ДО вызова initiate_replacement_protocol — чтобы generate_pi_number
            # внутри него взял уже новые реквизиты.
            for sample_field, new_value in field_updates.items():
                old_value = getattr(sample, sample_field)
                if old_value != new_value:
                    per_sample_changes[sample_field] = (old_value, new_value)
                    setattr(sample, sample_field, new_value)

            # Защита от «ЗАМ на пустом месте»: если на этом образце все поля
            # уже совпадают с новыми (кто-то ранее обновил руками) — ЗАМ не
            # выпускаем, галка пользователя в этом случае эффекта не даёт.
            if not per_sample_changes:
                continue

            # 2.2 pi_number у замещаемых НЕ трогаем — это исторический номер.
            # (Комментарий для явности — никакого кода здесь.)

            # 2.3 Вызываем инициирование ЗАМ. Она сама:
            #   - инкрементирует replacement_count
            #   - генерит replacement_pi_number по ТЕКУЩИМ реквизитам
            #   - ставит replacement_protocol_issued_date = today
            #   - меняет status на REPLACEMENT_PROTOCOL (если был COMPLETED)
            #   - пишет audit-запись 'replacement_issued' с метаданными
            sample.initiate_replacement_protocol(
                request=request,
                reason='cascade_from_act',
                source_act_id=act.id,
            )
            sample.save()

            # Лог каскад-полей как отдельная запись (пополняет audit-лог образца).
            # Запись об инициировании ЗАМа уже сделана внутри initiate_*.
            log_field_changes(
                request, 'sample', sample.id, per_sample_changes,
                action='cascade_from_act',
                extra_data={**audit_extra, 'with_replacement': True},
            )
            replaced_count += 1

    if updated_count or replaced_count:
        logger.info(
            'Cascade applied: act_id=%s, fields=%s, updated=%s, replaced=%s',
            act.id, list(cascade_changes.keys()), updated_count, replaced_count,
        )
    return updated_count, replaced_count


# ─────────────────────────────────────────────────────────────
# Реестр актов
# ─────────────────────────────────────────────────────────────

@login_required
def acts_registry(request):
    if not _check_acts_access(request.user):
        messages.error(request, 'У вас нет доступа к реестру актов')
        return redirect('workspace_home')

    search = request.GET.get('q', '').strip()
    client_id = request.GET.get('client', '')
    work_status = request.GET.get('work_status', '')
    lab_id = request.GET.get('laboratory', '')

    acts = AcceptanceAct.objects.select_related(
        'contract__client', 'created_by', 'client_direct',
        'invoice__client',  # ⭐ v3.62.0
    ).prefetch_related('act_laboratories__laboratory').all()

    if search:
        acts = acts.filter(
            Q(document_name__icontains=search) |
            Q(doc_number__icontains=search) |
            Q(contract__client__name__icontains=search) |
            Q(contract__number__icontains=search) |
            Q(client_direct__name__icontains=search) |
            Q(invoice__client__name__icontains=search)  # ⭐ v3.62.0
        )
    if client_id:
        acts = acts.filter(
            Q(contract__client_id=client_id) |
            Q(invoice__client_id=client_id) |
            Q(client_direct_id=client_id)
        )
    if work_status:
        acts = acts.filter(work_status=work_status)
    if lab_id:
        acts = acts.filter(act_laboratories__laboratory_id=lab_id)

    acts = acts.order_by('-created_at')

    clients = Client.objects.filter(is_active=True).order_by('name')
    laboratories = Laboratory.objects.filter(
        is_active=True, department_type='LAB'
    ).order_by('name')

    acts_data = []
    for act in acts:
        labs = act.act_laboratories.select_related('laboratory').all()
        acts_data.append({
            'act': act,
            'progress': act.progress,
            'deadline_check': act.deadline_check,
            'laboratories': labs,
        })

    return render(request, 'core/acceptance_acts_registry.html', {
        'acts_data': acts_data,
        'total_count': len(acts_data),
        'search': search,
        'filter_client': client_id,
        'filter_work_status': work_status,
        'filter_lab': lab_id,
        'clients': clients,
        'laboratories': laboratories,
        'work_status_choices': ACT_CHOICES['work_status'],
        'display': ACT_DISPLAY,
        'can_edit': _can_edit_acts(request.user),
    })


# ─────────────────────────────────────────────────────────────
# Создание акта
# ─────────────────────────────────────────────────────────────

@login_required
def act_create(request):
    if not _can_edit_acts(request.user):
        messages.error(request, 'Нет прав на создание актов')
        return redirect('acts_registry')

    if request.method == 'POST':
        return _save_act(request, act=None)

    # GET — форма создания
    preset_contract_id = request.GET.get('contract_id', '')
    preset_client_id = request.GET.get('client_id', '')
    preset_invoice_id = request.GET.get('invoice_id', '')
    preset_specification_id = request.GET.get('specification_id', '')

    # v3.37.0: Определяем тип привязки по preset
    # ⭐ v3.56.0: client_only — акт без договора/счёта
    preset_bind_type = 'contract'  # default
    if preset_invoice_id:
        preset_bind_type = 'invoice'
    elif preset_client_id and not preset_contract_id and not preset_invoice_id:
        preset_bind_type = 'client_only'

    clients = Client.objects.filter(is_active=True).order_by('name')
    laboratories = Laboratory.objects.filter(
        is_active=True, department_type__in=['LAB']
    ).order_by('name')

    context = {
        'act': None,
        'clients': clients,
        'laboratories': laboratories,
        'choices': ACT_CHOICES,
        'can_edit': True,
        'preset_contract_id': preset_contract_id,
        'preset_client_id': preset_client_id,
        'preset_invoice_id': preset_invoice_id,
        'preset_specification_id': preset_specification_id,
        'preset_bind_type': preset_bind_type,
    }
    return render(request, 'core/act_detail.html', context)


# ─────────────────────────────────────────────────────────────
# Просмотр / редактирование акта
# ─────────────────────────────────────────────────────────────

@login_required
def act_detail(request, act_id):
    if not _check_acts_access(request.user):
        messages.error(request, 'У вас нет доступа к актам')
        return redirect('workspace_home')

    act = get_object_or_404(
        AcceptanceAct.objects.select_related('contract__client', 'created_by'),
        id=act_id,
    )
    can_edit = _can_edit_acts(request.user)

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'Нет прав на редактирование')
            return redirect('act_detail', act_id=act_id)
        return _save_act(request, act=act)

    # GET — форма просмотра/редактирования
    context = _build_act_detail_context(request, act, can_edit)
    return render(request, 'core/act_detail.html', context)


def _build_act_detail_context(request, act, can_edit,
                              act_lab_ids_override=None,
                              cascade_confirm=None):
    """⭐ v3.85.0: Строит контекст для рендеринга act_detail.html.

    Используется в act_detail GET и при rerender'е формы с баннером
    подтверждения каскада (_save_act при наличии пропускаемых образцов
    и отсутствии confirm_cascade=1 в POST).

    Параметры:
      - act_lab_ids_override: если передан — перекрывает набор лабораторий
        из БД (нужно при rerender'е, чтобы чекбоксы показывали значения
        из POST, а не из БД).
      - cascade_confirm: dict или None. Если dict — передаётся в шаблон
        для отрисовки баннера подтверждения.
    """
    clients = Client.objects.filter(is_active=True).order_by('name')
    laboratories = Laboratory.objects.filter(
        is_active=True, department_type__in=['LAB', 'WORKSHOP']
    ).order_by('name')

    if act_lab_ids_override is not None:
        act_lab_ids = act_lab_ids_override
    else:
        act_lab_ids = set(
            act.act_laboratories.values_list('laboratory_id', flat=True)
        )

    # Образцы по акту
    from core.models import Sample
    samples = Sample.objects.filter(
        acceptance_act_id=act.id
    ).select_related('laboratory').order_by('sequence_number')

    from core.models import Laboratory as Lab
    ALL_LAB_CODES = ['MI', 'ACT', 'TA', 'ChA', 'WORKSHOP']
    all_labs = Lab.objects.filter(code__in=ALL_LAB_CODES).order_by('code')

    labs_progress = []
    for lab in all_labs:
        lab_samples = samples.filter(laboratory_id=lab.id)
        total = lab_samples.count()
        if total == 0:
            labs_progress.append({'laboratory': lab, 'total': 0, 'completed': 0, 'cancelled': 0, 'completed_date': None})
            continue
        completed = lab_samples.filter(status__in=['COMPLETED', 'PROTOCOL_ISSUED']).count()  # ⭐ v3.85.0
        cancelled = lab_samples.filter(status='CANCELLED').count()
        al = act.act_laboratories.filter(laboratory_id=lab.id).first()
        completed_date = None
        if al:
            if (completed + cancelled) == total and not al.completed_date:
                al.completed_date = al.compute_completed_date()
                if al.completed_date:
                    al.save()
            elif al.completed_date and (completed + cancelled) < total:
                al.completed_date = None
                al.save()
            completed_date = al.completed_date
        labs_progress.append({
            'laboratory': lab, 'total': total, 'completed': completed,
            'cancelled': cancelled, 'completed_date': completed_date,
        })

    # Файлы
    act_files = get_files_for_entity(request.user, 'acceptance_act', act.id)
    contract_files = get_files_for_entity(request.user, 'contract', act.contract_id) if act.contract_id else []
    can_edit_files = PermissionChecker.can_edit(request.user, 'FILES', 'clients_files')

    # v3.37.0 + v3.56.0: Определяем тип привязки
    bind_type = 'contract'
    if getattr(act, 'client_direct_id', None) and not act.contract_id and not getattr(act, 'invoice_id', None):
        bind_type = 'client_only'
    elif getattr(act, 'invoice_id', None):
        bind_type = 'invoice'

    # v3.37.0: Наследование финансов
    has_inherited_finance = getattr(act, 'has_inherited_finance', False)
    finance_source_label = getattr(act, 'finance_source_label', '')
    finance_source = getattr(act, 'finance_source', act)

    # ⭐ v3.85.0: Право инициировать выпуск ЗАМа через каскад.
    # Роли-based: не все, кто может редактировать акт, могут выпускать ЗАМы.
    user_role = getattr(request.user, 'role', '') or ''
    can_replace = user_role in CASCADE_REPLACEMENT_ROLES

    context = {
        'act': act,
        'clients': clients,
        'laboratories': laboratories,
        'act_lab_ids': act_lab_ids,
        'choices': ACT_CHOICES,
        'can_edit': can_edit,
        'progress': act.progress,
        'deadline_check': act.deadline_check,
        'samples': samples,
        'labs_progress': labs_progress,
        'act_files': act_files,
        'contract_files': contract_files,
        'can_edit_files': can_edit_files,
        # v3.37.0
        'bind_type': bind_type,
        'has_inherited_finance': has_inherited_finance,
        'finance_source_label': finance_source_label,
        'finance_source': finance_source,
        # ⭐ v3.85.0: баннер подтверждения каскада + право на ЗАМ
        'cascade_confirm': cascade_confirm,
        'can_replace': can_replace,
    }
    return context


# ─────────────────────────────────────────────────────────────
# Сохранение акта (общая логика для create и edit)
# ─────────────────────────────────────────────────────────────

def _save_act(request, act=None):
    """Сохраняет акт. act=None → создание, act=object → редактирование."""
    is_new = act is None

    # --- v3.37.0 + v3.56.0: Определяем тип привязки ---
    bind_type = request.POST.get('bind_type', 'contract').strip()
    contract = None
    invoice = None
    specification = None
    direct_client = None

    # --- Валидация лабораторий по спецификации ---
    lab_ids = request.POST.getlist('laboratories')
    lab_ids = [int(x) for x in lab_ids if x.isdigit()]


    if bind_type == 'client_only':
        # ⭐ v3.56.0: Только заказчик, без договора/счёта
        client_id_str = request.POST.get('client_id', '').strip()
        if not client_id_str:
            messages.error(request, 'Заказчик обязателен')
            return redirect('acts_registry')
        try:
            direct_client = Client.objects.get(id=client_id_str)
        except Client.DoesNotExist:
            messages.error(request, 'Заказчик не найден')
            return redirect('acts_registry')

    elif bind_type == 'invoice':
        # Путь без договора — привязка к счёту
        invoice_id = request.POST.get('invoice_id', '').strip()
        if not invoice_id and Invoice:
            messages.error(request, 'Счёт обязателен')
            return redirect('acts_registry')
        if Invoice:
            try:
                invoice = Invoice.objects.get(id=invoice_id)
            except Invoice.DoesNotExist:
                messages.error(request, 'Счёт не найден')
                return redirect('acts_registry')
    else:
        # Путь с договором
        contract_id = request.POST.get('contract_id', '').strip()
        if not contract_id:
            messages.error(request, 'Договор обязателен')
            return redirect('acts_registry')
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            messages.error(request, 'Договор не найден')
            return redirect('acts_registry')

            # Опциональная спецификация/ТЗ
        spec_id = request.POST.get('specification_id', '').strip()
        if spec_id and Specification:
            try:
                specification = Specification.objects.get(id=spec_id)
            except Specification.DoesNotExist:
                specification = None


        if specification:
            from core.models import SpecificationLaboratory
            allowed_lab_ids = set(
                SpecificationLaboratory.objects.filter(specification=specification)
                .values_list('laboratory_id', flat=True)
            )
            if allowed_lab_ids:
                invalid_labs = set(lab_ids) - allowed_lab_ids
                if invalid_labs:
                    lab_names = list(
                        Laboratory.objects.filter(id__in=invalid_labs).values_list('code_display', flat=True))
                    messages.error(request,
                                   f'Лаборатории {", ".join(lab_names)} не входят в спецификацию «{specification.number}»')
                    return redirect('acts_registry')

    # --- Текстовые / select поля ---
    fields_map = {
        'doc_number': ('doc_number', ''),
        'document_name': ('document_name', ''),
        'document_status': ('document_status', ''),
        'payment_terms': ('payment_terms', ''),
        'comment': ('comment', ''),
        'payment_invoice': ('payment_invoice', ''),
        'completion_act': ('completion_act', ''),
        'invoice_number': ('invoice_number', ''),
        'document_flow': ('document_flow', ''),
        'closing_status': ('closing_status', ''),
        'work_status': ('work_status', 'IN_PROGRESS'),
        'sending_method': ('sending_method', ''),
    }

    data = {}
    for form_name, (field_name, default) in fields_map.items():
        data[field_name] = request.POST.get(form_name, default).strip()

    # v3.38.0: Валидация «только латиница» для doc_number
    if data.get('doc_number') and re.search(r'[а-яА-ЯёЁ]', data['doc_number']):
        messages.error(request, 'Код документа должен содержать только латиницу, цифры и символы: - _ . /')
        return redirect('acts_registry')

    # Даты
    date_fields = ['samples_received_date', 'work_deadline', 'advance_date', 'full_payment_date']
    for df in date_fields:
        val = request.POST.get(df, '').strip()
        data[df] = datetime.strptime(val, '%Y-%m-%d').date() if val else None

    # Числовые
    services_count_str = request.POST.get('services_count', '').strip()
    data['services_count'] = int(services_count_str) if services_count_str else None

    work_cost_str = request.POST.get('work_cost', '').strip()
    try:
        data['work_cost'] = Decimal(work_cost_str) if work_cost_str else None
    except InvalidOperation:
        data['work_cost'] = None

    # Булев
    data['has_subcontract'] = request.POST.get('has_subcontract') == 'on'


    # --- Сохранение ---
    try:
        if is_new:
            act = AcceptanceAct()
            act.created_by = request.user

        old_values = {}
        if not is_new:
            for key in data:
                old_values[key] = getattr(act, key, None)

        # ⭐ v3.85.0: Каскадное наследование АПП → образцы (задачи 1а + 1г).
        # ДО записи акта в БД считаем, какие поля изменились каскадно и
        # нужно ли показать баннер подтверждения. Preview дешёвый (один
        # SELECT) и не пишет ничего в БД.
        #
        # Логика:
        #   - cascade_changes пустой → обычное сохранение, без каскада.
        #   - cascade_changes есть, replaceable+non_replaceable пусты →
        #       применяем каскад на активных образцах сразу.
        #   - cascade_changes есть, есть replaceable/non_replaceable,
        #     confirm_cascade != '1' → перерисовываем форму с баннером,
        #     БД не трогаем.
        #   - cascade_changes есть, confirm_cascade == '1' → применяем
        #     каскад, и для отмеченных галками образцов (replace_sample_ids)
        #     дополнительно выпускаем ЗАМ.
        cascade_changes = {}
        cascade_updated = 0
        cascade_replaced = 0
        replace_sample_ids = set()

        if not is_new:
            cascade_changes = _get_cascade_changes(act, data)
            if cascade_changes:
                update_count, replaceable, non_replaceable = _preview_cascade(
                    act, cascade_changes
                )
                needs_confirm = bool(replaceable or non_replaceable)

                if needs_confirm and request.POST.get('confirm_cascade') != '1':
                    # Показываем баннер подтверждения.
                    # Обновляем act в памяти (БЕЗ save!), чтобы форма отрисовала
                    # введённые пользователем значения, а не старые из БД.
                    act.contract = contract
                    if hasattr(act, 'invoice_id'):
                        act.invoice = invoice
                    if hasattr(act, 'specification_id'):
                        act.specification = specification
                    if hasattr(act, 'client_direct_id'):
                        act.client_direct = direct_client
                    for key, val in data.items():
                        setattr(act, key, val)

                    cascade_confirm = {
                        'changed_fields_labels': [
                            CASCADE_FIELDS_LABELS[f] for f in cascade_changes
                            if f in CASCADE_FIELDS_LABELS
                        ],
                        'update_count': update_count,
                        'replaceable': replaceable,
                        'non_replaceable': non_replaceable,
                    }
                    context = _build_act_detail_context(
                        request, act, can_edit=True,
                        act_lab_ids_override=set(lab_ids),
                        cascade_confirm=cascade_confirm,
                    )
                    return render(request, 'core/act_detail.html', context)

                # Подтверждено (или не было чего подтверждать) — собираем
                # выбранные для ЗАМа ID и продолжаем сохранение.
                if request.POST.get('confirm_cascade') == '1':
                    user_role = getattr(request.user, 'role', '') or ''
                    if user_role in CASCADE_REPLACEMENT_ROLES:
                        replace_sample_ids = {
                            int(x) for x in request.POST.getlist('replace_sample_ids')
                            if x.isdigit()
                        }
                        # Safety: принимаем только те ID, которые реально в
                        # replaceable (защита от подмены ID в POST'е).
                        allowed_ids = {r['id'] for r in replaceable}
                        replace_sample_ids &= allowed_ids

        # v3.37.0 + v3.56.0: Привязки
        act.contract = contract
        if hasattr(act, 'invoice_id'):
            act.invoice = invoice
        if hasattr(act, 'specification_id'):
            act.specification = specification
        # ⭐ v3.56.0: Прямая привязка к заказчику
        if hasattr(act, 'client_direct_id'):
            act.client_direct = direct_client

        for key, val in data.items():
            setattr(act, key, val)
        act.save()

        # M2M лаборатории
        existing_lab_ids = set(
            AcceptanceActLaboratory.objects.filter(act=act).values_list('laboratory_id', flat=True)
        )
        new_lab_ids = set(lab_ids)
        for lid in new_lab_ids - existing_lab_ids:
            AcceptanceActLaboratory.objects.create(act=act, laboratory_id=lid)
        AcceptanceActLaboratory.objects.filter(
            act=act, laboratory_id__in=existing_lab_ids - new_lab_ids
        ).delete()

        # ⭐ v3.85.0: Применяем каскад ПОСЛЕ сохранения акта.
        if cascade_changes:
            cascade_updated, cascade_replaced = _apply_cascade(
                act, cascade_changes, request,
                replace_sample_ids=replace_sample_ids,
            )

        # Аудит
        if is_new:
            extra = {'document_name': act.document_name, 'doc_number': act.doc_number}
            if contract:
                extra['contract_id'] = contract.id
            if invoice:
                extra['invoice_id'] = invoice.id
            if direct_client:
                extra['client_id'] = direct_client.id
            log_action(request, 'acceptance_act', act.id, 'act_created', extra_data=extra)
            messages.success(request, f'Акт «{act.document_name or act.doc_number}» создан')
        else:
            changes = {}
            for key in data:
                old_val = old_values.get(key)
                new_val = getattr(act, key)
                if str(old_val or '') != str(new_val or ''):
                    changes[key] = (old_val, new_val)
            if changes:
                log_field_changes(request, 'acceptance_act', act.id, changes, action='act_updated')
            # ⭐ v3.85.0: Сообщение с количеством каскадно обновлённых и выпущенных ЗАМов
            msg = f'Акт «{act.document_name or act.doc_number}» обновлён'
            tail = []
            if cascade_updated:
                tail.append(f'каскадно обновлено образцов: {cascade_updated}')
            if cascade_replaced:
                tail.append(f'выпущено ЗАМ: {cascade_replaced}')
            if tail:
                msg += ' (' + ', '.join(tail) + ')'
            messages.success(request, msg)

        if is_new:
            return redirect(f'/workspace/acceptance-acts/{act.id}/?upload=1')
        return redirect('act_detail', act_id=act.id)

    except Exception as e:
        logger.exception('Ошибка сохранения акта')
        messages.error(request, f'Ошибка: {e}')
        return redirect('acts_registry')


# ─────────────────────────────────────────────────────────────
# AJAX APIs
# ─────────────────────────────────────────────────────────────

@login_required
def api_contract_acts(request, contract_id):
    """Возвращает JSON список актов для данного договора."""
    acts = AcceptanceAct.objects.filter(contract_id=contract_id).order_by('-created_at')
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
            'progress': act.progress,
        })
    return JsonResponse(result, safe=False)


@login_required
def api_client_invoices(request, client_id):
    """v3.37.0: Возвращает JSON список счетов для заказчика."""
    if not Invoice:
        return JsonResponse([], safe=False)
    invoices = Invoice.objects.filter(
        client_id=client_id, status='ACTIVE'
    ).order_by('-date')
    result = []
    for inv in invoices:
        result.append({
            'id': inv.id,
            'number': inv.number,
            'date': str(inv.date),
            'work_cost': str(inv.work_cost) if inv.work_cost else '',
            'services_count': inv.services_count or '',
            'payment_terms': inv.payment_terms or '',
            'payment_invoice': inv.payment_invoice or '',
            'advance_date': str(inv.advance_date) if inv.advance_date else '',
            'full_payment_date': str(inv.full_payment_date) if inv.full_payment_date else '',
            'completion_act': inv.completion_act or '',
            'invoice_number': inv.invoice_number or '',
            'document_flow': inv.document_flow or '',
            'closing_status': inv.closing_status or '',
            'sending_method': inv.sending_method or '',
        })
    return JsonResponse(result, safe=False)


@login_required
def api_contract_specifications(request, contract_id):
    """v3.37.0: Возвращает JSON список спецификаций/ТЗ для договора."""
    if not Specification:
        return JsonResponse([], safe=False)
    specs = Specification.objects.filter(
        contract_id=contract_id
    ).order_by('-date')
    result = []
    for spec in specs:
        from core.models import SpecificationLaboratory
        lab_ids = list(SpecificationLaboratory.objects.filter(
            specification=spec
        ).values_list('laboratory_id', flat=True))
        result.append({
            'id': spec.id,
            'spec_type': spec.spec_type,
            'number': spec.number,
            'date': str(spec.date) if spec.date else '',
            'work_deadline': str(spec.work_deadline) if spec.work_deadline else '',
            'work_cost': str(spec.work_cost) if spec.work_cost else '',
            'services_count': spec.services_count or '',
            'payment_terms': spec.payment_terms or '',
            'payment_invoice': spec.payment_invoice or '',
            'advance_date': str(spec.advance_date) if spec.advance_date else '',
            'full_payment_date': str(spec.full_payment_date) if spec.full_payment_date else '',
            'completion_act': spec.completion_act or '',
            'invoice_number': spec.invoice_number or '',
            'document_flow': spec.document_flow or '',
            'closing_status': spec.closing_status or '',
            'sending_method': spec.sending_method or '',
            'notes': spec.notes or '',
            'status': spec.status,
            'laboratory_ids': lab_ids,
        })
    return JsonResponse(result, safe=False)


# ─────────────────────────────────────────────────────────────
# ⭐ v3.56.0: Акты по заказчику (без договора/счёта)
# ─────────────────────────────────────────────────────────────

@login_required
def api_client_acts(request, client_id):
    """Возвращает JSON список актов, привязанных напрямую к заказчику."""
    acts = AcceptanceAct.objects.filter(
        client_direct_id=client_id,
    ).order_by('-created_at')
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


# ⭐ v3.71.0: API — образцы конкретного акта (для модалки в sample_create)
@login_required
def api_act_samples(request, act_id):
    """Возвращает JSON-список образцов, прикреплённых к данному акту
    (кроме отменённых). Используется в модалке «Образцы акта» при
    создании нового образца.

    Формат ответа:
    {
        "act": {"id": ..., "doc_number": "...", "document_name": "..."},
        "samples": [
            {
                "id": 101,
                "sequence_number": 42,
                "cipher": "260408_3_CB-17_C_RTD",
                "laboratory": "ЛИМ",
                "standards": ["ГОСТ 1497-84", "ISO 527-1"],
                "status": "TESTED",
                "status_display": "Испытан",
                "detail_url": "/workspace/samples/101/",
            },
            ...
        ]
    }
    """
    from core.models.sample import Sample, SampleStatus

    act = get_object_or_404(AcceptanceAct, id=act_id)

    # Все образцы этого акта, кроме отменённых
    samples_qs = (
        Sample.objects
        .filter(acceptance_act_id=act.id)
        .exclude(status='CANCELLED')
        .select_related('laboratory')
        .prefetch_related('standards')
        .order_by('sequence_number')
    )

    # Получаем человекочитаемые метки статусов
    status_labels = dict(SampleStatus.choices)

    samples_data = []
    for s in samples_qs:
        standards_codes = [
            std.code for std in s.standards.all() if getattr(std, 'code', None)
        ]
        laboratory_name = ''
        if s.laboratory:
            # code_display — если есть, иначе name / code
            laboratory_name = (
                getattr(s.laboratory, 'code_display', None)
                or getattr(s.laboratory, 'name', None)
                or getattr(s.laboratory, 'code', '')
                or ''
            )
        samples_data.append({
            'id': s.id,
            'sequence_number': s.sequence_number,
            'cipher': s.cipher,
            'laboratory': laboratory_name,
            'standards': standards_codes,
            'status': s.status,
            'status_display': status_labels.get(s.status, s.status),
            'detail_url': f'/workspace/samples/{s.id}/',
        })

    return JsonResponse({
        'act': {
            'id': act.id,
            'doc_number': act.doc_number,
            'document_name': act.document_name,
        },
        'samples': samples_data,
    })
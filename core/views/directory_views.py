"""
CISIS v3.37.0 — Справочник заказчиков, договоров и контактов + реестр актов

Файл: core/views/directory_views.py
Действие: ПОЛНАЯ ЗАМЕНА файла

Изменения v3.37.0:
- Объединённая страница с табами: Заказчики | Реестр актов
- Единый view clients_and_acts_page для обоих табов
- CRUD заказчиков/договоров/контактов — без изменений
"""

import logging
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count

from core.models import Client, Contract, ClientContact
from core.models import AcceptanceAct, AcceptanceActLaboratory, Laboratory
from core.models import Invoice, Specification, SpecificationLaboratory
from core.models import ClosingDocumentBatch, ClosingBatchAct
from core.views.audit import log_action, log_field_changes
from core.permissions import PermissionChecker

logger = logging.getLogger(__name__)


def _check_clients_access(user):
    return PermissionChecker.can_view(user, 'CLIENTS', 'access')

def _can_edit_clients(user):
    return PermissionChecker.can_edit(user, 'CLIENTS', 'access')


ACT_WORK_STATUS_CHOICES = [
    ('IN_PROGRESS', 'В работе'),
    ('CLOSED', 'Работы закрыты'),
    ('CANCELLED', 'Отмена'),
]


# ─────────────────────────────────────────────────────────────
# Единая страница: Заказчики + Реестр актов (табы)
# ─────────────────────────────────────────────────────────────

@login_required
def clients_and_acts_page(request):
    if not _check_clients_access(request.user):
        messages.error(request, 'У вас нет доступа к справочнику заказчиков')
        return redirect('workspace_home')

    active_tab = request.GET.get('tab', 'clients')
    can_edit = _can_edit_clients(request.user)

    # ═══ TAB 1: Заказчики (плоская таблица) ═══
    clients_search = request.GET.get('q', '').strip() if active_tab == 'clients' else ''
    show_inactive = request.GET.get('show_inactive') == '1'

    clients_qs = Client.objects.annotate(
        contracts_count=Count('contracts', distinct=True),
        active_contracts_count=Count('contracts', filter=Q(contracts__status='ACTIVE'), distinct=True),
    )
    if not show_inactive:
        clients_qs = clients_qs.filter(is_active=True)
    if clients_search:
        clients_qs = clients_qs.filter(Q(name__icontains=clients_search) | Q(inn__icontains=clients_search))
    clients_qs = clients_qs.order_by('name')

    clients_data = []
    for client in clients_qs:
        acts_count = AcceptanceAct.objects.filter(
            Q(contract__client=client) | Q(invoice__client=client) | Q(client_direct=client)  # ⭐ v3.63.0
        ).count()
        invoices_count = Invoice.objects.filter(client=client).count()
        contacts_count = ClientContact.objects.filter(client=client).count()
        clients_data.append({
            'client': client,
            'contracts_count': client.contracts_count,
            'active_contracts_count': client.active_contracts_count,
            'invoices_count': invoices_count,
            'acts_count': acts_count,
            'contacts_count': contacts_count,
        })

    # ═══ TAB 2: Реестр актов ═══
    acts_search = request.GET.get('q', '').strip() if active_tab == 'acts' else ''
    acts_client_id = request.GET.get('client', '') if active_tab == 'acts' else ''
    acts_work_status = request.GET.get('work_status', '') if active_tab == 'acts' else ''
    acts_lab_id = request.GET.get('laboratory', '') if active_tab == 'acts' else ''

    acts_qs = AcceptanceAct.objects.select_related(
        'contract__client', 'created_by', 'client_direct', 'invoice__client',  # ⭐ v3.63.0
    ).prefetch_related('act_laboratories__laboratory').all()

    if acts_search:
        acts_qs = acts_qs.filter(
            Q(document_name__icontains=acts_search) |
            Q(doc_number__icontains=acts_search) |
            Q(contract__client__name__icontains=acts_search) |
            Q(contract__number__icontains=acts_search) |
            Q(client_direct__name__icontains=acts_search) |  # ⭐ v3.63.0
            Q(invoice__client__name__icontains=acts_search)  # ⭐ v3.63.0
        )
    if acts_client_id:
        acts_qs = acts_qs.filter(
            Q(contract__client_id=acts_client_id) |
            Q(invoice__client_id=acts_client_id) |  # ⭐ v3.63.0
            Q(client_direct_id=acts_client_id)      # ⭐ v3.63.0
        )
    if acts_work_status:
        acts_qs = acts_qs.filter(work_status=acts_work_status)
    if acts_lab_id:
        acts_qs = acts_qs.filter(act_laboratories__laboratory_id=acts_lab_id)
    acts_qs = acts_qs.order_by('-created_at')

    acts_data = []
    for act in acts_qs:
        labs = act.act_laboratories.select_related('laboratory').all()
        acts_data.append({
            'act': act,
            'progress': act.progress,
            'deadline_check': act.deadline_check,
            'laboratories': labs,
        })

    filter_clients = Client.objects.filter(is_active=True).order_by('name')
    laboratories = Laboratory.objects.filter(is_active=True, department_type='LAB').order_by('name')

    # ═══ TAB 3: Закрывающие документы (батчи + все акты) ═══
    batches_qs = ClosingDocumentBatch.objects.prefetch_related(
        'acts__contract__client', 'acts__invoice__client'
    ).order_by('-created_at')

    batches_data = []
    for batch in batches_qs:
        batch_acts = batch.acts.all()
        first_act = batch_acts.first()
        batch_client = None
        if first_act:
            batch_client = first_act.client
        batches_data.append({
            'batch': batch,
            'acts': batch_acts,
            'acts_count': batch_acts.count(),
            'client': batch_client,
        })

    # Все акты для сводной таблицы закрывающих
    closing_acts = AcceptanceAct.objects.select_related(
        'contract__client', 'invoice__client', 'specification'
    ).order_by('-created_at')

    closing_filter_client = request.GET.get('cl_client', '') if active_tab == 'closing' else ''
    closing_filter_status = request.GET.get('cl_status', '') if active_tab == 'closing' else ''
    if closing_filter_client:
        closing_acts = closing_acts.filter(
            Q(contract__client_id=closing_filter_client) |
            Q(invoice__client_id=closing_filter_client) |
            Q(client_direct_id=closing_filter_client)  # ⭐ v3.63.0
        )
    if closing_filter_status:
        if closing_filter_status == 'EMPTY':
            closing_acts = closing_acts.filter(
                Q(closing_status='') | Q(closing_status__isnull=True),
                specification__isnull=True, invoice__isnull=True,
            )
        else:
            closing_acts = closing_acts.filter(closing_status=closing_filter_status)

    closing_acts_data = []
    for act in closing_acts:
        fs = act.finance_source
        batch_link = None
        batch_obj = ClosingBatchAct.objects.filter(act=act).select_related('batch').first()
        if batch_obj:
            batch_link = batch_obj.batch
        closing_acts_data.append({
            'act': act,
            'finance_source': fs,
            'source_label': act.finance_source_label if act.has_inherited_finance else '',
            'batch': batch_link,
        })

    return render(request, 'core/directory_clients.html', {
        'active_tab': active_tab,
        'can_edit': can_edit,
        # Tab 1
        'clients_data': clients_data,
        'clients_search': clients_search,
        'show_inactive': show_inactive,
        'clients_total': len(clients_data),
        # Tab 2
        'acts_data': acts_data,
        'acts_total': len(acts_data),
        'acts_search': acts_search,
        'acts_filter_client': acts_client_id,
        'acts_filter_work_status': acts_work_status,
        'acts_filter_lab': acts_lab_id,
        'filter_clients': filter_clients,
        'laboratories': laboratories,
        'work_status_choices': ACT_WORK_STATUS_CHOICES,
        # Tab 3
        'batches_data': batches_data,
        'batches_total': len(batches_data),
        'closing_acts_data': closing_acts_data,
        'closing_acts_total': len(closing_acts_data),
        'closing_filter_client': closing_filter_client,
        'closing_filter_status': closing_filter_status,

        'closing_status_choices': [
            ('', 'Все'),
            ('EMPTY', 'Не заполнен'),
            ('PREPARED', 'Подготовлено'),
            ('SENT_TO_CLIENT', 'Передано заказчику'),
            ('RECEIVED', 'Получено'),
            ('CANCELLED', 'Отмена'),
        ],
    })


# Обратная совместимость: старый URL → редирект
@login_required
def clients_list(request):
    params = request.GET.urlencode()
    url = '/workspace/clients/' + ('?' + params if params else '')
    return redirect(url)


# ─────────────────────────────────────────────────────────────
# Заказчики — CRUD
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def client_create(request):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    name = request.POST.get('name', '').strip()
    inn = request.POST.get('inn', '').strip()
    address = request.POST.get('address', '').strip()
    if not name:
        messages.error(request, 'Название заказчика обязательно')
        return redirect('directory_clients')
    if Client.objects.filter(name__iexact=name).exists():
        messages.error(request, f'Заказчик «{name}» уже существует')
        return redirect('directory_clients')
    try:
        client = Client.objects.create(name=name, inn=inn, address=address, is_active=True)
        log_action(request, 'client', client.id, 'client_created', extra_data={'name': name})
        messages.success(request, f'Заказчик «{name}» создан')
        return redirect('client_detail', client_id=client.id)
    except Exception as e:
        logger.exception('Ошибка создания заказчика')
        messages.error(request, f'Ошибка: {e}')
    return redirect('directory_clients')


@login_required
@require_POST
def client_edit(request, client_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    client = get_object_or_404(Client, id=client_id)
    name = request.POST.get('name', '').strip()
    inn = request.POST.get('inn', '').strip()
    address = request.POST.get('address', '').strip()
    if not name:
        messages.error(request, 'Название заказчика обязательно')
        return redirect('client_detail', client_id=client_id)
    if Client.objects.filter(name__iexact=name).exclude(id=client_id).exists():
        messages.error(request, f'Заказчик «{name}» уже существует')
        return redirect('client_detail', client_id=client_id)
    changes = {}
    if client.name != name: changes['name'] = (client.name, name); client.name = name
    if (client.inn or '') != inn: changes['inn'] = (client.inn, inn); client.inn = inn
    if (client.address or '') != address: changes['address'] = (client.address, address); client.address = address
    if changes:
        client.save()
        log_field_changes(request, 'client', client.id, changes, action='client_updated')
        messages.success(request, f'Заказчик «{name}» обновлён')
    else:
        messages.info(request, 'Изменений не обнаружено')
    return redirect('client_detail', client_id=client_id)


@login_required
@require_POST
def client_toggle(request, client_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    client = get_object_or_404(Client, id=client_id)
    old_active = client.is_active
    client.is_active = not client.is_active
    client.save()
    log_action(request, 'client', client.id, 'client_toggled',
               field_name='is_active', old_value=old_active, new_value=client.is_active)
    status_text = 'активирован' if client.is_active else 'деактивирован'
    messages.success(request, f'Заказчик «{client.name}» {status_text}')
    if not client.is_active:
        return redirect('/workspace/clients/?show_inactive=1')
    return redirect('directory_clients')


# ─────────────────────────────────────────────────────────────
# Договоры — CRUD
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def contract_create(request, client_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    client = get_object_or_404(Client, id=client_id)
    number = request.POST.get('number', '').strip()
    date_str = request.POST.get('date', '').strip()
    end_date_str = request.POST.get('end_date', '').strip()
    notes = request.POST.get('notes', '').strip()
    if not number or not date_str:
        messages.error(request, 'Номер и дата договора обязательны')
        return redirect('client_detail', client_id=client_id)
    try:
        contract_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        contract = Contract.objects.create(
            client=client, number=number, date=contract_date,
            end_date=end_date, status='ACTIVE', notes=notes,
        )
        log_action(request, 'contract', contract.id, 'contract_created',
                   extra_data={'number': number, 'client_id': client_id})
        messages.success(request, f'Договор «{number}» создан для {client.name}')
        return redirect(f'/workspace/clients/{client_id}/detail/?upload_contract={contract.id}')
    except Exception as e:
        logger.exception('Ошибка создания договора')
        messages.error(request, f'Ошибка: {e}')
    return redirect('client_detail', client_id=client_id)


@login_required
@require_POST
def contract_edit(request, contract_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    contract = get_object_or_404(Contract, id=contract_id)
    number = request.POST.get('number', '').strip()
    date_str = request.POST.get('date', '').strip()
    end_date_str = request.POST.get('end_date', '').strip()
    notes = request.POST.get('notes', '').strip()
    status = request.POST.get('status', 'ACTIVE').strip()
    if not number or not date_str:
        messages.error(request, 'Номер и дата договора обязательны')
        return redirect('client_detail', client_id=contract.client_id)
    try:
        new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        changes = {}
        if contract.number != number: changes['number'] = (contract.number, number); contract.number = number
        if contract.date != new_date: changes['date'] = (str(contract.date), str(new_date)); contract.date = new_date
        if contract.end_date != new_end_date: changes['end_date'] = (str(contract.end_date), str(new_end_date)); contract.end_date = new_end_date
        if (contract.notes or '') != notes: changes['notes'] = (contract.notes, notes); contract.notes = notes
        if contract.status != status: changes['status'] = (contract.status, status); contract.status = status
        if changes:
            contract.save()
            log_field_changes(request, 'contract', contract.id, changes, action='contract_updated')
            messages.success(request, f'Договор «{number}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования договора')
        messages.error(request, f'Ошибка: {e}')
    return redirect('client_detail', client_id=contract.client_id)


@login_required
@require_POST
def contract_toggle(request, contract_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    contract = get_object_or_404(Contract, id=contract_id)
    old_status = contract.status
    contract.status = 'CLOSED' if contract.status == 'ACTIVE' else 'ACTIVE'
    contract.save()
    log_action(request, 'contract', contract.id, 'contract_toggled',
               field_name='status', old_value=old_status, new_value=contract.status)
    status_text = 'активирован' if contract.status == 'ACTIVE' else 'закрыт'
    messages.success(request, f'Договор «{contract.number}» {status_text}')
    return redirect('client_detail', client_id=contract.client_id)


# ─────────────────────────────────────────────────────────────
# Счета (Invoice) — CRUD
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def invoice_create(request, client_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    client = get_object_or_404(Client, id=client_id)
    number = request.POST.get('number', '').strip()
    date_str = request.POST.get('date', '').strip()

    if not number or not date_str:
        messages.error(request, 'Номер и дата счёта обязательны')
        return redirect('client_detail', client_id=client_id)

    try:
        from decimal import Decimal, InvalidOperation
        invoice_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        work_cost_str = request.POST.get('work_cost', '').strip()
        work_cost = None
        if work_cost_str:
            try: work_cost = Decimal(work_cost_str)
            except InvalidOperation: work_cost = None

        services_count_str = request.POST.get('services_count', '').strip()
        services_count = int(services_count_str) if services_count_str else None

        advance_str = request.POST.get('advance_date', '').strip()
        advance_date = datetime.strptime(advance_str, '%Y-%m-%d').date() if advance_str else None
        full_str = request.POST.get('full_payment_date', '').strip()
        full_payment_date = datetime.strptime(full_str, '%Y-%m-%d').date() if full_str else None

        invoice = Invoice.objects.create(
            client=client, number=number, date=invoice_date,
            services_count=services_count,
            work_cost=work_cost,
            payment_terms=request.POST.get('payment_terms', '').strip(),
            payment_invoice=request.POST.get('payment_invoice', '').strip(),
            advance_date=advance_date,
            full_payment_date=full_payment_date,
            completion_act=request.POST.get('completion_act', '').strip(),
            invoice_number=request.POST.get('invoice_number', '').strip(),
            document_flow=request.POST.get('document_flow', '').strip(),
            closing_status=request.POST.get('closing_status', '').strip(),
            sending_method=request.POST.get('sending_method', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            status='ACTIVE',
            created_by=request.user,
        )
        log_action(request, 'invoice', invoice.id, 'invoice_created',
                   extra_data={'number': number, 'client_id': client_id})
        messages.success(request, f'Счёт «{number}» создан для {client.name}')
    except Exception as e:
        logger.exception('Ошибка создания счёта')
        messages.error(request, f'Ошибка: {e}')

    return redirect('client_detail', client_id=client_id)


@login_required
@require_POST
def invoice_edit(request, invoice_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    invoice = get_object_or_404(Invoice, id=invoice_id)
    number = request.POST.get('number', '').strip()
    date_str = request.POST.get('date', '').strip()

    if not number or not date_str:
        messages.error(request, 'Номер и дата счёта обязательны')
        return redirect('client_detail', client_id=invoice.client_id)

    try:
        from decimal import Decimal, InvalidOperation
        new_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        work_cost_str = request.POST.get('work_cost', '').strip()
        new_work_cost = None
        if work_cost_str:
            try: new_work_cost = Decimal(work_cost_str)
            except InvalidOperation: new_work_cost = None

        services_str = request.POST.get('services_count', '').strip()
        new_services = int(services_str) if services_str else None

        advance_str = request.POST.get('advance_date', '').strip()
        new_advance = datetime.strptime(advance_str, '%Y-%m-%d').date() if advance_str else None
        full_str = request.POST.get('full_payment_date', '').strip()
        new_full = datetime.strptime(full_str, '%Y-%m-%d').date() if full_str else None

        text_fields = {
            'payment_terms': request.POST.get('payment_terms', '').strip(),
            'payment_invoice': request.POST.get('payment_invoice', '').strip(),
            'completion_act': request.POST.get('completion_act', '').strip(),
            'invoice_number': request.POST.get('invoice_number', '').strip(),
            'document_flow': request.POST.get('document_flow', '').strip(),
            'closing_status': request.POST.get('closing_status', '').strip(),
            'sending_method': request.POST.get('sending_method', '').strip(),
            'notes': request.POST.get('notes', '').strip(),
        }

        changes = {}
        if invoice.number != number:
            changes['number'] = (invoice.number, number); invoice.number = number
        if invoice.date != new_date:
            changes['date'] = (str(invoice.date), str(new_date)); invoice.date = new_date
        if invoice.work_cost != new_work_cost:
            changes['work_cost'] = (str(invoice.work_cost), str(new_work_cost)); invoice.work_cost = new_work_cost
        if invoice.services_count != new_services:
            changes['services_count'] = (invoice.services_count, new_services); invoice.services_count = new_services
        if invoice.advance_date != new_advance:
            changes['advance_date'] = (str(invoice.advance_date), str(new_advance)); invoice.advance_date = new_advance
        if invoice.full_payment_date != new_full:
            changes['full_payment_date'] = (str(invoice.full_payment_date), str(new_full)); invoice.full_payment_date = new_full

        for field, new_val in text_fields.items():
            old_val = getattr(invoice, field, '') or ''
            if old_val != new_val:
                changes[field] = (old_val, new_val)
                setattr(invoice, field, new_val)

        if changes:
            invoice.save()
            log_field_changes(request, 'invoice', invoice.id, changes, action='invoice_updated')
            messages.success(request, f'Счёт «{number}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования счёта')
        messages.error(request, f'Ошибка: {e}')

    return redirect('client_detail', client_id=invoice.client_id)


@login_required
@require_POST
def invoice_toggle(request, invoice_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    invoice = get_object_or_404(Invoice, id=invoice_id)
    old_status = invoice.status
    invoice.status = 'CLOSED' if invoice.status == 'ACTIVE' else 'ACTIVE'
    invoice.save()
    log_action(request, 'invoice', invoice.id, 'invoice_toggled',
               field_name='status', old_value=old_status, new_value=invoice.status)
    status_text = 'активирован' if invoice.status == 'ACTIVE' else 'закрыт'
    messages.success(request, f'Счёт «{invoice.number}» {status_text}')
    return redirect('client_detail', client_id=invoice.client_id)


# ─────────────────────────────────────────────────────────────
# Спецификации / ТЗ — CRUD
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def specification_create(request, contract_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    contract = get_object_or_404(Contract, id=contract_id)

    number = request.POST.get('number', '').strip()
    spec_type = request.POST.get('spec_type', 'SPEC').strip()
    date_str = request.POST.get('date', '').strip()
    deadline_str = request.POST.get('work_deadline', '').strip()

    if not number:
        messages.error(request, 'Номер спецификации обязателен')
        return redirect('client_detail', client_id=contract.client_id)

    try:
        from decimal import Decimal, InvalidOperation
        spec_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        work_deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        work_cost_str = request.POST.get('work_cost', '').strip()
        work_cost = None
        if work_cost_str:
            try: work_cost = Decimal(work_cost_str)
            except InvalidOperation: work_cost = None

        services_str = request.POST.get('services_count', '').strip()
        services_count = int(services_str) if services_str else None

        advance_str = request.POST.get('advance_date', '').strip()
        advance_date = datetime.strptime(advance_str, '%Y-%m-%d').date() if advance_str else None
        full_str = request.POST.get('full_payment_date', '').strip()
        full_payment_date = datetime.strptime(full_str, '%Y-%m-%d').date() if full_str else None

        spec = Specification.objects.create(
            contract=contract, spec_type=spec_type,
            number=number, date=spec_date, work_deadline=work_deadline,
            services_count=services_count, work_cost=work_cost,
            payment_terms=request.POST.get('payment_terms', '').strip(),
            payment_invoice=request.POST.get('payment_invoice', '').strip(),
            advance_date=advance_date, full_payment_date=full_payment_date,
            completion_act=request.POST.get('completion_act', '').strip(),
            invoice_number=request.POST.get('invoice_number', '').strip(),
            document_flow=request.POST.get('document_flow', '').strip(),
            closing_status=request.POST.get('closing_status', '').strip(),
            sending_method=request.POST.get('sending_method', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            status='ACTIVE', created_by=request.user,
        )

        lab_ids = request.POST.getlist('laboratories')
        for lid in lab_ids:
            if lid.isdigit():
                SpecificationLaboratory.objects.create(specification=spec, laboratory_id=int(lid))

        type_label = 'ТЗ' if spec_type == 'TZ' else 'Спецификация'
        log_action(request, 'specification', spec.id, 'specification_created',
                   extra_data={'number': number, 'contract_id': contract_id, 'spec_type': spec_type})
        messages.success(request, f'{type_label} «{number}» создана для договора {contract.number}')
    except Exception as e:
        logger.exception('Ошибка создания спецификации')
        messages.error(request, f'Ошибка: {e}')

    return redirect('client_detail', client_id=contract.client_id)


@login_required
@require_POST
def specification_edit(request, spec_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    spec = get_object_or_404(Specification, id=spec_id)

    number = request.POST.get('number', '').strip()
    if not number:
        messages.error(request, 'Номер спецификации обязателен')
        return redirect('client_detail', client_id=spec.contract.client_id)

    try:
        from decimal import Decimal, InvalidOperation

        date_str = request.POST.get('date', '').strip()
        new_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        deadline_str = request.POST.get('work_deadline', '').strip()
        new_deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        work_cost_str = request.POST.get('work_cost', '').strip()
        new_work_cost = None
        if work_cost_str:
            try: new_work_cost = Decimal(work_cost_str)
            except InvalidOperation: new_work_cost = None

        services_str = request.POST.get('services_count', '').strip()
        new_services = int(services_str) if services_str else None

        advance_str = request.POST.get('advance_date', '').strip()
        new_advance = datetime.strptime(advance_str, '%Y-%m-%d').date() if advance_str else None
        full_str = request.POST.get('full_payment_date', '').strip()
        new_full = datetime.strptime(full_str, '%Y-%m-%d').date() if full_str else None

        new_spec_type = request.POST.get('spec_type', spec.spec_type).strip()

        text_fields = {
            'payment_terms': request.POST.get('payment_terms', '').strip(),
            'payment_invoice': request.POST.get('payment_invoice', '').strip(),
            'completion_act': request.POST.get('completion_act', '').strip(),
            'invoice_number': request.POST.get('invoice_number', '').strip(),
            'document_flow': request.POST.get('document_flow', '').strip(),
            'closing_status': request.POST.get('closing_status', '').strip(),
            'sending_method': request.POST.get('sending_method', '').strip(),
            'notes': request.POST.get('notes', '').strip(),
        }

        changes = {}
        if spec.number != number: changes['number'] = (spec.number, number); spec.number = number
        if spec.spec_type != new_spec_type: changes['spec_type'] = (spec.spec_type, new_spec_type); spec.spec_type = new_spec_type
        if spec.date != new_date: changes['date'] = (str(spec.date), str(new_date)); spec.date = new_date
        if spec.work_deadline != new_deadline: changes['work_deadline'] = (str(spec.work_deadline), str(new_deadline)); spec.work_deadline = new_deadline
        if spec.work_cost != new_work_cost: changes['work_cost'] = (str(spec.work_cost), str(new_work_cost)); spec.work_cost = new_work_cost
        if spec.services_count != new_services: changes['services_count'] = (spec.services_count, new_services); spec.services_count = new_services
        if spec.advance_date != new_advance: changes['advance_date'] = (str(spec.advance_date), str(new_advance)); spec.advance_date = new_advance
        if spec.full_payment_date != new_full: changes['full_payment_date'] = (str(spec.full_payment_date), str(new_full)); spec.full_payment_date = new_full

        for field, new_val in text_fields.items():
            old_val = getattr(spec, field, '') or ''
            if old_val != new_val:
                changes[field] = (old_val, new_val)
                setattr(spec, field, new_val)

        lab_ids = set(int(x) for x in request.POST.getlist('laboratories') if x.isdigit())
        existing_lab_ids = set(SpecificationLaboratory.objects.filter(specification=spec).values_list('laboratory_id', flat=True))
        if lab_ids != existing_lab_ids:
            changes['laboratories'] = (list(existing_lab_ids), list(lab_ids))
            for lid in lab_ids - existing_lab_ids:
                SpecificationLaboratory.objects.create(specification=spec, laboratory_id=lid)
            SpecificationLaboratory.objects.filter(specification=spec, laboratory_id__in=existing_lab_ids - lab_ids).delete()

        if changes:
            spec.save()
            log_field_changes(request, 'specification', spec.id, changes, action='specification_updated')
            messages.success(request, f'Спецификация «{number}» обновлена')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования спецификации')
        messages.error(request, f'Ошибка: {e}')

    return redirect('client_detail', client_id=spec.contract.client_id)


@login_required
@require_POST
def specification_toggle(request, spec_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    spec = get_object_or_404(Specification, id=spec_id)
    old_status = spec.status
    spec.status = 'CLOSED' if spec.status == 'ACTIVE' else 'ACTIVE'
    spec.save()
    log_action(request, 'specification', spec.id, 'specification_toggled',
               field_name='status', old_value=old_status, new_value=spec.status)
    status_text = 'активирована' if spec.status == 'ACTIVE' else 'закрыта'
    type_label = 'ТЗ' if spec.spec_type == 'TZ' else 'Спецификация'
    messages.success(request, f'{type_label} «{spec.number}» {status_text}')
    return redirect('client_detail', client_id=spec.contract.client_id)


# ─────────────────────────────────────────────────────────────
# Массовые закрывающие документы (батчи) — CRUD
# (редиректят на табы, не на detail — т.к. батчи не привязаны к 1 заказчику)
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def closing_batch_create(request):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)

    batch_number = request.POST.get('batch_number', '').strip()
    act_ids = request.POST.getlist('act_ids')
    act_ids = [int(x) for x in act_ids if x.isdigit()]

    if not act_ids:
        messages.error(request, 'Выберите хотя бы один акт')
        return redirect('/workspace/clients/?tab=closing')

    try:
        from decimal import Decimal, InvalidOperation

        work_cost_str = request.POST.get('work_cost', '').strip()
        work_cost = None
        if work_cost_str:
            try: work_cost = Decimal(work_cost_str)
            except InvalidOperation: work_cost = None

        payment_date_str = request.POST.get('payment_date', '').strip()
        payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else None

        batch = ClosingDocumentBatch.objects.create(
            batch_number=batch_number,
            completion_act=request.POST.get('completion_act', '').strip(),
            invoice_number=request.POST.get('invoice_number', '').strip(),
            document_flow=request.POST.get('document_flow', '').strip(),
            closing_status=request.POST.get('closing_status', '').strip(),
            sending_method=request.POST.get('sending_method', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            work_cost=work_cost,
            payment_date=payment_date,
            created_by=request.user,
        )

        for aid in act_ids:
            ClosingBatchAct.objects.create(batch=batch, act_id=aid)

        _sync_batch_to_acts(batch)

        log_action(request, 'closing_batch', batch.id, 'closing_batch_created',
                   extra_data={'batch_number': batch_number, 'acts_count': len(act_ids)})
        messages.success(request, f'Пакет «{batch_number or batch.id}» создан ({len(act_ids)} актов)')

    except Exception as e:
        logger.exception('Ошибка создания пакета')
        messages.error(request, f'Ошибка: {e}')

    return redirect('/workspace/clients/?tab=closing')


@login_required
@require_POST
def closing_batch_edit(request, batch_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)

    batch = get_object_or_404(ClosingDocumentBatch, id=batch_id)

    try:
        from decimal import Decimal, InvalidOperation

        work_cost_str = request.POST.get('work_cost', '').strip()
        new_work_cost = None
        if work_cost_str:
            try: new_work_cost = Decimal(work_cost_str)
            except InvalidOperation: new_work_cost = None

        payment_date_str = request.POST.get('payment_date', '').strip()
        new_payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else None

        text_fields = {
            'batch_number': request.POST.get('batch_number', '').strip(),
            'completion_act': request.POST.get('completion_act', '').strip(),
            'invoice_number': request.POST.get('invoice_number', '').strip(),
            'document_flow': request.POST.get('document_flow', '').strip(),
            'closing_status': request.POST.get('closing_status', '').strip(),
            'sending_method': request.POST.get('sending_method', '').strip(),
            'notes': request.POST.get('notes', '').strip(),
        }

        changes = {}
        for field, new_val in text_fields.items():
            old_val = getattr(batch, field, '') or ''
            if old_val != new_val:
                changes[field] = (old_val, new_val)
                setattr(batch, field, new_val)
        if batch.work_cost != new_work_cost:
            changes['work_cost'] = (str(batch.work_cost), str(new_work_cost))
            batch.work_cost = new_work_cost
        if batch.payment_date != new_payment_date:
            changes['payment_date'] = (str(batch.payment_date), str(new_payment_date))
            batch.payment_date = new_payment_date

        act_ids = set(int(x) for x in request.POST.getlist('act_ids') if x.isdigit())
        existing_ids = set(ClosingBatchAct.objects.filter(batch=batch).values_list('act_id', flat=True))
        if act_ids != existing_ids:
            changes['acts'] = (list(existing_ids), list(act_ids))
            for aid in act_ids - existing_ids:
                ClosingBatchAct.objects.create(batch=batch, act_id=aid)
            ClosingBatchAct.objects.filter(batch=batch, act_id__in=existing_ids - act_ids).delete()

        if changes:
            batch.save()
            _sync_batch_to_acts(batch)
            log_field_changes(request, 'closing_batch', batch.id, changes, action='closing_batch_updated')
            messages.success(request, f'Пакет «{batch.batch_number or batch.id}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')

    except Exception as e:
        logger.exception('Ошибка редактирования пакета')
        messages.error(request, f'Ошибка: {e}')

    return redirect('/workspace/clients/?tab=closing')


@login_required
@require_POST
def closing_batch_delete(request, batch_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    batch = get_object_or_404(ClosingDocumentBatch, id=batch_id)
    label = batch.batch_number or str(batch.id)
    log_action(request, 'closing_batch', batch.id, 'closing_batch_deleted',
               extra_data={'batch_number': label})
    batch.delete()
    messages.success(request, f'Пакет «{label}» удалён')
    return redirect('/workspace/clients/?tab=closing')


def _sync_batch_to_acts(batch):
    """Синхронизирует закрывающие поля пакета → во все привязанные акты."""
    act_ids = ClosingBatchAct.objects.filter(batch=batch).values_list('act_id', flat=True)
    if not act_ids:
        return
    update_fields = {}
    if batch.completion_act:
        update_fields['completion_act'] = batch.completion_act
    if batch.invoice_number:
        update_fields['invoice_number'] = batch.invoice_number
    if batch.document_flow:
        update_fields['document_flow'] = batch.document_flow
    if batch.closing_status:
        update_fields['closing_status'] = batch.closing_status
    if batch.sending_method:
        update_fields['sending_method'] = batch.sending_method
    if update_fields:
        AcceptanceAct.objects.filter(id__in=act_ids).update(**update_fields)


@login_required
def api_acts_for_batch(request):
    """API: актов для выбора в батч (без наследования финансов, т.е. без спецификации/счёта)."""
    client_id = request.GET.get('client_id', '')

    acts = AcceptanceAct.objects.select_related('contract__client').order_by('-created_at')
    acts = acts.filter(specification__isnull=True, invoice__isnull=True)

    if client_id:
        acts = acts.filter(contract__client_id=client_id)

    result = []
    for act in acts[:100]:
        result.append({
            'id': act.id,
            'doc_number': act.doc_number or '',
            'document_name': act.document_name or '',
            'client_name': act.client.name if act.client else '—',
            'contract_number': act.contract.number if act.contract_id else '—',
            'work_status': act.work_status,
            'work_cost': str(act.work_cost) if act.work_cost else '',
            'closing_status': act.closing_status or '',
        })
    return JsonResponse(result, safe=False)


@login_required
def api_closing_batch_detail(request, batch_id):
    """API: данные одного пакета для модалки редактирования."""
    batch = get_object_or_404(ClosingDocumentBatch, id=batch_id)
    act_ids = list(ClosingBatchAct.objects.filter(batch=batch).values_list('act_id', flat=True))
    return JsonResponse({
        'id': batch.id,
        'batch_number': batch.batch_number or '',
        'work_cost': str(batch.work_cost) if batch.work_cost else '',
        'completion_act': batch.completion_act or '',
        'invoice_number': batch.invoice_number or '',
        'document_flow': batch.document_flow or '',
        'closing_status': batch.closing_status or '',
        'sending_method': batch.sending_method or '',
        'payment_date': str(batch.payment_date) if batch.payment_date else '',
        'notes': batch.notes or '',
        'act_ids': act_ids,
    })


# ─────────────────────────────────────────────────────────────
# Контакты — CRUD
# ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def contact_create(request, client_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    client = get_object_or_404(Client, id=client_id)
    full_name = request.POST.get('full_name', '').strip()
    position = request.POST.get('position', '').strip()
    phone = request.POST.get('phone', '').strip()
    email = request.POST.get('email', '').strip()
    is_primary = request.POST.get('is_primary') == 'on'
    if not full_name:
        messages.error(request, 'ФИО контакта обязательно')
        return redirect('client_detail', client_id=client_id)
    try:
        if is_primary:
            ClientContact.objects.filter(client=client, is_primary=True).update(is_primary=False)
        contact = ClientContact.objects.create(
            client=client, full_name=full_name, position=position,
            phone=phone, email=email, is_primary=is_primary,
        )
        log_action(request, 'client_contact', contact.id, 'contact_created',
                   extra_data={'full_name': full_name, 'client_id': client_id})
        messages.success(request, f'Контакт «{full_name}» добавлен')
    except Exception as e:
        logger.exception('Ошибка создания контакта')
        messages.error(request, f'Ошибка: {e}')
    return redirect('client_detail', client_id=client_id)


@login_required
@require_POST
def contact_edit(request, contact_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    contact = get_object_or_404(ClientContact, id=contact_id)
    full_name = request.POST.get('full_name', '').strip()
    position = request.POST.get('position', '').strip()
    phone = request.POST.get('phone', '').strip()
    email = request.POST.get('email', '').strip()
    is_primary = request.POST.get('is_primary') == 'on'
    if not full_name:
        messages.error(request, 'ФИО контакта обязательно')
        return redirect('client_detail', client_id=contact.client_id)
    try:
        changes = {}
        if contact.full_name != full_name: changes['full_name'] = (contact.full_name, full_name); contact.full_name = full_name
        if (contact.position or '') != position: changes['position'] = (contact.position, position); contact.position = position
        if (contact.phone or '') != phone: changes['phone'] = (contact.phone, phone); contact.phone = phone
        if (contact.email or '') != email: changes['email'] = (contact.email, email); contact.email = email
        if contact.is_primary != is_primary: changes['is_primary'] = (contact.is_primary, is_primary); contact.is_primary = is_primary
        if changes:
            if is_primary and 'is_primary' in changes:
                ClientContact.objects.filter(client=contact.client, is_primary=True).exclude(id=contact.id).update(is_primary=False)
            contact.save()
            log_field_changes(request, 'client_contact', contact.id, changes, action='contact_updated')
            messages.success(request, f'Контакт «{full_name}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования контакта')
        messages.error(request, f'Ошибка: {e}')
    return redirect('client_detail', client_id=contact.client_id)


@login_required
@require_POST
def contact_delete(request, contact_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    contact = get_object_or_404(ClientContact, id=contact_id)
    name = contact.full_name
    client_id = contact.client_id
    log_action(request, 'client_contact', contact.id, 'contact_deleted',
               extra_data={'full_name': name, 'client_id': client_id})
    contact.delete()
    messages.success(request, f'Контакт «{name}» удалён')
    return redirect('client_detail', client_id=client_id)


# ─────────────────────────────────────────────────────────────
# Карточка заказчика — detail
# ─────────────────────────────────────────────────────────────

@login_required
def client_detail(request, client_id):
    """Карточка заказчика — договоры, спецификации, акты, счета, контакты."""
    if not _check_clients_access(request.user):
        messages.error(request, 'У вас нет доступа к справочнику заказчиков')
        return redirect('workspace_home')

    client = get_object_or_404(Client, id=client_id)
    can_edit = _can_edit_clients(request.user)

    contracts = Contract.objects.filter(client=client).order_by('-date')
    contracts_with_acts = []
    for contract in contracts:
        acts = AcceptanceAct.objects.filter(contract=contract).select_related(
            'specification'
        ).prefetch_related('act_laboratories__laboratory').order_by('-created_at')

        specs = Specification.objects.filter(contract=contract).order_by('-date')
        specs_with_acts = []
        for spec in specs:
            spec_acts = AcceptanceAct.objects.filter(specification=spec).prefetch_related(
                'act_laboratories__laboratory'
            ).order_by('-created_at')
            specs_with_acts.append({
                'spec': spec,
                'acts': spec_acts,
                'acts_count': spec_acts.count(),
                'lab_ids': set(SpecificationLaboratory.objects.filter(
                    specification=spec
                ).values_list('laboratory_id', flat=True)),
            })

        direct_acts = acts.filter(specification__isnull=True)

        contracts_with_acts.append({
            'contract': contract,
            'acts': direct_acts,
            'all_acts_count': acts.count(),
            'specs_with_acts': specs_with_acts,
        })

    invoices_with_acts = []
    for inv in Invoice.objects.filter(client=client).order_by('-date'):
        inv_acts = AcceptanceAct.objects.filter(invoice=inv).prefetch_related(
            'act_laboratories__laboratory'
        ).order_by('-created_at')
        invoices_with_acts.append({
            'invoice': inv,
            'acts': inv_acts,
            'acts_count': inv_acts.count(),
        })

    contacts = ClientContact.objects.filter(client=client).order_by('-is_primary', 'full_name')
    laboratories = Laboratory.objects.filter(is_active=True, department_type='LAB').order_by('name')

    # ⭐ v3.56.0: Акты без договора/счёта (привязаны напрямую к заказчику)
    client_direct_acts = AcceptanceAct.objects.filter(
        client_direct_id=client.id,
    ).prefetch_related('act_laboratories__laboratory').order_by('-created_at')

    total_acts = AcceptanceAct.objects.filter(
        Q(contract__client=client) | Q(invoice__client=client) | Q(client_direct_id=client.id)
    ).count()
    active_contracts = contracts.filter(status='ACTIVE').count()

    return render(request, 'core/client_detail.html', {
        'client': client,
        'can_edit': can_edit,
        'contracts_with_acts': contracts_with_acts,
        'invoices_with_acts': invoices_with_acts,
        'contacts': contacts,
        'laboratories': laboratories,
        'direct_acts': client_direct_acts,
        'total_acts': total_acts,
        'total_contracts': contracts.count(),
        'active_contracts': active_contracts,
        'total_invoices': len(invoices_with_acts),
        'total_contacts': contacts.count(),
    })
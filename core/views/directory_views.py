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

    # ═══ TAB 1: Заказчики ═══
    clients_search = request.GET.get('q', '').strip() if active_tab == 'clients' else ''
    show_inactive = request.GET.get('show_inactive') == '1'

    clients_qs = Client.objects.annotate(
        contracts_count=Count('contracts'),
        active_contracts_count=Count('contracts', filter=Q(contracts__status='ACTIVE')),
    )
    if not show_inactive:
        clients_qs = clients_qs.filter(is_active=True)
    if clients_search:
        clients_qs = clients_qs.filter(Q(name__icontains=clients_search) | Q(inn__icontains=clients_search))
    clients_qs = clients_qs.order_by('name')

    clients_data = []
    for client in clients_qs:
        contracts = Contract.objects.filter(client=client).order_by('-date')
        contacts = ClientContact.objects.filter(client=client).order_by('-is_primary', 'full_name')
        contracts_with_acts = []
        for contract in contracts:
            acts = AcceptanceAct.objects.filter(contract=contract).order_by('-created_at')[:10]
            specs = Specification.objects.filter(contract=contract).order_by('-date')
            specs_with_acts = []
            for spec in specs:
                spec_acts = AcceptanceAct.objects.filter(specification=spec).order_by('-created_at')[:10]
                specs_with_acts.append({
                    'spec': spec,
                    'acts': spec_acts,
                    'acts_count': AcceptanceAct.objects.filter(specification=spec).count(),
                    'lab_ids': set(SpecificationLaboratory.objects.filter(specification=spec).values_list('laboratory_id', flat=True)),
                })
            contracts_with_acts.append({
                'contract': contract,
                'acts': acts,
                'acts_count': AcceptanceAct.objects.filter(contract=contract).count(),
                'specs_with_acts': specs_with_acts,
            })
        clients_data.append({
            'client': client,
            'contracts_with_acts': contracts_with_acts,
            'contracts': contracts,
            'invoices_with_acts': [
                {
                    'invoice': inv,
                    'acts': AcceptanceAct.objects.filter(invoice=inv).order_by('-created_at')[:10],
                    'acts_count': AcceptanceAct.objects.filter(invoice=inv).count(),
                }
                for inv in Invoice.objects.filter(client=client).order_by('-date')
            ],
            'contacts': contacts,
        })

    # ═══ TAB 2: Реестр актов ═══
    acts_search = request.GET.get('q', '').strip() if active_tab == 'acts' else ''
    acts_client_id = request.GET.get('client', '') if active_tab == 'acts' else ''
    acts_work_status = request.GET.get('work_status', '') if active_tab == 'acts' else ''
    acts_lab_id = request.GET.get('laboratory', '') if active_tab == 'acts' else ''

    acts_qs = AcceptanceAct.objects.select_related(
        'contract__client', 'created_by'
    ).prefetch_related('act_laboratories__laboratory').all()

    if acts_search:
        acts_qs = acts_qs.filter(
            Q(document_name__icontains=acts_search) |
            Q(doc_number__icontains=acts_search) |
            Q(contract__client__name__icontains=acts_search) |
            Q(contract__number__icontains=acts_search)
        )
    if acts_client_id:
        acts_qs = acts_qs.filter(contract__client_id=acts_client_id)
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
        return redirect('directory_clients')
    if Client.objects.filter(name__iexact=name).exclude(id=client_id).exists():
        messages.error(request, f'Заказчик «{name}» уже существует')
        return redirect('directory_clients')
    changes = {}
    if client.name != name: changes['name'] = (client.name, name); client.name = name
    if (client.inn or '') != inn: changes['inn'] = (client.inn, inn); client.inn = inn
    if (client.address or '') != address: changes['address'] = (client.address, address); client.address = address
    if changes:
        client.save()
        log_field_changes(request, 'client', client.id, changes)
        messages.success(request, f'Заказчик «{name}» обновлён')
    else:
        messages.info(request, 'Изменений не обнаружено')
    return redirect('directory_clients')


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
    show_inactive = '?show_inactive=1' if not client.is_active else ''
    return redirect(f'/workspace/clients/{show_inactive}')


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
        return redirect('directory_clients')
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
        return redirect(f'/workspace/clients/?upload_contract={contract.id}')
    except Exception as e:
        logger.exception('Ошибка создания договора')
        messages.error(request, f'Ошибка: {e}')
    return redirect('directory_clients')


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
        return redirect('directory_clients')
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
            log_field_changes(request, 'contract', contract.id, changes)
            messages.success(request, f'Договор «{number}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования договора')
        messages.error(request, f'Ошибка: {e}')
    return redirect('directory_clients')


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
    return redirect('directory_clients')


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
        return redirect('directory_clients')

    try:
        from decimal import Decimal, InvalidOperation
        invoice_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Финансы
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
        log_action(request, 'invoice', invoice.id, 'create',
                   extra_data={'number': number, 'client_id': client_id})
        messages.success(request, f'Счёт «{number}» создан для {client.name}')
    except Exception as e:
        logger.exception('Ошибка создания счёта')
        messages.error(request, f'Ошибка: {e}')

    return redirect('directory_clients')


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
        return redirect('directory_clients')

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

        # Все текстовые/select поля
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
            log_field_changes(request, 'invoice', invoice.id, changes)
            messages.success(request, f'Счёт «{number}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования счёта')
        messages.error(request, f'Ошибка: {e}')

    return redirect('directory_clients')


@login_required
@require_POST
def invoice_toggle(request, invoice_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    invoice = get_object_or_404(Invoice, id=invoice_id)
    old_status = invoice.status
    invoice.status = 'CLOSED' if invoice.status == 'ACTIVE' else 'ACTIVE'
    invoice.save()
    log_action(request, 'invoice', invoice.id, 'update',
               field_name='status', old_value=old_status, new_value=invoice.status)
    status_text = 'активирован' if invoice.status == 'ACTIVE' else 'закрыт'
    messages.success(request, f'Счёт «{invoice.number}» {status_text}')
    return redirect('directory_clients')


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
        return redirect('directory_clients')

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

        # M2M лаборатории
        lab_ids = request.POST.getlist('laboratories')
        for lid in lab_ids:
            if lid.isdigit():
                SpecificationLaboratory.objects.create(specification=spec, laboratory_id=int(lid))

        type_label = 'ТЗ' if spec_type == 'TZ' else 'Спецификация'
        log_action(request, 'specification', spec.id, 'create',
                   extra_data={'number': number, 'contract_id': contract_id, 'spec_type': spec_type})
        messages.success(request, f'{type_label} «{number}» создана для договора {contract.number}')
    except Exception as e:
        logger.exception('Ошибка создания спецификации')
        messages.error(request, f'Ошибка: {e}')

    return redirect('directory_clients')


@login_required
@require_POST
def specification_edit(request, spec_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    spec = get_object_or_404(Specification, id=spec_id)

    number = request.POST.get('number', '').strip()
    if not number:
        messages.error(request, 'Номер спецификации обязателен')
        return redirect('directory_clients')

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

        # M2M лаборатории
        lab_ids = set(int(x) for x in request.POST.getlist('laboratories') if x.isdigit())
        existing_lab_ids = set(SpecificationLaboratory.objects.filter(specification=spec).values_list('laboratory_id', flat=True))
        if lab_ids != existing_lab_ids:
            changes['laboratories'] = (list(existing_lab_ids), list(lab_ids))
            for lid in lab_ids - existing_lab_ids:
                SpecificationLaboratory.objects.create(specification=spec, laboratory_id=lid)
            SpecificationLaboratory.objects.filter(specification=spec, laboratory_id__in=existing_lab_ids - lab_ids).delete()

        if changes:
            spec.save()
            log_field_changes(request, 'specification', spec.id, changes)
            messages.success(request, f'Спецификация «{number}» обновлена')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования спецификации')
        messages.error(request, f'Ошибка: {e}')

    return redirect('directory_clients')


@login_required
@require_POST
def specification_toggle(request, spec_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    spec = get_object_or_404(Specification, id=spec_id)
    old_status = spec.status
    spec.status = 'CLOSED' if spec.status == 'ACTIVE' else 'ACTIVE'
    spec.save()
    log_action(request, 'specification', spec.id, 'update',
               field_name='status', old_value=old_status, new_value=spec.status)
    status_text = 'активирована' if spec.status == 'ACTIVE' else 'закрыта'
    type_label = 'ТЗ' if spec.spec_type == 'TZ' else 'Спецификация'
    messages.success(request, f'{type_label} «{spec.number}» {status_text}')
    return redirect('directory_clients')


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
        return redirect('directory_clients')
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
    return redirect('directory_clients')


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
        return redirect('directory_clients')
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
            log_field_changes(request, 'client_contact', contact.id, changes)
            messages.success(request, f'Контакт «{full_name}» обновлён')
        else:
            messages.info(request, 'Изменений не обнаружено')
    except Exception as e:
        logger.exception('Ошибка редактирования контакта')
        messages.error(request, f'Ошибка: {e}')
    return redirect('directory_clients')


@login_required
@require_POST
def contact_delete(request, contact_id):
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)
    contact = get_object_or_404(ClientContact, id=contact_id)
    name = contact.full_name
    log_action(request, 'client_contact', contact.id, 'contact_deleted',
               extra_data={'full_name': name, 'client_id': contact.client_id})
    contact.delete()
    messages.success(request, f'Контакт «{name}» удалён')
    return redirect('directory_clients')

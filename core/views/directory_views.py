"""
CISIS v3.16.0 — Справочник заказчиков, договоров и контактов

Файл: core/views/directory_views.py
Действие: ПОЛНАЯ ЗАМЕНА файла

Изменения v3.16.0:
- Доступ через PermissionChecker вместо хардкода ролей
- Разделение VIEW / EDIT: VIEW = только просмотр, EDIT = полный доступ
- Передача can_edit в шаблон для скрытия кнопок
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
from core.views.audit import log_action, log_field_changes
from core.permissions import PermissionChecker
from core.models import AcceptanceAct

logger = logging.getLogger(__name__)


def _check_clients_access(user):
    """VIEW или EDIT на столбце 'access' журнала CLIENTS"""
    return PermissionChecker.can_view(user, 'CLIENTS', 'access')


def _can_edit_clients(user):
    """Может ли редактировать (EDIT на столбце access)"""
    return PermissionChecker.can_edit(user, 'CLIENTS', 'access')


# ─────────────────────────────────────────────────────────────
# Заказчики — список
# ─────────────────────────────────────────────────────────────

@login_required
def clients_list(request):
    if not _check_clients_access(request.user):
        messages.error(request, 'У вас нет доступа к справочнику заказчиков')
        return redirect('workspace_home')

    search = request.GET.get('q', '').strip()
    show_inactive = request.GET.get('show_inactive') == '1'

    clients = Client.objects.annotate(
        contracts_count=Count('contracts'),
        active_contracts_count=Count(
            'contracts', filter=Q(contracts__status='ACTIVE')
        ),
    )

    if not show_inactive:
        clients = clients.filter(is_active=True)

    if search:
        clients = clients.filter(
            Q(name__icontains=search) | Q(inn__icontains=search)
        )

    clients = clients.order_by('name')

    clients_data = []
    for client in clients:
        contracts = Contract.objects.filter(client=client).order_by('-date')
        contacts = ClientContact.objects.filter(client=client).order_by('-is_primary', 'full_name')

            # Подгружаем акты для каждого договора
        contracts_with_acts = []
        for contract in contracts:
            acts = AcceptanceAct.objects.filter(
                contract=contract
            ).order_by('-created_at')[:10]  # последние 10
            contracts_with_acts.append({
                'contract': contract,
                'acts': acts,
                'acts_count': AcceptanceAct.objects.filter(contract=contract).count(),
            })

        clients_data.append({
            'client': client,
            'contracts_with_acts': contracts_with_acts,
            'contracts': contracts,  # оставляем для обратной совместимости
            'contacts': contacts,
        })

    return render(request, 'core/directory_clients.html', {
        'clients_data': clients_data,
        'search': search,
        'show_inactive': show_inactive,
        'total_count': len(clients_data),
        'user': request.user,
        'can_edit': _can_edit_clients(request.user),
    })


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
        log_action(request, 'client', client.id, 'create', extra_data={'name': name})
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
    if client.name != name:
        changes['name'] = (client.name, name)
        client.name = name
    if (client.inn or '') != inn:
        changes['inn'] = (client.inn, inn)
        client.inn = inn
    if (client.address or '') != address:
        changes['address'] = (client.address, address)
        client.address = address

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

    log_action(request, 'client', client.id, 'update',
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
        log_action(request, 'contract', contract.id, 'create',
                   extra_data={'number': number, 'client_id': client_id})
        messages.success(request, f'Договор «{number}» создан для {client.name}')
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
        if contract.number != number:
            changes['number'] = (contract.number, number)
            contract.number = number
        if contract.date != new_date:
            changes['date'] = (str(contract.date), str(new_date))
            contract.date = new_date
        if contract.end_date != new_end_date:
            changes['end_date'] = (str(contract.end_date), str(new_end_date))
            contract.end_date = new_end_date
        if (contract.notes or '') != notes:
            changes['notes'] = (contract.notes, notes)
            contract.notes = notes
        if contract.status != status:
            changes['status'] = (contract.status, status)
            contract.status = status

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

    log_action(request, 'contract', contract.id, 'update',
               field_name='status', old_value=old_status, new_value=contract.status)

    status_text = 'активирован' if contract.status == 'ACTIVE' else 'закрыт'
    messages.success(request, f'Договор «{contract.number}» {status_text}')

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
        # Если ставим основной — снимаем у остальных
        if is_primary:
            ClientContact.objects.filter(client=client, is_primary=True).update(is_primary=False)

        contact = ClientContact.objects.create(
            client=client, full_name=full_name, position=position,
            phone=phone, email=email, is_primary=is_primary,
        )
        log_action(request, 'client_contact', contact.id, 'create',
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
        if contact.full_name != full_name:
            changes['full_name'] = (contact.full_name, full_name)
            contact.full_name = full_name
        if (contact.position or '') != position:
            changes['position'] = (contact.position, position)
            contact.position = position
        if (contact.phone or '') != phone:
            changes['phone'] = (contact.phone, phone)
            contact.phone = phone
        if (contact.email or '') != email:
            changes['email'] = (contact.email, email)
            contact.email = email
        if contact.is_primary != is_primary:
            changes['is_primary'] = (contact.is_primary, is_primary)
            contact.is_primary = is_primary

        if changes:
            # Если ставим основной — снимаем у остальных
            if is_primary and 'is_primary' in changes:
                ClientContact.objects.filter(
                    client=contact.client, is_primary=True
                ).exclude(id=contact.id).update(is_primary=False)

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
    """Удаление контакта (физическое, т.к. нет is_active)."""
    if not _can_edit_clients(request.user):
        return JsonResponse({'error': 'Нет прав на редактирование'}, status=403)

    contact = get_object_or_404(ClientContact, id=contact_id)
    name = contact.full_name

    log_action(request, 'client_contact', contact.id, 'delete',
               extra_data={'full_name': name, 'client_id': contact.client_id})

    contact.delete()
    messages.success(request, f'Контакт «{name}» удалён')

    return redirect('directory_clients')
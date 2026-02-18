"""
CISIS — Views для журнала образцов.

Содержит:
- journal_samples: основная страница журнала
- export_journal_xlsx: экспорт в XLSX
- journal_filter_options: AJAX каскадные фильтры
- save_column_preferences: AJAX сохранение столбцов
- Вспомогательные функции фильтрации и отображения
"""

import json
from datetime import date, datetime

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.timezone import localtime
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from core.models import (
    Sample, Laboratory, WorkshopStatus, JournalColumn,
)
from core.permissions import PermissionChecker
from .constants import (
    WORKSHOP_ROLES, QMS_ROLES,
    JOURNAL_DISPLAYABLE_COLUMNS, DISPLAYABLE_COLUMNS_DICT,
    DEFAULT_COLUMNS_BY_ROLE, FILTERABLE_COLUMNS, ITEMS_PER_PAGE,
)


# ─────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────

def _get_user_visible_columns(user):
    """
    Возвращает список кодов столбцов, которые пользователь МОЖЕТ видеть
    (на основе role_permissions).
    """
    available = []
    for code, name in JOURNAL_DISPLAYABLE_COLUMNS:
        if PermissionChecker.can_view(user, 'SAMPLES', code):
            available.append(code)
    return available


def _get_user_selected_columns(user):
    """
    Возвращает список кодов столбцов, выбранных пользователем.
    Если нет сохранённых настроек — возвращает дефолт для роли.
    """
    prefs = user.ui_preferences or {}
    saved = prefs.get('journal_columns', {}).get('SAMPLES')

    if saved:
        available = set(_get_user_visible_columns(user))
        return [c for c in saved if c in available]

    role = user.role
    default = DEFAULT_COLUMNS_BY_ROLE.get(role, DEFAULT_COLUMNS_BY_ROLE['_default'])
    available = set(_get_user_visible_columns(user))
    return [c for c in default if c in available]


def _build_base_queryset(user):
    """Строит базовый queryset образцов с учётом роли пользователя."""
    user_role = user.role

    if user_role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'SYSADMIN',
                     'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST', 'CTO', 'CEO'):
        samples = Sample.objects.all()
    elif user_role == 'WORKSHOP_HEAD':
        samples = Sample.objects.filter(
            manufacturing=True
        ).exclude(status='PENDING_VERIFICATION')
    elif user_role == 'WORKSHOP':
        samples = Sample.objects.filter(
            workshop_status__isnull=False
        ).exclude(status='PENDING_VERIFICATION')
    elif user_role == 'LAB_HEAD':
        if user.laboratory:
            samples = Sample.objects.filter(laboratory_id__in=user.all_laboratory_ids)
        else:
            samples = Sample.objects.none()
    elif user.laboratory:
        samples = Sample.objects.filter(
            laboratory_id__in=user.all_laboratory_ids
        ).exclude(status='PENDING_VERIFICATION')
    else:
        samples = Sample.objects.none()

    return samples


def _apply_filters(queryset, params, user):
    """
    Применяет фильтры из GET-параметров к queryset.
    Возвращает отфильтрованный queryset.
    """
    # --- Select фильтры (множественный выбор) ---
    status_values = params.getlist('status')
    if status_values:
        queryset = queryset.filter(status__in=status_values)

    workshop_status_values = params.getlist('workshop_status')
    if workshop_status_values:
        queryset = queryset.filter(workshop_status__in=workshop_status_values)

    laboratory_values = params.getlist('laboratory')
    if laboratory_values:
        queryset = queryset.filter(laboratory_id__in=laboratory_values)

    client_values = params.getlist('client')
    if client_values:
        queryset = queryset.filter(client_id__in=client_values)

    contract_values = params.getlist('contract')
    if contract_values:
        queryset = queryset.filter(contract_id__in=contract_values)

    standard_values = params.getlist('standard')
    if standard_values:
        queryset = queryset.filter(standard_id__in=standard_values)

    accreditation_values = params.getlist('accreditation_area')
    if accreditation_values:
        queryset = queryset.filter(accreditation_area_id__in=accreditation_values)

    test_type_values = params.getlist('test_type')
    if test_type_values:
        queryset = queryset.filter(test_type__in=test_type_values)

    report_type_values = params.getlist('report_type')
    if report_type_values:
        queryset = queryset.filter(report_type__in=report_type_values)

    further_movement_values = params.getlist('further_movement')
    if further_movement_values:
        queryset = queryset.filter(further_movement__in=further_movement_values)

    registered_by_values = params.getlist('registered_by')
    if registered_by_values:
        queryset = queryset.filter(registered_by_id__in=registered_by_values)

    verified_by_values = params.getlist('verified_by')
    if verified_by_values:
        if '__none__' in verified_by_values:
            other_ids = [v for v in verified_by_values if v != '__none__']
            if other_ids:
                queryset = queryset.filter(
                    models.Q(verified_by__isnull=True) | models.Q(verified_by_id__in=other_ids)
                )
            else:
                queryset = queryset.filter(verified_by__isnull=True)
        else:
            queryset = queryset.filter(verified_by_id__in=verified_by_values)

    # --- Boolean фильтры ---
    manufacturing_val = params.get('manufacturing')
    if manufacturing_val in ('true', 'false'):
        queryset = queryset.filter(manufacturing=(manufacturing_val == 'true'))

    uzk_val = params.get('uzk_required')
    if uzk_val in ('true', 'false'):
        queryset = queryset.filter(uzk_required=(uzk_val == 'true'))

    # --- Text фильтры (поиск по подстроке) ---
    cipher_search = params.get('cipher_search', '').strip()
    if cipher_search:
        queryset = queryset.filter(cipher__icontains=cipher_search)

    object_id_search = params.get('object_id_search', '').strip()
    if object_id_search:
        queryset = queryset.filter(object_id__icontains=object_id_search)

    pi_number_search = params.get('pi_number_search', '').strip()
    if pi_number_search:
        queryset = queryset.filter(pi_number__icontains=pi_number_search)

    doc_number_search = params.get('accompanying_doc_number_search', '').strip()
    if doc_number_search:
        queryset = queryset.filter(accompanying_doc_number__icontains=doc_number_search)

    # --- Date range фильтры ---
    for date_field in ('registration_date', 'deadline', 'manufacturing_deadline'):
        date_from = params.get(f'{date_field}_from')
        date_to = params.get(f'{date_field}_to')
        if date_from:
            queryset = queryset.filter(**{f'{date_field}__gte': date_from})
        if date_to:
            queryset = queryset.filter(**{f'{date_field}__lte': date_to})

    return queryset


def _count_active_filters(params):
    """Подсчитывает количество активных фильтров."""
    count = 0
    filter_keys = [
        'status', 'workshop_status', 'laboratory', 'client', 'contract',
        'standard', 'accreditation_area', 'test_type', 'report_type',
        'further_movement', 'registered_by', 'verified_by',
        'manufacturing', 'uzk_required',
        'cipher_search', 'object_id_search', 'pi_number_search',
        'accompanying_doc_number_search',
    ]
    for key in filter_keys:
        if params.getlist(key):
            count += 1
    for date_field in ('registration_date', 'deadline', 'manufacturing_deadline'):
        if params.get(f'{date_field}_from') or params.get(f'{date_field}_to'):
            count += 1
    return count


def _get_filter_options_for_queryset(queryset):
    """
    Возвращает доступные варианты фильтров для данного queryset.
    Используется для каскадных фильтров.
    """
    from core.models import SampleStatus, WorkshopStatus, ReportType, FurtherMovement

    base_qs = queryset.order_by().select_related(None).prefetch_related(None)

    options = {}

    # Статусы
    existing_statuses = set(base_qs.values_list('status', flat=True).distinct())
    options['status'] = [
        {'value': s.value, 'label': s.label}
        for s in SampleStatus
        if s.value in existing_statuses
    ]

    # Workshop status
    existing_ws = set(base_qs.exclude(workshop_status__isnull=True).values_list('workshop_status', flat=True).distinct())
    options['workshop_status'] = [
        {'value': s.value, 'label': s.label}
        for s in WorkshopStatus
        if s.value in existing_ws
    ]

    # Лаборатории
    labs = base_qs.values_list(
        'laboratory_id', 'laboratory__code_display', 'laboratory__name'
    ).distinct().order_by('laboratory__code_display')
    options['laboratory'] = [
        {'value': str(l[0]), 'label': f"{l[1]} — {l[2]}"}
        for l in labs if l[0]
    ]

    # Заказчики
    clients = base_qs.values_list(
        'client_id', 'client__name'
    ).distinct().order_by('client__name')
    options['client'] = [
        {'value': str(c[0]), 'label': c[1]}
        for c in clients if c[0]
    ]

    # Договоры
    contracts = base_qs.exclude(contract__isnull=True).values_list(
        'contract_id', 'contract__number'
    ).distinct().order_by('contract__number')
    options['contract'] = [
        {'value': str(c[0]), 'label': c[1]}
        for c in contracts if c[0]
    ]

    # Стандарты
    stds = base_qs.values_list(
        'standard_id', 'standard__code'
    ).distinct().order_by('standard__code')
    options['standard'] = [
        {'value': str(s[0]), 'label': s[1]}
        for s in stds if s[0]
    ]

    # Области аккредитации
    areas = base_qs.values_list(
        'accreditation_area_id', 'accreditation_area__code'
    ).distinct().order_by('accreditation_area__code')
    options['accreditation_area'] = [
        {'value': str(a[0]), 'label': a[1]}
        for a in areas if a[0]
    ]

    # Типы испытаний
    test_types = base_qs.exclude(
        test_type=''
    ).values_list('test_type', flat=True).distinct().order_by('test_type')
    options['test_type'] = [
        {'value': t, 'label': t}
        for t in test_types
    ]

    # Report type
    existing_rt = set(base_qs.values_list('report_type', flat=True).distinct())
    options['report_type'] = [
        {'value': r.value, 'label': r.label}
        for r in ReportType
        if r.value in existing_rt
    ]

    # Further movement
    existing_fm = set(base_qs.exclude(further_movement='').values_list('further_movement', flat=True).distinct())
    options['further_movement'] = [
        {'value': f.value, 'label': f.label}
        for f in FurtherMovement
        if f.value and f.value in existing_fm
    ]

    # Registered by
    reg_by = base_qs.values_list(
        'registered_by_id', 'registered_by__last_name', 'registered_by__first_name'
    ).distinct().order_by('registered_by__last_name', 'registered_by__first_name')
    options['registered_by'] = [
        {'value': str(r[0]), 'label': f"{r[2]} {r[1]}".strip()}
        for r in reg_by if r[0]
    ]

    # Verified by (nullable)
    has_unverified = base_qs.filter(verified_by__isnull=True).exists()
    ver_by = base_qs.exclude(verified_by__isnull=True).values_list(
        'verified_by_id', 'verified_by__last_name', 'verified_by__first_name'
    ).distinct().order_by('verified_by__last_name', 'verified_by__first_name')
    verified_options = []
    if has_unverified:
        verified_options.append({'value': '__none__', 'label': '⏳ Ожидает проверки'})
    for v in ver_by:
        verified_options.append({'value': str(v[0]), 'label': f"{v[2]} {v[1]}".strip()})
    options['verified_by'] = verified_options

    return options


def _apply_sorting(samples, sort_field, sort_dir, user_role):
    """Применяет сортировку к queryset."""
    if sort_field and sort_field in DISPLAYABLE_COLUMNS_DICT:
        sort_map = {
            'client': 'client__name',
            'contract': 'contract__number',
            'standard': 'standard__code',
            'laboratory': 'laboratory__code_display',
            'accreditation_area': 'accreditation_area__code',
            'registered_by': 'registered_by__last_name',
            'verified_by': 'verified_by__last_name',
            'report_prepared_by': 'report_prepared_by__last_name',
            'protocol_checked_by': 'protocol_checked_by__last_name',
        }
        db_field = sort_map.get(sort_field, sort_field)
        if sort_dir == 'desc':
            db_field = f'-{db_field}'
        return samples.order_by(db_field)
    else:
        if user_role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'SYSADMIN'):
            return samples.order_by('-registration_date', '-sequence_number')
        return samples.order_by('-sequence_number')


def _get_export_value(sample, column_code):
    """Возвращает значение поля образца для экспорта в XLSX."""
    if column_code == 'sequence_number':
        return sample.sequence_number
    elif column_code == 'registration_date':
        return sample.registration_date
    elif column_code == 'laboratory':
        return sample.laboratory.code_display if sample.laboratory else ''
    elif column_code == 'cipher':
        return sample.cipher
    elif column_code == 'client':
        return sample.client.name if sample.client else ''
    elif column_code == 'contract':
        return sample.contract.number if sample.contract else ''
    elif column_code == 'contract_date':
        return sample.contract_date
    elif column_code == 'standard':
        return sample.standard.code if sample.standard else ''
    elif column_code == 'test_type':
        return sample.test_type or ''
    elif column_code == 'test_code':
        return sample.test_code or ''
    elif column_code == 'accreditation_area':
        return sample.accreditation_area.code if sample.accreditation_area else ''
    elif column_code == 'deadline':
        return sample.deadline
    elif column_code == 'manufacturing_deadline':
        return sample.manufacturing_deadline
    elif column_code == 'registered_by':
        return sample.registered_by.full_name if sample.registered_by else ''
    elif column_code == 'verified_by':
        return sample.verified_by.full_name if sample.verified_by else 'Ожидает'
    elif column_code == 'pi_number':
        return sample.pi_number or ''
    elif column_code == 'protocol_checked_by':
        return sample.protocol_checked_by.full_name if sample.protocol_checked_by else ''
    elif column_code == 'operators':
        ops = sample.operators.all()
        return ', '.join(op.full_name for op in ops) if ops else ''
    elif column_code == 'status':
        return sample.get_status_display()
    elif column_code == 'workshop_status':
        return sample.get_workshop_status_display() if sample.workshop_status else ''
    elif column_code == 'manufacturing':
        return 'Да' if sample.manufacturing else 'Нет'
    elif column_code == 'uzk_required':
        return 'Да' if sample.uzk_required else 'Нет'
    elif column_code == 'replacement_protocol_required':
        return 'Да' if sample.replacement_protocol_required else 'Нет'
    elif column_code == 'report_type':
        return sample.get_report_type_display() or ''
    elif column_code == 'further_movement':
        return sample.get_further_movement_display() or ''
    elif column_code == 'sample_count':
        return sample.sample_count_display
    elif column_code == 'additional_sample_count':
        return sample.additional_sample_count or 0
    elif column_code == 'working_days':
        return sample.working_days
    elif column_code == 'report_prepared_by':
        return sample.report_prepared_by.full_name if sample.report_prepared_by else ''
    # DateTime поля
    elif column_code in ('conditioning_start_datetime', 'conditioning_end_datetime',
                         'testing_start_datetime', 'testing_end_datetime',
                         'report_prepared_date', 'manufacturing_completion_date'):
        val = getattr(sample, column_code, None)
        if val:
            return localtime(val).strftime('%d.%m.%Y %H:%M')
        return ''
    # Date поля
    elif column_code in ('protocol_issued_date', 'protocol_printed_date',
                         'replacement_protocol_issued_date', 'sample_received_date'):
        val = getattr(sample, column_code, None)
        return val if val else ''
    # Текстовые поля
    else:
        val = getattr(sample, column_code, None)
        return val if val else ''


# ─────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────

@login_required
def journal_samples(request):
    """Журнал образцов: серверная пагинация, фильтрация, кастомизация столбцов."""

    if not PermissionChecker.has_journal_access(request.user, 'SAMPLES'):
        messages.error(request, 'У вас нет доступа к журналу образцов')
        return redirect('workspace_home')

    user = request.user
    user_role = user.role

    # ─── Queryset ───
    samples = _build_base_queryset(user)

    samples = samples.select_related(
        'laboratory', 'accreditation_area', 'standard', 'client', 'contract',
        'registered_by', 'verified_by', 'report_prepared_by', 'protocol_checked_by',
    ).prefetch_related(
        'operators'
    ).distinct()

    # ─── Фильтры ───
    samples = _apply_filters(samples, request.GET, user)
    active_filter_count = _count_active_filters(request.GET)

    total_count = samples.count()

    # ─── Статистика ───
    stats = {'total': total_count}
    if user_role in ('CLIENT_MANAGER', 'CLIENT_DEPT_HEAD', 'SYSADMIN', 'LAB_HEAD'):
        stats['pending'] = samples.filter(status='PENDING_VERIFICATION').count()
        stats['registered'] = samples.filter(status='REGISTERED').count()
    elif user_role in ('QMS_HEAD', 'QMS_ADMIN'):
        stats['pending_protocol'] = samples.filter(status='DRAFT_READY').count()
        stats['pending_results'] = samples.filter(status='RESULTS_UPLOADED').count()
    elif user_role in WORKSHOP_ROLES:
        stats['pending'] = samples.filter(workshop_status=WorkshopStatus.IN_WORKSHOP).count()
        stats['completed'] = samples.filter(workshop_status=WorkshopStatus.COMPLETED).count()

    # ─── Сортировка ───
    sort_field = request.GET.get('sort', '')
    sort_dir = request.GET.get('dir', 'desc')
    samples = _apply_sorting(samples, sort_field, sort_dir, user_role)

    # ─── Пагинация ───
    page_number = request.GET.get('page', 1)
    paginator = Paginator(samples, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(page_number)

    # ─── Столбцы ───
    available_columns = _get_user_visible_columns(user)
    selected_columns = _get_user_selected_columns(user)

    visible_columns = [
        {'code': code, 'name': DISPLAYABLE_COLUMNS_DICT.get(code, code)}
        for code in selected_columns
        if code in DISPLAYABLE_COLUMNS_DICT
    ]

    all_available_columns = [
        {
            'code': code,
            'name': DISPLAYABLE_COLUMNS_DICT.get(code, code),
            'selected': code in selected_columns,
        }
        for code in available_columns
        if code in DISPLAYABLE_COLUMNS_DICT
    ]

    # ─── Фильтры ───
    filter_options = _get_filter_options_for_queryset(samples)

    available_filters = {}
    for col_code, filter_config in FILTERABLE_COLUMNS.items():
        if col_code in available_columns:
            available_filters[col_code] = {
                **filter_config,
                'options': filter_options.get(col_code, []),
            }

    current_filters = {}
    for key in FILTERABLE_COLUMNS:
        values = request.GET.getlist(key)
        if values:
            current_filters[key] = values
    for suffix in ('_search', '_from', '_to'):
        for key in request.GET:
            if key.endswith(suffix):
                current_filters[key] = request.GET.get(key)

    # ─── URL params ───
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    query_string = query_params.urlencode()

    return render(request, 'core/journal_samples.html', {
        'page_obj': page_obj,
        'samples': page_obj.object_list,
        'visible_columns': visible_columns,
        'all_available_columns': all_available_columns,
        'available_filters': json.dumps(available_filters, ensure_ascii=False),
        'current_filters': json.dumps(current_filters, ensure_ascii=False),
        'active_filter_count': active_filter_count,
        'stats': stats,
        'user': request.user,
        'journal_name': 'Журнал образцов',
        'is_workshop_view': user_role in WORKSHOP_ROLES,
        'query_string': query_string,
        'current_sort': sort_field,
        'current_dir': sort_dir,
        'total_count': total_count,
    })


@login_required
def export_journal_xlsx(request):
    """
    Экспорт журнала образцов в XLSX.
    GET-параметры: те же фильтры что и journal_samples.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    if not PermissionChecker.has_journal_access(request.user, 'SAMPLES'):
        return HttpResponse('Нет доступа', status=403)

    user = request.user

    # ─── Queryset ───
    samples = _build_base_queryset(user)

    samples = samples.select_related(
        'laboratory', 'accreditation_area', 'standard', 'client', 'contract',
        'registered_by', 'verified_by', 'report_prepared_by', 'protocol_checked_by',
    ).prefetch_related('operators').distinct()

    samples = _apply_filters(samples, request.GET, user)

    sort_field = request.GET.get('sort', '')
    sort_dir = request.GET.get('dir', 'desc')
    samples = _apply_sorting(samples, sort_field, sort_dir, user.role)

    # ─── Столбцы пользователя ───
    selected_columns = _get_user_selected_columns(user)
    columns = [
        (code, DISPLAYABLE_COLUMNS_DICT.get(code, code))
        for code in selected_columns
        if code in DISPLAYABLE_COLUMNS_DICT
    ]

    # ─── Генерация XLSX ───
    wb = Workbook()
    ws = wb.active
    ws.title = 'Журнал образцов'

    # Стили
    header_font = Font(name='Arial', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill('solid', fgColor='4A90E2')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    cell_font = Font(name='Arial', size=10)
    cell_alignment = Alignment(vertical='top', wrap_text=True)
    date_alignment = Alignment(horizontal='center', vertical='top')
    thin_border = Border(
        left=Side(style='thin', color='D0D0D0'),
        right=Side(style='thin', color='D0D0D0'),
        top=Side(style='thin', color='D0D0D0'),
        bottom=Side(style='thin', color='D0D0D0'),
    )
    alt_fill = PatternFill('solid', fgColor='F8F9FA')

    # Заголовки
    for col_idx, (code, name) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    ws.freeze_panes = 'A2'

    if columns:
        last_col = get_column_letter(len(columns))
        ws.auto_filter.ref = f'A1:{last_col}1'

    # Данные
    row_idx = 2
    for sample in samples:
        for col_idx, (code, name) in enumerate(columns, 1):
            value = _get_export_value(sample, code)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font
            cell.border = thin_border

            if isinstance(value, date) and not isinstance(value, datetime):
                cell.number_format = 'DD.MM.YYYY'
                cell.alignment = date_alignment
            else:
                cell.alignment = cell_alignment

        if row_idx % 2 == 0:
            for col_idx in range(1, len(columns) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = alt_fill

        row_idx += 1

    # Автоширина
    for col_idx, (code, name) in enumerate(columns, 1):
        max_len = len(name)
        for row in range(2, min(row_idx, 52)):
            val = ws.cell(row=row, column=col_idx).value
            if val:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 3, 50)

    # ─── HTTP Response ───
    now_str = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M')
    filename = f'journal_samples_{now_str}.xlsx'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def journal_filter_options(request):
    """
    AJAX endpoint: возвращает доступные варианты фильтров
    с учётом уже выбранных фильтров (каскадность).
    """
    if not PermissionChecker.has_journal_access(request.user, 'SAMPLES'):
        return JsonResponse({'error': 'Нет доступа'}, status=403)

    user = request.user

    samples = _build_base_queryset(user)

    samples = samples.select_related(
        'laboratory', 'accreditation_area', 'standard', 'client', 'contract',
        'registered_by', 'verified_by',
    ).distinct()

    samples = _apply_filters(samples, request.GET, user)

    options = _get_filter_options_for_queryset(samples)
    return JsonResponse(options)


@login_required
@require_POST
def save_column_preferences(request):
    """
    AJAX endpoint: сохраняет выбранные столбцы в user.ui_preferences.
    POST body (JSON): {"columns": ["cipher", "client", "status", ...]}
    """
    try:
        data = json.loads(request.body)
        columns = data.get('columns', [])

        if not columns:
            return JsonResponse({'error': 'Список столбцов не может быть пустым'}, status=400)

        if columns == ['__reset__']:
            user = request.user
            prefs = user.ui_preferences or {}
            if 'journal_columns' in prefs and 'SAMPLES' in prefs['journal_columns']:
                del prefs['journal_columns']['SAMPLES']
                user.ui_preferences = prefs
                user.save(update_fields=['ui_preferences'])
            return JsonResponse({'status': 'ok', 'reset': True})

        available = set(_get_user_visible_columns(request.user))
        valid_columns = [c for c in columns if c in available]

        if not valid_columns:
            return JsonResponse({'error': 'Ни один из столбцов не доступен'}, status=400)

        user = request.user
        prefs = user.ui_preferences or {}
        if 'journal_columns' not in prefs:
            prefs['journal_columns'] = {}
        prefs['journal_columns']['SAMPLES'] = valid_columns
        user.ui_preferences = prefs
        user.save(update_fields=['ui_preferences'])

        return JsonResponse({'status': 'ok', 'columns': valid_columns})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

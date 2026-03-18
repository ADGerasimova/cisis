"""
climate_views.py — Журнал контроля параметров микроклимата
v3.35.0

Маршруты:
    path('workspace/climate/', climate_views.climate_log_view, name='climate_log')
    path('workspace/climate/add/', climate_views.climate_log_add, name='climate_log_add')
    path('workspace/climate/<int:log_id>/edit/', climate_views.climate_log_edit, name='climate_log_edit')
    path('workspace/climate/<int:log_id>/delete/', climate_views.climate_log_delete, name='climate_log_delete')
"""

from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from core.models import ClimateLog, Equipment, User
from core.models.equipment import Room

ITEMS_PER_PAGE = 50


@login_required
def climate_log_view(request):
    """Журнал климата — список записей с фильтрами."""

    # Фильтры
    room_id = request.GET.get('room', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    qs = ClimateLog.objects.select_related(
        'room', 'temp_humidity_equipment', 'pressure_equipment', 'responsible'
    ).order_by('-date', '-time')

    if room_id:
        qs = qs.filter(room_id=room_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    # Подсчёт фильтров
    active_filters = 0
    if room_id:
        active_filters += 1
    if date_from or date_to:
        active_filters += 1

    total_count = qs.count()

    # ⭐ v3.35.0: Сводка за выбранный период (помещение + хотя бы одна дата)
    summary = None
    if room_id and (date_from or date_to):
        from django.db.models import Min, Max
        agg = qs.aggregate(
            temp_min=Min('temperature'),
            temp_max=Max('temperature'),
            hum_min=Min('humidity'),
            hum_max=Max('humidity'),
            pres_min=Min('atmospheric_pressure'),
            pres_max=Max('atmospheric_pressure'),
        )
        # Показываем только если есть хоть одно значение
        if any(v is not None for v in agg.values()):
            summary = agg

    # Пагинация
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Справочники
    rooms = Room.objects.filter(is_active=True).order_by('number')

    # СИ для климата — по boolean-флагам
    equipment_temp_humidity = Equipment.objects.filter(
        is_temp_humidity=True
    ).select_related('laboratory').order_by('accounting_number')

    equipment_pressure = Equipment.objects.filter(
        is_pressure=True
    ).select_related('laboratory').order_by('accounting_number')

    users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')

    context = {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'total_count': total_count,
        'rooms': rooms,
        'equipment_temp_humidity': equipment_temp_humidity,
        'equipment_pressure': equipment_pressure,
        'users': users,
        'today': date.today().isoformat(),
        # Фильтры
        'f_room': room_id,
        'f_date_from': date_from,
        'f_date_to': date_to,
        'active_filters': active_filters,
        'summary': summary,
    }
    return render(request, 'core/climate_log.html', context)


@login_required
@require_POST
def climate_log_add(request):
    """Добавить запись в журнал климата."""
    log_date = request.POST.get('date', '').strip()
    log_time = request.POST.get('time', '').strip()
    room_id = request.POST.get('room', '').strip()

    if not log_date or not log_time or not room_id:
        messages.error(request, 'Дата, время и помещение обязательны')
        return redirect('climate_log')

    temperature = request.POST.get('temperature', '').strip() or None
    humidity = request.POST.get('humidity', '').strip() or None
    temp_eq_id = request.POST.get('temp_humidity_equipment', '').strip() or None
    pressure = request.POST.get('atmospheric_pressure', '').strip() or None
    pressure_eq_id = request.POST.get('pressure_equipment', '').strip() or None
    

    try:
        ClimateLog.objects.create(
            date=log_date,
            time=log_time,
            room_id=int(room_id),
            temperature=temperature,
            humidity=humidity,
            temp_humidity_equipment_id=int(temp_eq_id) if temp_eq_id else None,
            atmospheric_pressure=pressure,
            pressure_equipment_id=int(pressure_eq_id) if pressure_eq_id else None,
            responsible=request.user,
        )
        messages.success(request, 'Запись добавлена в журнал климата')
    except Exception as e:
        messages.error(request, f'Ошибка: {e}')

    return redirect('climate_log')


@login_required
@require_POST
def climate_log_edit(request, log_id):
    """Редактировать запись журнала климата."""
    log = get_object_or_404(ClimateLog, pk=log_id)

    log_date = request.POST.get('date', '').strip()
    log_time = request.POST.get('time', '').strip()
    room_id = request.POST.get('room', '').strip()

    if not log_date or not log_time or not room_id:
        messages.error(request, 'Дата, время и помещение обязательны')
        return redirect('climate_log')

    try:
        log.date = log_date
        log.time = log_time
        log.room_id = int(room_id)
        log.temperature = request.POST.get('temperature', '').strip() or None
        log.humidity = request.POST.get('humidity', '').strip() or None

        temp_eq_id = request.POST.get('temp_humidity_equipment', '').strip()
        log.temp_humidity_equipment_id = int(temp_eq_id) if temp_eq_id else None

        log.atmospheric_pressure = request.POST.get('atmospheric_pressure', '').strip() or None

        pressure_eq_id = request.POST.get('pressure_equipment', '').strip()
        log.pressure_equipment_id = int(pressure_eq_id) if pressure_eq_id else None

        responsible_id = request.POST.get('responsible', '').strip()
        log.responsible_id = int(responsible_id) if responsible_id else None

        log.save()
        messages.success(request, 'Запись обновлена')
    except Exception as e:
        messages.error(request, f'Ошибка: {e}')

    return redirect('climate_log')


@login_required
@require_POST
def climate_log_delete(request, log_id):
    """Удалить запись журнала климата."""
    log = get_object_or_404(ClimateLog, pk=log_id)
    log.delete()
    messages.success(request, 'Запись удалена')
    return redirect('climate_log')


# ─────────────────────────────────────────────────────────────
# ⭐ v3.35.0: Мобильная форма (QR-код)
# ─────────────────────────────────────────────────────────────

@login_required
def climate_quick_add(request):
    """Мобильная форма добавления записи (по QR-коду)."""
    from datetime import datetime as dt

    # Предзаполнение из GET-параметров (из QR-кода)
    preset_room = request.GET.get('room', '')
    preset_eq_th = request.GET.get('eq_th', '')
    preset_eq_p = request.GET.get('eq_p', '')

    rooms = Room.objects.filter(is_active=True).order_by('number')
    equipment_temp_humidity = Equipment.objects.filter(
        is_temp_humidity=True
    ).order_by('accounting_number')
    equipment_pressure = Equipment.objects.filter(
        is_pressure=True
    ).order_by('accounting_number')

    # Текущая дата/время
    now = dt.now()

    context = {
        'rooms': rooms,
        'equipment_temp_humidity': equipment_temp_humidity,
        'equipment_pressure': equipment_pressure,
        'preset_room': preset_room,
        'preset_eq_th': preset_eq_th,
        'preset_eq_p': preset_eq_p,
        'today': now.strftime('%Y-%m-%d'),
        'now_time': now.strftime('%H:%M'),
    }
    return render(request, 'core/climate_quick_add.html', context)


@login_required
@require_POST
def climate_quick_submit(request):
    """Обработка мобильной формы."""
    log_date = request.POST.get('date', '').strip()
    log_time = request.POST.get('time', '').strip()
    room_id = request.POST.get('room', '').strip()

    if not log_date or not log_time or not room_id:
        messages.error(request, 'Дата, время и помещение обязательны')
        return redirect(request.META.get('HTTP_REFERER', '/workspace/climate/quick/'))

    temperature = request.POST.get('temperature', '').strip() or None
    humidity = request.POST.get('humidity', '').strip() or None
    temp_eq_id = request.POST.get('temp_humidity_equipment', '').strip() or None
    pressure = request.POST.get('atmospheric_pressure', '').strip() or None
    pressure_eq_id = request.POST.get('pressure_equipment', '').strip() or None

    try:
        room = Room.objects.get(pk=int(room_id))
        ClimateLog.objects.create(
            date=log_date,
            time=log_time,
            room_id=int(room_id),
            temperature=temperature,
            humidity=humidity,
            temp_humidity_equipment_id=int(temp_eq_id) if temp_eq_id else None,
            atmospheric_pressure=pressure,
            pressure_equipment_id=int(pressure_eq_id) if pressure_eq_id else None,
            responsible=request.user,
        )
        return render(request, 'core/climate_quick_success.html', {
            'room': room,
            'temperature': temperature,
            'humidity': humidity,
            'pressure': pressure,
        })
    except Exception as e:
        messages.error(request, f'Ошибка: {e}')
        return redirect(request.META.get('HTTP_REFERER', '/workspace/climate/quick/'))


@login_required
def climate_qr_codes(request):
    """Страница генерации QR-кодов (для SYSADMIN)."""
    if request.user.role != 'SYSADMIN':
        messages.error(request, 'Доступ только для администратора')
        return redirect('climate_log')

    rooms = Room.objects.filter(is_active=True).order_by('number')
    equipment_temp_humidity = Equipment.objects.filter(
        is_temp_humidity=True
    ).order_by('accounting_number')
    equipment_pressure = Equipment.objects.filter(
        is_pressure=True
    ).order_by('accounting_number')

    # Базовый URL для QR-кодов
    base_url = request.build_absolute_uri('/workspace/climate/quick/')

    context = {
        'rooms': rooms,
        'equipment_temp_humidity': equipment_temp_humidity,
        'equipment_pressure': equipment_pressure,
        'base_url': base_url,
    }
    return render(request, 'core/climate_qr_codes.html', context)
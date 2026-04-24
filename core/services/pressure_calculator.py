"""
pressure_calculator.py — Расчёт атмосферного давления с поправками
⭐ v3.61.0
⭐ v3.89.0: Высотная поправка считается на РАЗНОСТЬ высот между помещением
журнала и помещением, где физически установлен барометр. Раньше барометр
молча считался стоящим на нулевом уровне, что давало некорректный результат
при его перемещении между этажами/подвалом.

Формула пересчёта (из калибровочных таблиц лаборатории):
1. Калибровочная поправка: линейная интерполяция по таблице барометра
2. Температурная поправка: P = H + ((24 − 1.2T − 0.00186T² + 0.00026T³
                                     + 0.000312×(209454 − H×1000)) / 1000) + cal_corr
3. Высотная поправка (барометрическая формула):
   Q = P × exp((-0.029 × 9.81 × Δh) / (8.314 × (T + 273.15)))
   где Δh = h_журнала − h_барометра (м)

Где:
    H           = показание барометра (кПа)
    T           = температура воздуха (°C)
    h_журнала   = высота помещения, где ведётся запись (м над нулевым уровнем)
    h_барометра = высота помещения, где физически стоит барометр (м)
"""

import math


def get_calibration_correction(equipment_id, pressure_kpa):
    """
    Калибровочная поправка по таблице барометра.
    Линейная интерполяция между двумя ближайшими точками.
    """
    if not equipment_id:
        return 0.0

    from core.models.equipment import BarometerCalibration

    calibrations = dict(
        BarometerCalibration.objects.filter(equipment_id=equipment_id)
        .values_list('reading_kpa', 'correction_kpa')
    )

    if not calibrations:
        return 0.0

    H = float(pressure_kpa)
    K = math.floor(H)
    L = K + 1

    cal = {float(k): float(v) for k, v in calibrations.items()}
    corr_K = cal.get(K)
    corr_L = cal.get(L)

    # Обе точки найдены → линейная интерполяция (аналог ПРЕДСКАЗ в Excel)
    if corr_K is not None and corr_L is not None:
        return corr_K + (H - K) * (corr_L - corr_K)

    # Одна точка → берём как есть
    if corr_K is not None:
        return corr_K
    if corr_L is not None:
        return corr_L

    # Нет подходящих точек → ближайшая
    readings = sorted(cal.keys())
    if not readings:
        return 0.0
    closest = min(readings, key=lambda r: abs(r - H))
    return cal[closest]


def _get_barometer_height_m(equipment_id):
    """
    ⭐ v3.89.0: Высота помещения, где физически установлен барометр, в метрах.

    Возвращает 0.0 (fallback на старое поведение — «барометр на нулевом
    уровне») в случаях:
      - equipment_id не задан
      - барометр не найден
      - у барометра не задано основное помещение (room_id IS NULL)
      - у помещения барометра не заполнена высота (height_above_zero IS NULL)

    Это обеспечивает обратную совместимость: пока админ не проставит высоту
    у помещения барометра, расчёт продолжит работать как раньше.
    """
    if not equipment_id:
        return 0.0

    from core.models.equipment import Equipment

    try:
        eq = Equipment.objects.select_related('room').get(pk=equipment_id)
    except Equipment.DoesNotExist:
        return 0.0

    if not eq.room_id or eq.room.height_above_zero is None:
        return 0.0

    return float(eq.room.height_above_zero)


def calculate_pressure_corrected(pressure_raw_kpa, temperature_c,
                                  height_m=None, equipment_id=None):
    """
    Полный расчёт давления с поправками.

    Args:
        pressure_raw_kpa: показание барометра, кПа
        temperature_c:    температура воздуха, °C
        height_m:         высота помещения журнала (где ведётся запись), м.
                          None → 0
        equipment_id:     ID барометра. Используется для:
                          - калибровочной таблицы
                          - ⭐ v3.89.0: определения высоты, где физически
                            установлен барометр (через equipment.room)

    Returns:
        float | None: скорректированное давление (кПа), округлённое до 0.01
    """
    if pressure_raw_kpa is None:
        return None

    H = float(pressure_raw_kpa)
    T = float(temperature_c) if temperature_c is not None else None
    h_journal = float(height_m) if height_m else 0.0

    # 1. Калибровочная поправка
    cal_corr = get_calibration_correction(equipment_id, H) if equipment_id else 0.0

    # 2. Температурная поправка + калибровка
    if T is not None:
        temp_corr = (
            24
            - 1.2 * T
            - 0.00186 * T ** 2
            + 0.00026 * T ** 3
            + 0.000312 * (209454 - H * 1000)
        ) / 1000
        P = H + temp_corr + cal_corr
    else:
        # Без температуры — только калибровка
        P = H + cal_corr

    # 3. Высотная поправка (барометрическая формула) на РАЗНОСТЬ высот
    # между точкой журнала и точкой, где стоит барометр. ⭐ v3.89.0
    h_barometer = _get_barometer_height_m(equipment_id)
    delta_h = h_journal - h_barometer

    if delta_h != 0 and T is not None:
        Q = P * math.exp((-0.029 * 9.81 * delta_h) / (8.314 * (T + 273.15)))
    else:
        Q = P

    return round(Q, 2)
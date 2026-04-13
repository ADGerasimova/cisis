"""
pressure_calculator.py — Расчёт атмосферного давления с поправками
⭐ v3.61.0

Формула пересчёта (из калибровочных таблиц лаборатории):
1. Калибровочная поправка: линейная интерполяция по таблице барометра
2. Температурная поправка: P = H + ((24 − 1.2T − 0.00186T² + 0.00026T³
                                     + 0.000312×(209454 − H×1000)) / 1000) + cal_corr
3. Высотная поправка (барометрическая формула):
   Q = P × exp((-0.029 × 9.81 × h) / (8.314 × (T + 273.15)))

Где:
    H  = показание барометра (кПа)
    T  = температура воздуха (°C)
    h  = высота помещения над нулевым уровнем (м)
"""

import math
from decimal import Decimal


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


def calculate_pressure_corrected(pressure_raw_kpa, temperature_c,
                                  height_m=None, equipment_id=None):
    """
    Полный расчёт давления с поправками.

    Args:
        pressure_raw_kpa: показание барометра, кПа
        temperature_c: температура воздуха, °C
        height_m: высота помещения над нулевым уровнем, м (None → 0)
        equipment_id: ID барометра (для калибровочной таблицы)

    Returns:
        float | None: скорректированное давление (кПа), округлённое до 0.01
    """
    if pressure_raw_kpa is None:
        return None

    H = float(pressure_raw_kpa)
    T = float(temperature_c) if temperature_c is not None else None
    h = float(height_m) if height_m else 0.0

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

    # 3. Высотная поправка (барометрическая формула)
    if h and h != 0 and T is not None:
        Q = P * math.exp((-0.029 * 9.81 * h) / (8.314 * (T + 273.15)))
    else:
        Q = P

    return round(Q, 2)

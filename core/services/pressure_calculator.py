"""
pressure_calculator.py — Расчёт атмосферного давления с поправками
⭐ v3.61.0
⭐ v3.89.0: Высотная поправка считается на РАЗНОСТЬ высот между помещением
журнала и помещением, где физически установлен барометр. Раньше барометр
молча считался стоящим на нулевом уровне, что давало некорректный результат
при его перемещении между этажами/подвалом.

⭐ v3.89.0 (fix): Если вызывающий код не передал height_m, журнал
приравнивается к высоте барометра (delta_h = 0), а не к нулю. Иначе при
ненулевой высоте барометра вылезала фантомная поправка в ситуации, когда
измерение ведётся в том же помещении, где стоит прибор.

⭐ v3.89.0: Температурная поправка применяется только если у барометра
установлен флаг apply_temperature_correction=True. Для механических приборов
(БАММ-1 и аналоги) это штатный режим — поправка обязательна по паспорту.
Для цифровых датчиков (Testo 622 и т.п.) компенсация уже выполнена внутри
прибора, поэтому флаг снимается вручную, чтобы не получить двойную поправку.

Формула пересчёта (из калибровочных таблиц лаборатории):
1. Калибровочная (шкаловая) поправка: линейная интерполяция по таблице барометра
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
    Калибровочная (шкаловая) поправка по таблице барометра.
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


def _get_barometer_meta(equipment_id):
    """
    ⭐ v3.89.0: Одним запросом возвращает метаданные барометра, нужные
    калькулятору: высоту помещения установки и флаг применения
    температурной поправки.

    Fallback-значения (возвращаются, если оборудование не задано / не
    найдено / у него нет основного помещения / высота не заполнена /
    миграция 083 ещё не применена) обеспечивают обратную совместимость
    со старым поведением калькулятора.

    Returns:
        dict:
            - 'height_m'              (float): высота помещения барометра,
                                               0.0 если не определена
            - 'apply_temp_correction' (bool):  применять ли температурную
                                               поправку, True по умолчанию
    """
    default = {'height_m': 0.0, 'apply_temp_correction': True}

    if not equipment_id:
        return default

    from core.models.equipment import Equipment

    try:
        eq = Equipment.objects.select_related('room').get(pk=equipment_id)
    except Equipment.DoesNotExist:
        return default

    if eq.room_id and eq.room.height_above_zero is not None:
        height_m = float(eq.room.height_above_zero)
    else:
        height_m = 0.0

    # getattr со значением по умолчанию True на случай, если миграция 083
    # ещё не применена локально (поля apply_temperature_correction пока нет).
    apply_temp = getattr(eq, 'apply_temperature_correction', True)

    return {
        'height_m': height_m,
        'apply_temp_correction': bool(apply_temp),
    }


def calculate_pressure_corrected(pressure_raw_kpa, temperature_c,
                                  height_m=None, equipment_id=None):
    """
    Полный расчёт давления с поправками.

    Args:
        pressure_raw_kpa: показание барометра, кПа
        temperature_c:    температура воздуха, °C
        height_m:         высота помещения журнала (где ведётся запись), м.
                          ⭐ v3.89.0: если None — приравнивается к высоте
                          барометра (delta_h = 0, поправка по высоте не
                          применяется). Явный 0.0 обрабатывается как ноль.
        equipment_id:     ID барометра. Используется для:
                          - калибровочной таблицы (шкаловой поправки)
                          - ⭐ v3.89.0: высоты помещения барометра
                            (через equipment.room)
                          - ⭐ v3.89.0: флага apply_temperature_correction

    Returns:
        float | None: скорректированное давление (кПа), округлённое до 0.01
    """
    if pressure_raw_kpa is None:
        return None

    H = float(pressure_raw_kpa)
    T = float(temperature_c) if temperature_c is not None else None

    # ⭐ v3.89.0: одним запросом достаём высоту барометра и флаг
    # применения температурной поправки. Высота используется дальше как
    # дефолт для h_journal, если вызывающий код не передал свою.
    meta = _get_barometer_meta(equipment_id)
    h_barometer = meta['height_m']
    apply_temp = meta['apply_temp_correction']

    if height_m is None:
        h_journal = h_barometer
    else:
        h_journal = float(height_m)

    # 1. Калибровочная (шкаловая) поправка — не зависит от типа барометра,
    # применяется всегда, когда есть таблица калибровки.
    cal_corr = get_calibration_correction(equipment_id, H) if equipment_id else 0.0

    # 2. Температурная поправка + калибровка.
    # ⭐ v3.89.0: температурная поправка применяется только для механических
    # барометров (apply_temp=True). Для цифровых датчиков с внутренней
    # компенсацией флаг снят, и в расчёте остаётся только калибровка.
    if T is not None and apply_temp:
        temp_corr = (
            24
            - 1.2 * T
            - 0.00186 * T ** 2
            + 0.00026 * T ** 3
            + 0.000312 * (209454 - H * 1000)
        ) / 1000
        P = H + temp_corr + cal_corr
    else:
        # Температура не задана ИЛИ прибор цифровой — только калибровка
        P = H + cal_corr

    # 3. Высотная поправка (барометрическая формула) на РАЗНОСТЬ высот
    # между точкой журнала и точкой, где стоит барометр. ⭐ v3.89.0
    delta_h = h_journal - h_barometer

    if delta_h != 0 and T is not None:
        Q = P * math.exp((-0.029 * 9.81 * delta_h) / (8.314 * (T + 273.15)))
    else:
        Q = P

    return round(Q, 2)
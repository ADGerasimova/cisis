
"""
v3.50.0: Генерация шаблона протокола из DOCX-шаблона + вставка таблиц результатов.

Файл: core/views/protocol_template_views.py
Шаблон: core/static/core/templates/protocol_template.docx

Изменения v3.50.0:
  - Вставка таблиц результатов из test_reports в DOCX-протокол.
  - Параграф «Результаты испытаний представлены в табл. N.»
  - Таблица с заголовком (D9D9D9), данными (F2F2F2), статистикой (gridSpan + vMerge).
  - Поддержка нескольких стандартов (несколько таблиц).

Изменения v3.48.0:
  - П.2: Основание для выполнения работ — Договор/Счёт + Акт ПП.
  - Рефакторинг: универсальная _inject_into_empty_cell для П.2 и П.10.

Изменения v3.47.0:
  - П.12: оборудование через абзацы ({{PARA}} → </w:p><w:p>).
  - П.10: давление мм рт. ст. → кПа; всегда диапазон «мин – макс».

Изменения v3.46.0:
  - П.1: адрес заказчика.  П.10: автозаполнение из ClimateLog.

Изменения v3.45.0:
  - Pass 0: мерж соседних run'ов.
  - Pass 1/2: замена без привязки к жёлтому выделению.
"""

import io
import os
import re
import zipfile
import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import Min, Max, Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404

from core.models import Sample, Standard, SampleStandard, ClimateLog
from core.models.equipment import Equipment, EquipmentMaintenance, Room

logger = logging.getLogger(__name__)

TEMPLATE_PATH = os.path.join(
    settings.BASE_DIR, 'core', 'static', 'core', 'templates', 'protocol_template.docx'
)

MONTHS_RU = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
    5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
    9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря',
}

# Arial 11pt, чёрный, без выделений
CLEAN_RPR = (
    '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    '<w:color w:val="000000"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/>'
)

# Arial 12pt, полужирный, чёрный (шапка «ПРОТОКОЛ ИСПЫТАНИЙ №»)
HEADER_RPR = (
    '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    '<w:b/><w:bCs/>'
    '<w:color w:val="000000"/>'
    '<w:sz w:val="24"/><w:szCs w:val="24"/>'
)

# Маркер мягкого переноса строки (Shift+Enter → <w:br/>)
_BR = '{{LBR}}'

# Маркер абзацного разрыва (Enter → </w:p><w:p>)
_PARA = '{{PARA}}'

# Коэффициент перевода мм рт. ст. → кПа
_MMHG_TO_KPA = Decimal('0.1333224')


# -----------------------------------------------------------
# Форматирование
# -----------------------------------------------------------

def _fmt(dt, style='short'):
    if dt is None:
        return ''
    d = dt.date() if hasattr(dt, 'date') and callable(dt.date) else dt
    if style == 'header':
        return f'\u00ab{d.day}\u00bb {MONTHS_RU.get(d.month, "")} {d.year}'
    return d.strftime('%d.%m.%Y')


def _fmt_decimal_ru(value, decimals=1):
    if value is None:
        return ''
    return f'{float(value):.{decimals}f}'.replace('.', ',')


def _io_fam(user):
    parts = []
    if user.first_name:
        parts.append(user.first_name[0] + '.')
    if user.sur_name:
        parts.append(user.sur_name[0] + '.')
    last = user.last_name or user.username
    init = ''.join(parts)
    return f'{init} {last}' if init else last


def _mmhg_to_kpa(val):
    if val is None:
        return None
    return Decimal(str(val)) * _MMHG_TO_KPA


# -----------------------------------------------------------
# Сборка текстов из БД
# -----------------------------------------------------------

def _standards_text(sample):
    std_ids = list(
        SampleStandard.objects.filter(sample=sample)
        .values_list('standard_id', flat=True)
    )
    if not std_ids:
        return ''
    stds = Standard.objects.filter(id__in=std_ids).order_by('code')
    return '; '.join(f'{s.code} {s.name}' for s in stds)


def _get_climate_equipment_ids(sample):
    if not sample.testing_start_datetime:
        return set()

    date_start = sample.testing_start_datetime.date()
    date_end = (
        sample.testing_end_datetime.date()
        if sample.testing_end_datetime
        else date_start
    )

    eq_ids = set()
    for qs in (
        sample.measuring_instruments.all(),
        sample.testing_equipment.all(),
        sample.auxiliary_equipment.all(),
    ):
        for e in qs:
            eq_ids.add(e.id)

    if not eq_ids:
        return set()

    room_ids = set(
        Equipment.objects.filter(id__in=eq_ids, room__isnull=False)
        .values_list('room_id', flat=True)
    )
    if not room_ids:
        return set()

    climate_equipment_ids = set()

    climate_logs = ClimateLog.objects.filter(
        room_id__in=room_ids,
        date__gte=date_start,
        date__lte=date_end
    ).select_related('temp_humidity_equipment', 'pressure_equipment')

    for log in climate_logs:
        if log.temp_humidity_equipment_id:
            climate_equipment_ids.add(log.temp_humidity_equipment_id)
        if log.pressure_equipment_id:
            climate_equipment_ids.add(log.pressure_equipment_id)

    return climate_equipment_ids


def _equipment_text(sample):
    main_eq_ids = set()
    for e in sample.measuring_instruments.all():
        main_eq_ids.add(e.id)
    for e in sample.testing_equipment.all():
        main_eq_ids.add(e.id)
    for e in sample.auxiliary_equipment.all():
        main_eq_ids.add(e.id)
    
    climate_eq_ids = _get_climate_equipment_ids(sample)
    climate_eq_ids = climate_eq_ids - main_eq_ids
    
    lines = []
    
    if main_eq_ids:
        main_eqs = Equipment.objects.filter(id__in=main_eq_ids).order_by('name')
        for eq in main_eqs:
            lines.append(_format_equipment_line(
                eq, 
                test_start=sample.testing_start_datetime, 
                test_end=sample.testing_end_datetime
            ))
    
    if climate_eq_ids:
        climate_eqs = Equipment.objects.filter(id__in=climate_eq_ids).order_by('name')
        for eq in climate_eqs:
            lines.append(_format_equipment_line(
                eq, 
                test_start=sample.testing_start_datetime, 
                test_end=sample.testing_end_datetime
            ))
    
    if not lines:
        return ''
    
    return _PARA.join(lines)


def _format_equipment_line(eq, test_start=None, test_end=None):
    line = eq.name

    if eq.factory_number:
        line += f', зав. № {eq.factory_number}'

    notes = (eq.notes or '').strip()
    if notes and notes not in ('-', '—', '–', ''):
        line += f'. {notes}'

    modifications = (eq.modifications or '').strip()
    if modifications and modifications not in ('-', '—', '–', ''):
        line += f'. {modifications}'

    maint_qs = EquipmentMaintenance.objects.filter(
        equipment=eq,
        maintenance_type__in=('VERIFICATION', 'CALIBRATION', 'ATTESTATION')
    )

    if test_start and test_end:
        maint_qs = maint_qs.filter(
            maintenance_date__lte=test_end,
            valid_until__gte=test_start,
        ).order_by('maintenance_date', 'valid_until')
    else:
        maint_qs = maint_qs.order_by('-maintenance_date')[:1]

    maint_list = list(maint_qs)

    if maint_list:
        maint_parts = []
        for maint in maint_list:
            mp = [maint.get_maintenance_type_display()]
            if maint.certificate_number:
                mp.append(f'свид. № {maint.certificate_number}')
            if maint.maintenance_date:
                mp.append(f'от {_fmt(maint.maintenance_date)}')
            if maint.valid_until:
                mp.append(f'до {_fmt(maint.valid_until)}')
            maint_parts.append(' '.join(mp))

        line += '. ' + ', '.join(maint_parts)

    line += '.'
    while '..' in line:
        line = line.replace('..', '.')

    return line


def _climate_text(sample):
    if not sample.testing_start_datetime:
        return ''

    date_start = sample.testing_start_datetime.date()
    date_end = (
        sample.testing_end_datetime.date()
        if sample.testing_end_datetime
        else date_start
    )

    eq_ids = set()
    for qs in (
        sample.measuring_instruments.all(),
        sample.testing_equipment.all(),
        sample.auxiliary_equipment.all(),
    ):
        for e in qs:
            eq_ids.add(e.id)

    if not eq_ids:
        return ''

    room_ids = set(
        Equipment.objects.filter(id__in=eq_ids, room__isnull=False)
        .values_list('room_id', flat=True)
    )
    if not room_ids:
        return ''

    rooms = Room.objects.filter(id__in=room_ids).order_by('number')
    blocks = []

    for room in rooms:
        agg = (
            ClimateLog.objects
            .filter(room=room, date__gte=date_start, date__lte=date_end)
            .aggregate(
                temp_min=Min('temperature'),
                temp_max=Max('temperature'),
                hum_min=Min('humidity'),
                hum_max=Max('humidity'),
                pres_min=Min('atmospheric_pressure'),
                pres_max=Max('atmospheric_pressure'),
            )
        )

        if not any(v is not None for v in agg.values()):
            continue

        parts = []

        if agg['temp_min'] is not None and agg['temp_max'] is not None:
            t_min = _fmt_decimal_ru(agg['temp_min'], 1)
            t_max = _fmt_decimal_ru(agg['temp_max'], 1)
            parts.append(f'Температура: {t_min} \u2013 {t_max} \u00b0С')

        if agg['hum_min'] is not None and agg['hum_max'] is not None:
            h_min = _fmt_decimal_ru(agg['hum_min'], 1)
            h_max = _fmt_decimal_ru(agg['hum_max'], 1)
            parts.append(f'относительная влажность: {h_min} \u2013 {h_max} %')

        if agg['pres_min'] is not None and agg['pres_max'] is not None:
            p_min_kpa = _mmhg_to_kpa(agg['pres_min'])
            p_max_kpa = _mmhg_to_kpa(agg['pres_max'])
            p_min = _fmt_decimal_ru(p_min_kpa, 3)
            p_max = _fmt_decimal_ru(p_max_kpa, 3)
            parts.append(f'атмосферное давление: {p_min} \u2013 {p_max} кПа')

        if not parts:
            continue

        line = (', ' + _BR).join(parts)

        if len(room_ids) > 1:
            room_label = f'Помещение {room.number}'
            if room.name:
                room_label += f' ({room.name})'
            line = f'{room_label}:{_BR}{line}'

        blocks.append(line)

    return (_BR + _BR).join(blocks)


def _basis_text(sample):
    parts = []
    if sample.contract_id and sample.contract:
        c = sample.contract
        line = f'Договор \u2116 {c.number}'
        if c.date:
            line += f' от {_fmt(c.date)}'
        line += '.'
        parts.append(line)
    elif sample.invoice_id and sample.invoice:
        inv = sample.invoice
        line = f'Счёт \u2116 {inv.number}'
        if inv.date:
            line += f' от {_fmt(inv.date)}'
        line += '.'
        parts.append(line)

    if sample.acceptance_act_id and sample.acceptance_act:
        act = sample.acceptance_act
        doc_name = (act.document_name or '').strip()
        if doc_name:
            parts.append(doc_name)

    if not parts:
        return ''
    return _BR.join(parts)


def _build_replacements(sample, user):
    stds = _standards_text(sample)
    equip = _equipment_text(sample)
    sig = _io_fam(user)

    return [
        ('Sample.pi_number', sample.pi_number or ''),
        ('Sample.report_prepared_date | format(\u201c\u00abDD\u00bb MMMM YYYY\u201d)', _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date | format("\u00abDD\u00bb MMMM YYYY")', _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date', _fmt(sample.report_prepared_date, 'header')),
        ('Sample.client.address', (getattr(sample.client, 'address', '') or '').strip() if sample.client else ''),
        ('Sample.client.name', sample.client.name if sample.client else ''),
        ('Sample.sample_received_date | format("DD.MM.YYYY")', _fmt(sample.sample_received_date)),
        ('Sample.sample_received_date', _fmt(sample.sample_received_date)),
        ('Sample.object_id', sample.object_id or ''),
        
        # Оставляем это здесь для одиночных образцов. 
        # Если образцов несколько, эта ячейка будет заменена ДО Pass 1.
        ('Sample.cipher', sample.cipher or ''),

        ('FOR std IN Sample.standards.all(): std.code + " " +std.name; \u0420\u0410\u0417\u0414\u0415\u041b\u0418\u0422\u0415\u041b\u042c "; "', stds),
        ('FOR std IN Sample.standards.all(): std.code + " " +', stds),
        ('Sample.determined_parameters)', sample.determined_parameters or ''),
        ('Sample.determined_parameters', sample.determined_parameters or ''),
        ('Sample.testing_start_datetime | format("DD.MM.YYYY")', _fmt(sample.testing_start_datetime)),
        ('Sample.testing_start_datetime', _fmt(sample.testing_start_datetime)),
        ('FOR eq IN (Sample.measuring_instruments \u222a Sample.testing_equipment): eq.name', equip),
        ('eq.maintenance_history.filter(maintenance_type="VERIFICATION").order_by("-maintenance_date").first()', ''),
        ('maintenance.maintenance_date | format("DD.MM.YYYY")', ''),
        ('maintenance.valid_until | format("DD.MM.YYYY")', ''),
        ('maintenance.maintenance_date', ''),
        ('maintenance.valid_until', ''),
        ('eq.factory_number', ''),
        ('eq.modifications', ''),
        ('eq.notes', ''),
        ('\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0437\u0430\u043f\u0438\u0441\u044c', ''),
        ('Sample.test_conditions', sample.test_conditions or ''),
        ('request.user.position', user.position or ''),
        ('request.user | format("\u0418.\u041e. \u0424\u0430\u043c\u0438\u043b\u0438\u044f")', sig),
        ('request.user | format(\u201c\u0418.\u041e. \u0424\u0430\u043c\u0438\u043b\u0438\u044f\u201d)', sig),
        ('request.user', sig),
        ('Sample.laboratory.code_display', sample.laboratory.code_display if sample.laboratory else ''),
        (' | format("DD.MM.YYYY")', ''),
        (' | format(\u201cDD.MM.YYYY\u201d)', ''),
        (' | format("\u00abDD\u00bb MMMM YYYY")', ''),
        (' | format(\u201c\u00abDD\u00bb MMMM YYYY\u201d)', ''),
        ('FOR eq IN (', ''),
        ('FOR std IN ', ''),
        ('Sample.measuring_instruments', ''),
        ('Sample.testing_equipment', ''),
        ('Sample.standards.all', ''),
        ('std.code + " " +', ''),
        ('std.name; ', ''),
        ('\u0420\u0410\u0417\u0414\u0415\u041b\u0418\u0422\u0415\u041b\u042c', ''),
        (' \u222a ', ''),
        ('): eq.name', ''),
        ('\u0424\u0430\u043c\u0438\u043b\u0438\u044f', ''),
        ('"DD.MM.YYYY")', ''),
        ('"\u00abDD\u00bb MMMM YYYY")', ''),
        (' | format("', ''),
        (' | format(', ''),
        ('format(', ''),
        (' "; "', ''),
        ('): ', ''),
        (' | ', ''),
        ('")', ''),
    ]

MIN_PASS1_LEN = 2
MIN_PASS2_LEN = 8


def _extract_run_text(run_xml):
    m = re.search(r'<w:t[^>]*>(.*?)</w:t>', run_xml, re.DOTALL)
    return m.group(1) if m else ''

def _extract_run_rpr(run_xml):
    m = re.search(r'<w:rPr>(.*?)</w:rPr>', run_xml, re.DOTALL)
    return m.group(1) if m else ''

def _extract_run_attrs(run_xml):
    m = re.match(r'<w:r\b([^>]*)>', run_xml)
    return m.group(1) if m else ''

def _normalize_placeholder(text):
    text = re.sub(r'(\w)\.\s+(\w)', r'\1.\2', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text

def _merge_placeholder_runs(xml, replacements):
    keys = set()
    for old, _new in replacements:
        if old and len(old) >= MIN_PASS1_LEN:
            keys.add(old)
            keys.add(_normalize_placeholder(old))

    run_re = re.compile(r'<w:r\b[^>]*>.*?</w:r>', re.DOTALL)

    def _process_para(p_match):
        para = p_match.group(0)
        runs = list(run_re.finditer(para))
        if len(runs) < 2:
            return para

        texts = [_extract_run_text(r.group(0)) for r in runs]
        merged_indices = set()
        merges = []
        max_window = min(len(runs), 12)
        
        for size in range(max_window, 1, -1):
            for start in range(len(runs) - size + 1):
                if any(i in merged_indices for i in range(start, start + size)):
                    continue
                combined = ''.join(texts[start:start + size])
                normalized = _normalize_placeholder(combined)
                if combined in keys or normalized in keys:
                    merges.append((start, start + size - 1, normalized))
                    for i in range(start, start + size):
                        merged_indices.add(i)

        if not merges:
            return para

        new_para = para
        for start_idx, end_idx, norm_key in sorted(merges, key=lambda x: x[0], reverse=True):
            first = runs[start_idx]
            last = runs[end_idx]

            rpr = _extract_run_rpr(first.group(0)) or CLEAN_RPR
            r_attrs = _extract_run_attrs(first.group(0))

            merged_run = (
                f'<w:r{r_attrs}>'
                f'<w:rPr>{rpr}</w:rPr>'
                f'<w:t xml:space="preserve">{norm_key}</w:t>'
                f'</w:r>'
            )

            seg_start = first.start()
            seg_end = last.end()
            new_para = new_para[:seg_start] + merged_run + new_para[seg_end:]

        return new_para

    xml = re.sub(r'<w:p\b[^>]*>.*?</w:p>', _process_para, xml, flags=re.DOTALL)
    return xml


def _inject_into_empty_cell(xml, row_label, text):
    if not text:
        return xml

    idx = xml.find(row_label)
    if idx == -1:
        return xml

    tr_start = xml.rfind('<w:tr ', 0, idx)
    if tr_start == -1:
        tr_start = xml.rfind('<w:tr>', 0, idx)
    tr_end = xml.find('</w:tr>', idx)
    if tr_start == -1 or tr_end == -1:
        return xml
    tr_end += len('</w:tr>')

    row_xml = xml[tr_start:tr_end]

    tc_pattern = re.compile(r'(<w:tc>)(.*?)(</w:tc>)', re.DOTALL)
    cells = list(tc_pattern.finditer(row_xml))
    if len(cells) < 2:
        return xml

    value_cell = cells[1]
    cell_xml = value_cell.group(0)

    run_xml = (
        '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
        '<w:t xml:space="preserve">' + text + '</w:t>'
        '</w:r>'
    )

    p_end_idx = cell_xml.rfind('</w:p>')
    if p_end_idx == -1:
        return xml

    new_cell_xml = cell_xml[:p_end_idx] + run_xml + cell_xml[p_end_idx:]

    cell_start = value_cell.start()
    cell_end = value_cell.end()
    new_row_xml = row_xml[:cell_start] + new_cell_xml + row_xml[cell_end:]

    return xml[:tr_start] + new_row_xml + xml[tr_end:]


# ═══════════════════════════════════════════════════════════
# НОВЫЙ БЛОК: Разбиение ячейки П.5 (через объединение строк)
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
# НОВЫЙ БЛОК: Разбиение ячейки П.5 (через объединение строк)
# ═══════════════════════════════════════════════════════════

def _inject_cipher_split_row(xml, sample):
    """
    Управляет строкой П.5:
    - Если образец один: объединяет 2-ю и 3-ю ячейки (gridSpan), скрывая пустой столбец.
    - Если несколько: разбивает на строки с вертикальным объединением левой ячейки (vMerge).
    """
    if not sample.pi_number:
        return xml

    idx = xml.find('Sample.cipher')
    if idx == -1:
        return xml

    # Ищем границы всей строки <w:tr>, где находится П.5
    tr_start = xml.rfind('<w:tr ', 0, idx)
    if tr_start == -1:
        tr_start = xml.rfind('<w:tr>', 0, idx)
    tr_end = xml.find('</w:tr>', idx)
    if tr_start == -1 or tr_end == -1:
        return xml
    tr_end += len('</w:tr>')

    row_xml = xml[tr_start:tr_end]

    # Извлекаем ячейки строки
    tc_pattern = re.compile(r'(<w:tc>|<w:tc [^>]*>)(.*?)(</w:tc>)', re.DOTALL)
    cells = list(tc_pattern.finditer(row_xml))
    
    if len(cells) < 3:
        # Если в шаблоне еще не разбили ячейку, просто выходим
        return xml

    first_cell_xml = cells[0].group(0)   # Левая ячейка (шапка П.5)
    second_cell_xml = cells[1].group(0)  # Средняя ячейка (Sample.cipher)
    third_cell_xml = cells[2].group(0)   # Правая ячейка (пустая)

    related_samples = sample.__class__.objects.filter(
        pi_number=sample.pi_number
    ).order_by('id')

    # ---------------------------------------------------------
    # ВЕТВКА 1: ОДИН ОБРАЗЕЦ (СЛИЯНИЕ 2 И 3 ЯЧЕЙКИ В ОДНУ)
    # ---------------------------------------------------------
    if related_samples.count() <= 1:
        # Складываем ширину второй и третьей ячейки для идеального выравнивания
        w2_match = re.search(r'<w:tcW w:w="(\d+)"', second_cell_xml)
        w3_match = re.search(r'<w:tcW w:w="(\d+)"', third_cell_xml)
        if w2_match and w3_match:
            total_w = int(w2_match.group(1)) + int(w3_match.group(1))
            second_cell_xml = re.sub(r'<w:tcW w:w="\d+"', f'<w:tcW w:w="{total_w}"', second_cell_xml)

        # Добавляем тег горизонтального объединения (gridSpan)
        if '<w:tcPr>' in second_cell_xml:
            if '<w:gridSpan' not in second_cell_xml:
                second_cell_xml = second_cell_xml.replace('<w:tcPr>', '<w:tcPr><w:gridSpan w:val="2"/>')
        else:
            second_cell_xml = re.sub(
                r'(<w:tc\b[^>]*>)', 
                r'\1<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>', 
                second_cell_xml, 
                count=1
            )

        # Собираем строку только из ПЕРВОЙ и ВТОРОЙ (объединенной) ячейки. Третью стираем.
        tr_open = re.match(r'<w:tr\b[^>]*>', row_xml).group(0)
        tr_pr_match = re.search(r'<w:trPr>.*?</w:trPr>', row_xml, re.DOTALL)
        tr_pr = tr_pr_match.group(0) if tr_pr_match else ''

        new_row = f'{tr_open}{tr_pr}{first_cell_xml}{second_cell_xml}</w:tr>'
        
        # Возвращаем XML. Дальше штатно сработает Pass 1 и заменит 'Sample.cipher'
        return xml[:tr_start] + new_row + xml[tr_end:]


    # ---------------------------------------------------------
    # ВЕТВКА 2: НЕСКОЛЬКО ОБРАЗЦОВ (РАЗБИЕНИЕ НА СТРОКИ И СТОЛБЦЫ)
    # ---------------------------------------------------------
    def extract_tcpr(cell_xml):
        m = re.search(r'<w:tcPr>.*?</w:tcPr>', cell_xml, re.DOTALL)
        return m.group(0) if m else '<w:tcPr></w:tcPr>'

    tcpr_2 = extract_tcpr(second_cell_xml)
    tcpr_3 = extract_tcpr(third_cell_xml)

    def build_cell(tcpr, text, fill=False):
        if fill:
            if '<w:shd ' in tcpr:
                tcpr = re.sub(r'<w:shd [^>]*>', '<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>', tcpr)
            else:
                tcpr = tcpr.replace('</w:tcPr>', '<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/></w:tcPr>')
        
        p = (
            f'<w:p>'
            f'<w:pPr><w:jc w:val="center"/></w:pPr>'
            f'<w:r><w:rPr>{CLEAN_RPR}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'
            f'</w:p>'
        )
        return f'<w:tc>{tcpr}{p}</w:tc>'


    # --- Подготовка левой колонки (вертикальное объединение) ---
    if '<w:tcPr>' in first_cell_xml:
        fc_restart = first_cell_xml.replace('<w:tcPr>', '<w:tcPr><w:vMerge w:val="restart"/>')
    else:
        fc_restart = re.sub(r'(<w:tc\b[^>]*>)', r'\1<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>', first_cell_xml, count=1)

    fc_continue = re.sub(r'<w:r\b[^>]*>.*?</w:r>', '', first_cell_xml, flags=re.DOTALL)
    if '<w:tcPr>' in fc_continue:
        fc_continue = fc_continue.replace('<w:tcPr>', '<w:tcPr><w:vMerge/>')
    else:
        fc_continue = re.sub(r'(<w:tc\b[^>]*>)', r'\1<w:tcPr><w:vMerge/></w:tcPr>', fc_continue, count=1)

    # --- Генерация новых строк ---
    new_rows = []

    tr_pr_match = re.search(r'<w:trPr>.*?</w:trPr>', row_xml, re.DOTALL)
    tr_pr = tr_pr_match.group(0) if tr_pr_match else '<w:trPr><w:cantSplit/></w:trPr>'

    # Строка 1: Внутренняя шапка
    row_0 = f'<w:tr>{tr_pr}{fc_restart}'
    row_0 += build_cell(tcpr_2, "Идентификационный номер", fill=False)
    row_0 += build_cell(tcpr_3, "Обозначение Заказчика", fill=False)
    row_0 += '</w:tr>'
    new_rows.append(row_0)

    # Строки 2..N: Значения шифров
    for rs in related_samples:
        r = f'<w:tr>{tr_pr}{fc_continue}'
        r += build_cell(tcpr_2, rs.cipher or '—', fill=False)
        r += build_cell(tcpr_3, '', fill=False)
        r += '</w:tr>'
        new_rows.append(r)

    return xml[:tr_start] + ''.join(new_rows) + xml[tr_end:]
# -----------------------------------------------------------
# XML-обработка
# -----------------------------------------------------------

_HEADER_KEYS = frozenset({'Sample.pi_number'})

_EQUIP_PARA_PPR = (
    '<w:pPr>'
    '<w:pStyle w:val="ab"/>'
    '<w:spacing w:before="120" w:after="120" w:line="0" w:lineRule="atLeast"/>'
    '<w:jc w:val="left"/>'
    '</w:pPr>'
)


def _process_xml(xml, sample, user):
    replacements = _build_replacements(sample, user)

    # ═══ Pass 0: Склейка разбитых run'ов ═══
    xml = _merge_placeholder_runs(xml, replacements)

    # ═══ ВСТАВКА ТАБЛИЦЫ ДЛЯ П.5 (Выполняется сразу после Pass 0) ═══
    xml = _inject_cipher_split_row(xml, sample)


    # ═══ Pass 1: Точное совпадение текста run'а с ключом замены ═══
    run_pattern = re.compile(
        r'(<w:r\b[^>]*>\s*)'
        r'(<w:rPr>)(.*?)(</w:rPr>)'
        r'(\s*<w:t)([^>]*>)(.*?)(</w:t>\s*</w:r>)',
        re.DOTALL
    )

    def _run_repl(m):
        g_open, rpr_open, rpr_body, rpr_close, g_t, g_tattr, old_text, g_end = m.groups()
        for old, new in replacements:
            if not old or len(old) < MIN_PASS1_LEN:
                continue
            if old == old_text:
                style = HEADER_RPR if old in _HEADER_KEYS else CLEAN_RPR
                return (
                    g_open
                    + rpr_open + style + rpr_close
                    + g_t + g_tattr + new + g_end
                )
        return m.group(0)

    xml = run_pattern.sub(_run_repl, xml)

    # ═══ Pass 2: Подстрочная замена в <w:t> ═══
    for old, new in replacements:
        if not old or len(old) < MIN_PASS2_LEN or old not in xml:
            continue
        escaped = re.escape(old)
        xml = re.sub(
            r'(<w:t[^>]*>)([^<]*?)' + escaped + r'([^<]*?)(</w:t>)',
            lambda m, n=new: m.group(1) + m.group(2) + n + m.group(3) + m.group(4),
            xml,
        )




    xml = _clean_equipment_cell(xml)

    basis = _basis_text(sample)
    xml = _inject_into_empty_cell(xml, 'Основание для выполнения работ', basis)

    climate = _climate_text(sample)
    xml = _inject_into_empty_cell(xml, 'Условия в помещении испытательной лаборатории', climate)

    para_xml = (
        '</w:t></w:r></w:p>'
        '<w:p>' + _EQUIP_PARA_PPR
        + '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
        '<w:t xml:space="preserve">'
    )
    xml = xml.replace(_PARA, para_xml)

    xml = _strip_empty_runs_in_equip_cell(xml)

    br_xml = (
        '</w:t></w:r>'
        '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
        '<w:br/>'
        '<w:t xml:space="preserve">'
    )
    xml = xml.replace(_BR, br_xml)

    xml = re.sub(
        r'(<w:t[^>]*>)(.*?)(</w:t>)',
        lambda m: m.group(1) + m.group(2).replace('..', '.') + m.group(3),
        xml, flags=re.DOTALL
    )

    xml = xml.replace('<w:highlight w:val="yellow"/>', '')

    def _clear_first_rows_values(xml, rows_to_clear=(0, 1, 2, 3)):
        # Находим первую таблицу
        tbl_match = re.search(r'<w:tbl\b[^>]*>.*?</w:tbl>', xml, re.DOTALL)
        if not tbl_match:
            return xml

        tbl_xml = tbl_match.group(0)

        # Все строки таблицы
        tr_pattern = re.compile(r'<w:tr\b[^>]*>.*?</w:tr>', re.DOTALL)
        rows = list(tr_pattern.finditer(tbl_xml))

        new_tbl_xml = tbl_xml

        for i, row_match in enumerate(rows):
            if i not in rows_to_clear:
                continue

            row_xml = row_match.group(0)

            # Ищем ячейки
            tc_pattern = re.compile(r'(<w:tc\b[^>]*>)(.*?)(</w:tc>)', re.DOTALL)
            cells = list(tc_pattern.finditer(row_xml))

            if len(cells) < 2:
                continue

            value_cell = cells[1]
            cell_xml = value_cell.group(0)

            # --- сохраняем стили ---
            tcpr_match = re.search(r'<w:tcPr>.*?</w:tcPr>', cell_xml, re.DOTALL)
            tcpr = tcpr_match.group(0) if tcpr_match else '<w:tcPr></w:tcPr>'

            # --- чистая ячейка ---
            cleaned_cell_xml = (
                '<w:tc>'
                f'{tcpr}'
                '<w:p>'
                '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
                '<w:t xml:space="preserve"></w:t>'
                '</w:r>'
                '</w:p>'
                '</w:tc>'
            )

            # Подмена ячейки
            row_xml_new = (
                row_xml[:value_cell.start()] +
                cleaned_cell_xml +
                row_xml[value_cell.end():]
            )

            # Подмена строки в таблице
            new_tbl_xml = new_tbl_xml.replace(row_xml, row_xml_new, 1)

        # Подмена таблицы в документе
        xml = xml.replace(tbl_xml, new_tbl_xml, 1)

        return xml


    restricted_roles = {'TESTER', 'WORKSHOP_HEAD', 'WORKSHOP'}

    if getattr(user, 'role', None) in restricted_roles:
        xml = _clear_first_rows_values(xml, rows_to_clear=(0, 1, 2, 3))

    return xml


def _clean_equipment_cell(xml):
    marker = '>зав</w:t>'
    idx = xml.find(marker)
    if idx == -1:
        return xml

    tc_start = xml.rfind('<w:tc>', 0, idx)
    tc_end = xml.find('</w:tc>', idx)
    if tc_start == -1 or tc_end == -1:
        return xml
    tc_end += len('</w:tc>')

    cell = xml[tc_start:tc_end]

    garbage = [
        ', ', 'зав', '. \u2116 ', '. № ', '. ',
        ' от', 'от', ' до', 'до', '.', ' ',
        'Последняя запись: ',
        'Последняя запись',
        'Последняя', 'запись',
        ': ',
        'eq.modifications', 'eq. modifications',
        'modifications', 'eq. ', 'eq.',
    ]
    for g in garbage:
        cell = re.sub(
            r'<w:t([^>]*)>' + re.escape(g) + r'</w:t>',
            r'<w:t\1></w:t>',
            cell
        )

    return xml[:tc_start] + cell + xml[tc_end:]


def _strip_empty_runs_in_equip_cell(xml):
    label = 'Средства измерений'
    idx = xml.find(label)
    if idx == -1:
        return xml

    tr_start = xml.rfind('<w:tr ', 0, idx)
    if tr_start == -1:
        tr_start = xml.rfind('<w:tr>', 0, idx)
    tr_end = xml.find('</w:tr>', idx)
    if tr_start == -1 or tr_end == -1:
        return xml
    tr_end += len('</w:tr>')

    row = xml[tr_start:tr_end]

    tc_positions = list(re.finditer(r'<w:tc>', row))
    if len(tc_positions) < 2:
        return xml

    second_tc_start = tc_positions[1].start()
    second_tc_end = row.find('</w:tc>', second_tc_start)
    if second_tc_end == -1:
        return xml
    second_tc_end += len('</w:tc>')

    cell = row[second_tc_start:second_tc_end]

    cell = re.sub(
        r'<w:r\b[^>]*>\s*'
        r'(?:<w:rPr>[^<]*(?:<[^/][^<]*)*</w:rPr>\s*)?'
        r'<w:t[^>]*></w:t>\s*</w:r>',
        '',
        cell,
    )
    cell = re.sub(
        r'<w:r\b[^>]*>\s*'
        r'(?:<w:rPr>[^<]*(?:<[^/][^<]*)*</w:rPr>\s*)?'
        r'<w:t[^>]*/>\s*</w:r>',
        '',
        cell,
    )

    new_row = row[:second_tc_start] + cell + row[second_tc_end:]
    return xml[:tr_start] + new_row + xml[tr_end:]


# ═══════════════════════════════════════════════════════════
# ВСТАВКА ТАБЛИЦ РЕЗУЛЬТАТОВ ИСПЫТАНИЙ В ПРОТОКОЛ
# С ПОДДЕРЖКОЙ export_settings И additional_tables
# v2.0 — исправлена работа с sub_measurements
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
# ВСТАВКА ТАБЛИЦ РЕЗУЛЬТАТОВ ИСПЫТАНИЙ В ПРОТОКОЛ
# v3.0 — Исправленная логика export_settings
# ═══════════════════════════════════════════════════════════

import json
import math
import re
import statistics as stats_module
import logging

logger = logging.getLogger(__name__)

_TBL_RPR = '<w:rFonts w:cs="Arial"/><w:szCs w:val="20"/>'
_SKIP_CODES = frozenset({'br'})
_STAT_LABELS = [
    ('mean', 'Среднее арифметическое значение'),
    ('stdev', 'Стандартное отклонение'),
    ('cv', 'Коэффициент вариации, %'),
    ('ci', 'Границы доверительного интервала среднего значения для P\u00a0=\u00a00,95'),
]


def _inject_results_tables(xml, sample):
    tables_xml = _build_results_tables_xml(sample)
    if not tables_xml:
        return xml

    marker = '</w:tbl>'
    pos = xml.find(marker)
    if pos == -1:
        return xml
    pos += len(marker)
    return xml[:pos] + tables_xml + xml[pos:]


# ═══════════════════════════════════════════════════════════
# ЗАГРУЗКА ДАННЫХ
# ═══════════════════════════════════════════════════════════

def _load_report_data(report):
    """Загружает все данные из отчёта."""
    # export_settings
    export_settings = {}
    if hasattr(report, 'export_settings') and report.export_settings:
        export_settings = report.export_settings if isinstance(report.export_settings, dict) else {}
    
    # additional_tables_data
    additional_tables_data = {}
    if hasattr(report, 'additional_tables_data') and report.additional_tables_data:
        additional_tables_data = report.additional_tables_data if isinstance(report.additional_tables_data, dict) else {}
    
    return export_settings, additional_tables_data


def _load_template_config(template):
    """Загружает конфигурацию из шаблона."""
    # additional_tables (конфиг)
    additional_tables = []
    if hasattr(template, 'additional_tables') and template.additional_tables:
        additional_tables = template.additional_tables if isinstance(template.additional_tables, list) else []
    
    # sub_measurements_config
    sub_config = None
    
    # Сначала ищем в additional_tables
    for at in additional_tables:
        if at.get('table_type') == 'SUB_MEASUREMENTS':
            sub_config = at
            break
    
    # Fallback на старый формат
    if not sub_config and hasattr(template, 'sub_measurements_config') and template.sub_measurements_config:
        sub_config = template.sub_measurements_config
    
    return additional_tables, sub_config


# ═══════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════════

def _build_results_tables_xml(sample):
    from core.models import TestReport

    reports = list(
        TestReport.objects.filter(
            sample=sample,
            status__in=('COMPLETED', 'APPROVED'),
        )
        .select_related('template')
        .order_by('standard_id')
    )
    
    if not reports:
        return ''

    all_tables = []

    for report in reports:
        tpl = report.template
        if not tpl:
            continue

        # ═══ ЗАГРУЗКА ДАННЫХ ═══
        export_settings = {}
        
        # Пробуем загрузить export_settings
        raw_export = getattr(report, 'export_settings', None)
        
        # ═══ ОТЛАДКА ═══
        print(f"\n{'='*60}")
        print(f"Report ID: {report.id}")
        print(f"Standard: {report.standard.code if report.standard else 'N/A'}")
        print(f"raw export_settings type: {type(raw_export)}")
        print(f"raw export_settings value: {raw_export}")
        
        if raw_export:
            if isinstance(raw_export, dict):
                export_settings = raw_export
            elif isinstance(raw_export, str):
                try:
                    export_settings = json.loads(raw_export)
                except:
                    export_settings = {}
        
        print(f"parsed export_settings: {export_settings}")
        
        # ═══ ДАННЫЕ ОТЧЁТА ═══
        col_cfg = tpl.column_config or []
        tbl_data = report.table_data or {}
        stats = report.statistics_data or {}
        specimens = tbl_data.get('specimens', [])
        
        additional_tables_config, sub_config = _load_template_config(tpl)
        additional_tables_data = {}
        raw_at_data = getattr(report, 'additional_tables_data', None)
        if raw_at_data:
            if isinstance(raw_at_data, dict):
                additional_tables_data = raw_at_data
            elif isinstance(raw_at_data, str):
                try:
                    additional_tables_data = json.loads(raw_at_data)
                except:
                    pass

        # ══════════════════════════════════════════════════════
        # 1. ТАБЛИЦА ПРОМЕЖУТОЧНЫХ ЗАМЕРОВ (sub_measurements)
        # ══════════════════════════════════════════════════════
        
        export_sub = export_settings.get('sub_measurements', False)
        print(f"  sub_measurements: {export_sub}")
        
        if export_sub:
            if sub_config:
                sub_table = _build_sub_measurements_table(sub_config, specimens)
                if sub_table:
                    print(f"    → ✅ Adding sub_measurements")
                    all_tables.append(sub_table)
                else:
                    print(f"    → ⚠️ Empty sub_measurements table")
            else:
                print(f"    → ⚠️ No sub_config in template")
        else:
            print(f"    → ❌ Skipped (disabled)")

        # ══════════════════════════════════════════════════════
        # 2. ОСНОВНАЯ ТАБЛИЦА (main)
        # ══════════════════════════════════════════════════════
        
        export_main = export_settings.get('main', False)  # ← ИЗМЕНЕНО НА FALSE!
        print(f"  main: {export_main}")
        
        if export_main:
            cols = [c for c in col_cfg if c.get('code') not in _SKIP_CODES]
            if cols and specimens:
                print(f"    → ✅ Adding main table ({len(cols)} cols, {len(specimens)} rows)")
                stat_labels = _get_stat_labels_for_cols(cols, stats)
                all_tables.append({
                    'title': None,
                    'cols': cols,
                    'specimens': specimens,
                    'stats': stats,
                    'stat_labels': stat_labels,
                })
            else:
                print(f"    → ⚠️ No columns or specimens")
        else:
            print(f"    → ❌ Skipped (disabled)")

        # ══════════════════════════════════════════════════════
        # 3. ДОПОЛНИТЕЛЬНЫЕ ТАБЛИЦЫ
        # ══════════════════════════════════════════════════════
        
        for at_cfg in additional_tables_config:
            at_id = at_cfg.get('id', '')
            table_type = at_cfg.get('table_type', '')
            
            if table_type == 'SUB_MEASUREMENTS':
                continue
            
            export_at = export_settings.get(at_id, False)
            print(f"  {at_id}: {export_at}")
            
            if not export_at:
                print(f"    → ❌ Skipped (disabled)")
                continue
            
            at_data = additional_tables_data.get(at_id, {})
            at_specimens = at_data.get('specimens', [])
            
            if not at_specimens:
                print(f"    → ⚠️ No data")
                continue
            
            at_cols = [c for c in at_cfg.get('columns', []) if c.get('code') not in _SKIP_CODES]
            if not at_cols:
                print(f"    → ⚠️ No columns")
                continue
            
            at_stats = _compute_stats_for_table(at_cols, at_specimens)
            at_stat_labels = _get_stat_labels_for_cols(at_cols, at_stats)
            
            print(f"    → ✅ Adding table '{at_id}'")
            all_tables.append({
                'title': at_cfg.get('title', ''),
                'cols': at_cols,
                'specimens': at_specimens,
                'stats': at_stats,
                'stat_labels': at_stat_labels,
            })

        print(f"{'='*60}")

    print(f"\n🎯 TOTAL TABLES TO RENDER: {len(all_tables)}\n")

    if not all_tables:
        return ''

    # Рендерим таблицы
    parts = []

    count = len(all_tables)
    if count == 1:
        intro = 'Результаты испытаний представлены в табл.\u00a01.'
    else:
        nums = ',\u00a0'.join(str(i + 1) for i in range(count))
        intro = f'Результаты испытаний представлены в табл.\u00a0{nums}.'
    parts.append(_res_para(intro, align='both'))

    for tbl_num, tbl_info in enumerate(all_tables, 1):
        caption = f'Таблица {tbl_num}'
        if tbl_info.get('title'):
            caption += f'. {tbl_info["title"]}'
        parts.append(_res_para(caption, align='right'))

        parts.append(_build_result_table(
            tbl_info['cols'],
            tbl_info['specimens'],
            tbl_info['stats'],
            tbl_info.get('stat_labels'),
        ))

    return ''.join(parts)


# ═══════════════════════════════════════════════════════════
# ПОСТРОЕНИЕ ТАБЛИЦЫ ПРОМЕЖУТОЧНЫХ ЗАМЕРОВ
# ═══════════════════════════════════════════════════════════

def _build_sub_measurements_table(sub_config, specimens):
    """
    Строит таблицу промежуточных замеров из specimens[].sub_measurements
    """
    columns = sub_config.get('columns', [])
    if not columns:
        return None
    
    mpp = sub_config.get('measurements_per_specimen', 3)
    
    # Проверяем что есть данные
    has_data = any(spec.get('sub_measurements') for spec in specimens)
    if not has_data:
        return None
    
    # Строим столбцы
    expanded_cols = []
    
    # Номер образца
    expanded_cols.append({
        'code': 'specimen_number',
        'name': '№',
        'type': 'INPUT',
    })
    
    for col in columns:
        code = col.get('code', '')
        name = col.get('name', code)
        unit = col.get('unit', '')
        col_type = col.get('type', 'INPUT')
        formula = col.get('formula', '')
        
        is_aggregate = bool(re.match(r'^\s*(MIN|MAX|AVERAGE|SUM)\s*\(', formula, re.IGNORECASE)) if formula else False
        is_text = col_type == 'TEXT'
        
        if is_aggregate or is_text:
            # Один столбец
            expanded_cols.append({
                'code': code,
                'name': name,
                'unit': unit,
                'type': col_type,
                'statistics': col.get('statistics', []),
            })
        else:
            # mpp столбцов (для каждого замера)
            for m in range(mpp):
                expanded_cols.append({
                    'code': f'{code}_{m}',
                    'name': f'{name}₍{m+1}₎',
                    'unit': unit,
                    'type': col_type,
                    'statistics': [],
                })
    
    # Строим данные
    table_specimens = []
    
    for i, spec in enumerate(specimens):
        sub_data = spec.get('sub_measurements', {})
        
        row = {
            'number': i + 1,
            'values': {},
        }
        
        for col in columns:
            code = col.get('code', '')
            col_type = col.get('type', 'INPUT')
            formula = col.get('formula', '')
            measurements = sub_data.get(code, [])
            
            is_aggregate = bool(re.match(r'^\s*(MIN|MAX|AVERAGE|SUM)\s*\(', formula, re.IGNORECASE)) if formula else False
            is_text = col_type == 'TEXT'
            
            if is_aggregate:
                # Вычисляем агрегат
                valid = [v for v in measurements if v is not None and isinstance(v, (int, float))]
                if valid:
                    match = re.match(r'^\s*(MIN|MAX|AVERAGE|SUM)', formula, re.IGNORECASE)
                    if match:
                        func = match.group(1).upper()
                        if func == 'MIN':
                            row['values'][code] = min(valid)
                        elif func == 'MAX':
                            row['values'][code] = max(valid)
                        elif func == 'AVERAGE':
                            row['values'][code] = sum(valid) / len(valid)
                        elif func == 'SUM':
                            row['values'][code] = sum(valid)
            elif is_text:
                row['values'][code] = measurements[0] if measurements else ''
            else:
                # Разворачиваем в отдельные столбцы
                for m in range(mpp):
                    col_code = f'{code}_{m}'
                    val = measurements[m] if m < len(measurements) else None
                    row['values'][col_code] = val
        
        table_specimens.append(row)
    
    # Статистика
    stats = _compute_stats_for_table(expanded_cols, table_specimens)
    stat_labels = _get_stat_labels_for_cols(expanded_cols, stats)
    
    return {
        'title': sub_config.get('title', 'Промежуточные замеры'),
        'cols': expanded_cols,
        'specimens': table_specimens,
        'stats': stats,
        'stat_labels': stat_labels,
    }


# ═══════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (статистика, рендеринг)
# ═══════════════════════════════════════════════════════════

def _get_column_statistics(col):
    stats = col.get('statistics')
    if isinstance(stats, list):
        return stats
    if col.get('has_stats') is True:
        return ['MEAN', 'STDEV', 'CV', 'CONFIDENCE']
    return []


def _get_stat_labels_for_cols(cols, stats):
    needed = set()
    for col in cols:
        for st in _get_column_statistics(col):
            needed.add(st)

    type_to_key = {'MEAN': 'mean', 'STDEV': 'stdev', 'CV': 'cv', 'CONFIDENCE': 'ci'}
    key_to_type = {v: k for k, v in type_to_key.items()}

    result = []
    for key, label in _STAT_LABELS:
        stat_type = key_to_type.get(key, '')
        if stat_type in needed:
            result.append((key, label))
    return result


def _compute_stats_for_table(cols, specimens):
    if len(specimens) < 2:
        return {}

    result = {}
    t_table = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262, 15: 2.145, 20: 2.093}

    for col in cols:
        code = col.get('code', '')
        col_stats = _get_column_statistics(col)
        if not col_stats:
            continue

        values = []
        for spec in specimens:
            v = spec.get('values', {}).get(code)
            if v is not None and isinstance(v, (int, float)):
                values.append(float(v))

        n = len(values)
        if n < 2:
            continue

        mean_val = stats_module.mean(values)
        stdev_val = stats_module.stdev(values)
        cv_val = (stdev_val / mean_val * 100) if mean_val != 0 else 0.0

        t_val = t_table.get(n) or t_table.get(min(t_table.keys(), key=lambda k: abs(k - n)))
        margin = t_val * stdev_val / math.sqrt(n)

        entry = {}
        if 'MEAN' in col_stats:
            entry['mean'] = round(mean_val, 4)
        if 'STDEV' in col_stats:
            entry['stdev'] = round(stdev_val, 4)
        if 'CV' in col_stats:
            entry['cv'] = round(cv_val, 2)
        if 'CONFIDENCE' in col_stats:
            entry['ci_lo'] = round(mean_val - margin, 4)
            entry['ci_hi'] = round(mean_val + margin, 4)

        if entry:
            result[code] = entry

    return result


# ═══════════════════════════════════════════════════════════
# РЕНДЕРИНГ (оставляем без изменений)
# ═══════════════════════════════════════════════════════════

def _res_para(text, align='both'):
    jc = f'<w:jc w:val="{align}"/>'
    rpr = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="22"/><w:szCs w:val="22"/>'
    return (
        f'<w:p><w:pPr><w:spacing w:before="120" w:after="120" w:line="240" w:lineRule="auto"/>'
        f'{jc}<w:rPr>{rpr}</w:rPr></w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def _fv(val, max_dec=4):
    if val is None or val == '':
        return ''
    if isinstance(val, str):
        return val
    try:
        f = float(val)
        if f == int(f) and abs(f) < 1e12:
            return str(int(f))
        s = f'{f:.{max_dec}f}'.rstrip('0').rstrip('.')
        return s.replace('.', ',')
    except (ValueError, TypeError):
        return str(val)


def _col_header_text(col):
    name = col.get('name', '')
    unit = col.get('unit', '')
    return f'{name}, {unit}' if unit else name


def _col_widths_pct(cols, total=4891):
    weights = []
    for c in cols:
        code = c.get('code', '')
        tp = c.get('type', '')
        if code == 'specimen_number':
            weights.append(1)
        elif tp == 'TEXT' and code in ('marking', 'failure_mode'):
            weights.append(3)
        elif tp == 'TEXT':
            weights.append(2)
        elif tp == 'SUB_AVG':
            weights.append(1.2)
        else:
            weights.append(1.5)
    s = sum(weights)
    ws = [int(total * w / s) for w in weights]
    ws[0] += total - sum(ws)
    return ws


def _tc(text, w, fill=None, gs=None, vm=False, vmr=False):
    pr = [f'<w:tcW w:w="{w}" w:type="pct"/>']
    if gs and gs > 1:
        pr.append(f'<w:gridSpan w:val="{gs}"/>')
    if fill == 'D9D9D9':
        pr.append('<w:tcBorders><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tcBorders>')
        pr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>')
    elif fill == 'F2F2F2':
        pr.append(f'<w:shd w:val="pct10" w:color="auto" w:fill="F2F2F2"/>')
    if vmr:
        pr.append('<w:vMerge w:val="restart"/>')
    elif vm:
        pr.append('<w:vMerge/>')
    pr.append('<w:vAlign w:val="center"/>')
    tcp = '<w:tcPr>' + ''.join(pr) + '</w:tcPr>'

    if fill == 'D9D9D9':
        pp = '<w:pPr><w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:contextualSpacing/><w:jc w:val="center"/><w:rPr>' + _TBL_RPR + '</w:rPr></w:pPr>'
    else:
        pp = '<w:pPr><w:spacing w:after="0" w:line="360" w:lineRule="auto"/><w:jc w:val="center"/><w:rPr>' + _TBL_RPR + '</w:rPr></w:pPr>'

    run = f'<w:r><w:rPr>{_TBL_RPR}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'

    return f'<w:tc>{tcp}<w:p>{pp}{run}</w:p></w:tc>'


def _build_result_table(cols, specimens, stats, stat_labels=None):
    n = len(cols)
    if n == 0:
        return ''

    if stat_labels is None:
        stat_labels = list(_STAT_LABELS)

    ws = _col_widths_pct(cols)

    tbl_pr = (
        '<w:tblPr><w:tblW w:w="4891" w:type="pct"/><w:tblInd w:w="108" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders>'
        '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
    )

    total_twips = 9418
    tw = [int(total_twips * w / 4891) for w in ws]
    tw[0] += total_twips - sum(tw)
    grid = '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{t}"/>' for t in tw) + '</w:tblGrid>'

    rows = []

    # Заголовок
    hdr_cells = [_tc(_col_header_text(col), ws[i], fill='D9D9D9') for i, col in enumerate(cols)]
    rows.append('<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="70"/></w:trPr>' + ''.join(hdr_cells) + '</w:tr>')

    # Данные
    for ri, spec in enumerate(specimens):
        vals = spec.get('values', {})
        cells = []
        for i, col in enumerate(cols):
            code = col.get('code', '')
            if code == 'specimen_number':
                v = str(spec.get('number', ri + 1))
            elif code == 'marking':
                v = str(spec.get('marking', ''))
            else:
                v = _fv(vals.get(code, ''))
            f = 'F2F2F2' if i == 0 else None
            cells.append(_tc(v, ws[i], fill=f))
        rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + ''.join(cells) + '</w:tr>')

    # Статистика
    if stats and stat_labels:
        stat_col_map = {}
        for i, col in enumerate(cols):
            code = col.get('code', '')
            col_stat_types = _get_column_statistics(col)
            if code in stats and col_stat_types:
                stat_col_map[i] = code

        if stat_col_map:
            first_si = min(stat_col_map)
            last_si = max(stat_col_map)
            after_count = n - last_si - 1
            if first_si < 1:
                first_si = 1
            label_w = sum(ws[:first_si])
            after_w = sum(ws[last_si + 1:]) if after_count > 0 else 0
            key_to_type = {'mean': 'MEAN', 'stdev': 'STDEV', 'cv': 'CV', 'ci': 'CONFIDENCE'}

            for si, (key, label) in enumerate(stat_labels):
                stat_type = key_to_type.get(key, '')
                cells = [_tc(label, label_w, fill='F2F2F2', gs=first_si if first_si > 1 else None)]

                for ci in range(first_si, last_si + 1):
                    code = stat_col_map.get(ci)
                    if code:
                        col = cols[ci]
                        col_stat_types = _get_column_statistics(col)
                        if stat_type and stat_type not in col_stat_types:
                            v = '\u2013'
                        else:
                            entry = stats.get(code, {})
                            if key == 'ci':
                                lo, hi = entry.get('ci_lo'), entry.get('ci_hi')
                                v = f'от {_fv(lo)} до {_fv(hi)}' if lo is not None and hi is not None else '\u2013'
                            else:
                                raw = entry.get(key)
                                v = _fv(raw) if raw is not None else '\u2013'
                    else:
                        v = '\u2013'
                    cells.append(_tc(v, ws[ci]))

                if after_count > 0:
                    if si == 0:
                        cells.append(_tc('\u2013', after_w, gs=after_count if after_count > 1 else None, vmr=True))
                    else:
                        cells.append(_tc('', after_w, gs=after_count if after_count > 1 else None, vm=True))

                rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + ''.join(cells) + '</w:tr>')

    return '<w:tbl>' + tbl_pr + grid + ''.join(rows) + '</w:tbl>'
# -----------------------------------------------------------
# View
# -----------------------------------------------------------

ALLOWED_STATUSES = frozenset([
    'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
    'PROTOCOL_ISSUED', 'COMPLETED',
])

@login_required
def generate_protocol_template(request, sample_id):
    sample = get_object_or_404(
        Sample.objects.select_related(
            'client', 'laboratory', 'contract', 'invoice', 'acceptance_act',
        ),
        id=sample_id,
    )
    if sample.status not in ALLOWED_STATUSES:
        raise Http404('Шаблон протокола недоступен для данного статуса')
    if not os.path.isfile(TEMPLATE_PATH):
        logger.error(f'Шаблон протокола не найден: {TEMPLATE_PATH}')
        raise Http404('Файл шаблона не найден')

    output = io.BytesIO()
    with zipfile.ZipFile(TEMPLATE_PATH, 'r') as zin:
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'word/document.xml':
                    xml_str = data.decode('utf-8')
                    xml_str = _process_xml(xml_str, sample, request.user)
                    xml_str = _inject_results_tables(xml_str, sample)
                    data = xml_str.encode('utf-8')
                zout.writestr(item, data)

    output.seek(0)
    cipher_safe = re.sub(r'[^\w\-.]', '_', sample.cipher or str(sample.id))
    filename = f'Protocol_{cipher_safe}.docx'

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

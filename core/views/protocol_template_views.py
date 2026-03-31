"""
v3.47.0: Генерация шаблона протокола из DOCX-шаблона.

Файл: core/views/protocol_template_views.py
Шаблон: core/static/core/templates/protocol_template.docx

Изменения v3.47.0:
  - П.12: оборудование разделяется АБЗАЦАМИ (Enter), а не переносом
    строки (Shift+Enter). Новый маркер {{PARA}}.
  - П.10: давление конвертируется из мм рт. ст. → кПа (* 0.133322).
  - П.10: формат всегда «мин – макс» даже при одном замере.

Изменения v3.46.0:
  - П.1: добавлен адрес заказчика (Sample.client.address).
  - П.10: автозаполнение условий из ClimateLog.

Изменения v3.45.0:
  - Pass 0: мерж соседних run'ов.
  - Pass 1/2: замена по тексту, без привязки к жёлтому.
"""

import io
import os
import re
import zipfile
import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import Min, Max
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

# Маркер переноса строки (Shift+Enter → <w:br/>)
_BR = '{{LBR}}'

# Маркер нового абзаца (Enter → </w:p><w:p>)
_PARA = '{{PARA}}'

# Коэффициент пересчёта мм рт. ст. → кПа
MMHG_TO_KPA = Decimal('0.133322')


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
    """
    Форматирует Decimal / float в строку с русской запятой.
    _fmt_decimal_ru(Decimal('22.05'), 1) → '22,0'
    _fmt_decimal_ru(Decimal('100.803'), 3) → '100,803'
    """
    if value is None:
        return ''
    return f'{float(value):.{decimals}f}'.replace('.', ',')


def _io_fam(user):
    """И.О. Фамилия"""
    parts = []
    if user.first_name:
        parts.append(user.first_name[0] + '.')
    if user.sur_name:
        parts.append(user.sur_name[0] + '.')
    last = user.last_name or user.username
    init = ''.join(parts)
    return f'{init} {last}' if init else last


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


def _equipment_text(sample):
    """
    П.12: Список оборудования. Каждое — отдельным абзацем ({{PARA}}).
    """
    eq_ids = set()
    for e in sample.measuring_instruments.all():
        eq_ids.add(e.id)
    for e in sample.testing_equipment.all():
        eq_ids.add(e.id)
    for e in sample.auxiliary_equipment.all():
        eq_ids.add(e.id)
    if not eq_ids:
        return ''
    eqs = Equipment.objects.filter(id__in=eq_ids).order_by('name')
    lines = []
    for eq in eqs:
        line = eq.name
        if eq.factory_number:
            line += f', зав. \u2116 {eq.factory_number}'
        notes = (eq.notes or '').strip()
        if notes and notes not in ('-', '\u2014', '\u2013', ''):
            line += f'. {notes}'

        modifications = (eq.modifications or '').strip()
        if modifications and modifications not in ('-', '\u2014', '\u2013', ''):
            line += f'. {modifications}'
        maint = (
            EquipmentMaintenance.objects
            .filter(equipment=eq, maintenance_type__in=(
                'VERIFICATION', 'CALIBRATION', 'ATTESTATION'))
            .order_by('-maintenance_date').first()
        )
        if maint:
            mp = [maint.get_maintenance_type_display()]
            if maint.certificate_number:
                mp.append(f'свид. \u2116 {maint.certificate_number}')
            if maint.maintenance_date:
                mp.append(f'от {_fmt(maint.maintenance_date)}')
            if maint.valid_until:
                mp.append(f'до {_fmt(maint.valid_until)}')
            line += '. ' + ' '.join(mp)
        line += '.'
        while '..' in line:
            line = line.replace('..', '.')
        lines.append(line)
    # v3.47.0: {{PARA}} — каждый прибор отдельным абзацем (Enter)
    return _PARA.join(lines)


def _client_text(sample):
    """П.1: Название заказчика + адрес (через запятую)."""
    if not sample.client:
        return ''
    name = sample.client.name or ''
    address = getattr(sample.client, 'address', '') or ''
    address = address.strip()
    if address:
        return f'{name}, {address}'
    return name


def _climate_text(sample):
    """
    П.10: Условия в помещении из журнала климата.

    Логика:
    1. Собираем все комнаты (Room) из оборудования образца.
    2. Берём диапазон дат: testing_start … testing_end.
    3. Для каждой комнаты агрегируем ClimateLog: min/max.
    4. Давление конвертируется: мм рт. ст. → кПа (* 0.133322).
    5. Формат ВСЕГДА «мин – макс» (даже при одном замере).
    """
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

        # Температура — всегда мин – макс
        if agg['temp_min'] is not None and agg['temp_max'] is not None:
            t_min = _fmt_decimal_ru(agg['temp_min'], 1)
            t_max = _fmt_decimal_ru(agg['temp_max'], 1)
            parts.append(f'Температура: {t_min} \u2013 {t_max} \u00b0С')

        # Влажность — всегда мин – макс
        if agg['hum_min'] is not None and agg['hum_max'] is not None:
            h_min = _fmt_decimal_ru(agg['hum_min'], 1)
            h_max = _fmt_decimal_ru(agg['hum_max'], 1)
            parts.append(
                f'относительная влажность: {h_min} \u2013 {h_max} %'
            )

        # Давление — конвертация мм рт. ст. → кПа, всегда мин – макс
        if agg['pres_min'] is not None and agg['pres_max'] is not None:
            kpa_min = float(agg['pres_min']) * float(MMHG_TO_KPA)
            kpa_max = float(agg['pres_max']) * float(MMHG_TO_KPA)
            p_min = _fmt_decimal_ru(kpa_min, 3)
            p_max = _fmt_decimal_ru(kpa_max, 3)
            parts.append(
                f'атмосферное давление: {p_min} \u2013 {p_max} кПа'
            )

        if not parts:
            continue

        line = (',' + _BR).join(parts)

        if len(room_ids) > 1:
            room_label = f'Помещение {room.number}'
            if room.name:
                room_label += f' ({room.name})'
            line = f'{room_label}:{_BR}{line}'

        blocks.append(line)

    return (_BR + _BR).join(blocks)


# -----------------------------------------------------------
# Карта замен: плейсхолдер → значение
# -----------------------------------------------------------

def _build_replacements(sample, user):
    stds = _standards_text(sample)
    equip = _equipment_text(sample)
    sig = _io_fam(user)
    client_full = _client_text(sample)

    return [
        # --- Номер протокола ---
        ('Sample.pi_number', sample.pi_number or ''),

        # --- Дата протокола ---
        ('Sample.report_prepared_date | format(\u201c\u00abDD\u00bb MMMM YYYY\u201d)',
         _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date | format("\u00abDD\u00bb MMMM YYYY")',
         _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date', _fmt(sample.report_prepared_date, 'header')),

        # --- П.1 Заказчик ---
        ('Sample.client.address',
         getattr(sample.client, 'address', '') or '' if sample.client else ''),
        ('Sample.client.name', client_full),

        # --- П.3 ---
        ('Sample.sample_received_date | format("DD.MM.YYYY")',
         _fmt(sample.sample_received_date)),
        ('Sample.sample_received_date', _fmt(sample.sample_received_date)),

        # --- П.4 ---
        ('Sample.object_id', sample.object_id or ''),

        # --- П.5 ---
        ('Sample.cipher', sample.cipher or ''),

        # --- П.6 Стандарты ---
        ('FOR std IN Sample.standards.all(): std.code + " " +std.name; \u0420\u0410\u0417\u0414\u0415\u041b\u0418\u0422\u0415\u041b\u042c "; "', stds),
        ('FOR std IN Sample.standards.all(): std.code + " " +', stds),

        # --- П.7 ---
        ('Sample.determined_parameters)', sample.determined_parameters or ''),
        ('Sample.determined_parameters', sample.determined_parameters or ''),

        # --- П.8 ---
        ('Sample.testing_start_datetime | format("DD.MM.YYYY")',
         _fmt(sample.testing_start_datetime)),
        ('Sample.testing_start_datetime', _fmt(sample.testing_start_datetime)),

        # --- П.12 Оборудование ---
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

        # --- П.14 Условия ---
        ('Sample.test_conditions', sample.test_conditions or ''),

        # --- Подпись ---
        ('request.user.position', user.position or ''),
        ('request.user | format("\u0418.\u041e. \u0424\u0430\u043c\u0438\u043b\u0438\u044f")', sig),
        ('request.user | format(\u201c\u0418.\u041e. \u0424\u0430\u043c\u0438\u043b\u0438\u044f\u201d)', sig),
        ('request.user', sig),
        ('Sample.laboratory.code_display', sample.laboratory.code_display if sample.laboratory else ''),

        # --- Хвосты формата ---
        (' | format("DD.MM.YYYY")', ''),
        (' | format(\u201cDD.MM.YYYY\u201d)', ''),
        (' | format("\u00abDD\u00bb MMMM YYYY")', ''),
        (' | format(\u201c\u00abDD\u00bb MMMM YYYY\u201d)', ''),

        # --- Остатки шаблонных конструкций ---
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


# Минимальная длина ключа для Pass 1.
MIN_PASS1_LEN = 2
# Минимальная длина для Pass 2.
MIN_PASS2_LEN = 8


# -----------------------------------------------------------
# Pass 0: Мерж соседних run'ов, образующих плейсхолдер
# -----------------------------------------------------------

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
        for start_idx, end_idx, norm_key in sorted(
            merges, key=lambda x: x[0], reverse=True
        ):
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
            new_para = new_para[:first.start()] + merged_run + new_para[last.end():]

        return new_para

    xml = re.sub(r'<w:p\b[^>]*>.*?</w:p>', _process_para, xml, flags=re.DOTALL)
    return xml


# -----------------------------------------------------------
# Инъекция текста в пустую ячейку П.10
# -----------------------------------------------------------

def _inject_climate_into_cell(xml, climate_text):
    """
    Находит строку таблицы с «10. Условия в помещении испытательной
    лаборатории», берёт вторую (пустую) ячейку и вставляет текст.

    Ячейка П.10 в шаблоне пустая — в ней нет плейсхолдера.
    Остальные пункты работают через плейсхолдеры внутри ячеек.
    Подход различается, т.к. здесь ячейка изначально пуста.
    При желании можно добавить плейсхолдер в шаблон и перейти
    на общую карту замен.
    """
    if not climate_text:
        return xml

    marker = 'Условия в помещении испытательной лаборатории'
    idx = xml.find(marker)
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
        '<w:t xml:space="preserve">' + climate_text + '</w:t>'
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


# -----------------------------------------------------------
# XML-обработка
# -----------------------------------------------------------

_HEADER_KEYS = frozenset({
    'Sample.pi_number',
})

# pPr для новых абзацев оборудования (П.12) — компактный интервал
_EQUIP_PARA_PPR = (
    '<w:pPr>'
    '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
    '</w:pPr>'
)


def _process_xml(xml, sample, user):
    replacements = _build_replacements(sample, user)

    # ═══ Pass 0: Склейка разбитых run'ов ═══
    xml = _merge_placeholder_runs(xml, replacements)

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

    # ═══ Pass 2: Подстрочная замена в <w:t> (ловит остатки) ═══
    for old, new in replacements:
        if not old or len(old) < MIN_PASS2_LEN or old not in xml:
            continue
        escaped = re.escape(old)
        xml = re.sub(
            r'(<w:t[^>]*>)([^<]*?)' + escaped + r'([^<]*?)(</w:t>)',
            lambda m, n=new: m.group(1) + m.group(2) + n + m.group(3) + m.group(4),
            xml,
        )

    # ═══ Очистка мусора в ячейке п.12 ═══
    xml = _clean_equipment_cell(xml)

    # ═══ П.10: Инъекция данных климата ═══
    climate = _climate_text(sample)
    xml = _inject_climate_into_cell(xml, climate)

    # ═══ Новые абзацы: {{PARA}} → </w:p><w:p> ═══
    # Идёт ДО обработки {{LBR}}, т.к. PARA — разрыв абзаца,
    # а LBR — перенос строки внутри абзаца.
    para_xml = (
        '</w:t></w:r></w:p>'
        '<w:p>' + _EQUIP_PARA_PPR
        + '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
        '<w:t xml:space="preserve">'
    )
    xml = xml.replace(_PARA, para_xml)

    # ═══ Переносы строк: {{LBR}} → <w:br/> ═══
    br_xml = (
        '</w:t></w:r>'
        '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
        '<w:br/>'
        '<w:t xml:space="preserve">'
    )
    xml = xml.replace(_BR, br_xml)

    # ═══ Двойные точки ═══
    xml = re.sub(
        r'(<w:t[^>]*>)(.*?)(</w:t>)',
        lambda m: m.group(1) + m.group(2).replace('..', '.') + m.group(3),
        xml, flags=re.DOTALL
    )

    # ═══ Убираем ВСЕ жёлтые выделения ═══
    xml = xml.replace('<w:highlight w:val="yellow"/>', '')

    return xml


def _clean_equipment_cell(xml):
    """Очистка мусорных статических run'ов в ячейке п.12."""
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


# -----------------------------------------------------------
# View
# -----------------------------------------------------------

ALLOWED_STATUSES = frozenset([
    'TESTED', 'DRAFT_READY', 'RESULTS_UPLOADED',
    'PROTOCOL_ISSUED', 'COMPLETED',
])


@login_required
def generate_protocol_template(request, sample_id):
    """
    v3.47.0: Генерация предзаполненного шаблона протокола (DOCX).
    GET /workspace/samples/<id>/protocol-template/
    """
    sample = get_object_or_404(
        Sample.objects.select_related('client', 'laboratory'),
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
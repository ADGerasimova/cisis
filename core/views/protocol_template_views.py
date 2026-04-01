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


def _mmhg_to_kpa(val):
    """Конвертация мм рт. ст. → кПа."""
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


def _equipment_text(sample):
    """
    П.12: Собирает текст оборудования.
    Каждый прибор отделяется маркером {{PARA}} (абзацный разрыв).
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
    return _PARA.join(lines)


def _climate_text(sample):
    """
    П.10: Условия в помещении из журнала климата.

    Давление конвертируется: мм рт. ст. → кПа (* 0.1333224).
    Формат ВСЕГДА «мин – макс» (даже при одном замере).
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

        # Температура (всегда мин – макс)
        if agg['temp_min'] is not None and agg['temp_max'] is not None:
            t_min = _fmt_decimal_ru(agg['temp_min'], 1)
            t_max = _fmt_decimal_ru(agg['temp_max'], 1)
            parts.append(f'Температура: {t_min} \u2013 {t_max} \u00b0С')

        # Влажность (всегда мин – макс)
        if agg['hum_min'] is not None and agg['hum_max'] is not None:
            h_min = _fmt_decimal_ru(agg['hum_min'], 1)
            h_max = _fmt_decimal_ru(agg['hum_max'], 1)
            parts.append(f'относительная влажность: {h_min} \u2013 {h_max} %')

        # Давление: мм рт. ст. → кПа (всегда мин – макс)
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
    """
    П.2: Основание для выполнения работ.

    Формат:
        Договор № 2025.04.10-Т107/МСП-АВД от 10.04.2025.
        Акт приема-передачи образцов и документации № К-985 от 09.06.2025.

    Или:
        Счёт № 123 от 15.05.2025.
    """
    parts = []

    # Строка 1: Договор или Счёт
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

    # Строка 2: Акт приёма-передачи (если есть)
    if sample.acceptance_act_id and sample.acceptance_act:
        act = sample.acceptance_act
        doc_name = (act.document_name or '').strip()
        if doc_name:
            parts.append(doc_name)

    if not parts:
        return ''
    return _BR.join(parts)


# -----------------------------------------------------------
# Карта замен: плейсхолдер → значение
# -----------------------------------------------------------

def _build_replacements(sample, user):
    stds = _standards_text(sample)
    equip = _equipment_text(sample)
    sig = _io_fam(user)

    return [
        # --- Номер протокола ---
        ('Sample.pi_number', sample.pi_number or ''),

        # --- Дата протокола ---
        ('Sample.report_prepared_date | format(\u201c\u00abDD\u00bb MMMM YYYY\u201d)',
         _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date | format("\u00abDD\u00bb MMMM YYYY")',
         _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date', _fmt(sample.report_prepared_date, 'header')),

        # --- П.1 Заказчик (имя и адрес — отдельные замены) ---
        ('Sample.client.address',
         (getattr(sample.client, 'address', '') or '').strip() if sample.client else ''),
        ('Sample.client.name',
         sample.client.name if sample.client else ''),

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
# Минимальная длина для Pass 2 (подстрочная замена в <w:t>).
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


# -----------------------------------------------------------
# Инъекция текста в пустую ячейку по метке строки
# -----------------------------------------------------------

def _inject_into_empty_cell(xml, row_label, text):
    """
    Универсальная инъекция текста во вторую (пустую) ячейку
    строки таблицы, найденной по row_label.
    Используется для П.2 и П.10.
    """
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


# -----------------------------------------------------------
# XML-обработка
# -----------------------------------------------------------

_HEADER_KEYS = frozenset({
    'Sample.pi_number',
})

# pPr для новых абзацев оборудования (П.12) — копия из шаблона
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
    # v3.47.1: удаляем мусорные run'ы ЦЕЛИКОМ, а не просто
    # обнуляем <w:t>. Иначе пустые <w:r> остаются в абзаце
    # последнего прибора после раскрытия {{PARA}}.
    xml = _clean_equipment_cell(xml)

    # ═══ П.2: Инъекция основания для выполнения работ ═══
    basis = _basis_text(sample)
    xml = _inject_into_empty_cell(xml, 'Основание для выполнения работ', basis)

    # ═══ П.10: Инъекция данных климата ═══
    climate = _climate_text(sample)
    xml = _inject_into_empty_cell(xml, 'Условия в помещении испытательной лаборатории', climate)

    # ═══ Новые абзацы: {{PARA}} → </w:p><w:p> ═══
    para_xml = (
        '</w:t></w:r></w:p>'
        '<w:p>' + _EQUIP_PARA_PPR
        + '<w:r><w:rPr>' + CLEAN_RPR + '</w:rPr>'
        '<w:t xml:space="preserve">'
    )
    xml = xml.replace(_PARA, para_xml)

    # ═══ Чистка пустых run'ов в ячейке п.12 ═══
    # После {{PARA}} раскрытия мусорные run'ы (обнулённые ранее)
    # оказались в абзаце последнего прибора — удаляем их целиком.
    xml = _strip_empty_runs_in_equip_cell(xml)

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
    """
    Очистка мусорных статических run'ов в ячейке п.12.
    Обнуляем текст (безопасно), а не удаляем run'ы целиком.
    """
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
    """
    Удаляет пустые run'ы из ячейки п.12 (оборудование).
    Вызывается ПОСЛЕ {{PARA}} раскрытия, чтобы последний абзац
    не содержал пустых run'ов от обнулённого мусора.
    Находит ячейку по тексту заголовка строки «Средства измерений».
    """
    label = 'Средства измерений'
    idx = xml.find(label)
    if idx == -1:
        return xml

    # Находим <w:tr> содержащий метку
    tr_start = xml.rfind('<w:tr ', 0, idx)
    if tr_start == -1:
        tr_start = xml.rfind('<w:tr>', 0, idx)
    tr_end = xml.find('</w:tr>', idx)
    if tr_start == -1 or tr_end == -1:
        return xml
    tr_end += len('</w:tr>')

    row = xml[tr_start:tr_end]

    # Вторая ячейка — ячейка значений
    tc_positions = list(re.finditer(r'<w:tc>', row))
    if len(tc_positions) < 2:
        return xml

    second_tc_start = tc_positions[1].start()
    second_tc_end = row.find('</w:tc>', second_tc_start)
    if second_tc_end == -1:
        return xml
    second_tc_end += len('</w:tc>')

    cell = row[second_tc_start:second_tc_end]

    # Удаляем run'ы с пустым <w:t></w:t>
    cell = re.sub(
        r'<w:r\b[^>]*>\s*'
        r'(?:<w:rPr>[^<]*(?:<[^/][^<]*)*</w:rPr>\s*)?'
        r'<w:t[^>]*></w:t>\s*</w:r>',
        '',
        cell,
    )
    # Удаляем self-closing <w:t/>
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
# v3.50.0
# ═══════════════════════════════════════════════════════════

# rPr для ячеек таблицы результатов (Arial ~10pt)
_TBL_RPR = '<w:rFonts w:cs="Arial"/><w:szCs w:val="20"/>'

# Коды столбцов, исключаемых из протокола
_SKIP_CODES = frozenset({'br'})

# Метки строк статистики в порядке вывода
_STAT_LABELS = [
    ('mean', 'Среднее арифметическое значение'),
    ('stdev', 'Стандартное отклонение'),
    ('cv', 'Коэффициент вариации, %'),
    ('ci', 'Границы доверительного интервала среднего значения '
           'для P\u00a0=\u00a00,95'),
]


def _inject_results_tables(xml, sample):
    """
    Вставка таблиц результатов из test_reports между основной
    таблицей (секции 1-14) и подписью.

    Точка вставки: сразу после </w:tbl>.
    """
    tables_xml = _build_results_tables_xml(sample)
    if not tables_xml:
        return xml

    marker = '</w:tbl>'
    pos = xml.find(marker)
    if pos == -1:
        return xml
    pos += len(marker)
    return xml[:pos] + tables_xml + xml[pos:]


def _build_results_tables_xml(sample):
    """
    Построение XML всех таблиц результатов для образца.

    Возвращает: строку XML (параграфы + таблицы) или '' если нет данных.
    """
    from core.models.test_reports import TestReport

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

    parts = []

    # ── Вводный параграф ──
    count = len(reports)
    if count == 1:
        intro = 'Результаты испытаний представлены в табл.\u00a01.'
    else:
        nums = ',\u00a0'.join(str(i + 1) for i in range(count))
        intro = f'Результаты испытаний представлены в табл.\u00a0{nums}.'
    parts.append(_res_para(intro, align='both'))

    tbl_num = 1
    for report in reports:
        tpl = report.template
        if not tpl:
            continue
        col_cfg = tpl.column_config or []
        tbl_data = report.table_data or {}
        stats = report.statistics_data or {}
        specimens = tbl_data.get('specimens', [])

        # Фильтруем столбцы
        cols = [c for c in col_cfg if c.get('code') not in _SKIP_CODES]
        if not cols:
            continue

        # Заголовок «Таблица N»
        parts.append(_res_para(f'Таблица {tbl_num}', align='right'))

        # Сама таблица
        parts.append(_build_result_table(cols, specimens, stats))

        tbl_num += 1

    return ''.join(parts)


def _res_para(text, align='both'):
    """Параграф для секции результатов (Arial 11pt)."""
    jc = f'<w:jc w:val="{align}"/>'
    rpr = (
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
        '<w:sz w:val="22"/><w:szCs w:val="22"/>'
    )
    return (
        f'<w:p><w:pPr>'
        f'<w:spacing w:before="120" w:after="120" '
        f'w:line="240" w:lineRule="auto"/>'
        f'{jc}<w:rPr>{rpr}</w:rPr></w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr>'
        f'<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def _fv(val, max_dec=4):
    """
    Форматирование числа для таблицы протокола.
    Русская запятая, удаление trailing zeros.
    """
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
    """Текст заголовка столбца: имя + единица измерения."""
    name = col.get('name', '')
    unit = col.get('unit', '')
    if unit:
        return f'{name}, {unit}'
    return name


def _col_widths_pct(cols, total=4891):
    """
    Расчёт ширин столбцов в pct (из 5000).

    Весовые коэффициенты:
        specimen_number: 1 (узкий — только «№»)
        TEXT (marking, failure_mode): 3 (широкие текстовые)
        TEXT (прочие): 2
        SUB_AVG: 1.2 (размеры — средние)
        INPUT/CALCULATED: 1.5 (числовые)
    """
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
    # Корректируем остаток на первый столбец
    ws[0] += total - sum(ws)
    return ws


def _tc(text, w, fill=None, gs=None, vm=False, vmr=False):
    """
    Построение XML одной ячейки таблицы <w:tc>.

    Args:
        text: содержимое ячейки
        w: ширина в pct
        fill: 'D9D9D9' (заголовок) | 'F2F2F2' (данные/стат.) | None
        gs: gridSpan (объединение столбцов)
        vm: True для vMerge (продолжение вертикального объединения)
        vmr: True для vMerge restart (начало вертикального объединения)
    """
    # ── tcPr ──
    pr = [f'<w:tcW w:w="{w}" w:type="pct"/>']
    if gs and gs > 1:
        pr.append(f'<w:gridSpan w:val="{gs}"/>')
    if fill == 'D9D9D9':
        pr.append(
            '<w:tcBorders>'
            '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
            '</w:tcBorders>'
        )
        pr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>')
    elif fill == 'F2F2F2':
        pr.append(f'<w:shd w:val="pct10" w:color="auto" w:fill="F2F2F2"/>')
    if vmr:
        pr.append('<w:vMerge w:val="restart"/>')
    elif vm:
        pr.append('<w:vMerge/>')
    pr.append('<w:vAlign w:val="center"/>')
    tcp = '<w:tcPr>' + ''.join(pr) + '</w:tcPr>'

    # ── pPr (заголовок vs данные) ──
    if fill == 'D9D9D9':
        pp = (
            '<w:pPr>'
            '<w:spacing w:before="20" w:after="20" '
            'w:line="240" w:lineRule="auto"/>'
            '<w:contextualSpacing/>'
            '<w:jc w:val="center"/>'
            f'<w:rPr>{_TBL_RPR}</w:rPr>'
            '</w:pPr>'
        )
    else:
        pp = (
            '<w:pPr>'
            '<w:spacing w:after="0" w:line="360" w:lineRule="auto"/>'
            f'<w:jc w:val="center"/><w:rPr>{_TBL_RPR}</w:rPr>'
            '</w:pPr>'
        )

    # ── run ──
    run = (
        f'<w:r><w:rPr>{_TBL_RPR}</w:rPr>'
        f'<w:t xml:space="preserve">{text}</w:t></w:r>'
    )

    return f'<w:tc>{tcp}<w:p>{pp}{run}</w:p></w:tc>'


def _build_result_table(cols, specimens, stats):
    """
    Построение полной XML-таблицы результатов для одного стандарта.

    Структура (из примера протокола):
        ┌───────────────────────────────────────────────┐
        │ Заголовок (D9D9D9): №, Маркировка, A, P, σ…  │
        ├───────────────────────────────────────────────┤
        │ Данные (F2F2F2 на №): 1, К292_1, 2500, …     │
        │ ...                                           │
        ├───────────────────────────────────────────────┤
        │ Среднее [gridSpan] │ значение │ «–» [vMerge]  │
        │ Ст.откл [gridSpan] │ значение │     [vMerge]  │
        │ CV, %   [gridSpan] │ значение │     [vMerge]  │
        │ ДИ      [gridSpan] │ значение │     [vMerge]  │
        └───────────────────────────────────────────────┘
    """
    n = len(cols)
    if n == 0:
        return ''

    ws = _col_widths_pct(cols)

    # ── tblPr ──
    tbl_pr = (
        '<w:tblPr>'
        '<w:tblW w:w="4891" w:type="pct"/>'
        '<w:tblInd w:w="108" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '</w:tblBorders>'
        '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0"'
        ' w:firstColumn="1" w:lastColumn="0"'
        ' w:noHBand="0" w:noVBand="1"/>'
        '</w:tblPr>'
    )

    # ── tblGrid (twips пропорционально pct) ──
    total_twips = 9418
    tw = [int(total_twips * w / 4891) for w in ws]
    tw[0] += total_twips - sum(tw)  # корректируем остаток
    grid = (
        '<w:tblGrid>'
        + ''.join(f'<w:gridCol w:w="{t}"/>' for t in tw)
        + '</w:tblGrid>'
    )

    rows = []

    # ═══ Строка заголовка ═══
    hdr_cells = []
    for i, col in enumerate(cols):
        hdr_cells.append(_tc(_col_header_text(col), ws[i], fill='D9D9D9'))
    rows.append(
        '<w:tr><w:trPr><w:cantSplit/>'
        '<w:trHeight w:val="70"/></w:trPr>'
        + ''.join(hdr_cells)
        + '</w:tr>'
    )

    # ═══ Строки данных ═══
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
            # Лёгкая заливка на первой ячейке (как в примере)
            f = 'F2F2F2' if i == 0 else None
            cells.append(_tc(v, ws[i], fill=f))
        rows.append(
            '<w:tr><w:trPr><w:cantSplit/></w:trPr>'
            + ''.join(cells)
            + '</w:tr>'
        )

    # ═══ Строки статистики ═══
    if stats:
        # Определяем индексы столбцов со статистикой
        stat_col_map = {}
        for i, col in enumerate(cols):
            code = col.get('code', '')
            if code in stats:
                stat_col_map[i] = code

        if stat_col_map:
            first_si = min(stat_col_map)
            last_si = max(stat_col_map)
            after_count = n - last_si - 1

            # Гарантируем минимум 1 столбец под метку
            if first_si < 1:
                first_si = 1

            label_w = sum(ws[:first_si])
            after_w = sum(ws[last_si + 1:]) if after_count > 0 else 0

            for si, (key, label) in enumerate(_STAT_LABELS):
                cells = []

                # ── Ячейка метки (объединение первых столбцов) ──
                cells.append(_tc(
                    label, label_w,
                    fill='F2F2F2',
                    gs=first_si if first_si > 1 else None,
                ))

                # ── Ячейки значений (от first_si до last_si) ──
                for ci in range(first_si, last_si + 1):
                    code = stat_col_map.get(ci)
                    if code:
                        entry = stats.get(code, {})
                        if key == 'ci':
                            lo = entry.get('ci_lo')
                            hi = entry.get('ci_hi')
                            if lo is not None and hi is not None:
                                v = f'от {_fv(lo)} до {_fv(hi)}'
                            else:
                                v = '\u2013'
                        else:
                            raw = entry.get(key)
                            v = _fv(raw) if raw is not None else '\u2013'
                    else:
                        # Столбец между стат. столбцами, но без данных
                        v = '\u2013'
                    cells.append(_tc(v, ws[ci]))

                # ── Объединённые ячейки после статистики (vMerge) ──
                if after_count > 0:
                    if si == 0:
                        # Первая стат. строка: начало vMerge
                        cells.append(_tc(
                            '\u2013', after_w,
                            gs=after_count if after_count > 1 else None,
                            vmr=True,
                        ))
                    else:
                        # Продолжение vMerge
                        cells.append(_tc(
                            '', after_w,
                            gs=after_count if after_count > 1 else None,
                            vm=True,
                        ))

                rows.append(
                    '<w:tr><w:trPr><w:cantSplit/></w:trPr>'
                    + ''.join(cells)
                    + '</w:tr>'
                )

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
    """
    v3.50.0: Генерация предзаполненного шаблона протокола (DOCX).
    GET /workspace/samples/<id>/protocol-template/

    Включает:
      - Замена плейсхолдеров данными образца (Pass 0/1/2)
      - Инъекция текста в П.2 и П.10
      - Вставка таблиц результатов из test_reports
    """
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
                    # Pass 0/1/2: замена плейсхолдеров + инъекция текстов
                    xml_str = _process_xml(xml_str, sample, request.user)
                    # v3.50.0: вставка таблиц результатов
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
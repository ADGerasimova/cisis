"""
v3.44.0: Генерация шаблона протокола из DOCX-шаблона.

Файл: core/views/protocol_template_views.py
Шаблон: core/static/core/templates/protocol_template.docx
"""

import io
import os
import re
import zipfile
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404

from core.models import Sample, Standard, SampleStandard
from core.models.equipment import Equipment, EquipmentMaintenance

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

# Маркер переноса строки
_BR = '{{LBR}}'


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
    return _BR.join(lines)


# -----------------------------------------------------------
# Карта замен: плейсхолдер → значение
# -----------------------------------------------------------
# Главная стратегия: ТЕКСТОВАЯ замена внутри <w:t>.
# Не зависит от жёлтого выделения или разбивки на run'ы.
# Порядок: длинные строки ПЕРЕД короткими (чтобы не
# «съедать» часть длинного плейсхолдера).
# -----------------------------------------------------------

def _build_replacements(sample, user):
    stds = _standards_text(sample)
    equip = _equipment_text(sample)
    sig = _io_fam(user)

    return [
        # --- Номер протокола ---
        ('Sample.pi_number', sample.pi_number or ''),

        # --- Дата протокола (разные склейки) ---
        ('Sample.report_prepared_date | format(\u201c\u00abDD\u00bb MMMM YYYY\u201d)',
         _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date | format("\u00abDD\u00bb MMMM YYYY")',
         _fmt(sample.report_prepared_date, 'header')),
        ('Sample.report_prepared_date', _fmt(sample.report_prepared_date, 'header')),

        # --- П.1 Заказчик ---
        ('Sample.client.name', sample.client.name if sample.client else ''),

        # --- П.3 ---
        ('Sample.sample_received_date | format("DD.MM.YYYY")',
         _fmt(sample.sample_received_date)),
        ('Sample.sample_received_date', _fmt(sample.sample_received_date)),

        # --- П.4 ---
        ('Sample.object_id', sample.object_id or ''),

        # --- П.5 ---
        ('Sample.cipher', sample.cipher or ''),

        # --- П.6 Стандарты (длинная → короткие) ---
        ('FOR std IN Sample.standards.all(): std.code + " " +std.name; \u0420\u0410\u0417\u0414\u0415\u041b\u0418\u0422\u0415\u041b\u042c "; "', stds),
        ('FOR std IN Sample.standards.all(): std.code + " " +', stds),
        ('FOR std IN ', stds),
        ('Sample.standards.all', ''),
        ('std.code', ''),
        (' + " " +', ''),
        ('std.name; ', ''),
        ('\u0420\u0410\u0417\u0414\u0415\u041b\u0418\u0422\u0415\u041b\u042c', ''),
        (' "; "', ''),
        ('): ', ''),

        # --- П.7 ---
        ('Sample.determined_parameters)', sample.determined_parameters or ''),
        ('Sample.determined_parameters', sample.determined_parameters or ''),

        # --- П.8 ---
        ('Sample.testing_start_datetime | format("DD.MM.YYYY")',
         _fmt(sample.testing_start_datetime)),
        ('Sample.testing_start_datetime', _fmt(sample.testing_start_datetime)),

        # --- П.12 Оборудование (длинная → короткие) ---
        ('FOR eq IN (Sample.measuring_instruments \u222a Sample.testing_equipment): eq.name', equip),
        ('FOR eq IN (', equip),
        ('Sample.measuring_instruments', ''),
        (' \u222a ', ''),
        ('Sample.testing_equipment', ''),
        ('): eq.name', ''),
        ('eq.factory_number', ''),
        ('eq.factory', ''),
        ('_number', ''),
        ('eq.notes', ''),
        ('eq.modifications', ''),
        ('eq.maintenance_history.filter(maintenance_type="VERIFICATION").order_by("-maintenance_date").first()', ''),
        ('eq.maintenance', ''),
        ('_history.filter(maintenance_type="VERIFICATION").order_by("-maintenance_date").first()', ''),
        ('maintenance.maintenance_date | format("DD.MM.YYYY")', ''),
        ('maintenance.maintenance_date', ''),
        ('maintenance.valid_until | format("DD.MM.YYYY")', ''),
        ('maintenance.valid_until', ''),
        ('\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f', ''),
        ('\u0437\u0430\u043f\u0438\u0441\u044c', ''),

        # --- П.14 Условия ---
        ('Sample.test_conditions', sample.test_conditions or ''),
        

        # --- Подпись ---
        ('request.user.position', user.position or ''),
        ('request.user | format("', sig),
        ('request.user | format(\u201c', sig),
        ('request.user', sig),
        ('Sample.laboratory.code', sample.laboratory.code if sample.laboratory else ''),
        ('\u0424\u0430\u043c\u0438\u043b\u0438\u044f', ''),

        # --- Хвосты формата (встречаются многократно) ---
        (' | format("DD.MM.YYYY")', ''),
        (' | format(\u201cDD.MM.YYYY\u201d)', ''),
        ('"DD.MM.YYYY")', ''),
        (' | format("\u00abDD\u00bb MMMM YYYY")', ''),
        ('"\u00abDD\u00bb MMMM YYYY")', ''),
        (' | format("', ''),
        (' | ', ''),
        ('format(', ''),

        # --- Одиночные run'ы (для Pass 1, когда Word разбивает текст) ---
        # ВАЖНО: эти записи идут ПОСЛЕ длинных, чтобы не перебить их
        ('Sample.', ''),
        ('pi_number', sample.pi_number or ''),
        ('request.', ''),
        ('user.position', user.position or ''),
        ('eq.factory', ''),
        ('_number', ''),
        ('eq.maintenance', ''),
        ('_history.filter(maintenance_type="VERIFICATION").order_by("-maintenance_date").first()', ''),
        ('\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f', ''),
        ('\u0437\u0430\u043f\u0438\u0441\u044c', ''),
        (': ', ''),
        ('\xa0', ''),
        (' ', ''),
        ('\u0418', ''),
        ('.', ''),
        ('\u041e', ''),
        ('. ', ''),
        ('")', ''),
    ]

# Минимальная длина плейсхолдера для Pass 2 (текстовая замена).
# Короткие записи ('. ', 'И', '.', и т.д.) опасны как подстроки —
# они обрабатываются только в Pass 1 (точное совпадение run'а).
MIN_TEXT_REPLACE_LEN = 8


# -----------------------------------------------------------
# XML-обработка
# -----------------------------------------------------------

def _process_xml(xml, sample, user):
    replacements = _build_replacements(sample, user)

    # ═══ Проход 1: Замена жёлтых run'ов (с правильным rPr) ═══
    # Находим все <w:r> с <w:highlight w:val="yellow"/>, пытаемся подставить
    # значение И установить правильный шрифт (CLEAN_RPR / HEADER_RPR).
    run_pattern = re.compile(
        r'(<w:r\b[^>]*>\s*)'
        r'<w:rPr>(.*?)</w:rPr>'
        r'(\s*<w:t)([^>]*>)(.*?)(</w:t>\s*</w:r>)',
        re.DOTALL
    )

    # Ключи для header-стиля
    header_keys = {'Sample.', 'pi_number', 'Sample.pi_number',
                   'Sample. pi_number', 'Samplepi_number'}

    def _run_repl(m):
        g1, rpr, g3, g4, old_text, g6 = m.groups()
        if 'w:val="yellow"' not in rpr:
            return m.group(0)

        for old, new in replacements:
            if old == old_text:
                style = HEADER_RPR if old in header_keys else CLEAN_RPR
                return g1 + '<w:rPr>' + style + '</w:rPr>' + g3 + g4 + new + g6
        return m.group(0)

    xml = run_pattern.sub(_run_repl, xml)

    # ═══ Проход 2: Текстовая замена в <w:t> (ловит все остатки) ═══
    # Не зависит от жёлтого / rPr — просто ищет плейсхолдер в тексте.
    # Короткие паттерны пропускаем (они опасны как подстроки).
    for old, new in replacements:
        if not old or len(old) < MIN_TEXT_REPLACE_LEN or old not in xml:
            continue
        escaped = re.escape(old)
        xml = re.sub(
            r'(<w:t[^>]*>)([^<]*?)' + escaped + r'([^<]*?)(</w:t>)',
            lambda m, n=new: m.group(1) + m.group(2) + n + m.group(3) + m.group(4),
            xml,
        )

    # ═══ Очистка мусора в ячейке п.12 ═══
    xml = _clean_equipment_cell(xml)

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
        # Может быть уже убрано или по-другому
        return xml

    tc_start = xml.rfind('<w:tc>', 0, idx)
    tc_end = xml.find('</w:tc>', idx)
    if tc_start == -1 or tc_end == -1:
        return xml
    tc_end += len('</w:tc>')

    cell = xml[tc_start:tc_end]

    # Обнуляем мусорные тексты (только точное совпадение содержимого <w:t>)
    for g in [', ', 'зав', '. \u2116 ', '. № ', '. ',
              ' от', 'от', ' до', 'до', '.', ' ',
              '\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0437\u0430\u043f\u0438\u0441\u044c: ',
              '\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f', '\u0437\u0430\u043f\u0438\u0441\u044c',
              ': ']:
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
    v3.44.0: Генерация предзаполненного шаблона протокола (DOCX).
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
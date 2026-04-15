"""
Views для генерации этикеток образцов.
Генерирует PDF A4 с этикетками на листе (2 колонки, динамическая высота).
Единый шаблон с тремя блоками:
  1. Шапка (общее): шифр крупно, материал, тип испытания, УЗК
  2. Мастерская (только при manufacturing=True): срок изгот., стандарт нарезки,
     направление вырезки, панель, примечания мастерской
  3. Испытания: все остальные поля + пустые ячейки для ручного заполнения
"""

import io
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.models import Sample, Laboratory
from core.permissions import PermissionChecker

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Регистрация шрифтов
# ─────────────────────────────────────────────────────────────
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONTS_DIR = os.path.join(BASE_DIR, 'fonts')

FONT_PATH = os.path.join(FONTS_DIR, 'DejaVuSans.ttf')
FONT_BOLD_PATH = os.path.join(FONTS_DIR, 'DejaVuSans-Bold.ttf')

try:
    pdfmetrics.registerFont(TTFont('DejaVu', FONT_PATH))
    pdfmetrics.registerFont(TTFont('DejaVuBold', FONT_BOLD_PATH))
    logger.info('Шрифты DejaVu успешно зарегистрированы')
except Exception as e:
    logger.exception(f'Не удалось загрузить шрифты DejaVu: {e}')

# ─────────────────────────────────────────────────────────────
# Константы макета
# ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4

COLS = 2
ROWS = 4
MARGIN_X = 10 * mm
MARGIN_Y = 8 * mm
GAP_X = 6 * mm
GAP_Y = 5 * mm

LABEL_W = (PAGE_W - 2 * MARGIN_X - (COLS - 1) * GAP_X) / COLS
LABEL_H = (PAGE_H - 2 * MARGIN_Y - (ROWS - 1) * GAP_Y) / ROWS

PADDING = 2 * mm
FONT_SIZE_CIPHER = 8
FONT_SIZE_DATA = 5.5
FONT_SIZE_SMALL = 5
LINE_HEIGHT = FONT_SIZE_DATA * 0.45 * mm + 1.2 * mm
SEPARATOR_GAP = 0.8 * mm + 0.3 * mm


# ─────────────────────────────────────────────────────────────
# Шаблон этикетки — три блока
# ─────────────────────────────────────────────────────────────

# Каждый auto_field: (label, field_code, is_bold_value)

# Блок 1 — Шапка (всегда). Шифр рисуется отдельно крупным шрифтом.
HEADER_FIELDS = [
    ('Материал',   'material',           False),
    ('Тип испыт.', 'test_type',          False),
    ('Кол-во обр.', 'sample_count_display', False),
    ('УЗК',        'uzk_required',       False),
]

# Блок 2 — Мастерская (только при manufacturing=True)
WORKSHOP_FIELDS = [
    ('Срок изгот.',    'manufacturing_deadline',  False),
    ('Панель',         'panel_id',                False),
    ('Станд. нарезки', 'cutting_standard_code',   False),
    ('Напр. вырезки',  'cutting_direction',        False),
    ('Прим. маст.',    'workshop_notes',            False),
    ('Передать',       'further_movement_short',   False),
]

WORKSHOP_EMPTY_FIELDS = [
    ('Изготовил', ['ФИО', 'Дата']),
]

# Блок 3 — Испытания (всегда)
TESTING_FIELDS = [
    ('Срок испыт.',  'deadline',              False),
    ('Стандарт',     'standard_code',         False),
    ('Параметры',    'determined_parameters',  False),
    ('Условия',      'test_conditions',        True),
    ('Пробоподг.',   'preparation',            False),
    ('Примечания',   'notes',                  False),
    ('Отчётность',   'report_type',           False),
]

TESTING_EMPTY_FIELDS = [
    ('Кондиц.(ИО)', ['Дата']),
    ('Фото',        ['ДО №', 'ПОСЛЕ №']),
    ('Испытал',     ['ФИО', 'Дата']),
    ('Оборудование', None),
]


# ─────────────────────────────────────────────────────────────
# Значения полей
# ─────────────────────────────────────────────────────────────

def _get_sample_value(sample, field_code):
    """Получает отображаемое значение поля образца."""
    if field_code == 'cutting_standard_code':
        if sample.cutting_standard:
            return sample.cutting_standard.code
        std_codes = [s.code for s in sample.standards.all()]
        return ', '.join(std_codes) if std_codes else '—'
    elif field_code == 'standard_code':
        std_codes = [s.code for s in sample.standards.all()]
        return ', '.join(std_codes) if std_codes else '—'
    elif field_code == 'report_type':
        return sample.report_type_display if sample.report_type else '—'
    elif field_code == 'sample_count_display':
        return sample.sample_count_display
    elif field_code == 'uzk_required':
        return 'Да' if sample.uzk_required else 'Нет'
    elif field_code == 'further_movement':
        if not sample.further_movement:
            return '—'
        code = sample.further_movement.replace('TO_', '', 1)
        try:
            lab = Laboratory.objects.get(code=code)
            return lab.name
        except Laboratory.DoesNotExist:
            return sample.get_further_movement_display()
    elif field_code == 'further_movement_short':
        if not sample.further_movement:
            return '—'
        code = sample.further_movement.replace('TO_', '', 1)
        try:
            lab = Laboratory.objects.get(code=code)
            return lab.code_display
        except Laboratory.DoesNotExist:
            return code
    elif field_code == 'deadline':
        return sample.deadline.strftime('%d.%m.%Y') if sample.deadline else '—'
    elif field_code == 'manufacturing_deadline':
        return sample.manufacturing_deadline.strftime('%d.%m.%Y') if sample.manufacturing_deadline else '—'
    else:
        value = getattr(sample, field_code, None)
        return str(value) if value else '—'


# ─────────────────────────────────────────────────────────────
# Утилиты для текста
# ─────────────────────────────────────────────────────────────

def _wrap_text(c, text, font, font_size, max_width):
    """Разбивает текст на строки, помещающиеся в max_width."""
    if c.stringWidth(text, font, font_size) <= max_width:
        return [text]
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        test = (current_line + ' ' + word).strip()
        if c.stringWidth(test, font, font_size) <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            if c.stringWidth(word, font, font_size) > max_width:
                partial = ''
                for ch in word:
                    if c.stringWidth(partial + ch, font, font_size) > max_width:
                        if partial:
                            lines.append(partial)
                        partial = ch
                    else:
                        partial += ch
                current_line = partial
            else:
                current_line = word
    if current_line:
        lines.append(current_line)
    return lines if lines else [text]


def _calc_section_height(c, inner_w, sample, auto_fields, empty_fields):
    """Высота одного блока (auto + empty поля)."""
    total = 0
    for label_text, field_code, bold in auto_fields:
        label_w = c.stringWidth(label_text + ': ', 'DejaVuBold', FONT_SIZE_SMALL)
        font = 'DejaVuBold' if bold else 'DejaVu'
        max_val_w = inner_w - label_w - 1 * mm
        value = str(_get_sample_value(sample, field_code))
        lines = _wrap_text(c, value, font, FONT_SIZE_DATA, max_val_w)
        total += LINE_HEIGHT * len(lines)
    total += LINE_HEIGHT * len(empty_fields)
    return total


def _calc_label_height(c, w, sample):
    """Предрасчёт полной высоты этикетки."""
    inner_w = w - 2 * PADDING
    total = PADDING

    # Шифр (крупная строка)
    total += FONT_SIZE_CIPHER * 0.45 * mm + 1.5 * mm

    # Шапка
    total += _calc_section_height(c, inner_w, sample, HEADER_FIELDS, [])

    # Разделитель шапка → мастерская/испытания
    total += SEPARATOR_GAP

    # Мастерская (если есть и НЕ WORKSHOP как целевая лаба)
    # ⭐ v3.65.0: При WORKSHOP — данные наследуются из основного блока
    if sample.manufacturing and not (sample.laboratory and sample.laboratory.code == 'WORKSHOP'):
        total += _calc_section_height(c, inner_w, sample, WORKSHOP_FIELDS, WORKSHOP_EMPTY_FIELDS)
        # Разделитель мастерская → испытания
        total += SEPARATOR_GAP

    # Испытания
    total += _calc_section_height(c, inner_w, sample, TESTING_FIELDS, TESTING_EMPTY_FIELDS)

    total += PADDING
    return total


# ─────────────────────────────────────────────────────────────
# Отрисовка одной этикетки
# ─────────────────────────────────────────────────────────────

def _draw_label(c, x, y, w, h, sample):
    """Рисует одну этикетку с тремя визуальными блоками."""

    inner_x = x + PADDING
    inner_w = w - 2 * PADDING
    cur_y = y + h - PADDING

    # Рамка
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.rect(x, y, w, h)

    # ── Вспомогательные функции ──

    def draw_data_row(label, value, bold_value=False):
        nonlocal cur_y
        cur_y -= LINE_HEIGHT

        c.setFont('DejaVuBold', FONT_SIZE_SMALL)
        c.drawString(inner_x, cur_y, label + ':')

        label_w = c.stringWidth(label + ': ', 'DejaVuBold', FONT_SIZE_SMALL)
        font = 'DejaVuBold' if bold_value else 'DejaVu'
        c.setFont(font, FONT_SIZE_DATA)

        max_val_w = inner_w - label_w - 1 * mm
        lines = _wrap_text(c, str(value), font, FONT_SIZE_DATA, max_val_w)

        c.drawString(inner_x + label_w, cur_y, lines[0])
        for line in lines[1:]:
            cur_y -= LINE_HEIGHT
            c.setFont(font, FONT_SIZE_DATA)
            c.drawString(inner_x + label_w, cur_y, line)

    def draw_separator():
        nonlocal cur_y
        cur_y -= 0.8 * mm
        c.setLineWidth(0.2)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(inner_x, cur_y, inner_x + inner_w, cur_y)
        c.setStrokeColorRGB(0, 0, 0)
        cur_y -= 0.3 * mm

    def draw_empty_row(label, cells=None):
        nonlocal cur_y
        cur_y -= LINE_HEIGHT

        c.setFont('DejaVu', FONT_SIZE_SMALL)
        c.drawString(inner_x, cur_y, label + ':')

        if cells:
            label_w = c.stringWidth(label + ': ', 'DejaVu', FONT_SIZE_SMALL)
            remaining_w = inner_w - label_w
            cell_w = remaining_w / len(cells)
            for i, cell_label in enumerate(cells):
                cx = inner_x + label_w + i * cell_w
                c.setFont('DejaVu', FONT_SIZE_SMALL - 0.5)
                c.drawString(cx, cur_y, cell_label + ' ___')
        else:
            label_w = c.stringWidth(label + ': ', 'DejaVu', FONT_SIZE_SMALL)
            c.setLineWidth(0.2)
            c.line(inner_x + label_w, cur_y - 0.3 * mm,
                   inner_x + inner_w, cur_y - 0.3 * mm)

    def draw_section(auto_fields, empty_fields):
        for label, field_code, bold in auto_fields:
            value = _get_sample_value(sample, field_code)
            draw_data_row(label, value, bold_value=bold)
        for label, cells in empty_fields:
            draw_empty_row(label, cells)

    # ── Блок 1: Шапка ──

    # Шифр — крупно, без метки
    cipher = str(sample.cipher) if sample.cipher else str(sample.id)
    cur_y -= FONT_SIZE_CIPHER * 0.45 * mm + 1.5 * mm
    c.setFont('DejaVuBold', FONT_SIZE_CIPHER)
    c.drawString(inner_x, cur_y, cipher)

    # Общие поля шапки
    draw_section(HEADER_FIELDS, [])

    # ── Разделитель ──
    draw_separator()

    # ── Блок 2: Мастерская (если manufacturing и НЕ WORKSHOP как целевая лаба) ──
    # ⭐ v3.65.0: При WORKSHOP — данные наследуются из основного блока, не дублируются
    if sample.manufacturing and not (sample.laboratory and sample.laboratory.code == 'WORKSHOP'):
        draw_section(WORKSHOP_FIELDS, WORKSHOP_EMPTY_FIELDS)
        draw_separator()

    # ── Блок 3: Испытания ──
    draw_section(TESTING_FIELDS, TESTING_EMPTY_FIELDS)


# ─────────────────────────────────────────────────────────────
# Генерация PDF
# ─────────────────────────────────────────────────────────────

def _generate_labels_pdf(samples):
    """
    Генерирует PDF с этикетками. Возвращает bytes.
    Единый шаблон: блок мастерской включается только при manufacturing=True.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle('Этикетки образцов')

    label_list = list(samples)

    # Предрасчёт высоты каждой этикетки
    label_heights = [_calc_label_height(c, LABEL_W, s) for s in label_list]

    # Раскладка: 2 колонки, динамическая высота строк
    idx = 0
    cur_top = PAGE_H - MARGIN_Y
    first_on_page = True

    while idx < len(label_list):
        h_left = label_heights[idx]
        h_right = label_heights[idx + 1] if idx + 1 < len(label_list) else 0
        row_h = max(h_left, h_right) if h_right else h_left

        if cur_top - row_h < MARGIN_Y and not first_on_page:
            c.showPage()
            cur_top = PAGE_H - MARGIN_Y
            first_on_page = True

        # Левая этикетка
        lx = MARGIN_X
        ly = cur_top - h_left
        _draw_label(c, lx, ly, LABEL_W, h_left, label_list[idx])
        idx += 1

        # Правая этикетка (если есть)
        if idx < len(label_list) and h_right > 0:
            rx = MARGIN_X + LABEL_W + GAP_X
            ry = cur_top - h_right
            _draw_label(c, rx, ry, LABEL_W, h_right, label_list[idx])
            idx += 1

        cur_top -= row_h + GAP_Y
        first_on_page = False

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────

@login_required
def labels_page(request):
    """Страница генератора этикеток — выбор образцов и печать."""

    if not PermissionChecker.can_view(request.user, 'LABELS', 'access'):
        messages.error(request, 'У вас нет доступа к генератору этикеток')
        return redirect('workspace_home')

    laboratories = Laboratory.objects.filter(is_active=True, department_type='LAB').order_by('code')

    lab_filter = request.GET.get('lab', '')

    samples = Sample.objects.select_related(
        'laboratory', 'client', 'cutting_standard'
    ).prefetch_related('standards').exclude(
        status='CANCELLED'
    ).order_by('-sequence_number')

    if lab_filter:
        samples = samples.filter(laboratory__code=lab_filter)

    samples = samples[:200]

    preselected_ids = request.GET.getlist('ids')

    return render(request, 'core/labels_page.html', {
        'samples': samples,
        'laboratories': laboratories,
        'lab_filter': lab_filter,
        'preselected_ids': preselected_ids,
    })


@login_required
def labels_generate(request):
    """Генерирует PDF с этикетками для выбранных образцов."""

    if request.method != 'POST':
        return redirect('labels_page')

    if not PermissionChecker.can_view(request.user, 'LABELS', 'access'):
        messages.error(request, 'У вас нет доступа к генератору этикеток')
        return redirect('workspace_home')

    sample_ids = request.POST.getlist('sample_ids')

    if not sample_ids:
        messages.error(request, 'Не выбрано ни одного образца')
        return redirect('labels_page')

    samples = Sample.objects.select_related(
        'laboratory', 'client', 'cutting_standard'
    ).prefetch_related('standards').filter(
        id__in=sample_ids
    ).order_by('sequence_number')

    if not samples.exists():
        messages.error(request, 'Образцы не найдены')
        return redirect('labels_page')

    try:
        pdf_bytes = _generate_labels_pdf(samples)
    except Exception as e:
        logger.exception('Ошибка генерации этикеток')
        messages.error(request, f'Ошибка генерации PDF: {e}')
        return redirect('labels_page')
    Sample.objects.filter(id__in=sample_ids).update(label_printed=True)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="labels.pdf"'
    return response
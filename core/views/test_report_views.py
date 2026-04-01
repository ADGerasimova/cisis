"""
core/views/test_report_views.py

Views для отчётов об испытаниях:
1. Загрузка xlsx-шаблонов (админ)
2. Формирование отчёта / ввод данных (оператор)
3. API для расчётов и сохранения
"""

import json
import os
import tempfile
import math
import statistics as stats_module

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import connection

from core.models import (
    Sample, Standard, User,
    ReportTemplateSource, ReportTemplateIndex, TestReport,
)


# ═══════════════════════════════════════════════════════════════
# 1. ЗАГРУЗКА ШАБЛОНОВ (админ)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_upload_report_template(request):
    """
    POST /api/report-templates/upload/
    Загружает xlsx-файл, парсит и создаёт индекс шаблонов.

    Form data:
        file: xlsx-файл
        laboratory_id: ID лаборатории
        description: описание (опционально)
    """
    from core.services.template_parser import parse_template_file

    xlsx_file = request.FILES.get('file')
    if not xlsx_file:
        return JsonResponse({'success': False, 'error': 'Файл не выбран'}, status=400)

    if not xlsx_file.name.endswith(('.xlsx', '.xlsm')):
        return JsonResponse({'success': False, 'error': 'Поддерживаются только .xlsx файлы'}, status=400)

    laboratory_id = request.POST.get('laboratory_id')
    if not laboratory_id:
        return JsonResponse({'success': False, 'error': 'Не указана лаборатория'}, status=400)

    description = request.POST.get('description', '')

    # Сохраняем во временный файл для парсинга
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        for chunk in xlsx_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        # Сохраняем файл на постоянное хранение (S3 или локально)
        permanent_path = _save_template_file(xlsx_file, laboratory_id)

        result = parse_template_file(
            file_path=tmp_path,
            laboratory_id=int(laboratory_id),
            uploaded_by_id=request.user.id,
            description=description,
        )

        # Обновляем путь в source на постоянный
        if result['source_id']:
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE report_template_sources SET file_path = %s WHERE id = %s",
                    [permanent_path, result['source_id']]
                )

        return JsonResponse({
            'success': True,
            'source_id': result['source_id'],
            'templates_found': result['templates_found'],
            'templates_created': result['templates_created'],
            'templates_updated': result['templates_updated'],
            'errors': result['errors'],
            'details': result['details'],
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    finally:
        os.unlink(tmp_path)


def _save_template_file(uploaded_file, laboratory_id):
    """Сохраняет xlsx на диск или в S3. Возвращает путь."""
    from django.conf import settings

    # Директория для шаблонов
    template_dir = os.path.join(settings.MEDIA_ROOT, 'report_templates', str(laboratory_id))
    os.makedirs(template_dir, exist_ok=True)

    file_path = os.path.join(template_dir, uploaded_file.name)

    with open(file_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    return file_path


@login_required
@require_GET
def api_report_template_list(request):
    """
    GET /api/report-templates/
    Список загруженных источников шаблонов.
    """
    laboratory_id = request.GET.get('laboratory_id')

    with connection.cursor() as cur:
        sql = """
            SELECT rts.id, rts.file_name, rts.description,
                   rts.laboratory_id, l.display_name AS lab_name,
                   rts.is_active, rts.created_at,
                   u.last_name || ' ' || u.first_name AS uploaded_by,
                   COUNT(rti.id) AS template_count
            FROM report_template_sources rts
            LEFT JOIN laboratories l ON l.id = rts.laboratory_id
            LEFT JOIN users u ON u.id = rts.uploaded_by_id
            LEFT JOIN report_template_index rti ON rti.source_id = rts.id
        """
        params = []
        if laboratory_id:
            sql += " WHERE rts.laboratory_id = %s"
            params.append(int(laboratory_id))

        sql += " GROUP BY rts.id, l.display_name, u.last_name, u.first_name ORDER BY rts.created_at DESC"

        cur.execute(sql, params)
        columns = [col[0] for col in cur.description]
        sources = [dict(zip(columns, row)) for row in cur.fetchall()]

    return JsonResponse({'success': True, 'sources': sources})


@login_required
@require_GET
def api_report_template_detail(request, source_id):
    """
    GET /api/report-templates/<source_id>/
    Список шаблонов (стандартов) в источнике.
    """
    with connection.cursor() as cur:
        cur.execute("""
            SELECT rti.id, rti.standard_id, s.code AS standard_code, s.name AS standard_name,
                   rti.sheet_name, rti.start_row, rti.end_row,
                   rti.layout_type, rti.column_config, rti.is_active,
                   rti.version, rti.is_current, rti.changes_description
            FROM report_template_index rti
            JOIN standards s ON s.id = rti.standard_id
            WHERE rti.source_id = %s
            ORDER BY s.code, rti.version DESC
        """, [source_id])
        columns = [col[0] for col in cur.description]
        templates = [dict(zip(columns, row)) for row in cur.fetchall()]

    return JsonResponse({'success': True, 'templates': templates})


# ═══════════════════════════════════════════════════════════════
# 2. ФОРМИРОВАНИЕ ОТЧЁТА (оператор)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_get_report_form(request, sample_id):
    """
    GET /api/test-report/form/<sample_id>/
    Возвращает конфигурацию формы для ввода данных отчёта.

    Логика:
    1. Берём стандарт образца
    2. Находим шаблон (report_template_index)
    3. Возвращаем column_config + header_config + предзаполненные данные
    """
    sample = get_object_or_404(Sample, id=sample_id)

    # Получаем стандарт(ы) образца
    with connection.cursor() as cur:
        cur.execute("""
            SELECT s.id, s.code, s.name
            FROM sample_standards ss
            JOIN standards s ON s.id = ss.standard_id
            WHERE ss.sample_id = %s
        """, [sample_id])
        standards = [{'id': r[0], 'code': r[1], 'name': r[2]} for r in cur.fetchall()]

    if not standards:
        return JsonResponse({
            'success': False,
            'error': 'У образца не указаны стандарты испытания',
        }, status=400)

    # Для каждого стандарта ищем шаблон
    forms = []
    for std in standards:
        # Проверяем, есть ли уже отчёт
        existing_report = TestReport.objects.filter(
            sample_id=sample_id, standard_id=std['id']
        ).first()

        # Для существующего отчёта — берём его версию шаблона
        # Для нового — берём текущую (is_current=True)
        if existing_report and existing_report.template_id:
            template = ReportTemplateIndex.objects.filter(
                id=existing_report.template_id
            ).first()
        else:
            template = ReportTemplateIndex.objects.filter(
                standard_id=std['id'], is_current=True, is_active=True
            ).first()

        if not template:
            forms.append({
                'standard': std,
                'has_template': False,
                'message': f'Шаблон для {std["code"]} не загружен',
            })
            continue

        # Предзаполняем шапку из БД
        prefilled_header = _prefill_header(sample, template)

        forms.append({
            'standard': std,
            'has_template': True,
            'template_id': template.id,
            'template_version': template.version,
            'column_config': template.column_config,
            'header_config': template.header_config,
            'statistics_config': template.statistics_config,
            'sub_measurements_config': template.sub_measurements_config,
            'layout_type': template.layout_type,
            'prefilled_header': prefilled_header,
            'existing_report': _report_to_dict(existing_report) if existing_report else None,
        })

    return JsonResponse({'success': True, 'sample_id': sample_id, 'forms': forms})


def _prefill_header(sample, template):
    """Предзаполняет поля шапки из данных образца."""
    header = {}

    # ID номер (шифр образца)
    header['identification_number'] = getattr(sample, 'cipher', '') or ''

    # Условия испытаний
    header['conditions'] = getattr(sample, 'test_conditions', '') or ''

    # Оператор — текущий пользователь будет подставлен на фронте

    # Оборудование (СИ + ИО)
    with connection.cursor() as cur:
        # Средства измерений (СИ)
        cur.execute("""
            SELECT e.name, e.factory_number
            FROM sample_measuring_instruments smi
            JOIN equipment e ON e.id = smi.equipment_id
            WHERE smi.sample_id = %s
        """, [sample.id])
        si = [f'{r[0]} (зав.№ {r[1]})' if r[1] else r[0] for r in cur.fetchall()]
        header['measuring_instruments'] = '; '.join(si)

        # Испытательное оборудование (ИО)
        cur.execute("""
            SELECT e.name, e.factory_number
            FROM sample_testing_equipment ste
            JOIN equipment e ON e.id = ste.equipment_id
            WHERE ste.sample_id = %s
        """, [sample.id])
        io_list = [f'{r[0]} (зав.№ {r[1]})' if r[1] else r[0] for r in cur.fetchall()]
        header['test_equipment'] = '; '.join(io_list)

    return header


def _report_to_dict(report):
    """Преобразует TestReport в dict для JSON."""
    if not report:
        return None
    return {
        'id': report.id,
        'status': report.status,
        'header_data': report.header_data,
        'table_data': report.table_data,
        'statistics_data': report.statistics_data,
        'specimen_count': report.specimen_count,
        'created_at': report.created_at.isoformat() if report.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════
# 3. СОХРАНЕНИЕ ДАННЫХ ОТЧЁТА
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_save_test_report(request):
    """
    POST /api/test-report/save/
    Сохраняет данные отчёта (создаёт или обновляет).

    JSON body:
    {
        "sample_id": 123,
        "standard_id": 45,
        "template_id": 3,
        "header_data": {...},
        "table_data": {"specimens": [...]},
        "status": "DRAFT" | "COMPLETED"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    sample_id = data.get('sample_id')
    standard_id = data.get('standard_id')
    template_id = data.get('template_id')
    header_data = data.get('header_data', {})
    table_data = data.get('table_data', {'specimens': []})
    status = data.get('status', 'DRAFT')

    if not sample_id or not standard_id:
        return JsonResponse({'success': False, 'error': 'sample_id и standard_id обязательны'}, status=400)

    # Вычисляем статистику
    template = ReportTemplateIndex.objects.filter(id=template_id).first() if template_id else None
    statistics_data = _calculate_statistics(table_data, template)

    # Создаём или обновляем отчёт
    report, created = TestReport.objects.update_or_create(
        sample_id=sample_id,
        standard_id=standard_id,
        defaults={
            'template_id': template_id,
            'created_by_id': request.user.id,
            'status': status,
            'header_data': header_data,
            'table_data': table_data,
            'statistics_data': statistics_data,
        }
    )

    # Извлекаем ключевые метрики в отдельные поля
    report.extract_key_metrics()
    # Сохраняем метрики напрямую через SQL (managed=False)
    with connection.cursor() as cur:
        cur.execute("""
            UPDATE test_reports
            SET specimen_count = %s, mean_strength = %s, mean_modulus = %s,
                mean_elongation = %s, cv_strength = %s, updated_at = NOW()
            WHERE id = %s
        """, [
            report.specimen_count, report.mean_strength,
            report.mean_modulus, report.mean_elongation,
            report.cv_strength, report.id,
        ])

    return JsonResponse({
        'success': True,
        'report_id': report.id,
        'created': created,
        'statistics_data': statistics_data,
    })


def _calculate_statistics(table_data, template):
    """
    Вычисляет статистику (среднее, ст.откл, CV%, дов.интервал) по данным таблицы.
    """
    specimens = table_data.get('specimens', [])
    if len(specimens) < 2:
        return {}

    result = {}

    # Определяем числовые столбцы из шаблона
    if template and template.column_config:
        numeric_codes = [
            c['code'] for c in template.column_config
            if c['type'] in ('INPUT', 'CALCULATED', 'SUB_AVG')
            and c['code'] not in ('specimen_number', 'marking', 'failure_mode', 'br', 'notes', 'time', 'n_minutes')
        ]
    else:
        # Fallback — берём все числовые значения
        numeric_codes = set()
        for spec in specimens:
            for k, v in spec.get('values', {}).items():
                if isinstance(v, (int, float)):
                    numeric_codes.add(k)
        numeric_codes = list(numeric_codes)

    n = len(specimens)

    for code in numeric_codes:
        values = []
        for spec in specimens:
            v = spec.get('values', {}).get(code)
            if v is not None and isinstance(v, (int, float)):
                values.append(float(v))

        if len(values) < 2:
            continue

        mean = stats_module.mean(values)
        stdev = stats_module.stdev(values)
        cv = (stdev / mean * 100) if mean != 0 else 0

        stat_entry = {
            'mean': round(mean, 4),
            'stdev': round(stdev, 4),
            'cv': round(cv, 2),
        }

        # Доверительный интервал (t-распределение, α=0.05)
        try:
            from scipy import stats as scipy_stats
            t_val = scipy_stats.t.ppf(0.975, len(values) - 1)
            margin = t_val * stdev / math.sqrt(len(values))
            stat_entry['ci_lo'] = round(mean - margin, 4)
            stat_entry['ci_hi'] = round(mean + margin, 4)
        except ImportError:
            # Без scipy — используем приближённые значения t
            t_table = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571,
                       7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262, 15: 2.145, 20: 2.093}
            t_val = t_table.get(len(values), 2.0)
            margin = t_val * stdev / math.sqrt(len(values))
            stat_entry['ci_lo'] = round(mean - margin, 4)
            stat_entry['ci_hi'] = round(mean + margin, 4)

        result[code] = stat_entry

    return result


# ═══════════════════════════════════════════════════════════════
# 4. API ДЛЯ ВЫЧИСЛЕНИЙ НА ЛЕТУ (JS вызывает при вводе данных)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_calculate_report(request):
    """
    POST /api/test-report/calculate/
    Пересчитывает вычисляемые поля и статистику на лету.

    JSON body: { "table_data": {...}, "template_id": int }

    Возвращает обновлённый table_data + statistics_data.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    table_data = data.get('table_data', {'specimens': []})
    template_id = data.get('template_id')

    template = ReportTemplateIndex.objects.filter(id=template_id).first() if template_id else None

    # Пересчитываем вычисляемые столбцы
    if template:
        table_data = _recalculate_columns(table_data, template)

    # Пересчитываем статистику
    statistics_data = _calculate_statistics(table_data, template)

    return JsonResponse({
        'success': True,
        'table_data': table_data,
        'statistics_data': statistics_data,
    })


def _recalculate_columns(table_data, template):
    """Пересчитывает SUB_AVG и CALCULATED столбцы."""
    specimens = table_data.get('specimens', [])

    for spec in specimens:
        values = spec.get('values', {})
        sub = spec.get('sub_measurements', {})

        for col in template.column_config:
            code = col['code']

            if col['type'] == 'SUB_AVG' and sub:
                # Среднее из промежуточных замеров
                # Определяем код замера по имени столбца (h_avg → h, b_avg → b)
                sub_code = code.replace('_avg', '')
                measurements = sub.get(sub_code, [])
                if measurements:
                    values[code] = round(
                        sum(m for m in measurements if m is not None) / len([m for m in measurements if m is not None]),
                        col.get('decimal_places', 2)
                    )

            elif col['type'] == 'CALCULATED' and col.get('formula'):
                # Подставляем значения в формулу
                try:
                    result = _eval_formula(col['formula'], values, spec)
                    if result is not None:
                        values[code] = round(result, col.get('decimal_places', 2))
                except Exception:
                    pass  # Если формула не вычисляется — пропускаем

        spec['values'] = values

    table_data['specimens'] = specimens
    return table_data


def _eval_formula(formula_template, values, specimen):
    """
    Вычисляет формулу, подставляя значения.
    Пример: '=E{row}/D{row}/C{row}*1000'
    Используем маппинг col_letter → code → value.
    """
    # Простые формулы вида: value1 / value2 / value3 * 1000
    # Пока поддерживаем базовую арифметику
    formula = formula_template.replace('{row}', '')

    # Убираем "=" в начале
    if formula.startswith('='):
        formula = formula[1:]

    # Заменяем ссылки на ячейки (A, B, C...) на значения
    # Это упрощённый подход — для продакшна может потребоваться доработка
    for code, val in values.items():
        if val is not None and isinstance(val, (int, float)):
            formula = formula.replace(code, str(val))

    try:
        result = eval(formula)  # noqa: S307
        if isinstance(result, (int, float)) and not math.isnan(result) and not math.isinf(result):
            return result
    except Exception:
        pass

    return None


# ═══════════════════════════════════════════════════════════════
# 5. EXCEL-ЭКСПОРТ
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_export_test_report_xlsx(request, report_id):
    """
    GET /api/test-report/<report_id>/export-xlsx/
    Скачивает заполненный xlsx-файл отчёта.
    """
    import os as _os
    from django.http import FileResponse

    report = get_object_or_404(TestReport, id=report_id)

    if not report.template_id:
        return JsonResponse({'success': False, 'error': 'Нет привязанного шаблона'}, status=400)

    template = get_object_or_404(ReportTemplateIndex, id=report.template_id)
    report.template = template

    try:
        from core.services.report_exporter import export_test_report_xlsx
        tmp_path = export_test_report_xlsx(report)
    except FileNotFoundError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Имя файла
    sample = report.sample
    standard_code = report.standard.code if report.standard else 'report'
    safe_code = standard_code.replace(' ', '_').replace('/', '-')
    cipher = getattr(sample, 'cipher', '') or f'sample_{sample.id}'
    safe_cipher = cipher.replace(' ', '_').replace('/', '-')
    filename = f'Report_{safe_cipher}_{safe_code}.xlsx'

    response = FileResponse(
        open(tmp_path, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        filename=filename,
    )

    import atexit
    atexit.register(lambda: _os.unlink(tmp_path) if _os.path.exists(tmp_path) else None)

    return response


@login_required
@require_GET
def api_export_test_report_xlsx_by_sample(request, sample_id, standard_id):
    """
    GET /api/test-report/export-xlsx/<sample_id>/<standard_id>/
    Скачивает xlsx — ищет отчёт по sample + standard.
    Если отчёта нет — генерирует пустой шаблон с предзаполненной шапкой.
    """
    import os as _os
    from django.http import FileResponse

    report = TestReport.objects.filter(
        sample_id=sample_id, standard_id=standard_id
    ).first()

    if report and report.template_id:
        template = get_object_or_404(ReportTemplateIndex, id=report.template_id)
        report.template = template
    else:
        template = ReportTemplateIndex.objects.filter(
            standard_id=standard_id, is_current=True, is_active=True
        ).first()

        if not template:
            return JsonResponse({'success': False, 'error': 'Шаблон не найден'}, status=404)

        sample = get_object_or_404(Sample, id=sample_id)
        report = TestReport(
            sample=sample,
            standard_id=standard_id,
            template=template,
            header_data=_prefill_header(sample, template),
            table_data={'specimens': []},
        )

    try:
        from core.services.report_exporter import export_test_report_xlsx
        tmp_path = export_test_report_xlsx(report)
    except FileNotFoundError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    sample = report.sample
    std = Standard.objects.filter(id=standard_id).first()
    safe_code = (std.code if std else 'report').replace(' ', '_').replace('/', '-')
    cipher = getattr(sample, 'cipher', '') or f'sample_{sample.id}'
    safe_cipher = cipher.replace(' ', '_').replace('/', '-')
    filename = f'Report_{safe_cipher}_{safe_code}.xlsx'

    response = FileResponse(
        open(tmp_path, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        filename=filename,
    )

    import atexit
    atexit.register(lambda: _os.unlink(tmp_path) if _os.path.exists(tmp_path) else None)

    return response
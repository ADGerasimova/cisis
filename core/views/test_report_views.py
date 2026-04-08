"""
core/views/test_report_views.py

Views для отчётов об испытаниях:
1. Конструктор шаблонов (CRUD для report_template_index)
2. Загрузка xlsx-шаблонов (legacy, оставлен для совместимости)
3. Формирование отчёта / ввод данных (оператор)
4. API для расчётов и сохранения
5. Excel-экспорт

v4.0.0: переход на statistics[], унификация additional_tables
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
# HELPER: извлечение SUB_MEASUREMENTS из additional_tables
# ═══════════════════════════════════════════════════════════════

def _get_sub_measurements_config(template):
    """
    Возвращает конфиг промежуточных замеров.
    Приоритет:
    1. additional_tables с table_type="SUB_MEASUREMENTS"
    2. Устаревший sub_measurements_config (для совместимости)
    """
    # 1) Пробуем из additional_tables
    additional_tables = _get_additional_tables(template.id)
    if additional_tables:
        for table in additional_tables:
            if table.get('table_type') == 'SUB_MEASUREMENTS':
                return table
    
    # 2) Fallback: устаревший sub_measurements_config
    if template.sub_measurements_config:
        return template.sub_measurements_config
    
    return None


# ═══════════════════════════════════════════════════════════════
# 1. КОНСТРУКТОР ШАБЛОНОВ
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_get_template_config(request, standard_id):
    """
    GET /api/report-templates/config/<standard_id>/

    Возвращает текущий шаблон для стандарта (is_current=True).
    """
    standard = get_object_or_404(Standard, id=standard_id)

    template = ReportTemplateIndex.objects.filter(
        standard_id=standard_id,
        is_current=True,
        is_active=True,
    ).first()

    if not template:
        return JsonResponse({
            'success': True,
            'has_template': False,
            'standard': {'id': standard.id, 'code': standard.code},
            'template': None,
        })

    return JsonResponse({
        'success': True,
        'has_template': True,
        'standard': {'id': standard.id, 'code': standard.code},
        'template': _template_to_dict(template),
    })


@login_required
@require_GET
def api_get_template_versions(request, standard_id):
    """GET /api/report-templates/config/<standard_id>/versions/"""
    get_object_or_404(Standard, id=standard_id)

    with connection.cursor() as cur:
        cur.execute("""
            SELECT rti.id, rti.version, rti.is_current,
                   rti.changes_description, rti.created_at,
                   u.last_name || ' ' || u.first_name AS created_by
            FROM report_template_index rti
            LEFT JOIN report_template_sources rts ON rts.id = rti.source_id
            LEFT JOIN users u ON u.id = rts.uploaded_by_id
            WHERE rti.standard_id = %s AND rti.is_active = true
            ORDER BY rti.version DESC
        """, [standard_id])
        cols = [c[0] for c in cur.description]
        versions = [dict(zip(cols, row)) for row in cur.fetchall()]

    for v in versions:
        if v.get('created_at'):
            v['created_at'] = v['created_at'].isoformat()

    return JsonResponse({'success': True, 'versions': versions})


@login_required
@require_POST
def api_save_template_config(request):
    """POST /api/report-templates/config/save/"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    standard_id = data.get('standard_id')
    if not standard_id:
        return JsonResponse({'success': False, 'error': 'standard_id обязателен'}, status=400)

    standard = get_object_or_404(Standard, id=standard_id)

    column_config = data.get('column_config')
    if not column_config or not isinstance(column_config, list):
        return JsonResponse({'success': False, 'error': 'column_config обязателен'}, status=400)

    errors = _validate_column_config(column_config)
    if errors:
        return JsonResponse({'success': False, 'error': '; '.join(errors)}, status=400)

    header_config = data.get('header_config', {})
    additional_tables = data.get('additional_tables')  # новое
    layout_type = data.get('layout_type', 'A')
    changes_description = data.get('changes_description', '').strip()

    if layout_type not in ('A', 'B', 'C'):
        return JsonResponse({'success': False, 'error': 'layout_type должен быть A, B или C'}, status=400)

    # Проверка: если layout_type=B, должна быть таблица SUB_MEASUREMENTS
    if layout_type == 'B':
        has_sub = False
        if additional_tables:
            for table in additional_tables:
                if table.get('table_type') == 'SUB_MEASUREMENTS':
                    has_sub = True
                    break
        if not has_sub:
            return JsonResponse({
                'success': False,
                'error': 'layout_type=B требует таблицу с table_type=SUB_MEASUREMENTS в additional_tables',
            }, status=400)

    # Версионирование
    current = ReportTemplateIndex.objects.filter(
        standard_id=standard_id,
        is_current=True,
        is_active=True,
    ).first()

    if current:
        new_version = current.version + 1
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE report_template_index SET is_current = false WHERE id = %s",
                [current.id]
            )
    else:
        new_version = 1

    # Создаём новый шаблон
    with connection.cursor() as cur:
        cur.execute("""
            INSERT INTO report_template_index (
                standard_id, source_id,
                sheet_name, start_row, end_row, header_row, data_start_row,
                column_config, header_config, sub_measurements_config,
                statistics_config, additional_tables,
                layout_type, version, is_current, changes_description,
                is_active, created_at, updated_at
            ) VALUES (
                %s, NULL,
                '', 0, 0, 0, 0,
                %s, %s, NULL,
                '[]', %s,
                %s, %s, true, %s,
                true, NOW(), NOW()
            )
            RETURNING id
        """, [
            standard_id,
            json.dumps(column_config, ensure_ascii=False),
            json.dumps(header_config, ensure_ascii=False),
            json.dumps(additional_tables, ensure_ascii=False) if additional_tables else None,
            layout_type,
            new_version,
            changes_description,
        ])
        new_id = cur.fetchone()[0]
    
    new_template = ReportTemplateIndex.objects.get(id=new_id)

    return JsonResponse({
        'success': True,
        'template_id': new_id,
        'version': new_version,
        'created': True,
        'template': _template_to_dict(new_template), 
    })


@login_required
@require_POST
def api_delete_template_config(request):
    """POST /api/report-templates/config/delete/"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    template_id = data.get('template_id')
    if not template_id:
        return JsonResponse({'success': False, 'error': 'template_id обязателен'}, status=400)

    template = get_object_or_404(ReportTemplateIndex, id=template_id)

    with connection.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM test_reports WHERE template_id = %s",
            [template_id]
        )
        count = cur.fetchone()[0]

    if count > 0:
        return JsonResponse({
            'success': False,
            'error': f'Нельзя удалить — {count} отчёт(ов) ссылается на этот шаблон',
        }, status=400)

    with connection.cursor() as cur:
        cur.execute(
            "UPDATE report_template_index SET is_active = false, updated_at = NOW() WHERE id = %s",
            [template_id]
        )

        if template.is_current:
            cur.execute("""
                UPDATE report_template_index
                SET is_current = true, updated_at = NOW()
                WHERE standard_id = %s AND is_active = true
                  AND version = (
                      SELECT MAX(version) FROM report_template_index
                      WHERE standard_id = %s AND is_active = true AND id != %s
                  )
            """, [template.standard_id, template.standard_id, template_id])

    return JsonResponse({'success': True})


@login_required
@require_POST
def api_restore_template_version(request, standard_id):
    """POST /api/report-templates/config/<standard_id>/restore/"""
    get_object_or_404(Standard, id=standard_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    template_id = data.get('template_id')
    if not template_id:
        return JsonResponse({'success': False, 'error': 'template_id обязателен'}, status=400)

    target = get_object_or_404(
        ReportTemplateIndex, id=template_id, standard_id=standard_id, is_active=True
    )

    if target.is_current:
        return JsonResponse({'success': False, 'error': 'Версия уже является текущей'}, status=400)

    with connection.cursor() as cur:
        cur.execute(
            "UPDATE report_template_index SET is_current = false WHERE standard_id = %s AND is_current = true",
            [standard_id]
        )
        cur.execute(
            "UPDATE report_template_index SET is_current = true, updated_at = NOW() WHERE id = %s",
            [template_id]
        )

    return JsonResponse({'success': True, 'version': target.version})


@login_required
@require_GET
def api_preview_template_config(request, template_id):
    """GET /api/report-templates/config/preview/<template_id>/"""
    template = get_object_or_404(ReportTemplateIndex, id=template_id)
    preview_row = _generate_preview_row(template)
    return JsonResponse({
        'success': True,
        'template': _template_to_dict(template),
        'preview_row': preview_row,
    })


def _generate_preview_row(template):
    """Генерирует тестовую строку для предпросмотра."""
    import random

    sub_measurements = {}
    sub_cfg = _get_sub_measurements_config(template)
    
    if sub_cfg:
        cols = sub_cfg.get('columns', [])
        n = sub_cfg.get('measurements_per_specimen', 3)
        for c in cols:
            sub_measurements[c['code']] = [round(random.uniform(0.9, 1.1) * 10, 2) for _ in range(n)]

    header_example = {}
    for key, cfg in (template.header_config or {}).items():
        if isinstance(cfg, dict) and cfg.get('type') == 'NUMERIC':
            header_example[key] = round(random.uniform(0.5, 5.0), 3)

    values = {}
    for col in template.column_config:
        code = col['code']
        col_type = col.get('type')
        decimals = col.get('decimal_places', 2)

        if col_type == 'INPUT':
            values[code] = round(random.uniform(300, 500), 1)
        elif col_type == 'TEXT':
            values[code] = 'LGM'
        elif col_type == 'SUB_AVG':
            sub_code = code.replace('_avg', '')
            measurements = sub_measurements.get(sub_code, [])
            if measurements:
                values[code] = round(sum(measurements) / len(measurements), decimals)
        elif col_type in ('CALC', 'NORM'):
            ctx = {k: v for k, v in values.items() if isinstance(v, (int, float))}
            if col_type == 'NORM':
                ctx.update(header_example)
            result = _eval_formula_safe(col.get('formula', ''), ctx)
            if result is not None:
                values[code] = round(result, decimals)

    values['specimen_number'] = 1
    values['marking'] = 'Образец-001'
    return values


# ─── Вспомогательные функции конструктора ────────────────────

def _template_to_dict(template):
    """Сериализует ReportTemplateIndex в dict."""
    additional_tables = _get_additional_tables(template.id)
    return {
        'id': template.id,
        'version': template.version,
        'is_current': template.is_current,
        'layout_type': template.layout_type,
        'column_config': template.column_config,
        'header_config': template.header_config,
        'sub_measurements_config': template.sub_measurements_config,  # deprecated, но оставляем для совместимости
        'additional_tables': additional_tables,
        'changes_description': template.changes_description,
        'created_at': template.created_at.isoformat() if template.created_at else None,
    }


def _get_additional_tables(template_id):
    """Загружает additional_tables из БД."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT additional_tables FROM report_template_index WHERE id = %s",
                [template_id]
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0] if isinstance(row[0], list) else json.loads(row[0])
    except Exception:
        pass
    return None


def _get_additional_tables_data(report_id):
    """Загружает additional_tables_data из отчёта."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT additional_tables_data FROM test_reports WHERE id = %s",
                [report_id]
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except Exception:
        pass
    return None
def _get_export_settings(report_id):
    """Загружает export_settings из отчёта."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT export_settings FROM test_reports WHERE id = %s",
                [report_id]
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except Exception:
        pass
    return {}

def _validate_column_config(column_config):
    """Валидирует column_config."""
    errors = []
    valid_types = ('INPUT', 'TEXT', 'SUB_AVG', 'VLOOKUP', 'CALC', 'NORM')
    codes_seen = set()

    for i, col in enumerate(column_config):
        prefix = f'Столбец {i+1} ({col.get("code", "?")})'

        if not col.get('code'):
            errors.append(f'{prefix}: поле "code" обязательно')
            continue

        code = col['code']
        if code in codes_seen:
            errors.append(f'Дублирующийся код столбца: "{code}"')
        codes_seen.add(code)

        if not col.get('name'):
            errors.append(f'{prefix}: поле "name" обязательно')

        col_type = col.get('type')
        if col_type not in valid_types:
            errors.append(f'{prefix}: неизвестный тип "{col_type}"')

        if col_type in ('CALC', 'NORM', 'VLOOKUP') and not col.get('formula'):
            errors.append(f'{prefix}: тип {col_type} требует поле "formula"')

        if col_type == 'NORM' and not col.get('params'):
            errors.append(f'{prefix}: тип NORM требует поле "params"')

        if col_type == 'SUB_AVG' and col.get('formula'):
            errors.append(f'{prefix}: тип SUB_AVG не требует formula')

        # Валидация statistics
        stats = col.get('statistics')
        if stats is not None:
            if not isinstance(stats, list):
                errors.append(f'{prefix}: "statistics" должен быть массивом')
            else:
                valid_stats = {'MEAN', 'STDEV', 'CV', 'CONFIDENCE'}
                for st in stats:
                    if st not in valid_stats:
                        errors.append(f'{prefix}: неизвестная метрика "{st}" в statistics')

    return errors


# ═══════════════════════════════════════════════════════════════
# 2. ЗАГРУЗКА XLSX-ШАБЛОНОВ (legacy)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_upload_report_template(request):
    """POST /api/report-templates/upload/"""
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

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        for chunk in xlsx_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        result = parse_template_file(
            file_path=tmp_path,
            laboratory_id=int(laboratory_id),
            uploaded_by_id=request.user.id,
            description=description,
        )

        if result['source_id']:
            permanent_path = _save_template_file(xlsx_file, laboratory_id)
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE report_template_sources SET file_path = %s WHERE id = %s",
                    [permanent_path, result['source_id']]
                )

        return JsonResponse({
            'success': True,
            'source_id': result['source_id'],
            'templates_created': result.get('templates_created', 0),
            'templates_updated': result.get('templates_updated', 0),
            'templates_skipped': result.get('templates_skipped', 0),
            'details': result.get('details', []),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _save_template_file(uploaded_file, laboratory_id):
    """Сохраняет xlsx на постоянное место."""
    from django.conf import settings
    from datetime import datetime

    template_dir = os.path.join(settings.MEDIA_ROOT, 'report_templates', str(laboratory_id))
    os.makedirs(template_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(uploaded_file.name)
    safe_name = f"{timestamp}_{name}{ext}"
    file_path = os.path.join(template_dir, safe_name)

    with open(file_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    return file_path


@login_required
@require_GET
def api_report_template_list(request):
    """GET /api/report-templates/"""
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
    """GET /api/report-templates/<source_id>/"""
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
# 3. ФОРМИРОВАНИЕ ОТЧЁТА (оператор)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_get_report_form(request, sample_id):
    """GET /api/test-report/form/<sample_id>/"""
    sample = get_object_or_404(Sample, id=sample_id)

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

    forms = []
    for std in standards:
        existing_report = TestReport.objects.filter(
            sample_id=sample_id, standard_id=std['id']
        ).first()

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
                'message': f'Шаблон для {std["code"]} не настроен',
            })
            continue

        prefilled_header = _prefill_header(sample, template)
        
        # Получаем sub_measurements_config из additional_tables
        sub_cfg = _get_sub_measurements_config(template)

        forms.append({
            'standard': std,
            'has_template': True,
            'template_id': template.id,
            'template_version': template.version,
            'column_config': template.column_config,
            'header_config': template.header_config,
            'sub_measurements_config': sub_cfg,  # для совместимости с фронтендом
            'statistics_config': template.statistics_config,
            'additional_tables': _get_additional_tables(template.id),
            'layout_type': template.layout_type,
            'prefilled_header': prefilled_header,
            'existing_report': _report_to_dict(existing_report) if existing_report else None,
        })

    return JsonResponse({'success': True, 'sample_id': sample_id, 'forms': forms})


def _prefill_header(sample, template):
    """Предзаполняет поля шапки из данных образца."""
    header = {}

    header['identification_number'] = getattr(sample, 'cipher', '') or ''
    header['conditions'] = getattr(sample, 'test_conditions', '') or ''

    with connection.cursor() as cur:
        cur.execute("""
            SELECT e.name, e.factory_number
            FROM sample_measuring_instruments smi
            JOIN equipment e ON e.id = smi.equipment_id
            WHERE smi.sample_id = %s
        """, [sample.id])
        si = [f'{r[0]} (зав.№ {r[1]})' if r[1] else r[0] for r in cur.fetchall()]
        header['measuring_instruments'] = '; '.join(si)

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
    """Преобразует TestReport в dict."""
    if not report:
        return None
    return {
        'id': report.id,
        'status': report.status,
        'header_data': report.header_data,
        'table_data': report.table_data,
        'statistics_data': report.statistics_data,
        'additional_tables_data': _get_additional_tables_data(report.id),
        'export_settings': _get_export_settings(report.id),  
        'specimen_count': report.specimen_count,
        'created_at': report.created_at.isoformat() if report.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════
# 4. СОХРАНЕНИЕ ДАННЫХ ОТЧЁТА
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_save_test_report(request):
    """POST /api/test-report/save/"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    sample_id = data.get('sample_id')
    standard_id = data.get('standard_id')
    template_id = data.get('template_id')
    header_data = data.get('header_data', {})
    table_data = data.get('table_data', {'specimens': []})
    additional_tables_data = data.get('additional_tables_data')
    export_settings = data.get('export_settings', {})
    status = data.get('status', 'DRAFT')

    if not sample_id or not standard_id:
        return JsonResponse({'success': False, 'error': 'sample_id и standard_id обязательны'}, status=400)

    template = ReportTemplateIndex.objects.filter(id=template_id).first() if template_id else None
    statistics_data = _calculate_statistics(table_data, template, header_data)

    # ═══ ИСПРАВЛЕНИЕ: Используем RAW SQL для полного контроля ═══
    with connection.cursor() as cur:
        # Проверяем, существует ли отчёт
        cur.execute("""
            SELECT id FROM test_reports 
            WHERE sample_id = %s AND standard_id = %s
        """, [sample_id, standard_id])
        
        existing = cur.fetchone()
        
        if existing:
            # UPDATE существующего отчёта
            report_id = existing[0]
            cur.execute("""
                UPDATE test_reports
                SET template_id = %s,
                    created_by_id = %s,
                    status = %s,
                    header_data = %s,
                    table_data = %s,
                    statistics_data = %s,
                    additional_tables_data = %s,
                    export_settings = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, [
                template_id,
                request.user.id,
                status,
                json.dumps(header_data, ensure_ascii=False),
                json.dumps(table_data, ensure_ascii=False),
                json.dumps(statistics_data, ensure_ascii=False),
                json.dumps(additional_tables_data, ensure_ascii=False) if additional_tables_data else None,
                json.dumps(export_settings, ensure_ascii=False),
                report_id,
            ])
            created = False
        else:
            # INSERT нового отчёта
            cur.execute("""
                INSERT INTO test_reports (
                    sample_id, standard_id, template_id, created_by_id,
                    status, header_data, table_data, statistics_data,
                    additional_tables_data, export_settings,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    NOW(), NOW()
                )
                RETURNING id
            """, [
                sample_id, standard_id, template_id, request.user.id,
                status,
                json.dumps(header_data, ensure_ascii=False),
                json.dumps(table_data, ensure_ascii=False),
                json.dumps(statistics_data, ensure_ascii=False),
                json.dumps(additional_tables_data, ensure_ascii=False) if additional_tables_data else None,
                json.dumps(export_settings, ensure_ascii=False),
            ])
            report_id = cur.fetchone()[0]
            created = True

    # Получаем объект для extract_key_metrics
    report = TestReport.objects.get(id=report_id)
    report.extract_key_metrics()
    
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

# ═══════════════════════════════════════════════════════════════
# 5. API ДЛЯ ВЫЧИСЛЕНИЙ НА ЛЕТУ
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_calculate_report(request):
    """POST /api/test-report/calculate/"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    table_data = data.get('table_data', {'specimens': []})
    header_data = data.get('header_data', {})
    template_id = data.get('template_id')

    template = ReportTemplateIndex.objects.filter(id=template_id).first() if template_id else None

    if template:
        table_data = _recalculate_columns(table_data, template, header_data)

    statistics_data = _calculate_statistics(table_data, template, header_data)

    return JsonResponse({
        'success': True,
        'table_data': table_data,
        'statistics_data': statistics_data,
    })


# ─── Логика вычислений ────────────────────────────────────────

def _recalculate_columns(table_data, template, header_data=None):
    """Пересчитывает SUB_AVG, VLOOKUP, CALC и NORM столбцы."""
    if header_data is None:
        header_data = {}

    specimens = table_data.get('specimens', [])
    sub_cfg = _get_sub_measurements_config(template)

    for spec in specimens:
        values = spec.get('values', {})
        sub = spec.get('sub_measurements', {})

        if sub and sub_cfg and sub_cfg.get('derived'):
            _recalculate_sub_derived(sub, sub_cfg['derived'], header_data)
            spec['sub_measurements'] = sub

        for col in template.column_config:
            code = col['code']
            col_type = col.get('type')
            decimal_places = col.get('decimal_places', 2)

            if col_type == 'SUB_AVG' and sub:
                sub_code = col.get('sub_code') or code.replace('_avg', '')
                measurements = sub.get(sub_code, [])
                valid = [m for m in measurements if m is not None and isinstance(m, (int, float))]
                if valid:
                    values[code] = round(sum(valid) / len(valid), decimal_places)

            elif col_type == 'VLOOKUP' and col.get('formula') and sub:
                result = _compute_vlookup_backend(col['formula'], sub, sub_cfg)
                if result is not None:
                    values[code] = round(result, decimal_places)

            elif col_type == 'CALC' and col.get('formula'):
                result = _eval_formula(col['formula'], values)
                if result is not None:
                    values[code] = round(result, decimal_places)

            elif col_type == 'NORM' and col.get('formula'):
                merged = {**values}
                for param in col.get('params', []):
                    if param in header_data:
                        try:
                            merged[param] = float(header_data[param])
                        except (ValueError, TypeError):
                            pass
                result = _eval_formula(col['formula'], merged)
                if result is not None:
                    values[code] = round(result, decimal_places)

        spec['values'] = values

    table_data['specimens'] = specimens
    return table_data


def _compute_vlookup_backend(formula, sub, sub_cfg):
    """Вычисляет VLOOKUP на бэкенде."""
    import re

    match = re.match(
        r'VLOOKUP\s*\(\s*([A-Z]+)\d+\s*,\s*([A-Z]+)\d+:([A-Z]+)\d+\s*,\s*(\d+)\s*,\s*\d+\s*\)',
        formula, re.IGNORECASE,
    )
    if not match:
        return None

    lookup_letter = match.group(1).upper()
    range_start = match.group(2).upper()
    range_end = match.group(3).upper()
    col_index = int(match.group(4))

    all_cols = list(sub_cfg.get('columns', []))
    for d in sub_cfg.get('derived', []):
        if d.get('code') not in {c['code'] for c in all_cols}:
            all_cols.append(d)

    letter_to_code = {c.get('col_letter', '').upper(): c['code'] for c in all_cols if c.get('col_letter')}

    lookup_code = letter_to_code.get(lookup_letter)
    if not lookup_code:
        return None

    lookup_val = sub.get(lookup_code)
    if lookup_val is None:
        return None
    if isinstance(lookup_val, list):
        lookup_val = lookup_val[0] if lookup_val else None
    if lookup_val is None:
        return None

    start_idx = ord(range_start) - 65
    end_idx = ord(range_end) - 65
    range_letters = [chr(65 + i) for i in range(start_idx, end_idx + 1)]

    first_letter = range_letters[0]
    first_code = letter_to_code.get(first_letter)
    if not first_code:
        return None

    first_measurements = sub.get(first_code, [])
    if not isinstance(first_measurements, list):
        return None

    found_idx = -1
    for i, v in enumerate(first_measurements):
        if v is not None and abs(v - lookup_val) < 0.0001:
            found_idx = i
            break

    if found_idx == -1:
        return None

    if col_index < 1 or col_index > len(range_letters):
        return None

    target_letter = range_letters[col_index - 1]
    target_code = letter_to_code.get(target_letter)
    if not target_code:
        return None

    target_measurements = sub.get(target_code, [])
    if isinstance(target_measurements, list) and found_idx < len(target_measurements):
        val = target_measurements[found_idx]
        if val is not None and isinstance(val, (int, float)):
            return float(val)

    return None


def _eval_formula_safe(formula, ctx):
    """Обёртка _eval_formula для preview."""
    try:
        return _eval_formula(formula, ctx)
    except Exception:
        return None


def _recalculate_sub_derived(sub, derived_config, header_data):
    """Пересчитывает derived-поля внутри sub_measurements."""
    import re
    import statistics as _stats

    for derived in derived_config:
        code = derived['code']
        formula = derived.get('formula', '')
        if not formula:
            continue

        pure_agg = re.match(r'^(MIN|MAX|AVERAGE|SUM)\s*\(\s*\{(\w+)\}\s*\)$', formula, re.IGNORECASE)
        if pure_agg:
            func = pure_agg.group(1).upper()
            src_code = pure_agg.group(2)
            src_values = sub.get(src_code, [])
            valid = [v for v in (src_values if isinstance(src_values, list) else [src_values])
                     if v is not None and isinstance(v, (int, float))]
            if not valid:
                sub[code] = None
                continue
            if func == 'MIN':
                sub[code] = min(valid)
            elif func == 'MAX':
                sub[code] = max(valid)
            elif func == 'AVERAGE':
                sub[code] = sum(valid) / len(valid)
            elif func == 'SUM':
                sub[code] = sum(valid)
            continue

        def _resolve_inline_agg(m):
            func = m.group(1).upper()
            src_code = m.group(2)
            src_values = sub.get(src_code, [])
            valid = [v for v in (src_values if isinstance(src_values, list) else [])
                     if v is not None and isinstance(v, (int, float))]
            if not valid:
                return 'None'
            if func == 'MIN':
                return str(min(valid))
            elif func == 'MAX':
                return str(max(valid))
            elif func == 'AVERAGE':
                return str(sum(valid) / len(valid))
            elif func == 'SUM':
                return str(sum(valid))
            return 'None'

        resolved_formula = re.sub(
            r'\b(MIN|MAX|AVERAGE|SUM)\s*\(\s*\{(\w+)\}\s*\)',
            _resolve_inline_agg, formula, flags=re.IGNORECASE
        )

        n = max((len(v) for v in sub.values() if isinstance(v, list)), default=0)
        results = []
        for i in range(n):
            row_vals = {}
            for k, vals in sub.items():
                if isinstance(vals, list) and i < len(vals):
                    row_vals[k] = vals[i]
            for param, val in header_data.items():
                try:
                    row_vals[param] = float(val)
                except (ValueError, TypeError):
                    pass
            result = _eval_formula(resolved_formula, row_vals)
            results.append(result)
        sub[code] = results


def _eval_formula(formula, values):
    """Вычисляет формулу."""
    import re

    expr = formula.strip()

    def replace_var(match):
        code = match.group(1)
        val = values.get(code)
        if val is None or not isinstance(val, (int, float)):
            return 'None'
        return str(float(val))

    expr = re.sub(r'\{(\w+)\}', replace_var, expr)

    if 'None' in expr:
        return None

    def _resolve_excel(e):
        e = re.sub(
            r'ROUND\s*\(([^,]+),\s*(\d+)\)',
            lambda m: f'round({m.group(1)},{m.group(2)})',
            e, flags=re.IGNORECASE,
        )
        while re.search(r'IF\s*\(', e, re.IGNORECASE):
            e = re.sub(
                r'IF\s*\(([^,]+),([^,]+),([^)]+)\)',
                lambda m: f'(({m.group(2)}) if ({m.group(1)}) else ({m.group(3)}))',
                e, count=1, flags=re.IGNORECASE,
            )
        iferror_match = re.search(r'IFERROR\s*\((.+),([^)]+)\)', e, re.IGNORECASE)
        if iferror_match:
            try:
                result = _safe_eval(iferror_match.group(1))
                if result is not None:
                    return str(result)
                return iferror_match.group(2).strip().strip('"')
            except Exception:
                return iferror_match.group(2).strip().strip('"')
        return e

    expr = _resolve_excel(expr)

    return _safe_eval(expr)


def _safe_eval(expr):
    try:
        result = eval(expr, {"__builtins__": {}, "round": round})  # noqa: S307
        if isinstance(result, (int, float)) and not math.isnan(result) and not math.isinf(result):
            return float(result)
    except Exception:
        pass
    return None


def _calculate_statistics(table_data, template, header_data=None):
    """
    Вычисляет статистику.
    ОБНОВЛЕНО: использует массив statistics[] вместо has_stats.
    """
    if header_data is None:
        header_data = {}

    specimens = table_data.get('specimens', [])
    if len(specimens) < 2:
        return {}

    result = {}

    # Определяем коды столбцов с статистикой
    if template and template.column_config:
        stat_codes = []
        for col in template.column_config:
            col_type = col.get('type')
            code = col['code']

            if col_type == 'TEXT':
                continue
            if code in ('specimen_number', 'marking', 'failure_mode', 'br', 'number'):
                continue

            # Проверяем массив statistics
            stats_list = col.get('statistics', [])
            if stats_list and len(stats_list) > 0:
                stat_codes.append(code)
    else:
        stat_codes = [
            k for k, v in specimens[0].get('values', {}).items()
            if isinstance(v, (int, float))
        ]

    n = len(specimens)

    t_table = {
        2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776,
        6: 2.571,  7: 2.447, 8: 2.365, 9: 2.306,
        10: 2.262, 11: 2.228, 12: 2.201, 13: 2.179,
        14: 2.160, 15: 2.145, 20: 2.093, 25: 2.060,
        30: 2.042,
    }

    for code in stat_codes:
        values = []
        for spec in specimens:
            v = spec.get('values', {}).get(code)
            if v is not None and isinstance(v, (int, float)):
                values.append(float(v))

        if len(values) < 2:
            continue

        mean = stats_module.mean(values)
        stdev = stats_module.stdev(values)
        cv = (stdev / mean * 100) if mean != 0 else 0.0

        try:
            from scipy import stats as scipy_stats
            t_val = scipy_stats.t.ppf(0.975, len(values) - 1)
        except ImportError:
            t_val = t_table.get(len(values)) or t_table.get(
                min(t_table.keys(), key=lambda k: abs(k - len(values)))
            )

        margin = t_val * stdev / math.sqrt(len(values))

        result[code] = {
            'mean':   round(mean, 4),
            'stdev':  round(stdev, 4),
            'cv':     round(cv, 2),
            'ci_lo':  round(mean - margin, 4),
            'ci_hi':  round(mean + margin, 4),
        }

    return result


# ═══════════════════════════════════════════════════════════════
# 6. EXCEL-ЭКСПОРТ
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_export_test_report_xlsx(request, report_id):
    """GET /api/test-report/<report_id>/export-xlsx/"""
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
    """GET /api/test-report/export-xlsx/<sample_id>/<standard_id>/"""
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
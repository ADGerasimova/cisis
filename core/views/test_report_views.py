"""
core/views/test_report_views.py

Views для отчётов об испытаниях:
1. Конструктор шаблонов (CRUD для report_template_index) ← НОВОЕ
2. Загрузка xlsx-шаблонов (legacy, оставлен для совместимости)
3. Формирование отчёта / ввод данных (оператор)
4. API для расчётов и сохранения
5. Excel-экспорт
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
# 1. КОНСТРУКТОР ШАБЛОНОВ
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_get_template_config(request, standard_id):
    """
    GET /api/report-templates/config/<standard_id>/

    Возвращает текущий шаблон для стандарта (is_current=True).
    Если шаблона нет — возвращает пустую заготовку.

    Response:
    {
        "success": true,
        "has_template": true,
        "template": {
            "id": 3,
            "version": 2,
            "layout_type": "B",
            "column_config": [...],
            "header_config": {...},
            "sub_measurements_config": {...} | null,
            "changes_description": "..."
        }
    }
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
    """
    GET /api/report-templates/config/<standard_id>/versions/

    Возвращает историю версий шаблона для стандарта.

    Response:
    {
        "success": true,
        "versions": [
            {"id": 5, "version": 3, "is_current": true,  "created_at": "...", "changes_description": "..."},
            {"id": 3, "version": 2, "is_current": false, ...},
        ]
    }
    """
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

    # Конвертируем datetime в строку
    for v in versions:
        if v.get('created_at'):
            v['created_at'] = v['created_at'].isoformat()

    return JsonResponse({'success': True, 'versions': versions})


@login_required
@require_POST
def api_save_template_config(request):
    """
    POST /api/report-templates/config/save/

    Создаёт новый шаблон или новую версию существующего.
    Версионирование: если шаблон уже есть, старый → is_current=False,
    новый получает version+1 и is_current=True.

    JSON body:
    {
        "standard_id": 12,
        "layout_type": "A" | "B",
        "changes_description": "Добавлен столбец σnorm",

        "column_config": [
            {
                "code": "h_avg",
                "name": "hср",
                "unit": "мм",
                "type": "SUB_AVG",
                "decimal_places": 2,
                "formula": null         // для INPUT/TEXT/SUB_AVG — null
            },
            {
                "code": "sigma",
                "name": "σВ",
                "unit": "МПа",
                "type": "CALC",
                "decimal_places": 1,
                "formula": "{Pmax} / {b} / {h} * 1000"
            },
            {
                "code": "sigma_norm",
                "name": "σВnorm",
                "unit": "МПа",
                "type": "NORM",
                "decimal_places": 1,
                "formula": "{sigma} * {h} / {tply} / {n_layers}",
                "params": ["tply", "n_layers"],
                "has_stats": true
            }
        ],

        "header_config": {
            "date":       {"label": "Дата:",          "type": "DATE"},
            "operator":   {"label": "Оператор:",      "type": "TEXT"},
            "standard":   {"label": "НД:",            "type": "TEXT"},
            "id_number":  {"label": "Идент. номер:",  "type": "TEXT"},
            "force_sensor":{"label": "Датчик силы:",  "type": "TEXT"},
            "speed":      {"label": "Скорость траверсы:", "type": "TEXT"},
            "specimen_count": {"label": "Кол-во образцов:", "type": "NUMERIC"},
            "conditions": {"label": "Условия испытаний:", "type": "TEXT"},
            "notes":      {"label": "Примечания:",    "type": "TEXT"},
            "room":       {"label": "Помещение:",     "type": "TEXT"},
            "tply":       {"label": "tply, мм",       "type": "NUMERIC"},  // параметр для NORM
            "n_layers":   {"label": "Кол-во слоёв:",  "type": "NUMERIC"}
        },

        // null — если нет боковой таблицы замеров
        "sub_measurements_config": {
            "measurements_per_specimen": 3,
            "columns": [
                {"code": "h", "name": "h", "unit": "мм"},
                {"code": "b", "name": "b", "unit": "мм"}
            ],
            // опциональные вычисляемые поля внутри замеров:
            "derived": [
                {
                    "code": "S",
                    "name": "S",
                    "unit": "мм²",
                    "formula": "{h} * {b}"
                },
                {
                    "code": "S_min",
                    "name": "Smin",
                    "unit": "мм²",
                    "formula": "MIN({S})"
                }
            ]
        }
    }

    Response:
    {
        "success": true,
        "template_id": 7,
        "version": 3,
        "created": true   // false если перезаписали единственную черновую версию
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    standard_id = data.get('standard_id')
    if not standard_id:
        return JsonResponse({'success': False, 'error': 'standard_id обязателен'}, status=400)

    standard = get_object_or_404(Standard, id=standard_id)

    # --- Валидация ---
    column_config = data.get('column_config')
    if not column_config or not isinstance(column_config, list):
        return JsonResponse({'success': False, 'error': 'column_config обязателен'}, status=400)

    errors = _validate_column_config(column_config)
    if errors:
        return JsonResponse({'success': False, 'error': '; '.join(errors)}, status=400)

    header_config = data.get('header_config', {})
    sub_measurements_config = data.get('sub_measurements_config')  # может быть null
    layout_type = data.get('layout_type', 'A')
    changes_description = data.get('changes_description', '').strip()

    if layout_type not in ('A', 'B', 'C'):
        return JsonResponse({'success': False, 'error': 'layout_type должен быть A, B или C'}, status=400)

    # Проверяем: если layout_type=B, должен быть sub_measurements_config
    if layout_type == 'B' and not sub_measurements_config:
        return JsonResponse({
            'success': False,
            'error': 'layout_type=B требует sub_measurements_config',
        }, status=400)

    # --- Версионирование ---
    current = ReportTemplateIndex.objects.filter(
        standard_id=standard_id,
        is_current=True,
        is_active=True,
    ).first()

    if current:
        new_version = current.version + 1
        # Помечаем текущий как архивный
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE report_template_index SET is_current = false WHERE id = %s",
                [current.id]
            )
    else:
        new_version = 1

    # --- Создаём новый шаблон ---
    # source_id = null (шаблон создан вручную, не через парсер xlsx)
    with connection.cursor() as cur:
        cur.execute("""
            INSERT INTO report_template_index (
                standard_id, source_id,
                sheet_name, start_row, end_row, header_row, data_start_row,
                column_config, header_config, sub_measurements_config,
                statistics_config,
                layout_type, version, is_current, changes_description,
                is_active, created_at, updated_at
            ) VALUES (
                %s, NULL,
                '', 0, 0, 0, 0,
                %s, %s, %s,
                '[]',
                %s, %s, true, %s,
                true, NOW(), NOW()
            )
            RETURNING id
        """, [
            standard_id,
            json.dumps(column_config, ensure_ascii=False),
            json.dumps(header_config, ensure_ascii=False),
            json.dumps(sub_measurements_config, ensure_ascii=False) if sub_measurements_config else None,
            layout_type,
            new_version,
            changes_description,
        ])
        new_id = cur.fetchone()[0]

    return JsonResponse({
        'success': True,
        'template_id': new_id,
        'version': new_version,
        'created': True,
    })


@login_required
@require_POST
def api_delete_template_config(request):
    """
    POST /api/report-templates/config/delete/

    Мягкое удаление текущего шаблона (is_active=False).
    Использовать с осторожностью — старые отчёты ссылаются на template_id.

    JSON body: { "standard_id": 12 }  или  { "template_id": 7 }

    Response: { "success": true }
    """
    get_object_or_404(Standard, id=standard_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Невалидный JSON'}, status=400)

    template_id = data.get('template_id')
    if not template_id:
        return JsonResponse({'success': False, 'error': 'template_id обязателен'}, status=400)

    # Проверяем что шаблон принадлежит этому стандарту
    template = get_object_or_404(ReportTemplateIndex, id=template_id, standard_id=standard_id)

    # Проверяем — нет ли отчётов, ссылающихся на этот шаблон
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

        # Если удалили текущий — поднимаем предыдущую версию
        if template.is_current:
            cur.execute("""
                UPDATE report_template_index
                SET is_current = true, updated_at = NOW()
                WHERE standard_id = %s AND is_active = true
                  AND version = (
                      SELECT MAX(version) FROM report_template_index
                      WHERE standard_id = %s AND is_active = true AND id != %s
                  )
            """, [standard_id, standard_id, template_id])

    return JsonResponse({'success': True})


@login_required
@require_POST
def api_restore_template_version(request, standard_id):
    """
    POST /api/report-templates/config/<standard_id>/restore/

    Восстанавливает архивную версию шаблона как текущую.
    Текущая версия при этом становится архивной (не удаляется).

    JSON body: { "template_id": 3 }

    Response: { "success": true, "version": 2 }
    """
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
        # Снимаем флаг с текущей
        cur.execute(
            "UPDATE report_template_index SET is_current = false WHERE standard_id = %s AND is_current = true",
            [standard_id]
        )
        # Поднимаем нужную
        cur.execute(
            "UPDATE report_template_index SET is_current = true, updated_at = NOW() WHERE id = %s",
            [template_id]
        )

    return JsonResponse({'success': True, 'version': target.version})


@login_required
@require_GET
def api_preview_template_config(request, template_id):
    """
    GET /api/report-templates/config/preview/<template_id>/

    Возвращает конфиг шаблона + сгенерированную тестовую строку с примером данных.
    Используется в UI-конструкторе для предпросмотра таблицы.
    """
    template = get_object_or_404(ReportTemplateIndex, id=template_id)
    preview_row = _generate_preview_row(template)
    return JsonResponse({
        'success': True,
        'template': _template_to_dict(template),
        'preview_row': preview_row,
    })


def _generate_preview_row(template):
    """
    Генерирует тестовую строку данных для предпросмотра шаблона.
    """
    import random

    sub_measurements = {}
    if template.sub_measurements_config:
        cols = template.sub_measurements_config.get('columns', [])
        n = template.sub_measurements_config.get('measurements_per_specimen', 3)
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
    """Сериализует ReportTemplateIndex в dict для JSON-ответа."""
    return {
        'id': template.id,
        'version': template.version,
        'is_current': template.is_current,
        'layout_type': template.layout_type,
        'column_config': template.column_config,
        'header_config': template.header_config,
        'sub_measurements_config': template.sub_measurements_config,
        'changes_description': template.changes_description,
        'created_at': template.created_at.isoformat() if template.created_at else None,
    }


def _validate_column_config(column_config):
    """
    Валидирует column_config.
    Возвращает список ошибок (пустой список = всё ок).
    """
    errors = []
    valid_types = ('INPUT', 'TEXT', 'SUB_AVG', 'CALC', 'NORM')
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
            errors.append(f'{prefix}: неизвестный тип "{col_type}", допустимые: {", ".join(valid_types)}')

        # CALC и NORM обязаны иметь formula
        if col_type in ('CALC', 'NORM') and not col.get('formula'):
            errors.append(f'{prefix}: тип {col_type} требует поле "formula"')

        # NORM обязан иметь params
        if col_type == 'NORM' and not col.get('params'):
            errors.append(f'{prefix}: тип NORM требует поле "params" (список кодов из header_config)')

        # SUB_AVG — нет формулы (вычисляется автоматически из sub_measurements)
        if col_type == 'SUB_AVG' and col.get('formula'):
            errors.append(f'{prefix}: тип SUB_AVG не требует formula (среднее считается автоматически)')

    return errors


# ═══════════════════════════════════════════════════════════════
# 2. ЗАГРУЗКА XLSX-ШАБЛОНОВ (legacy)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_upload_report_template(request):
    """
    POST /api/report-templates/upload/
    Загружает xlsx-файл, парсит и создаёт индекс шаблонов.
    Legacy-метод, оставлен для совместимости.

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
    """Сохраняет xlsx на постоянное место. Возвращает путь."""
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
    """
    GET /api/report-templates/
    Список загруженных источников шаблонов (legacy xlsx).
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
    Список шаблонов (стандартов) в источнике (legacy xlsx).
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
# 3. ФОРМИРОВАНИЕ ОТЧЁТА (оператор)
# ═══════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_get_report_form(request, sample_id):
    """
    GET /api/test-report/form/<sample_id>/
    Возвращает конфигурацию формы для ввода данных отчёта.

    Логика:
    1. Берём стандарт(ы) образца
    2. Находим шаблон (report_template_index)
    3. Возвращаем column_config + header_config + предзаполненные данные
    """
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

        forms.append({
            'standard': std,
            'has_template': True,
            'template_id': template.id,
            'template_version': template.version,
            'column_config': template.column_config,
            'header_config': template.header_config,
            'sub_measurements_config': template.sub_measurements_config,
            'statistics_config': template.statistics_config,
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
# 4. СОХРАНЕНИЕ ДАННЫХ ОТЧЁТА
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

    template = ReportTemplateIndex.objects.filter(id=template_id).first() if template_id else None
    statistics_data = _calculate_statistics(table_data, template, header_data)

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
    """
    POST /api/test-report/calculate/
    Пересчитывает вычисляемые поля и статистику на лету.

    JSON body:
    {
        "table_data": {...},
        "header_data": {...},   // нужен для NORM-столбцов
        "template_id": int
    }
    """
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
    """
    Пересчитывает SUB_AVG, CALC и NORM столбцы для всех образцов.

    - SUB_AVG: среднее из sub_measurements
    - CALC:    формула вида "{Pmax} / {b} / {h} * 1000"
    - NORM:    формула с параметрами из header_data
    """
    if header_data is None:
        header_data = {}

    specimens = table_data.get('specimens', [])
    sub_cfg = template.sub_measurements_config or {}

    for spec in specimens:
        values = spec.get('values', {})
        sub = spec.get('sub_measurements', {})

        for col in template.column_config:
            code = col['code']
            col_type = col.get('type')
            decimal_places = col.get('decimal_places', 2)

            if col_type == 'SUB_AVG' and sub:
                # Код замера: h_avg → h, b_avg → b, или явно через sub_code
                sub_code = col.get('sub_code') or code.replace('_avg', '')
                measurements = sub.get(sub_code, [])
                valid = [m for m in measurements if m is not None and isinstance(m, (int, float))]
                if valid:
                    values[code] = round(sum(valid) / len(valid), decimal_places)

            elif col_type == 'CALC' and col.get('formula'):
                result = _eval_formula(col['formula'], values)
                if result is not None:
                    values[code] = round(result, decimal_places)

            elif col_type == 'NORM' and col.get('formula'):
                # Подставляем и значения строки, и параметры из шапки
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

        # Производные в sub_measurements (derived)
        if sub and sub_cfg.get('derived'):
            _recalculate_sub_derived(sub, sub_cfg['derived'], header_data)
            spec['sub_measurements'] = sub

        spec['values'] = values

    # Пересчёт derived внутри sub_measurements (MIN по всем образцам не нужен —
    # MIN({S}) означает MIN по трём замерам одного образца, это уже выше)

    table_data['specimens'] = specimens
    return table_data


def _recalculate_sub_derived(sub, derived_config, header_data):
    """
    Пересчитывает derived-поля внутри sub_measurements одного образца.
    sub — dict вида {"h": [1.0, 1.1, 1.0], "b": [12.5, 12.4, 12.5]}
    """
    for derived in derived_config:
        code = derived['code']
        formula = derived.get('formula', '')
        if not formula:
            continue

        # Формула вида "{h} * {b}" применяется к каждому замеру
        if 'MIN(' in formula.upper():
            # MIN({S}) — минимум из массива другого derived-поля
            import re
            match = re.search(r'MIN\(\{(\w+)\}\)', formula, re.IGNORECASE)
            if match:
                src_code = match.group(1)
                src_values = sub.get(src_code, [])
                valid = [v for v in src_values if v is not None and isinstance(v, (int, float))]
                sub[code] = min(valid) if valid else None
        else:
            # Поэлементное вычисление
            n = max((len(v) for v in sub.values() if isinstance(v, list)), default=0)
            results = []
            for i in range(n):
                row_vals = {}
                for k, vals in sub.items():
                    if isinstance(vals, list) and i < len(vals):
                        row_vals[k] = vals[i]
                # Добавляем параметры из шапки
                for param, val in header_data.items():
                    try:
                        row_vals[param] = float(val)
                    except (ValueError, TypeError):
                        pass
                result = _eval_formula(formula, row_vals)
                results.append(result)
            sub[code] = results


def _eval_formula(formula, values):
    """
    Вычисляет формулу, подставляя значения по кодам.
    Формат: "{Pmax} / {b} / {h} * 1000"

    Возвращает float или None при ошибке.
    """
    import re

    expr = formula.strip()

    # Подставляем значения
    def replace_var(match):
        code = match.group(1)
        val = values.get(code)
        if val is None or not isinstance(val, (int, float)):
            return 'None'
        return str(float(val))

    expr = re.sub(r'\{(\w+)\}', replace_var, expr)

    # Если после подстановки есть None — формула не вычисляется
    if 'None' in expr:
        return None

    try:
        result = eval(expr, {"__builtins__": {}})  # noqa: S307
        if isinstance(result, (int, float)) and not math.isnan(result) and not math.isinf(result):
            return float(result)
    except Exception:
        pass

    return None


def _calculate_statistics(table_data, template, header_data=None):
    """
    Вычисляет статистику по данным таблицы.
    Считает mean, stdev, cv%, доверительный интервал (α=0.05).

    Для NORM-столбцов с has_stats=True — статистика считается так же,
    как для обычных числовых столбцов.
    """
    if header_data is None:
        header_data = {}

    specimens = table_data.get('specimens', [])
    if len(specimens) < 2:
        return {}

    result = {}

    # Определяем коды столбцов, по которым считаем статистику
    if template and template.column_config:
        stat_codes = []
        for col in template.column_config:
            col_type = col.get('type')
            code = col['code']

            # Пропускаем нечисловые и служебные
            if col_type == 'TEXT':
                continue
            if code in ('specimen_number', 'marking', 'failure_mode', 'br', 'number'):
                continue

            # INPUT, SUB_AVG, CALC — всегда в статистику (если числовые)
            if col_type in ('INPUT', 'SUB_AVG', 'CALC'):
                stat_codes.append(code)

            # NORM — только если has_stats=True
            elif col_type == 'NORM' and col.get('has_stats'):
                stat_codes.append(code)
    else:
        # Fallback — берём все числовые значения из первого образца
        stat_codes = [
            k for k, v in specimens[0].get('values', {}).items()
            if isinstance(v, (int, float))
        ]

    n = len(specimens)

    # Таблица критических значений t (двусторонний, α=0.05)
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

        # Доверительный интервал
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
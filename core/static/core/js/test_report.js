/* ═══════════════════════════════════════════════════════════════
   test_report.js — v5.0.0
   Форма ввода данных отчёта об испытании
   Рефакторинг: has_stats → statistics[]
   ═══════════════════════════════════════════════════════════════ */

const TestReport = {
    sampleId: null,
    forms: [],
    activeForm: null,
    _calcTimer: null,

    // ─── Инициализация ───
    async init(sampleId) {
        this.sampleId = sampleId;
        try {
            const resp = await fetch(`/api/test-report/form/${sampleId}/`);
            const data = await resp.json();
            if (!data.success) {
                document.getElementById('test-report-container').innerHTML =
                    `<div class="tr-msg tr-msg-err">Ошибка: ${data.error || 'Нет данных'}</div>`;
                return;
            }
            this.forms = data.forms;
            this._renderFormSelector();
        } catch (e) {
            console.error('TestReport init:', e);
            document.getElementById('test-report-container').innerHTML =
                '<div class="tr-msg tr-msg-err">Ошибка загрузки формы отчёта</div>';
        }
    },

    // ─── Табы стандартов ───
    _renderFormSelector() {
        const container = document.getElementById('test-report-container');
        if (!container) return;

        if (this.forms.length === 0) {
            container.innerHTML = '<div class="tr-msg">Нет доступных шаблонов отчётов</div>';
            return;
        }

        if (this.forms.length === 1) {
            container.innerHTML = '<div id="tr-form-area"></div>';
            this._renderForm(this.forms[0]);
            return;
        }

        let html = '<div class="tr-tabs">';
        this.forms.forEach((form, i) => {
            const cls = i === 0 ? ' active' : '';
            html += `<div class="tr-tab${cls}" onclick="TestReport._switchTab(${i})">${form.standard.code}</div>`;
        });
        html += '</div><div id="tr-form-area"></div>';
        container.innerHTML = html;
        this._renderForm(this.forms[0]);
    },

    _switchTab(index) {
        document.querySelectorAll('.tr-tab').forEach((el, i) => el.classList.toggle('active', i === index));
        this._renderForm(this.forms[index]);
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ХЕЛПЕР: получить массив statistics для столбца ───
    // Поддерживает и новый формат (statistics:[...]) и старый (has_stats:bool)
    // ═══════════════════════════════════════════════════════════
    _getColumnStatistics(col) {
        // Новый формат: массив statistics
        if (Array.isArray(col.statistics)) {
            return col.statistics;
        }
        // Обратная совместимость: старый формат has_stats
        if (col.has_stats === true) {
            return ['MEAN', 'STDEV', 'CV', 'CONFIDENCE'];
        }
        return [];
    },

    // Проверяет, нужна ли конкретная метрика для столбца
    _columnHasStat(col, statType) {
        return this._getColumnStatistics(col).includes(statType);
    },

    // Проверяет, нужна ли хоть какая-то статистика для столбца
    _columnHasAnyStats(col) {
        return this._getColumnStatistics(col).length > 0;
    },

    // ─── Рендер формы ───
    _renderForm(formConfig) {
        this.activeForm = formConfig;
        const area = document.getElementById('tr-form-area') || document.getElementById('test-report-container');

        if (!formConfig.has_template) {
            area.innerHTML = `<div class="tr-msg">${formConfig.message}</div>`;
            return;
        }

        // ── Нормализация sub_measurements_config ──
        this._normalizeSubConfig(formConfig);

        // ── Автогенерация statistics_config если пустая ──
        this._ensureStatisticsConfig(formConfig);

        const existing = formConfig.existing_report;
        const specimens = existing ? existing.table_data.specimens : [];
        const headerData = existing ? existing.header_data : (formConfig.prefilled_header || {});
        const cols = formConfig.column_config.filter(c => c.code !== 'br');
        const specCount = specimens.length || parseInt(headerData.specimen_count) || 6;

        let html = '';
        html += this._renderHeader(headerData);

        html += `<div class="tr-controls">
            <label>Количество образцов:</label>
            <input type="number" id="tr-spec-count" value="${specCount}" min="1" max="30"
                   onchange="TestReport._updateSpecimenCount(this.value)">
            <span class="tr-std-badge">${formConfig.standard.code}</span>
        </div>`;

        if (formConfig.sub_measurements_config) {
            html += this._renderSubMeasurements(formConfig, specimens, specCount);
        }

        html += '<div class="tr-table-wrap"><table class="tr-table">';
        html += this._renderTableHead(cols);
        html += this._renderTableBody(cols, specimens, specCount);
        html += this._renderStatistics(formConfig, cols, existing);
        html += '</table></div>';

        // ── Дополнительные таблицы ──
        if (formConfig.additional_tables && formConfig.additional_tables.length > 0) {
            formConfig.additional_tables.forEach(at => {
                if (at.table_type === 'SUB_MEASUREMENTS') return; // ← добавить эту строку
                html += this._renderAdditionalTable(at, existing, specCount);
            });
        }

        const label = existing && existing.status === 'COMPLETED' ? 'Обновить' : 'Сохранить';
        html += `<div class="tr-actions">
            <button class="tr-btn tr-btn-draft" onclick="TestReport._save('DRAFT')">💾 Черновик</button>
            <button class="tr-btn tr-btn-complete" onclick="TestReport._save('COMPLETED')">✅ ${label}</button>
            <button class="tr-btn tr-btn-xlsx" onclick="TestReport._downloadXlsx()">📥 Скачать Excel</button>
        </div>`;

        area.innerHTML = html;
        this._initPasteHandler();
        setTimeout(() => this._localRecalculate(), 50);
    },

    // ─── Шапка ───
    _renderHeader(hd) {
        const baseFields = [
            {key: 'identification_number', label: 'Идентификационный номер', ro: true},
            {key: 'conditions', label: 'Условия испытаний'},
            {key: 'force_sensor', label: 'Датчик силы'},
            {key: 'traverse_speed', label: 'Скорость траверсы'},
            {key: 'specimen_count', label: 'Кол-во образцов', type: 'number'},
            {key: 'notes', label: 'Примечания'},
            {key: 'room', label: 'Помещение'},
        ];

        const headerConfig = this.activeForm?.header_config || {};
        const baseKeys = new Set(baseFields.map(f => f.key));
        const skipKeys = new Set(['date', 'operator', 'measuring_instruments', 'test_equipment']);

        const extraFields = [];
        Object.entries(headerConfig).forEach(([key, cfg]) => {
            if (baseKeys.has(key) || skipKeys.has(key)) return;
            extraFields.push({
                key: key,
                label: cfg.label || key,
                type: cfg.type === 'NUMERIC' ? 'number' : 'text',
            });
        });

        const fields = [...baseFields, ...extraFields];

        let html = '<div class="tr-section"><div class="tr-section-title">Шапка отчёта</div>';
        html += '<div class="tr-header-grid">';
        fields.forEach(f => {
            const val = hd[f.key] || '';
            const ro = f.ro ? ' readonly' : '';
            html += `<div class="tr-hfield">
                <label>${f.label}</label>
                <input type="${f.type || 'text'}" data-header="${f.key}" value="${this._esc(val)}"${ro}>
            </div>`;
        });

        if (hd.measuring_instruments) {
            html += `<div class="tr-hfield tr-hfield-full">
                <label>СИ (средства измерений)</label>
                <textarea data-header="measuring_instruments" readonly rows="2">${this._esc(hd.measuring_instruments)}</textarea>
            </div>`;
        }
        if (hd.test_equipment) {
            html += `<div class="tr-hfield tr-hfield-full">
                <label>ИО (испытательное оборудование)</label>
                <textarea data-header="test_equipment" readonly rows="2">${this._esc(hd.test_equipment)}</textarea>
            </div>`;
        }

        html += '</div></div>';
        return html;
    },

    // ─── Заголовки основной таблицы ───
    _renderTableHead(cols) {
        let html = '<thead><tr>';
        cols.forEach(c => {
            const title = c.unit ? `${c.name}, ${c.unit}` : c.name;
            const cls = (['CALCULATED', 'SUB_AVG', 'VLOOKUP', 'CALC', 'NORM'].includes(c.type)) ? ' tr-th-calc' : '';
            html += `<th class="${cls}">${this._esc(title)}</th>`;
        });
        html += '</tr></thead>';
        return html;
    },

    // ─── Строки основной таблицы ───
    _renderTableBody(cols, specimens, specCount) {
        let html = '<tbody>';
        for (let i = 0; i < specCount; i++) {
            const spec = specimens[i] || {};
            const vals = spec.values || {};

            html += '<tr>';

            cols.forEach(c => {
                const val = c.code === 'specimen_number' ? (i + 1) : (vals[c.code] ?? '');

                if (c.code === 'specimen_number') {
                    html += `<td class="tr-td-num">${i + 1}</td>`;
                } else if (c.type === 'TEXT') {
                    html += `<td><input type="text" data-row="${i}" data-col="${c.code}"
                            value="${this._esc(val)}" class="tr-inp tr-inp-txt"></td>`;
                } else if (c.type === 'CALCULATED' || c.type === 'SUB_AVG' || c.type === 'CALC' || c.type === 'NORM') {
                    html += `<td class="tr-td-calc" data-row="${i}" data-col="${c.code}">${val !== '' && val !== null ? val : ''}</td>`;
                } else if (c.type === 'VLOOKUP') {
                    const title = c.formula ? `Формула: ${c.formula}` : '';
                    html += `<td class="tr-td-calc tr-td-vlookup" data-row="${i}" data-col="${c.code}" title="${this._esc(title)}">${val !== '' && val !== null ? val : '—'}</td>`;
                } else {
                    html += `<td><input type="number" step="any" data-row="${i}" data-col="${c.code}"
                            value="${val}" class="tr-inp tr-inp-num"
                            oninput="TestReport._onValueChange(${i},'${c.code}',this.value)"></td>`;
                }
            });

            html += '</tr>';
        }
        html += '</tbody>';
        return html;
    },

    // ═══════════════════════════════════════════════════════════
    // ─── СТАТИСТИКА (РЕФАКТОРИНГ: statistics[] вместо has_stats) ───
    // ═══════════════════════════════════════════════════════════
    _renderStatistics(formConfig, cols, existing) {
        // Собираем уникальный набор типов статистики, которые нужны
        // хоть одному столбцу
        const allStatTypes = new Set();
        cols.forEach(c => {
            this._getColumnStatistics(c).forEach(st => allStatTypes.add(st));
        });

        if (allStatTypes.size === 0) return '';

        // Порядок вывода строк статистики
        const orderedTypes = ['MEAN', 'STDEV', 'CV', 'CONFIDENCE'];
        const activeTypes = orderedTypes.filter(t => allStatTypes.has(t));

        if (activeTypes.length === 0) return '';

        const statsData = existing ? existing.statistics_data : {};

        const labels = {
            'MEAN': 'Среднее арифметическое',
            'STDEV': 'Стандартное отклонение',
            'CV': 'Коэффициент вариации, %',
            'CONFIDENCE': 'Доверительный интервал',
        };

        // Определяем colspan для label-ячейки
        let labelSpan = 0;
        for (const c of cols) {
            if (['specimen_number', 'marking'].includes(c.code)) {
                labelSpan++;
            } else {
                break;
            }
        }
        if (labelSpan < 1) labelSpan = 1;

        const dataCols = cols.slice(labelSpan);

        let html = '<tfoot>';
        activeTypes.forEach((statType, si) => {
            const rowCls = si === 0 ? ' tr-stat-first' : '';
            html += `<tr class="tr-stat-row tr-stat-${statType.toLowerCase()}${rowCls}">`;
            html += `<td colspan="${labelSpan}" class="tr-stat-label">${labels[statType] || statType}</td>`;

            dataCols.forEach(c => {
                // Проверяем, нужна ли ЭТА метрика для ЭТОГО столбца
                if (c.type === 'TEXT' || !this._columnHasStat(c, statType)) {
                    html += '<td class="tr-stat-empty"></td>';
                    return;
                }

                const colStats = statsData[c.code];
                let val = '';

                if (colStats) {
                    if (statType === 'MEAN') val = this._fmt(colStats.mean);
                    else if (statType === 'STDEV') val = this._fmt(colStats.stdev);
                    else if (statType === 'CV') val = this._fmt(colStats.cv);
                    else if (statType === 'CONFIDENCE') {
                        if (colStats.ci_lo != null && colStats.ci_hi != null) {
                            val = `${this._fmt(colStats.ci_lo)} – ${this._fmt(colStats.ci_hi)}`;
                        }
                    }
                }

                html += `<td class="tr-stat-val" data-stat="${statType}" data-col="${c.code}">${val}</td>`;
            });

            html += '</tr>';
        });
        html += '</tfoot>';
        return html;
    },

    // Автогенерация statistics_config из statistics[] массивов столбцов
    _ensureStatisticsConfig(formConfig) {
        // Собираем все уникальные типы статистики из столбцов
        const allStatTypes = new Set();
        const colsByStatType = {};

        (formConfig.column_config || []).forEach(c => {
            const stats = this._getColumnStatistics(c);
            stats.forEach(st => {
                allStatTypes.add(st);
                if (!colsByStatType[st]) colsByStatType[st] = [];
                colsByStatType[st].push({
                    col_letter: c.col_letter || c.code,
                    code: c.code
                });
            });
        });

        if (allStatTypes.size === 0) {
            formConfig.statistics_config = [];
            return;
        }

        // Генерируем statistics_config в правильном порядке
        const orderedTypes = ['MEAN', 'STDEV', 'CV', 'CONFIDENCE'];
        formConfig.statistics_config = orderedTypes
            .filter(t => allStatTypes.has(t))
            .map(t => ({
                type: t,
                columns: colsByStatType[t] || []
            }));
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ОПРЕДЕЛЕНИЕ ТИПА СТОЛБЦА В БОКОВОЙ ТАБЛИЦЕ ───
    // ═══════════════════════════════════════════════════════════
    _isAggregateColumn(col) {
        if (!col.formula) return false;
        return /^\s*(MIN|MAX|AVERAGE|SUM)\s*\([A-Z]+\d+:[A-Z]+\d+\)\s*$/i.test(col.formula);
    },

    _isSubInputType(col) {
        const t = col.type || 'INPUT';
        if (t === 'TEXT') return false;
        if (this._isAggregateColumn(col)) return false;
        if (['FORMULA', 'CALCULATED', 'SUB_AVG'].includes(t) && col.formula) return false;
        return true;
    },

    _normalizeSubConfig(formConfig) {
        const sub = formConfig.sub_measurements_config;
        if (!sub || !sub.columns) return;

        const usedLetters = new Set();
        (formConfig.column_config || []).forEach(c => {
            if (c.col_letter) usedLetters.add(c.col_letter.toUpperCase());
        });

        let nextCharCode = 65;
        const getNextLetter = () => {
            let letter;
            do {
                letter = String.fromCharCode(nextCharCode++);
            } while (usedLetters.has(letter) && nextCharCode <= 90);
            usedLetters.add(letter);
            return letter;
        };

        sub.columns.forEach(c => {
            if (!c.type) c.type = 'INPUT';
            if (!c.col_letter) {
                c.col_letter = c.code.toUpperCase().charAt(0);
                if (usedLetters.has(c.col_letter)) {
                    c.col_letter = getNextLetter();
                } else {
                    usedLetters.add(c.col_letter);
                }
            }
        });

        if (sub.derived && Array.isArray(sub.derived) && sub.derived.length > 0) {
            sub.derived.forEach(d => {
                if (!d.type) {
                    if (d.formula && /\b(MIN|MAX|AVERAGE|SUM)\s*\(/i.test(d.formula)) {
                        d.type = 'CALCULATED';
                    } else {
                        d.type = 'FORMULA';
                    }
                }
                if (!d.col_letter) {
                    d.col_letter = d.code ? d.code.toUpperCase().charAt(0) : getNextLetter();
                    if (usedLetters.has(d.col_letter)) {
                        d.col_letter = getNextLetter();
                    } else {
                        usedLetters.add(d.col_letter);
                    }
                }
            });
            const existingCodes = new Set(sub.columns.map(c => c.code));
            sub.derived.forEach(d => {
                if (!existingCodes.has(d.code)) {
                    sub.columns.push(d);
                }
            });
        }

        const codeToLetter = {};
        sub.columns.forEach(c => {
            if (c.code && c.col_letter) codeToLetter[c.code] = c.col_letter;
        });
        const mpp = sub.measurements_per_specimen || 3;

        sub.columns.forEach(c => {
            if (!c.formula) return;
            let f = c.formula;
            if (!f.includes('{')) return;

            const aggMatch = f.match(/^(MIN|MAX|AVERAGE|SUM)\s*\(\s*\{(\w+)\}\s*\)$/i);
            if (aggMatch) {
                const func = aggMatch[1].toUpperCase();
                const refCode = aggMatch[2];
                const letter = codeToLetter[refCode];
                if (letter) {
                    c.formula = `${func}(${letter}1:${letter}${mpp})`;
                    return;
                }
            }

            f = f.replace(/\b(MIN|MAX|AVERAGE|SUM)\s*\(\s*\{(\w+)\}\s*\)/gi, (_, func, code) => {
                const letter = codeToLetter[code];
                if (letter) {
                    return `${func.toUpperCase()}(${letter}1:${letter}${mpp})`;
                }
                return '0';
            });

            const colParams = c.params || [];

            f = f.replace(/\{(\w+)\}/g, (_, code) => {
                if (colParams.includes(code)) {
                    return `__HEADER_${code}__`;
                }
                const letter = codeToLetter[code];
                return letter ? `${letter}1` : '0';
            });
            c.formula = f;
        });
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ПРОМЕЖУТОЧНЫЕ ЗАМЕРЫ (БОКОВАЯ ТАБЛИЦА) ───
    // ═══════════════════════════════════════════════════════════
    _renderSubMeasurements(formConfig, specimens, specCount) {
        const sub = formConfig.sub_measurements_config;
        if (!sub || !sub.columns) return '';

        const mpp = sub.measurements_per_specimen || 3;

        let html = '<div class="tr-section">';
        html += '<div class="tr-section-title">Промежуточные замеры</div>';
        html += '<div class="tr-table-wrap" style="overflow-x: auto;">';
        html += '<table class="tr-table tr-table-sub">';

        html += '<thead><tr>';
        html += '<th>№</th>';

        sub.columns.forEach(c => {
            const title = c.unit ? `${c.name}, ${c.unit}` : c.name;
            const isCalc = ['FORMULA', 'CALCULATED', 'SUB_AVG'].includes(c.type);
            const cls = isCalc ? ' class="tr-th-calc"' : '';

            if (c.type === 'TEXT' || this._isAggregateColumn(c)) {
                html += `<th${cls}>${this._esc(title)}</th>`;
            } else {
                for (let m = 0; m < mpp; m++) {
                    html += `<th${cls}>${this._esc(title)}<sub>${m + 1}</sub></th>`;
                }
            }
        });
        html += '</tr></thead>';

        html += '<tbody>';
        for (let i = 0; i < specCount; i++) {
            const spec = specimens[i] || {};
            const subData = spec.sub_measurements || {};

            html += '<tr>';
            html += `<td class="tr-td-num">${i + 1}</td>`;

            sub.columns.forEach(c => {
                const subKey = c.col_letter;
                const measurements = subData[c.code] || [];
                const cType = c.type || 'INPUT';
                const isFormula = ['FORMULA', 'CALCULATED', 'SUB_AVG'].includes(cType) && c.formula;
                const isAggregate = this._isAggregateColumn(c);
                const isInput = !isFormula && !isAggregate && cType !== 'TEXT';

                if (cType === 'TEXT') {
                    const val = measurements[0] ?? '';
                    html += '<td>';
                    html += `<input type="text" class="tr-inp tr-inp-txt tr-inp-sub"
                             data-row="${i}" data-sub="${subKey}" data-meas="0"
                             value="${this._esc(val)}"
                             oninput="TestReport._onSubChange(${i},'${subKey}',0,this.value)">`;
                    html += '</td>';
                } else if (isAggregate) {
                    let calcValue = '';
                    if (spec.values && spec.values[subKey] !== undefined) {
                        calcValue = spec.values[subKey];
                    }
                    const dv = this._formatCalcValue(calcValue);
                    html += `<td class="tr-td-calc" data-row="${i}" data-sub="${subKey}" data-aggregate="1">${dv}</td>`;
                } else if (isInput) {
                    for (let m = 0; m < mpp; m++) {
                        const val = measurements[m] ?? '';
                        html += '<td>';
                        html += `<input type="number" step="any" class="tr-inp tr-inp-num tr-inp-sub"
                                 data-row="${i}" data-sub="${subKey}" data-meas="${m}"
                                 value="${val}"
                                 oninput="TestReport._onSubChange(${i},'${subKey}',${m},this.value)">`;
                        html += '</td>';
                    }
                } else {
                    for (let m = 0; m < mpp; m++) {
                        let calcValue = '';
                        const cacheKey = `${subKey}_${m}`;
                        if (spec.values && spec.values[cacheKey] !== undefined) {
                            calcValue = spec.values[cacheKey];
                        }
                        const dv = this._formatCalcValue(calcValue);
                        html += `<td class="tr-td-calc" data-row="${i}" data-sub="${subKey}" data-meas="${m}">${dv}</td>`;
                    }
                }
            });

            html += '</tr>';
        }
        html += '</tbody>';
        html += '</table></div></div>';

        return html;
    },

    _formatCalcValue(val) {
        if (val === '' || val === null || val === undefined) return '—';
        const n = parseFloat(val);
        if (isNaN(n)) return '—';
        return (Math.round(n * 100) / 100).toString();
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ВЫЧИСЛЕНИЕ ПОЯЧЕЙЕЧНОЙ ФОРМУЛЫ ───
    // ═══════════════════════════════════════════════════════════
    _computeSubFormulaForMeasurement(formula, rowIndex, measIndex, subConfig) {
        try {
            let expr = formula.startsWith('=') ? formula.substring(1) : formula;

            if (this._isAggregateColumn({formula: expr})) return '';

            const mpp = subConfig.measurements_per_specimen || 3;

            const headerData = this._collectHeaderData();
            expr = expr.replace(/__HEADER_(\w+)__/g, (_, code) => {
                const val = headerData[code];
                if (val !== undefined && val !== '') {
                    const v = parseFloat(val);
                    if (!isNaN(v)) return v.toString();
                }
                return 'null';
            });
            if (expr.includes('null')) return '';

            expr = expr.replace(/\b(MIN|MAX|AVERAGE|SUM)\s*\(([A-Z]+)\d+:([A-Z]+)\d+\)/gi, (_, func, startCol, endCol) => {
                const colLetter = startCol.toUpperCase();
                const values = [];
                for (let m = 0; m < mpp; m++) {
                    let val = null;
                    const targetCol = subConfig.columns.find(c => c.col_letter === colLetter);
                    if (targetCol && this._isSubInputType(targetCol)) {
                        const input = document.querySelector(
                            `input[data-row="${rowIndex}"][data-sub="${colLetter}"][data-meas="${m}"]`
                        );
                        if (input && input.value !== '') val = parseFloat(input.value);
                    } else {
                        const cell = document.querySelector(
                            `td[data-row="${rowIndex}"][data-sub="${colLetter}"][data-meas="${m}"]`
                        );
                        if (cell && cell.textContent && cell.textContent !== '—') {
                            val = parseFloat(cell.textContent.replace(/[^\d.\-]/g, ''));
                        }
                    }
                    if (val !== null && !isNaN(val)) values.push(val);
                }
                if (values.length === 0) return '0';
                switch (func.toUpperCase()) {
                    case 'AVERAGE': return (values.reduce((a, b) => a + b, 0) / values.length).toString();
                    case 'MIN': return Math.min(...values).toString();
                    case 'MAX': return Math.max(...values).toString();
                    case 'SUM': return values.reduce((a, b) => a + b, 0).toString();
                    default: return '0';
                }
            });

            const cellRefs = expr.match(/[A-Z]+\d+/gi);
            if (!cellRefs) {
                expr = expr.replace(/\s/g, '');
                if (/^[\d+\-*/().]+$/.test(expr)) {
                    const result = Function('"use strict";return (' + expr + ')')();
                    if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
                        return Math.round(result * 100) / 100;
                    }
                }
                return '';
            }

            let resultExpr = expr;

            for (const ref of cellRefs) {
                const refMatch = ref.match(/([A-Z]+)(\d+)/i);
                if (!refMatch) continue;

                const colLetter = refMatch[1].toUpperCase();
                const targetCol = subConfig.columns.find(c => c.col_letter === colLetter);
                if (!targetCol) {
                    resultExpr = resultExpr.replace(new RegExp(ref, 'g'), '0');
                    continue;
                }

                let value = null;
                if (this._isSubInputType(targetCol)) {
                    const input = document.querySelector(
                        `input[data-row="${rowIndex}"][data-sub="${colLetter}"][data-meas="${measIndex}"]`
                    );
                    if (input && input.value !== '') {
                        value = parseFloat(input.value);
                    }
                } else {
                    const cell = document.querySelector(
                        `td[data-row="${rowIndex}"][data-sub="${colLetter}"][data-meas="${measIndex}"]`
                    );
                    if (cell && cell.textContent && cell.textContent !== '—') {
                        const text = cell.textContent.replace(/[^\d.\-]/g, '');
                        value = parseFloat(text);
                    }
                }

                const replacement = (value !== null && !isNaN(value)) ? value.toString() : '0';
                resultExpr = resultExpr.replace(new RegExp(ref, 'g'), replacement);
            }

            resultExpr = resultExpr.replace(/\s/g, '');
            if (/^[\d+\-*/().]+$/.test(resultExpr)) {
                const result = Function('"use strict";return (' + resultExpr + ')')();
                if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
                    return Math.round(result * 100) / 100;
                }
            }

            return '';
        } catch (e) {
            console.error('SubFormula error:', e, formula);
            return '';
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ВЫЧИСЛЕНИЕ АГРЕГАТНОЙ ФОРМУЛЫ ───
    // ═══════════════════════════════════════════════════════════
    _computeAggregateFormula(formula, rowIndex, subConfig, mpp) {
        try {
            let expr = formula.startsWith('=') ? formula.substring(1) : formula;

            const match = expr.match(/\b(MIN|MAX|AVERAGE|SUM)\s*\(([A-Z]+)\d+:([A-Z]+)\d+\)/i);
            if (!match) return '';

            const func = match[1].toUpperCase();
            const colLetter = match[2].toUpperCase();

            const targetCol = subConfig.columns.find(c => c.col_letter === colLetter);
            if (!targetCol) return '';

            const values = [];

            for (let m = 0; m < mpp; m++) {
                let val = null;

                if (this._isSubInputType(targetCol)) {
                    const input = document.querySelector(
                        `input[data-row="${rowIndex}"][data-sub="${colLetter}"][data-meas="${m}"]`
                    );
                    if (input && input.value !== '') {
                        val = parseFloat(input.value);
                    }
                } else {
                    const cell = document.querySelector(
                        `td[data-row="${rowIndex}"][data-sub="${colLetter}"][data-meas="${m}"]`
                    );
                    if (cell && cell.textContent && cell.textContent !== '—') {
                        const text = cell.textContent.replace(/[^\d.\-]/g, '');
                        val = parseFloat(text);
                    }
                }

                if (val !== null && !isNaN(val)) {
                    values.push(val);
                }
            }

            if (values.length === 0) return '';

            switch (func) {
                case 'MIN':     return Math.min(...values);
                case 'MAX':     return Math.max(...values);
                case 'AVERAGE': return values.reduce((a, b) => a + b, 0) / values.length;
                case 'SUM':     return values.reduce((a, b) => a + b, 0);
                default:        return '';
            }
        } catch (e) {
            console.error('Aggregate formula error:', e, formula);
            return '';
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── VLOOKUP для основной таблицы ───
    // ═══════════════════════════════════════════════════════════
    _computeVlookup(formula, rowIndex, specimen, allSpecimens) {
        try {
            let expr = formula.startsWith('=') ? formula.substring(1) : formula;
            const cols = this.activeForm?.column_config || [];
            const sub = this.activeForm?.sub_measurements_config;
            const mpp = sub?.measurements_per_specimen || 3;

            const vlookupMatch = expr.match(/VLOOKUP\s*\(\s*([A-Z]+)\d+\s*,\s*([A-Z]+)\d+:([A-Z]+)\d+\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/i);

            if (vlookupMatch && sub) {
                const lookupColLetter = vlookupMatch[1].toUpperCase();
                const rangeStartCol = vlookupMatch[2].toUpperCase();
                const rangeEndCol = vlookupMatch[3].toUpperCase();
                const colIndex = parseInt(vlookupMatch[4]);

                let lookupValue = null;
                const lookupCell = document.querySelector(
                    `td[data-row="${rowIndex}"][data-sub="${lookupColLetter}"][data-aggregate="1"]`
                );
                if (lookupCell && lookupCell.textContent !== '—') {
                    const text = lookupCell.textContent.replace(/[^\d.\-]/g, '');
                    lookupValue = parseFloat(text);
                }

                if (lookupValue === null || isNaN(lookupValue)) {
                    return '—';
                }

                const startIdx = rangeStartCol.charCodeAt(0) - 65;
                const endIdx = rangeEndCol.charCodeAt(0) - 65;
                const rangeColLetters = [];
                for (let idx = startIdx; idx <= endIdx; idx++) {
                    rangeColLetters.push(String.fromCharCode(65 + idx));
                }

                let foundMeasIndex = -1;
                const firstColLetter = rangeColLetters[0];

                for (let m = 0; m < mpp; m++) {
                    let cellValue = null;
                    const firstCol = sub.columns.find(c => c.col_letter === firstColLetter);
                    if (firstCol) {
                        if (this._isSubInputType(firstCol)) {
                            const input = document.querySelector(
                                `input[data-row="${rowIndex}"][data-sub="${firstColLetter}"][data-meas="${m}"]`
                            );
                            if (input && input.value !== '') {
                                cellValue = parseFloat(input.value);
                            }
                        } else {
                            const cell = document.querySelector(
                                `td[data-row="${rowIndex}"][data-sub="${firstColLetter}"][data-meas="${m}"]`
                            );
                            if (cell && cell.textContent !== '—') {
                                const text = cell.textContent.replace(/[^\d.\-]/g, '');
                                cellValue = parseFloat(text);
                            }
                        }
                    }

                    if (cellValue !== null && !isNaN(cellValue)) {
                        if (Math.abs(cellValue - lookupValue) < 0.0001) {
                            foundMeasIndex = m;
                            break;
                        }
                    }
                }

                if (foundMeasIndex === -1) {
                    return '—';
                }

                const targetColLetter = rangeColLetters[colIndex - 1];
                if (!targetColLetter) {
                    return '—';
                }

                const targetCol = sub.columns.find(c => c.col_letter === targetColLetter);
                if (!targetCol) {
                    return '—';
                }

                let resultValue = null;
                if (this._isSubInputType(targetCol)) {
                    const input = document.querySelector(
                        `input[data-row="${rowIndex}"][data-sub="${targetColLetter}"][data-meas="${foundMeasIndex}"]`
                    );
                    if (input && input.value !== '') {
                        resultValue = parseFloat(input.value);
                    }
                } else {
                    const cell = document.querySelector(
                        `td[data-row="${rowIndex}"][data-sub="${targetColLetter}"][data-meas="${foundMeasIndex}"]`
                    );
                    if (cell && cell.textContent !== '—') {
                        const text = cell.textContent.replace(/[^\d.\-]/g, '');
                        resultValue = parseFloat(text);
                    }
                }

                if (resultValue !== null && !isNaN(resultValue)) {
                    return Math.round(resultValue * 100) / 100;
                }
                return '—';
            }

            // FALLBACK: обычная формула
            const rowValues = {};

            cols.forEach(c => {
                if (!c.col_letter) return;
                const letter = c.col_letter.toUpperCase();

                const input = document.querySelector(`input[data-row="${rowIndex}"][data-col="${c.code}"]`);
                if (input && input.value !== '') {
                    rowValues[letter] = parseFloat(input.value);
                    return;
                }

                const cell = document.querySelector(`td[data-row="${rowIndex}"][data-col="${c.code}"]`);
                if (cell) {
                    const text = cell.textContent.replace(/[^\d.\-]/g, '');
                    const v = parseFloat(text);
                    if (!isNaN(v)) rowValues[letter] = v;
                }
            });

            if (sub && sub.columns) {
                sub.columns.forEach(sc => {
                    if (!sc.col_letter) return;
                    const letter = sc.col_letter.toUpperCase();

                    if (this._isAggregateColumn(sc)) {
                        const aggCell = document.querySelector(
                            `td[data-row="${rowIndex}"][data-sub="${letter}"][data-aggregate="1"]`
                        );
                        if (aggCell && aggCell.textContent !== '—') {
                            const text = aggCell.textContent.replace(/[^\d.\-]/g, '');
                            const v = parseFloat(text);
                            if (!isNaN(v)) rowValues[letter] = v;
                        }
                    }
                });
            }

            if (specimen && specimen.values) {
                cols.forEach(c => {
                    if (!c.col_letter) return;
                    const letter = c.col_letter.toUpperCase();
                    if (rowValues[letter] === undefined && specimen.values[c.code] != null) {
                        const v = parseFloat(specimen.values[c.code]);
                        if (!isNaN(v)) rowValues[letter] = v;
                    }
                });
            }

            const currentRow = rowIndex + 1;
            return this._computeFormula(expr, rowValues, currentRow);
        } catch (e) {
            console.error('VLOOKUP compute error:', e, formula);
            return null;
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ПЕРЕСЧЁТ ФОРМУЛ В БОКОВОЙ ТАБЛИЦЕ ───
    // ═══════════════════════════════════════════════════════════
    _recalculateSubFormulas() {
        const sub = this.activeForm?.sub_measurements_config;
        if (!sub || !sub.columns) return;

        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;
        const mpp = sub.measurements_per_specimen || 3;

        const formulaColumns = sub.columns.filter(sc =>
            ['FORMULA', 'CALCULATED', 'SUB_AVG'].includes(sc.type) && sc.formula
        );

        if (formulaColumns.length === 0) return;

        const perMeasCols = formulaColumns.filter(c => !this._isAggregateColumn(c));
        const aggCols = formulaColumns.filter(c => this._isAggregateColumn(c));

        for (let i = 0; i < specCount; i++) {
            for (let m = 0; m < mpp; m++) {
                perMeasCols.forEach(sc => {
                    const result = this._computeSubFormulaForMeasurement(sc.formula, i, m, sub);
                    const cell = document.querySelector(
                        `td[data-row="${i}"][data-sub="${sc.col_letter}"][data-meas="${m}"]`
                    );
                    if (cell) {
                        cell.textContent = this._formatCalcValue(result);
                    }
                });
            }

            aggCols.forEach(sc => {
                const result = this._computeAggregateFormula(sc.formula, i, sub, mpp);
                const cell = document.querySelector(
                    `td[data-row="${i}"][data-sub="${sc.col_letter}"][data-aggregate="1"]`
                );
                if (cell) {
                    cell.textContent = this._formatCalcValue(result);
                }
            });
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ПЕРЕСЧЁТ SUB_AVG В ОСНОВНОЙ ТАБЛИЦЕ ───
    // ═══════════════════════════════════════════════════════════
    _recalculateMainSubAverages() {
        const sub = this.activeForm?.sub_measurements_config;
        const cols = this.activeForm?.column_config || [];
        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;

        const subAvgColumns = cols.filter(c => c.type === 'SUB_AVG');
        if (subAvgColumns.length === 0) return;

        for (let i = 0; i < specCount; i++) {
            subAvgColumns.forEach(col => {
                const subCode = col.code.replace('_avg', '');
                const subColumn = sub?.columns?.find(sc => sc.code === subCode);

                if (subColumn && this._isSubInputType(subColumn)) {
                    const inputs = document.querySelectorAll(
                        `input[data-row="${i}"][data-sub="${subColumn.col_letter}"]`
                    );
                    const values = [];
                    inputs.forEach(inp => {
                        const v = parseFloat(inp.value);
                        if (!isNaN(v)) values.push(v);
                    });

                    if (values.length > 0) {
                        const avg = values.reduce((a, b) => a + b, 0) / values.length;
                        const cell = document.querySelector(`td[data-row="${i}"][data-col="${col.code}"]`);
                        if (cell) {
                            cell.textContent = avg.toFixed(2);
                        }
                    }
                }
            });
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ВЫЧИСЛЕНИЕ ФОРМУЛ {code} (CALC / NORM) ───
    // ═══════════════════════════════════════════════════════════
    _computeCodeFormula(formula, rowIndex, cols, headerData, params) {
        try {
            let expr = formula;

            const ctx = {};
            cols.forEach(c => {
                const inp = document.querySelector(`input[data-row="${rowIndex}"][data-col="${c.code}"]`);
                if (inp && inp.value !== '') {
                    const v = parseFloat(inp.value);
                    if (!isNaN(v)) ctx[c.code] = v;
                } else {
                    const td = document.querySelector(`td[data-row="${rowIndex}"][data-col="${c.code}"]`);
                    if (td && td.textContent && td.textContent !== '—' && td.textContent !== '') {
                        const text = td.textContent.replace(/[^\d.\-]/g, '');
                        const v = parseFloat(text);
                        if (!isNaN(v)) ctx[c.code] = v;
                    }
                }
            });

            if (params && Array.isArray(params)) {
                params.forEach(p => {
                    if (headerData[p] !== undefined && headerData[p] !== '') {
                        const v = parseFloat(headerData[p]);
                        if (!isNaN(v)) ctx[p] = v;
                    }
                });
            }

            expr = expr.replace(/\{(\w+)\}/g, (_, code) => {
                return ctx[code] !== undefined ? ctx[code].toString() : 'null';
            });

            if (expr.includes('null')) return '';

            expr = expr.replace(/ROUND\s*\(([^,]+),\s*(\d+)\)/gi, (_, e, d) => {
                const factor = Math.pow(10, parseInt(d));
                return `(Math.round((${e})*${factor})/${factor})`;
            });

            for (let i = 0; i < 5; i++) {
                const prev = expr;
                expr = expr.replace(/IF\s*\(([^,]+),([^,]+),([^)]+)\)/i, '(($1)?($2):($3))');
                if (prev === expr) break;
            }

            const iferrorMatch = expr.match(/IFERROR\s*\((.+),([^)]+)\)/i);
            if (iferrorMatch) {
                try {
                    const testExpr = iferrorMatch[1].replace(/\s/g, '');
                    if (/^[\d+\-*/().?:<>=Math.round,]+$/.test(testExpr)) {
                        const testResult = Function('"use strict";return (' + testExpr + ')')();
                        if (typeof testResult === 'number' && !isNaN(testResult) && isFinite(testResult)) {
                            return Math.round(testResult * 100) / 100;
                        }
                    }
                } catch (_) {}
                const fb = iferrorMatch[2].trim().replace(/"/g, '');
                return fb === '-' ? '' : fb;
            }

            expr = expr.replace(/\s/g, '');
            if (/^[\d+\-*/().?:<>=Math.round,]+$/.test(expr)) {
                const result = Function('"use strict";return (' + expr + ')')();
                if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
                    return Math.round(result * 100) / 100;
                }
            }

            return '';
        } catch (e) {
            console.error('CodeFormula error:', e, formula);
            return '';
        }
    },

    _computeFormula(formula, rowValues, currentRow) {
        try {
            let expr = formula.startsWith('=') ? formula.substring(1) : formula;

            const rangeFuncs = ['SUM', 'AVERAGE', 'MIN', 'MAX'];

            rangeFuncs.forEach(fn => {
                const re = new RegExp(`${fn}\\(([A-Z]+)\\d+:([A-Z]+)\\d+\\)`, 'gi');
                expr = expr.replace(re, (_, startCol, endCol) => {
                    const values = [];
                    const startIdx = startCol.toUpperCase().charCodeAt(0) - 65;
                    const endIdx = endCol.toUpperCase().charCodeAt(0) - 65;

                    for (let idx = startIdx; idx <= endIdx; idx++) {
                        const colLetter = String.fromCharCode(65 + idx);
                        const val = rowValues[colLetter];
                        if (val !== null && val !== undefined && !isNaN(parseFloat(val))) {
                            values.push(parseFloat(val));
                        }
                    }

                    if (values.length === 0) return '0';

                    switch (fn) {
                        case 'SUM': return values.reduce((a, b) => a + b, 0).toString();
                        case 'AVERAGE': return (values.reduce((a, b) => a + b, 0) / values.length).toString();
                        case 'MIN': return Math.min(...values).toString();
                        case 'MAX': return Math.max(...values).toString();
                        default: return '0';
                    }
                });
            });

            expr = expr.replace(/([A-Z]+)\d+/gi, (match, colLetter) => {
                const val = rowValues[colLetter.toUpperCase()];
                return (val !== null && val !== undefined && !isNaN(parseFloat(val)))
                    ? val
                    : '0';
            });

            const ifErrorMatch = expr.match(/IFERROR\(([^,]+),([^)]+)\)/i);
            if (ifErrorMatch) {
                try {
                    const testResult = this._computeFormula(ifErrorMatch[1], rowValues, currentRow);
                    if (testResult === null || testResult === '' || isNaN(parseFloat(testResult))) {
                        expr = ifErrorMatch[2];
                    } else {
                        expr = ifErrorMatch[1];
                    }
                } catch (e) {
                    expr = ifErrorMatch[2];
                }
            }

            if (/^[\d\s+\-*/().]+$/.test(expr)) {
                const result = Function('"use strict";return (' + expr + ')')();
                if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
                    return Math.round(result * 10000) / 10000;
                }
                return result;
            }

            return null;
        } catch (e) {
            console.error('Compute formula error:', e, formula);
            return null;
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ДОПОЛНИТЕЛЬНЫЕ ТАБЛИЦЫ (РЕФАКТОРИНГ statistics[]) ───
    // ═══════════════════════════════════════════════════════════
    _renderAdditionalTable(atConfig, existing, specCount) {
        const atData = existing?.additional_tables_data?.[atConfig.id] || {};
        const specimens = atData.specimens || [];
        const cols = atConfig.columns || [];
        // Собираем уникальные типы статистики из столбцов доп. таблицы
        const allStatTypes = new Set();
        cols.forEach(c => {
            this._getColumnStatistics(c).forEach(st => allStatTypes.add(st));
        });
        // Также учитываем statistics на уровне таблицы (legacy)
        const tableStats = atConfig.statistics || [];
        tableStats.forEach(st => allStatTypes.add(st));

        const orderedTypes = ['MEAN', 'STDEV', 'CV', 'CONFIDENCE'];
        const activeTypes = orderedTypes.filter(t => allStatTypes.has(t));

        let html = '<div class="tr-section">';
        html += `<div class="tr-section-title">${this._esc(atConfig.title)}</div>`;
        html += '<div class="tr-table-wrap"><table class="tr-table">';

        // Header
        html += '<thead><tr>';
        cols.forEach(c => {
            const title = c.unit ? `${c.name}, ${c.unit}` : c.name;
            const cls = (c.type === 'CALC') ? ' tr-th-calc' : '';
            html += `<th class="${cls}">${this._esc(title)}</th>`;
        });
        html += '</tr></thead>';

        // Body
        html += '<tbody>';
        for (let i = 0; i < specCount; i++) {
            const spec = specimens[i] || {};
            const vals = spec.values || {};
            html += '<tr>';
            cols.forEach(c => {
                const val = vals[c.code] ?? '';
                if (c.code.startsWith('specimen_number')) {
                    html += `<td class="tr-td-num">${i + 1}</td>`;
                } else if (c.type === 'TEXT') {
                    html += `<td><input type="text" data-row="${i}" data-at="${atConfig.id}" data-col="${c.code}" value="${this._esc(val)}" class="tr-inp tr-inp-txt"></td>`;
                } else if (c.type === 'CALC') {
                    html += `<td class="tr-td-calc" data-row="${i}" data-at="${atConfig.id}" data-col="${c.code}">${val !== '' && val !== null ? val : ''}</td>`;
                } else {
                    html += `<td><input type="number" step="any" data-row="${i}" data-at="${atConfig.id}" data-col="${c.code}" value="${val}" class="tr-inp tr-inp-num" oninput="TestReport._onValueChange(${i},'${c.code}',this.value)"></td>`;
                }
            });
            html += '</tr>';
        }
        html += '</tbody>';

        // Statistics
        if (activeTypes.length > 0) {
            const labels = {
                'MEAN': 'Среднее арифметическое',
                'STDEV': 'Стандартное отклонение',
                'CV': 'Коэффициент вариации, %',
                'CONFIDENCE': 'Доверительный интервал'
            };
            html += '<tfoot>';
            activeTypes.forEach((st, si) => {
                const rowCls = si === 0 ? ' tr-stat-first' : '';
                html += `<tr class="tr-stat-row${rowCls}">`;
                let labelPlaced = false;
                cols.forEach(c => {
                    if (!labelPlaced && (c.code.startsWith('specimen_number') || c.type === 'TEXT')) {
                        html += `<td class="tr-stat-label">${labels[st] || st}</td>`;
                        labelPlaced = true;
                    } else if (!labelPlaced) {
                        html += `<td class="tr-stat-label">${labels[st] || st}</td>`;
                        labelPlaced = true;
                    } else if (this._columnHasStat(c, st) || tableStats.includes(st)) {
                        // Столбец имеет эту метрику ИЛИ таблица глобально запрашивает
                        html += `<td class="tr-stat-val" data-at-stat="${st}" data-at="${atConfig.id}" data-col="${c.code}"></td>`;
                    } else {
                        html += '<td class="tr-stat-empty"></td>';
                    }
                });
                html += '</tr>';
            });
            html += '</tfoot>';
        }

        html += '</table></div></div>';
        return html;
    },

    _recalculateAdditionalTables() {
        const additionalTables = this.activeForm?.additional_tables;
        if (!additionalTables || additionalTables.length === 0) return;

        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;
        const headerData = this._collectHeaderData();
        const mainCols = this.activeForm.column_config || [];

        additionalTables.forEach(at => {
            const cols = at.columns || [];
            const formulaCols = cols.filter(c => c.type === 'CALC' && c.formula);

            // Recalculate formulas
            for (let i = 0; i < specCount; i++) {
                const ctx = {};

                cols.forEach(c => {
                    const inp = document.querySelector(`input[data-row="${i}"][data-at="${at.id}"][data-col="${c.code}"]`);
                    if (inp && inp.value !== '') {
                        const v = parseFloat(inp.value);
                        if (!isNaN(v)) ctx[c.code] = v;
                    }
                });

                mainCols.forEach(c => {
                    const inp = document.querySelector(`input[data-row="${i}"][data-col="${c.code}"]`);
                    if (inp && inp.value !== '') {
                        const v = parseFloat(inp.value);
                        if (!isNaN(v)) ctx[c.code] = v;
                    } else {
                        const td = document.querySelector(`td[data-row="${i}"][data-col="${c.code}"]`);
                        if (td && td.textContent && td.textContent !== '—') {
                            const v = parseFloat(td.textContent.replace(/[^\d.\-]/g, ''));
                            if (!isNaN(v)) ctx[c.code] = v;
                        }
                    }
                });

                Object.entries(headerData).forEach(([k, v]) => {
                    if (v !== '' && ctx[k] === undefined) {
                        const n = parseFloat(v);
                        if (!isNaN(n)) ctx[k] = n;
                    }
                });

                formulaCols.forEach(col => {
                    let expr = col.formula;
                    expr = expr.replace(/\{(\w+)\}/g, (_, code) => {
                        return ctx[code] !== undefined ? ctx[code].toString() : 'null';
                    });

                    let result = '';
                    if (!expr.includes('null')) {
                        try {
                            expr = expr.replace(/\s/g, '');
                            const evalResult = Function('"use strict";return (' + expr + ')')();
                            if (typeof evalResult === 'boolean') {
                                result = evalResult ? 'ДА' : 'НЕТ';
                            } else if (typeof evalResult === 'number' && !isNaN(evalResult) && isFinite(evalResult)) {
                                result = (Math.round(evalResult * 100) / 100).toString();
                            }
                        } catch(_) {}
                    }

                    const cell = document.querySelector(`td[data-row="${i}"][data-at="${at.id}"][data-col="${col.code}"]`);
                    if (cell) cell.textContent = result || '—';

                    if (result && result !== '—' && result !== 'ДА' && result !== 'НЕТ') {
                        ctx[col.code] = parseFloat(result);
                    }
                });
            }

            // Recalculate statistics — теперь на основе statistics[] каждого столбца
            // Собираем все уникальные типы
            const allStatTypes = new Set();
            cols.forEach(c => {
                this._getColumnStatistics(c).forEach(st => allStatTypes.add(st));
            });
            // Legacy: statistics на уровне таблицы
            const tableStats = at.statistics || [];
            tableStats.forEach(st => allStatTypes.add(st));

            if (allStatTypes.size === 0) return;

            // Для каждого столбца с статистикой — считаем
            cols.forEach(col => {
                const colStats = this._getColumnStatistics(col);
                // Также проверяем legacy tableStats
                const effectiveStats = new Set([...colStats, ...tableStats.filter(() => this._columnHasAnyStats(col) || colStats.length > 0)]);

                // Если у столбца нет статистики и tableStats пустой — пропускаем
                if (colStats.length === 0 && tableStats.length === 0) return;

                // Собираем значения
                const values = [];
                for (let i = 0; i < specCount; i++) {
                    const inp = document.querySelector(`input[data-row="${i}"][data-at="${at.id}"][data-col="${col.code}"]`);
                    if (inp && inp.value !== '') {
                        const v = parseFloat(inp.value);
                        if (!isNaN(v)) { values.push(v); continue; }
                    }
                    const td = document.querySelector(`td[data-row="${i}"][data-at="${at.id}"][data-col="${col.code}"]`);
                    if (td && td.textContent && td.textContent !== '—') {
                        const v = parseFloat(td.textContent.replace(/[^\d.\-]/g, ''));
                        if (!isNaN(v)) values.push(v);
                    }
                }

                const n = values.length;
                if (n === 0) return;

                // Определяем какие типы считать для этого столбца
                const typesToCalc = colStats.length > 0 ? colStats : tableStats;

                typesToCalc.forEach(st => {
                    const cell = document.querySelector(`td[data-at-stat="${st}"][data-at="${at.id}"][data-col="${col.code}"]`);
                    if (!cell) return;

                    if (st === 'MEAN' && n >= 1) {
                        cell.textContent = (values.reduce((a, b) => a + b, 0) / n).toFixed(2);
                    } else if (st === 'STDEV' && n >= 2) {
                        const m = values.reduce((a, b) => a + b, 0) / n;
                        const s = Math.sqrt(values.reduce((acc, v) => acc + (v - m) ** 2, 0) / (n - 1));
                        cell.textContent = s.toFixed(2);
                    } else if (st === 'CV' && n >= 2) {
                        const m = values.reduce((a, b) => a + b, 0) / n;
                        const s = Math.sqrt(values.reduce((acc, v) => acc + (v - m) ** 2, 0) / (n - 1));
                        cell.textContent = m !== 0 ? (s / m * 100).toFixed(2) : '0.00';
                    } else if (st === 'CONFIDENCE' && n >= 2) {
                        const m = values.reduce((a, b) => a + b, 0) / n;
                        const s = Math.sqrt(values.reduce((acc, v) => acc + (v - m) ** 2, 0) / (n - 1));
                        const tTable = {2:12.706,3:4.303,4:3.182,5:2.776,6:2.571,7:2.447,8:2.365,9:2.306,10:2.262};
                        const tVal = tTable[n] || 2.0;
                        const margin = tVal * s / Math.sqrt(n);
                        cell.textContent = `${(m - margin).toFixed(2)} – ${(m + margin).toFixed(2)}`;
                    }
                });
            });
        });
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ВСТАВКА ИЗ EXCEL ───
    // ═══════════════════════════════════════════════════════════
    _initPasteHandler() {
        const container = document.getElementById('tr-form-area') || document.getElementById('test-report-container');
        if (!container) return;

        container.addEventListener('paste', (e) => {
            const target = e.target;
            if (!target.matches || !target.matches('.tr-inp')) return;

            const clipText = (e.clipboardData || window.clipboardData).getData('text');
            if (!clipText) return;

            const lines = clipText.trim().split(/\r?\n/);
            const delimiter = this._detectDelimiter(lines[0]);
            const rows = lines.map(r => r.split(delimiter).map(v => v.trim()));

            if (rows.length === 1 && rows[0].length === 1) return;

            e.preventDefault();

            const startRow = parseInt(target.dataset.row);
            const startCol = target.dataset.col;
            const isSub = !!target.dataset.sub;

            if (isSub) {
                this._pasteIntoSub(target, rows);
            } else {
                this._pasteIntoMain(startRow, startCol, rows);
            }

            this._localRecalculate();
        });
    },

    _pasteIntoMain(startRow, startCol, rows) {
        const cols = (this.activeForm.column_config || []).filter(c => c.code !== 'br');
        const startColIdx = cols.findIndex(c => c.code === startCol);
        if (startColIdx === -1) return;

        rows.forEach((rowData, ri) => {
            const targetRow = startRow + ri;
            rowData.forEach((cellVal, ci) => {
                const colIdx = startColIdx + ci;
                if (colIdx >= cols.length) return;

                const col = cols[colIdx];
                if (['CALCULATED', 'SUB_AVG', 'VLOOKUP', 'CALC', 'NORM'].includes(col.type)) return;
                if (col.code === 'specimen_number') return;

                const input = document.querySelector(`input[data-row="${targetRow}"][data-col="${col.code}"]`);
                if (input) {
                    input.value = cellVal.trim().replace(/,/g, '.');
                    input.style.background = '#e8f5e9';
                    setTimeout(() => { input.style.background = ''; }, 1500);
                }
            });
        });
    },

    _pasteIntoSub(target, rows) {
        const startRow = parseInt(target.dataset.row);
        const startSub = target.dataset.sub;
        const startMeas = parseInt(target.dataset.meas);

        const sub = this.activeForm.sub_measurements_config;
        if (!sub) return;

        const mpp = sub.measurements_per_specimen || 3;

        const allSubInputs = [];
        sub.columns.forEach(sc => {
            if (this._isSubInputType(sc)) {
                for (let m = 0; m < mpp; m++) {
                    allSubInputs.push({ colLetter: sc.col_letter, meas: m });
                }
            }
        });

        const startIdx = allSubInputs.findIndex(
            si => si.colLetter === startSub && si.meas === startMeas
        );
        if (startIdx === -1) return;

        rows.forEach((rowData, ri) => {
            const targetRow = startRow + ri;
            rowData.forEach((cellVal, ci) => {
                const idx = startIdx + ci;
                if (idx >= allSubInputs.length) return;

                const si = allSubInputs[idx];
                const input = document.querySelector(
                    `input[data-row="${targetRow}"][data-sub="${si.colLetter}"][data-meas="${si.meas}"]`
                );
                if (input) {
                    input.value = cellVal.trim().replace(/,/g, '.');
                    input.style.background = '#e8f5e9';
                    setTimeout(() => { input.style.background = ''; }, 1500);
                }
            });
        });
    },

    // ─── Обработчики ───
    _onValueChange(row, code, value) {
        clearTimeout(this._calcTimer);
        this._calcTimer = setTimeout(() => this._localRecalculate(), 300);
    },

    _onSubChange(row, subKey, measIndex, value) {
        clearTimeout(this._calcTimer);
        this._calcTimer = setTimeout(() => this._localRecalculate(), 300);
    },

    _updateSpecimenCount(count) {
        if (this.activeForm.existing_report) {
            const current = this._collectData();
            this.activeForm.existing_report.table_data = current.table_data;
            this.activeForm.existing_report.header_data = current.header_data;
        }
        this.activeForm.prefilled_header = this._collectHeaderData();
        this.activeForm.prefilled_header.specimen_count = count;
        this._renderForm(this.activeForm);
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ЛОКАЛЬНЫЙ ПЕРЕСЧЁТ ───
    // ═══════════════════════════════════════════════════════════
    _localRecalculate() {
        if (!this.activeForm) return;

        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;
        const cols = this.activeForm.column_config || [];
        const sub = this.activeForm.sub_measurements_config;
        const statsConfig = this.activeForm.statistics_config || [];

        // 1) Боковая таблица — СНАЧАЛА
        this._recalculateSubFormulas();

        // 2) SUB_AVG в основной
        this._recalculateMainSubAverages();

        // 3) CALCULATED / CALC / NORM формулы
        const formulaCols = cols.filter(c =>
            (['VLOOKUP', 'CALCULATED', 'CALC', 'NORM'].includes(c.type)) && c.formula
        );

        if (formulaCols.length > 0) {
            const typePriority = {'VLOOKUP': 0, 'CALCULATED': 1, 'CALC': 2, 'NORM': 3};
            const sortedFormulaCols = formulaCols.sort((a, b) => {
                return (typePriority[a.type] || 9) - (typePriority[b.type] || 9);
            });

            const headerData = this._collectHeaderData();

            for (let i = 0; i < specCount; i++) {
                sortedFormulaCols.forEach(col => {
                    const rowValues = this._collectRowValues(i, cols, sub);

                    let result = null;

                    if (col.formula.toUpperCase().includes('VLOOKUP')) {
                        result = this._computeVlookup(col.formula, i, null, []);
                    } else if (col.type === 'CALC' || col.type === 'NORM') {
                        result = this._computeCodeFormula(col.formula, i, cols, headerData, col.params);
                    } else {
                        const expr = col.formula.startsWith('=') ? col.formula.substring(1) : col.formula;
                        const currentRow = i + 1;
                        result = this._computeFormula(expr, rowValues, currentRow);
                    }

                    const cell = document.querySelector(`td[data-row="${i}"][data-col="${col.code}"]`);
                    if (cell) {
                        cell.textContent = this._formatCalcValue(result);
                    }
                });
            }
        }

        // 4) Статистика
        this._recalculateStatistics(specCount, cols, statsConfig);

        // 5) Дополнительные таблицы
        this._recalculateAdditionalTables();
    },

    // ═══════════════════════════════════════════════════════════
    // ─── СБОР ЗНАЧЕНИЙ СТРОКИ ПО COL_LETTER ───
    // ═══════════════════════════════════════════════════════════
    _collectRowValues(rowIndex, cols, sub) {
        const rowValues = {};

        cols.forEach(c => {
            if (!c.col_letter) return;
            const letter = c.col_letter.toUpperCase();

            const input = document.querySelector(`input[data-row="${rowIndex}"][data-col="${c.code}"]`);
            if (input && input.value !== '') {
                const v = parseFloat(input.value);
                if (!isNaN(v)) {
                    rowValues[letter] = v;
                    return;
                }
            }

            const cell = document.querySelector(`td[data-row="${rowIndex}"][data-col="${c.code}"]`);
            if (cell && cell.textContent && cell.textContent !== '—') {
                const text = cell.textContent.replace(/[^\d.\-]/g, '');
                const v = parseFloat(text);
                if (!isNaN(v)) {
                    rowValues[letter] = v;
                }
            }
        });

        if (sub && sub.columns) {
            sub.columns.forEach(sc => {
                if (!sc.col_letter) return;
                const letter = sc.col_letter.toUpperCase();

                if (this._isAggregateColumn(sc)) {
                    const aggCell = document.querySelector(
                        `td[data-row="${rowIndex}"][data-sub="${letter}"][data-aggregate="1"]`
                    );
                    if (aggCell && aggCell.textContent !== '—') {
                        const text = aggCell.textContent.replace(/[^\d.\-]/g, '');
                        const v = parseFloat(text);
                        if (!isNaN(v)) rowValues[letter] = v;
                    }
                }
            });
        }

        return rowValues;
    },

    // ═══════════════════════════════════════════════════════════
    // ─── ПЕРЕСЧЁТ СТАТИСТИКИ (РЕФАКТОРИНГ: statistics[]) ───
    // ═══════════════════════════════════════════════════════════
    _recalculateStatistics(specCount, cols, statsConfig) {
        // Собираем столбцы, у которых есть хоть какая-то статистика
        const colsWithStats = cols.filter(c => this._columnHasAnyStats(c));
        if (colsWithStats.length === 0) return;

        colsWithStats.forEach(col => {
            const colStatTypes = this._getColumnStatistics(col);

            // Собираем значения столбца
            const values = [];
            for (let i = 0; i < specCount; i++) {
                const inp = document.querySelector(`input[data-row="${i}"][data-col="${col.code}"]`);
                if (inp && inp.value !== '') {
                    const v = parseFloat(inp.value);
                    if (!isNaN(v)) { values.push(v); continue; }
                }
                const td = document.querySelector(`td[data-row="${i}"][data-col="${col.code}"]`);
                if (td) {
                    const text = td.textContent.replace(/[^\d.\-]/g, '');
                    const v = parseFloat(text);
                    if (!isNaN(v)) values.push(v);
                }
            }

            const n = values.length;

            // Предрассчитываем общие метрики
            let mean = null, stdev = null, cv = null, ciLo = null, ciHi = null;

            if (n >= 1) {
                mean = values.reduce((a, b) => a + b, 0) / n;

                if (n >= 2) {
                    stdev = Math.sqrt(values.reduce((acc, v) => acc + (v - mean) ** 2, 0) / (n - 1));
                    cv = mean !== 0 ? (stdev / mean * 100) : 0;

                    const tTable = {2:12.706, 3:4.303, 4:3.182, 5:2.776, 6:2.571,
                                    7:2.447, 8:2.365, 9:2.306, 10:2.262, 15:2.145, 20:2.093};
                    const tVal = tTable[n] || 2.0;
                    const margin = tVal * stdev / Math.sqrt(n);
                    ciLo = mean - margin;
                    ciHi = mean + margin;
                }
            }

            // Обновляем только те ячейки, которые столбец запросил
            colStatTypes.forEach(statType => {
                const cell = document.querySelector(`td[data-stat="${statType}"][data-col="${col.code}"]`);
                if (!cell) return;

                switch (statType) {
                    case 'MEAN':
                        cell.textContent = mean !== null ? mean.toFixed(2) : '';
                        break;
                    case 'STDEV':
                        cell.textContent = stdev !== null ? stdev.toFixed(2) : '';
                        break;
                    case 'CV':
                        cell.textContent = cv !== null ? cv.toFixed(2) : '';
                        break;
                    case 'CONFIDENCE':
                        cell.textContent = (ciLo !== null && ciHi !== null)
                            ? `${ciLo.toFixed(2)} – ${ciHi.toFixed(2)}`
                            : '';
                        break;
                    default:
                        break;
                }
            });
        });
    },

    _getColumnCodeByLetter(letter, cols) {
        const found = cols.find(c => c.col_letter === letter);
        if (found) return found.code;
        const byCode = cols.find(c => c.code === letter);
        if (byCode) return byCode.code;
        const index = letter.charCodeAt(0) - 65;
        if (index >= 0 && index < cols.length) return cols[index].code;
        return null;
    },

    // ─── Пересчёт на сервере ───
    async _recalculate() {
        const data = this._collectData();
        try {
            const resp = await fetch('/api/test-report/calculate/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': this._csrf()},
                body: JSON.stringify({table_data: data.table_data, template_id: this.activeForm.template_id}),
            });
            const result = await resp.json();
            if (result.success) {
                this.activeForm.existing_report = {
                    ...(this.activeForm.existing_report || {}),
                    table_data: result.table_data,
                    statistics_data: result.statistics_data,
                    header_data: data.header_data,
                };
                this._renderForm(this.activeForm);
            }
        } catch (e) { console.error('Recalculate error:', e); }
    },

    // ─── Сохранение ───
    async _save(status) {
        const data = this._collectData();
        try {
            const resp = await fetch('/api/test-report/save/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': this._csrf()},
                body: JSON.stringify({
                    sample_id: this.sampleId,
                    standard_id: this.activeForm.standard.id,
                    template_id: this.activeForm.template_id,
                    header_data: data.header_data,
                    table_data: data.table_data,
                    additional_tables_data: data.additional_tables_data,
                    status: status,
                }),
            });
            const result = await resp.json();
            if (result.success) {
                this.activeForm.existing_report = {
                    id: result.report_id, status,
                    table_data: data.table_data,
                    statistics_data: result.statistics_data,
                    header_data: data.header_data,
                    additional_tables_data: data.additional_tables_data,
                };
                this._renderForm(this.activeForm);
                const msg = result.created ? 'Отчёт создан' : 'Отчёт обновлён';
                alert(`${msg} (${status === 'COMPLETED' ? 'завершён' : 'черновик'})`);
            } else {
                alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            }
        } catch (e) {
            console.error('Save error:', e);
            alert('Ошибка сохранения');
        }
    },

    _downloadXlsx() {
        const existing = this.activeForm.existing_report;
        if (existing && existing.id) {
            window.location.href = `/api/test-report/${existing.id}/export-xlsx/`;
        } else {
            const stdId = this.activeForm.standard.id;
            window.location.href = `/api/test-report/export-xlsx/${this.sampleId}/${stdId}/`;
        }
    },

    // ═══════════════════════════════════════════════════════════
    // ─── СБОР ДАННЫХ ───
    // ═══════════════════════════════════════════════════════════
    _collectData() {
        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;
        const cols = this.activeForm.column_config;
        const sub = this.activeForm.sub_measurements_config;
        const specimens = [];
        const mpp = sub?.measurements_per_specimen || 3;

        for (let i = 0; i < specCount; i++) {
            const spec = {number: i + 1, values: {}, sub_measurements: {}};

            cols.forEach(c => {
                if (c.code === 'specimen_number') return;
                const input = document.querySelector(`input[data-row="${i}"][data-col="${c.code}"]`);
                if (input) {
                    spec.values[c.code] = c.type === 'TEXT' ? input.value : (parseFloat(input.value) || null);
                    return;
                }
                const cell = document.querySelector(`td[data-row="${i}"][data-col="${c.code}"]`);
                if (cell) {
                    const text = cell.textContent.replace(/[^\d.\-]/g, '');
                    const v = parseFloat(text);
                    if (!isNaN(v)) {
                        spec.values[c.code] = v;
                    }
                }
            });

            const markInput = document.querySelector(`input[data-row="${i}"][data-col="marking"]`);
            if (markInput) spec.marking = markInput.value;

            if (sub && sub.columns) {
                sub.columns.forEach(sc => {
                    const subKey = sc.col_letter;
                    const measurements = [];

                    if (this._isAggregateColumn(sc)) {
                        const cell = document.querySelector(
                            `td[data-row="${i}"][data-sub="${subKey}"][data-aggregate="1"]`
                        );
                        if (cell && cell.textContent !== '—') {
                            const text = cell.textContent.replace(/[^\d.\-]/g, '');
                            const v = parseFloat(text);
                            measurements.push(isNaN(v) ? null : v);
                            spec.values[sc.code] = isNaN(v) ? null : v;
                        } else {
                            measurements.push(null);
                        }
                    } else if (sc.type === 'TEXT') {
                        const input = document.querySelector(
                            `input[data-row="${i}"][data-sub="${subKey}"][data-meas="0"]`
                        );
                        measurements.push(input ? (input.value || null) : null);
                    } else if (this._isSubInputType(sc)) {
                        for (let m = 0; m < mpp; m++) {
                            const input = document.querySelector(
                                `input[data-row="${i}"][data-sub="${subKey}"][data-meas="${m}"]`
                            );
                            if (input) {
                                const v = parseFloat(input.value);
                                measurements.push(isNaN(v) ? null : v);
                            } else {
                                measurements.push(null);
                            }
                        }
                    } else {
                        for (let m = 0; m < mpp; m++) {
                            const cell = document.querySelector(
                                `td[data-row="${i}"][data-sub="${subKey}"][data-meas="${m}"]`
                            );
                            if (cell && cell.textContent !== '—') {
                                const text = cell.textContent.replace(/[^\d.\-]/g, '');
                                const v = parseFloat(text);
                                if (!isNaN(v)) {
                                    spec.values[`${sc.code}_${m}`] = v;
                                }
                                measurements.push(isNaN(v) ? null : v);
                            } else {
                                measurements.push(null);
                            }
                        }
                    }

                    spec.sub_measurements[sc.code] = measurements;
                });
            }

            specimens.push(spec);
        }

        const additional_tables_data = {};
        const additionalTables = this.activeForm.additional_tables || [];
        additionalTables.forEach(at => {
            const atSpecimens = [];
            const atCols = at.columns || [];
            for (let i = 0; i < specCount; i++) {
                const spec = {values: {}};
                atCols.forEach(c => {
                    const inp = document.querySelector(`input[data-row="${i}"][data-at="${at.id}"][data-col="${c.code}"]`);
                    if (inp) {
                        spec.values[c.code] = c.type === 'TEXT' ? inp.value : (parseFloat(inp.value) || null);
                        return;
                    }
                    const cell = document.querySelector(`td[data-row="${i}"][data-at="${at.id}"][data-col="${c.code}"]`);
                    if (cell && cell.textContent && cell.textContent !== '—') {
                        const text = cell.textContent.replace(/[^\d.\-]/g, '');
                        const v = parseFloat(text);
                        if (!isNaN(v)) spec.values[c.code] = v;
                    }
                });
                atSpecimens.push(spec);
            }
            additional_tables_data[at.id] = {specimens: atSpecimens};
        });

        return {
            header_data: this._collectHeaderData(),
            table_data: {specimens},
            additional_tables_data
        };
    },

    _collectHeaderData() {
        const hd = {};
        document.querySelectorAll('[data-header]').forEach(el => { hd[el.dataset.header] = el.value; });
        return hd;
    },

    // ─── Утилиты ───
    _esc(s) { return s == null ? '' : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },
    _fmt(v) { if (v == null || v === '') return ''; const n = parseFloat(v); return isNaN(n) ? '' : n.toFixed(2); },
    _csrf() { const m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : (document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''); },

    _detectDelimiter(line) {
        if (line.includes('\t')) return /\t/;
        if (line.includes(';')) return /;/;
        if (/\s{2,}/.test(line)) return /\s{2,}/;
        return /\t/;
    },
};

document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('test-report-container');
    if (container && container.dataset.sampleId) {
        TestReport.init(container.dataset.sampleId);
    }
});
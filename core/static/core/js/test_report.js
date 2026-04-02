/* ═══════════════════════════════════════════════════════════════
   test_report.js — v3.49.0
   Форма ввода данных отчёта об испытании
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

    // ─── Рендер формы ───
    _renderForm(formConfig) {
        this.activeForm = formConfig;
        const area = document.getElementById('tr-form-area') || document.getElementById('test-report-container');

        if (!formConfig.has_template) {
            area.innerHTML = `<div class="tr-msg">${formConfig.message}</div>`;
            return;
        }

        const existing = formConfig.existing_report;
        const specimens = existing ? existing.table_data.specimens : [];
        const headerData = existing ? existing.header_data : (formConfig.prefilled_header || {});
        const cols = formConfig.column_config.filter(c => c.code !== 'br');
        const specCount = specimens.length || parseInt(headerData.specimen_count) || 6;

        let html = '';

        // ─── Шапка ───
        html += this._renderHeader(headerData);

        // ─── Кол-во образцов ───
        html += `<div class="tr-controls">
            <label>Количество образцов:</label>
            <input type="number" id="tr-spec-count" value="${specCount}" min="1" max="30"
                   onchange="TestReport._updateSpecimenCount(this.value)">
            <span class="tr-std-badge">${formConfig.standard.code}</span>
        </div>`;

        // ─── Промежуточные замеры ───
        if (formConfig.sub_measurements_config) {
            html += this._renderSubMeasurements(formConfig, specimens, specCount);
        }

        // ─── Основная таблица ───
        html += '<div class="tr-table-wrap"><table class="tr-table">';
        html += this._renderTableHead(cols);
        html += this._renderTableBody(cols, specimens, specCount);
        html += this._renderStatistics(formConfig, cols, existing);
        html += '</table></div>';

        // ─── Кнопки ───
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
        const fields = [
            {key: 'identification_number', label: 'Идентификационный номер', ro: true},
            {key: 'conditions', label: 'Условия испытаний'},
            {key: 'force_sensor', label: 'Датчик силы'},
            {key: 'traverse_speed', label: 'Скорость траверсы'},
            {key: 'specimen_count', label: 'Кол-во образцов', type: 'number'},
            {key: 'notes', label: 'Примечания'},
            {key: 'room', label: 'Помещение'},
        ];

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

    // ─── Заголовки таблицы ───
    _renderTableHead(cols) {
        let html = '<thead><tr>';
        cols.forEach(c => {
            const title = c.unit ? `${c.name}, ${c.unit}` : c.name;
            const cls = (c.type === 'CALCULATED' || c.type === 'SUB_AVG' || c.type === 'VLOOKUP') ? ' tr-th-calc' : '';
            html += `<th class="${cls}">${this._esc(title)}</th>`;
        });
        html += '</tr></thead>';
        return html;
    },

    // ─── Строки данных ───
    _renderTableBody(cols, specimens, specCount) {
        let html = '<tbody>';
        for (let i = 0; i < specCount; i++) {
            const spec = specimens[i] || {};
            const vals = spec.values || {};
            
            html += `<tr>`;
            
            cols.forEach(c => {
                const val = c.code === 'specimen_number' ? (i + 1) : (vals[c.code] ?? '');

                if (c.code === 'specimen_number') {
                    html += `<td class="tr-td-num">${i + 1}</td>`;
                } else if (c.type === 'TEXT') {
                    html += `<td><input type="text" data-row="${i}" data-col="${c.code}"
                            value="${this._esc(val)}" class="tr-inp tr-inp-txt"></td>`;
                } else if (c.type === 'CALCULATED' || c.type === 'SUB_AVG') {
                    html += `<td class="tr-td-calc" data-row="${i}" data-col="${c.code}">${val !== '' && val !== null ? val : ''}${c.unit ? ` ${c.unit}` : ''}</td>`;
                } else if (c.type === 'VLOOKUP') {
                    const title = c.formula ? `Формула: ${c.formula}` : '';
                    html += `<td class="tr-td-calc tr-td-vlookup" data-row="${i}" data-col="${c.code}" title="${this._esc(title)}">${val !== '' && val !== null ? val : '—'}${c.unit ? ` ${c.unit}` : ''}</td>`;
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

    // ─── Статистика ───
    _renderStatistics(formConfig, cols, existing) {
        const statsConfig = formConfig.statistics_config;
        if (!statsConfig || statsConfig.length === 0) return '';

        const statsData = existing ? existing.statistics_data : {};

        const labels = {
            'MEAN': 'Среднее арифметическое',
            'STDEV': 'Стандартное отклонение',
            'CV': 'Коэффициент вариации, %',
            'CONFIDENCE': 'Доверительный интервал',
        };

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
        statsConfig.forEach((s, si) => {
            const rowCls = si === 0 ? ' tr-stat-first' : '';
            html += `<tr class="tr-stat-row tr-stat-${s.type.toLowerCase()}${rowCls}">`;
            html += `<td colspan="${labelSpan}" class="tr-stat-label">${labels[s.type] || s.type}</td>`;

            dataCols.forEach(c => {
                if (c.type === 'TEXT') {
                    html += '<td class="tr-stat-empty"></td>';
                    return;
                }

                const colStats = statsData[c.code];
                let val = '';

                if (colStats) {
                    if (s.type === 'MEAN') val = this._fmt(colStats.mean);
                    else if (s.type === 'STDEV') val = this._fmt(colStats.stdev);
                    else if (s.type === 'CV') val = this._fmt(colStats.cv);
                    else if (s.type === 'CONFIDENCE') {
                        if (colStats.ci_lo != null && colStats.ci_hi != null) {
                            val = `${this._fmt(colStats.ci_lo)} – ${this._fmt(colStats.ci_hi)}`;
                        }
                    }
                }

                html += `<td class="tr-stat-val" data-stat="${s.type}" data-col="${c.code}">${val}</td>`;
            });

            html += '</tr>';
        });
        html += '</tfoot>';
        return html;
    },

    // ─── Промежуточные замеры (с поддержкой вычисляемых столбцов по 3 замерам) ───
    // ─── Промежуточные замеры ───
_renderSubMeasurements(formConfig, specimens, specCount) {
    const sub = formConfig.sub_measurements_config;
    if (!sub || !sub.columns) return '';

    const mpp = sub.measurements_per_specimen || 3;

    let html = '<div class="tr-section"><div class="tr-section-title">Промежуточные замеры</div>';
    html += '<div class="tr-table-wrap" style="overflow-x: auto;">';
    html += '<table class="tr-table tr-table-sub" style="min-width: 100%; border-collapse: collapse;">';
    
    // ЗАГОЛОВОК
    html += '<thead>';
    html += '<tr>';
    html += '<th style="position: sticky; left: 0; background: var(--bg-card); z-index: 1;">№</th>';
    
    sub.columns.forEach(c => {
        const title = c.unit ? `${c.name}, ${c.unit}` : c.name;
        
        // Для каждого столбца создаём нужное количество заголовков
        if (c.type === 'TEXT') {
            html += `<th style="min-width: 120px;">${this._esc(title)}</th>`;
        } else {
            // INPUT, FORMULA, CALCULATED, SUB_AVG - по одному заголовку на каждый замер
            for (let m = 0; m < mpp; m++) {
                const cls = (c.type === 'FORMULA' || c.type === 'CALCULATED' || c.type === 'SUB_AVG') ? 'tr-th-calc' : '';
                html += `<th class="${cls}" style="min-width: 70px;">${this._esc(title)}<sub>${m + 1}</sub></th>`;
            }
        }
    });
    html += '</tr>';
    html += '</thead>';
    
    // ТЕЛО ТАБЛИЦЫ
    html += '<tbody>';
    for (let i = 0; i < specCount; i++) {
        const spec = specimens[i] || {};
        const subData = spec.sub_measurements || {};
        
        html += '<tr>';
        html += `<td style="position: sticky; left: 0; background: var(--bg-card); font-weight: 600; text-align: center;">${i + 1}</td>`;
        
        sub.columns.forEach(c => {
            const measurements = subData[c.code] || [];
            
            if (c.type === 'TEXT') {
                // TEXT - одна ячейка
                const val = measurements[0] ?? '';
                html += `<td style="padding: 4px;"><input type="text" class="tr-inp tr-inp-txt tr-inp-sub"
                         data-row="${i}" data-sub="${c.code}" data-meas="0" value="${this._esc(val)}"
                         style="width: 100%; min-width: 100px;"
                         oninput="TestReport._onSubChange(${i},'${c.code}',0,this.value)"></td>`;
            } else {
                // INPUT, FORMULA, CALCULATED, SUB_AVG - по одной ячейке на каждый замер
                for (let m = 0; m < mpp; m++) {
                    if (c.type === 'INPUT') {
                        const val = measurements[m] ?? '';
                        html += `<td style="padding: 4px;"><input type="number" step="any" class="tr-inp tr-inp-num tr-inp-sub"
                                 data-row="${i}" data-sub="${c.code}" data-meas="${m}" value="${val}"
                                 style="width: 100%; min-width: 60px; text-align: center;"
                                 oninput="TestReport._onSubChange(${i},'${c.code}',${m},this.value)"></td>`;
                    } else {
    // FORMULA, CALCULATED, SUB_AVG - вычисляемые ячейки
    let calcValue = '';
    const cacheKey = `${c.code}_${m}`;
    if (spec.values && spec.values[cacheKey] !== undefined) {
        calcValue = spec.values[cacheKey];
    } else if (c.formula) {
        // ВАЖНО: передаём subConfig, а не this.activeForm.sub_measurements_config
        calcValue = this._computeSubFormulaForMeasurement(c.formula, i, m, specimens, sub);
        if (!spec.values) spec.values = {};
        spec.values[cacheKey] = calcValue;
    }
    const displayValue = (calcValue !== '' && calcValue !== null && !isNaN(parseFloat(calcValue))) 
        ? (Math.round(parseFloat(calcValue) * 100) / 100) 
        : (calcValue || '—');
    html += `<td class="tr-td-calc" data-row="${i}" data-sub="${c.code}" data-meas="${m}" data-col="${c.code}" style="text-align: center;">${displayValue}${c.unit ? ` ${c.unit}` : ''}</td>`;
}
                }
            }
        });
        html += '</tr>';
    }
    html += '</tbody>';
    html += '</table>';
    html += '</div></div>';
    
    return html;
},

// ─── Вычисление формулы для конкретного замера в боковой таблице ───
_computeSubFormulaForMeasurement(formula, rowIndex, measIndex, allSpecimens, subConfig) {
    try {
        // Убираем знак = в начале
        let expr = formula.startsWith('=') ? formula.substring(1) : formula;
        const currentRow = rowIndex + 1;
        const mpp = subConfig.measurements_per_specimen || 3;
        
        console.log(`=== COMPUTE: ${formula} for row ${currentRow}, meas ${measIndex} ===`);
        console.log(`Expression: ${expr}`);
        
        // Обработка MIN(range), MAX(range), AVERAGE(range), SUM(range)
        // Диапазон вида O509:O511 - это ссылка на тот же столбец O, но разные строки
        // В веб-форме это означает: для текущего образца, все замеры (1,2,3) этого столбца
        const rangeMatch = expr.match(/(MIN|MAX|AVERAGE|SUM)\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)/i);
        if (rangeMatch) {
            const func = rangeMatch[1].toUpperCase();
            const colLetter = rangeMatch[2].toUpperCase(); // O
            // Игнорируем номера строк, всегда используем текущий образец и все замеры
            const startIdx = colLetter.charCodeAt(0) - 65;
            
            console.log(`Range function detected: ${func} on column ${colLetter}`);
            
            // Находим столбец в конфиге
            const targetCol = subConfig.columns.find(c => c.col_letter === colLetter);
            if (targetCol) {
                const values = [];
                
                // Собираем значения для ВСЕХ замеров (0,1,2) этого столбца
                for (let m = 0; m < mpp; m++) {
                    let val = null;
                    
                    if (targetCol.type === 'INPUT') {
                        const input = document.querySelector(`input[data-row="${rowIndex}"][data-sub="${targetCol.code}"][data-meas="${m}"]`);
                        if (input && input.value !== '') {
                            val = parseFloat(input.value);
                        }
                    } else if (targetCol.type === 'CALCULATED' || targetCol.type === 'FORMULA') {
                        const cell = document.querySelector(`td[data-row="${rowIndex}"][data-sub="${targetCol.code}"][data-meas="${m}"]`);
                        if (cell && cell.textContent && cell.textContent !== '—') {
                            val = parseFloat(cell.textContent);
                        }
                    }
                    
                    if (val !== null && !isNaN(val)) {
                        values.push(val);
                        console.log(`  Value for ${colLetter}${m+1}: ${val}`);
                    }
                }
                
                if (values.length > 0) {
                    let result = 0;
                    switch (func) {
                        case 'MIN': result = Math.min(...values); break;
                        case 'MAX': result = Math.max(...values); break;
                        case 'AVERAGE': result = values.reduce((a, b) => a + b, 0) / values.length; break;
                        case 'SUM': result = values.reduce((a, b) => a + b, 0); break;
                    }
                    console.log(`Range ${func} result: ${result}`);
                    return Math.round(result * 100) / 100;
                }
            }
            return '';
        }
        
        // Находим все ссылки на ячейки (например P509, Q509)
        const cellRefs = expr.match(/[A-Z]+\d+/gi);
        if (!cellRefs) {
            console.log('No cell references found');
            return '';
        }
        
        console.log('Cell references:', cellRefs);
        
        // Для каждой ссылки находим значение и заменяем
        let resultExpr = expr;
        
        for (const ref of cellRefs) {
            const match = ref.match(/([A-Z]+)(\d+)/i);
            if (!match) continue;
            
            const colLetter = match[1].toUpperCase();
            // ИГНОРИРУЕМ номер строки - всегда используем текущую строку и текущий замер
            const rowNum = parseInt(match[2]);
            
            console.log(`  Processing ${ref}: colLetter=${colLetter}, ignoring row number ${rowNum}, using currentRow=${currentRow}, measIndex=${measIndex}`);
            
            // Находим столбец в конфиге по букве
            const targetCol = subConfig.columns.find(c => c.col_letter === colLetter);
            if (!targetCol) {
                console.log(`    Column with letter ${colLetter} not found, replacing with 0`);
                resultExpr = resultExpr.replace(new RegExp(ref, 'g'), '0');
                continue;
            }
            
            console.log(`    Found column: ${targetCol.code} (type: ${targetCol.type})`);
            
            // Ищем значение - ВСЕГДА для текущего замера (measIndex)
            let value = null;
            
            // 1. Прямой поиск в DOM для INPUT полей
            if (targetCol.type === 'INPUT') {
                const inputSelector = `input[data-row="${rowIndex}"][data-sub="${targetCol.code}"][data-meas="${measIndex}"]`;
                const input = document.querySelector(inputSelector);
                console.log(`    DOM selector: ${inputSelector}`);
                if (input && input.value !== '') {
                    value = parseFloat(input.value);
                    if (!isNaN(value)) {
                        console.log(`    Value from DOM INPUT: ${value}`);
                    }
                }
            }
            
            // 2. Для CALCULATED полей ищем в DOM ячейку
            if (value === null && (targetCol.type === 'CALCULATED' || targetCol.type === 'FORMULA')) {
                const cellSelector = `td[data-row="${rowIndex}"][data-sub="${targetCol.code}"][data-meas="${measIndex}"]`;
                const cell = document.querySelector(cellSelector);
                console.log(`    DOM selector: ${cellSelector}`);
                if (cell && cell.textContent && cell.textContent !== '—') {
                    value = parseFloat(cell.textContent);
                    if (!isNaN(value)) {
                        console.log(`    Value from DOM CALC: ${value}`);
                    }
                }
            }
            
            // 3. Если не нашли в DOM, пробуем из specimen
            if (value === null) {
                const specimen = allSpecimens[rowIndex] || {};
                if (targetCol.type === 'INPUT') {
                    const measurements = specimen.sub_measurements?.[targetCol.code] || [];
                    const val = measurements[measIndex];
                    if (val !== null && val !== undefined && !isNaN(parseFloat(val))) {
                        value = parseFloat(val);
                        console.log(`    Value from specimen INPUT: ${value}`);
                    }
                } else if (targetCol.type === 'CALCULATED' || targetCol.type === 'FORMULA') {
                    const cacheKey = `${targetCol.code}_${measIndex}`;
                    const val = specimen.values?.[cacheKey];
                    if (val !== undefined && val !== null && !isNaN(parseFloat(val))) {
                        value = parseFloat(val);
                        console.log(`    Value from specimen CALC: ${value}`);
                    }
                }
            }
            
            // Заменяем ссылку на значение
            const replacement = (value !== null && !isNaN(value)) ? value.toString() : '0';
            console.log(`    Replacement: ${replacement}`);
            resultExpr = resultExpr.replace(new RegExp(ref, 'g'), replacement);
        }
        
        console.log(`Expression after replacement: ${resultExpr}`);
        
        // Вычисляем результат
        resultExpr = resultExpr.replace(/\s/g, '');
        
        if (/^[\d+\-*/().]+$/.test(resultExpr)) {
            try {
                const result = Function('"use strict";return (' + resultExpr + ')')();
                console.log(`Calculation result: ${result}`);
                if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
                    return Math.round(result * 100) / 100;
                }
                return result;
            } catch (e) {
                console.error('Evaluation error:', e, resultExpr);
                return '';
            }
        }
        
        console.log('Expression not safe:', resultExpr);
        return '';
    } catch (e) {
        console.error('SubFormula error:', e, formula);
        return '';
    }
},
    // ─── Пересчёт формул в боковой таблице ───
    _recalculateSubFormulas() {
        const sub = this.activeForm?.sub_measurements_config;
        if (!sub || !sub.columns) return;
        
        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;
        const mpp = sub.measurements_per_specimen || 3;
        
        const formulaColumns = sub.columns.filter(sc => 
            sc.type === 'FORMULA' || sc.type === 'CALCULATED' || sc.type === 'SUB_AVG'
        );
        
        if (formulaColumns.length === 0) return;
        
        const currentData = this._collectData();
        const specimens = currentData.table_data.specimens;
        
        for (let i = 0; i < specCount; i++) {
            const spec = specimens[i] || {};
            
            for (let m = 0; m < mpp; m++) {
                formulaColumns.forEach(sc => {
                    if (!sc.formula) return;
                    
                    const cacheKey = `${sc.code}_${m}`;
                    const result = this._computeSubFormulaForMeasurement(sc.formula, i, m, specimens, sub);
                    
                    const cell = document.querySelector(`td[data-row="${i}"][data-sub="${sc.code}"][data-meas="${m}"]`);
                    if (cell) {
                        const displayValue = (result !== null && result !== '' && !isNaN(parseFloat(result))) 
                            ? (Math.round(parseFloat(result) * 100) / 100) 
                            : result;
                        cell.textContent = displayValue || '—';
                    }
                    
                    if (!spec.values) spec.values = {};
                    spec.values[cacheKey] = result ? (isNaN(parseFloat(result)) ? result : parseFloat(result)) : null;
                });
            }
        }
    },

    // ─── Пересчёт SUB_AVG в основной таблице ───
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
                
                if (subColumn && subColumn.type === 'INPUT') {
                    const inputs = document.querySelectorAll(`input[data-row="${i}"][data-sub="${subCode}"]`);
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

    // ─── Безопасное вычисление формулы ───
    _computeFormula(formula, rowValues, currentRow) {
        try {
            let expr = formula;
            
            const cellRefs = expr.match(/[A-Z]+\d+/gi);
            if (cellRefs) {
                cellRefs.forEach(ref => {
                    const match = ref.match(/([A-Z]+)(\d+)/i);
                    if (match) {
                        const colLetter = match[1].toUpperCase();
                        const rowNum = parseInt(match[2]);
                        
                        if (rowNum === currentRow) {
                            const val = rowValues[colLetter];
                            const replacement = (val !== null && val !== undefined && !isNaN(parseFloat(val))) ? val : '0';
                            expr = expr.replace(new RegExp(ref, 'gi'), replacement);
                        } else {
                            expr = expr.replace(new RegExp(ref, 'gi'), '0');
                        }
                    }
                });
            }
            
            const sumMatch = expr.match(/SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)/i);
            if (sumMatch) {
                const startCol = sumMatch[1].toUpperCase();
                const endCol = sumMatch[3].toUpperCase();
                const startRow = parseInt(sumMatch[2]);
                const endRow = parseInt(sumMatch[4]);
                
                if (startRow === endRow && startRow === currentRow) {
                    const values = [];
                    const startIdx = startCol.charCodeAt(0) - 65;
                    const endIdx = endCol.charCodeAt(0) - 65;
                    
                    for (let idx = startIdx; idx <= endIdx; idx++) {
                        const colLetter = String.fromCharCode(65 + idx);
                        const val = rowValues[colLetter];
                        if (val !== null && val !== undefined && !isNaN(parseFloat(val))) {
                            values.push(parseFloat(val));
                        }
                    }
                    
                    if (values.length > 0) {
                        const sum = values.reduce((a, b) => a + b, 0);
                        expr = expr.replace(/SUM\([A-Z]+\d+:[A-Z]+\d+\)/i, sum.toString());
                    }
                }
            }
            
            const avgMatch = expr.match(/AVERAGE\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)/i);
            if (avgMatch) {
                const startCol = avgMatch[1].toUpperCase();
                const endCol = avgMatch[3].toUpperCase();
                const startRow = parseInt(avgMatch[2]);
                const endRow = parseInt(avgMatch[4]);
                
                if (startRow === endRow && startRow === currentRow) {
                    const values = [];
                    const startIdx = startCol.charCodeAt(0) - 65;
                    const endIdx = endCol.charCodeAt(0) - 65;
                    
                    for (let idx = startIdx; idx <= endIdx; idx++) {
                        const colLetter = String.fromCharCode(65 + idx);
                        const val = rowValues[colLetter];
                        if (val !== null && val !== undefined && !isNaN(parseFloat(val))) {
                            values.push(parseFloat(val));
                        }
                    }
                    
                    if (values.length > 0) {
                        const average = values.reduce((a, b) => a + b, 0) / values.length;
                        expr = expr.replace(/AVERAGE\([A-Z]+\d+:[A-Z]+\d+\)/i, average.toString());
                    }
                }
            }
            
            const minMatch = expr.match(/MIN\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)/i);
            if (minMatch) {
                const startCol = minMatch[1].toUpperCase();
                const endCol = minMatch[3].toUpperCase();
                const startRow = parseInt(minMatch[2]);
                const endRow = parseInt(minMatch[4]);
                
                if (startRow === endRow && startRow === currentRow) {
                    const values = [];
                    const startIdx = startCol.charCodeAt(0) - 65;
                    const endIdx = endCol.charCodeAt(0) - 65;
                    
                    for (let idx = startIdx; idx <= endIdx; idx++) {
                        const colLetter = String.fromCharCode(65 + idx);
                        const val = rowValues[colLetter];
                        if (val !== null && val !== undefined && !isNaN(parseFloat(val))) {
                            values.push(parseFloat(val));
                        }
                    }
                    
                    if (values.length > 0) {
                        const min = Math.min(...values);
                        expr = expr.replace(/MIN\([A-Z]+\d+:[A-Z]+\d+\)/i, min.toString());
                    }
                }
            }
            
            const maxMatch = expr.match(/MAX\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)/i);
            if (maxMatch) {
                const startCol = maxMatch[1].toUpperCase();
                const endCol = maxMatch[3].toUpperCase();
                const startRow = parseInt(maxMatch[2]);
                const endRow = parseInt(maxMatch[4]);
                
                if (startRow === endRow && startRow === currentRow) {
                    const values = [];
                    const startIdx = startCol.charCodeAt(0) - 65;
                    const endIdx = endCol.charCodeAt(0) - 65;
                    
                    for (let idx = startIdx; idx <= endIdx; idx++) {
                        const colLetter = String.fromCharCode(65 + idx);
                        const val = rowValues[colLetter];
                        if (val !== null && val !== undefined && !isNaN(parseFloat(val))) {
                            values.push(parseFloat(val));
                        }
                    }
                    
                    if (values.length > 0) {
                        const max = Math.max(...values);
                        expr = expr.replace(/MAX\([A-Z]+\d+:[A-Z]+\d+\)/i, max.toString());
                    }
                }
            }
            
            const ifErrorMatch = expr.match(/IFERROR\(([^,]+),([^)]+)\)/i);
            if (ifErrorMatch) {
                try {
                    const mainExpr = ifErrorMatch[1];
                    const fallback = ifErrorMatch[2];
                    const testResult = this._computeFormula(mainExpr, rowValues, currentRow);
                    if (testResult === null || testResult === '' || testResult === '0' || isNaN(parseFloat(testResult))) {
                        expr = fallback;
                    } else {
                        expr = mainExpr;
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

    // ─── Вставка из Excel ───
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
                if (['CALCULATED', 'SUB_AVG', 'VLOOKUP'].includes(col.type)) return;
                if (col.code === 'specimen_number') return;

                const input = document.querySelector(`input[data-row="${targetRow}"][data-col="${col.code}"]`);
                if (input) {
                    const trimmed = cellVal.trim().replace(/,/g, '.');
                    input.value = trimmed;
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
            if (sc.type === 'INPUT') {
                for (let m = 0; m < mpp; m++) {
                    allSubInputs.push({ code: sc.code, meas: m });
                }
            }
        });

        const startIdx = allSubInputs.findIndex(si => si.code === startSub && si.meas === startMeas);
        if (startIdx === -1) return;

        rows.forEach((rowData, ri) => {
            const targetRow = startRow + ri;
            rowData.forEach((cellVal, ci) => {
                const idx = startIdx + ci;
                if (idx >= allSubInputs.length) return;

                const si = allSubInputs[idx];
                const input = document.querySelector(`input[data-row="${targetRow}"][data-sub="${si.code}"][data-meas="${si.meas}"]`);
                if (input) {
                    const trimmed = cellVal.trim().replace(/,/g, '.');
                    input.value = trimmed;
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

    _onSubChange(row, subCode, measIndex, value) {
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

    // ─── Локальный пересчёт ───
    _localRecalculate() {
        if (!this.activeForm) return;
        
        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;
        const cols = this.activeForm.column_config || [];
        const statsConfig = this.activeForm.statistics_config || [];
        
        const currentData = this._collectData();
        const specimens = currentData.table_data.specimens;
        
        this._recalculateSubFormulas();
        this._recalculateMainSubAverages();
        
        const vlookupColumns = cols.filter(c => c.type === 'VLOOKUP');
        if (vlookupColumns.length > 0) {
            for (let i = 0; i < specCount; i++) {
                const specimen = specimens[i];
                
                vlookupColumns.forEach(col => {
                    if (col.formula) {
                        const result = this._computeVlookup(col.formula, i, specimen, specimens);
                        
                        const cell = document.querySelector(`td[data-row="${i}"][data-col="${col.code}"]`);
                        if (cell) {
                            const displayValue = (result !== null && result !== '' && !isNaN(parseFloat(result))) 
                                ? (Math.round(parseFloat(result) * 100) / 100) 
                                : result;
                            cell.textContent = displayValue || '—';
                        }
                        
                        if (!specimen.values) specimen.values = {};
                        specimen.values[col.code] = result ? (isNaN(parseFloat(result)) ? result : parseFloat(result)) : null;
                    }
                });
            }
        }
        
        if (!statsConfig.length) return;
        
        const columnsToCalculate = new Set();
        statsConfig.forEach(statItem => {
            if (statItem.columns && Array.isArray(statItem.columns)) {
                statItem.columns.forEach(col => {
                    const colCode = this._getColumnCodeByLetter(col.col_letter, cols);
                    if (colCode) {
                        columnsToCalculate.add(colCode);
                    }
                });
            }
        });
        
        columnsToCalculate.forEach(code => {
            const values = [];
            for (let i = 0; i < specCount; i++) {
                const inp = document.querySelector(`input[data-row="${i}"][data-col="${code}"]`);
                if (inp && inp.value !== '') {
                    const v = parseFloat(inp.value);
                    if (!isNaN(v)) values.push(v);
                    continue;
                }
                const td = document.querySelector(`td[data-row="${i}"][data-col="${code}"]`);
                if (td) {
                    const v = parseFloat(td.textContent);
                    if (!isNaN(v)) values.push(v);
                }
            }
            
            const n = values.length;
            let mean = '', stdev = '', cv = '', ciLo = '', ciHi = '';
            
            if (n >= 1) {
                const m = values.reduce((a, b) => a + b, 0) / n;
                mean = m.toFixed(2);
                
                if (n >= 2) {
                    const s = Math.sqrt(values.reduce((acc, v) => acc + (v - m) ** 2, 0) / (n - 1));
                    stdev = s.toFixed(2);
                    cv = m !== 0 ? (s / m * 100).toFixed(2) : '0.00';
                    
                    const tTable = {2:12.706, 3:4.303, 4:3.182, 5:2.776, 6:2.571,
                                    7:2.447, 8:2.365, 9:2.306, 10:2.262, 15:2.145, 20:2.093};
                    const tVal = tTable[n] || 2.0;
                    const margin = tVal * s / Math.sqrt(n);
                    ciLo = (m - margin).toFixed(2);
                    ciHi = (m + margin).toFixed(2);
                }
            }
            
            const cellMean = document.querySelector(`td[data-stat="MEAN"][data-col="${code}"]`);
            const cellStdev = document.querySelector(`td[data-stat="STDEV"][data-col="${code}"]`);
            const cellCv = document.querySelector(`td[data-stat="CV"][data-col="${code}"]`);
            const cellConf = document.querySelector(`td[data-stat="CONFIDENCE"][data-col="${code}"]`);
            
            if (cellMean) cellMean.textContent = mean;
            if (cellStdev) cellStdev.textContent = stdev;
            if (cellCv) cellCv.textContent = cv;
            if (cellConf) cellConf.textContent = (ciLo && ciHi) ? `${ciLo} – ${ciHi}` : '';
        });
    },

    // ─── Вспомогательная ───
    _getColumnCodeByLetter(letter, cols) {
        const found = cols.find(c => c.col_letter === letter);
        if (found) return found.code;
        const index = letter.charCodeAt(0) - 65;
        if (index >= 0 && index < cols.length) {
            return cols[index].code;
        }
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

    // ─── Скачать Excel ───
    _downloadXlsx() {
        const existing = this.activeForm.existing_report;
        if (existing && existing.id) {
            window.location.href = `/api/test-report/${existing.id}/export-xlsx/`;
        } else {
            const stdId = this.activeForm.standard.id;
            window.location.href = `/api/test-report/export-xlsx/${this.sampleId}/${stdId}/`;
        }
    },

    // ─── Сбор данных ───
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
                    const v = parseFloat(cell.textContent);
                    if (!isNaN(v)) {
                        spec.values[c.code] = v;
                    } else if (cell.textContent !== '—' && cell.textContent !== '') {
                        spec.values[c.code] = cell.textContent;
                    }
                }
            });

            const markInput = document.querySelector(`input[data-row="${i}"][data-col="marking"]`);
            if (markInput) spec.marking = markInput.value;

            if (sub && sub.columns) {
                sub.columns.forEach(sc => {
                    const measurements = [];
                    const isFormula = sc.type === 'FORMULA' || sc.type === 'CALCULATED' || sc.type === 'SUB_AVG';
                    const isText = sc.type === 'TEXT';
                    
                    if (isFormula) {
                        for (let m = 0; m < mpp; m++) {
                            const cell = document.querySelector(`td[data-row="${i}"][data-sub="${sc.code}"][data-meas="${m}"]`);
                            if (cell && cell.textContent) {
                                const v = parseFloat(cell.textContent);
                                if (!isNaN(v)) {
                                    spec.values[`${sc.code}_${m}`] = v;
                                }
                                measurements.push(v || null);
                            } else {
                                measurements.push(null);
                            }
                        }
                    } else if (isText) {
                        const input = document.querySelector(`input[data-row="${i}"][data-sub="${sc.code}"][data-meas="0"]`);
                        if (input) {
                            measurements.push(input.value || null);
                        } else {
                            measurements.push(null);
                        }
                    } else {
                        const inputs = document.querySelectorAll(`input[data-row="${i}"][data-sub="${sc.code}"]`);
                        inputs.forEach(inp => {
                            const v = parseFloat(inp.value);
                            measurements.push(isNaN(v) ? null : v);
                        });
                    }
                    spec.sub_measurements[sc.code] = measurements;
                });
            }

            specimens.push(spec);
        }

        return {
            header_data: this._collectHeaderData(),
            table_data: {specimens}
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

// Автоматическая инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('test-report-container');
    if (container && container.dataset.sampleId) {
        TestReport.init(container.dataset.sampleId);
    }
});
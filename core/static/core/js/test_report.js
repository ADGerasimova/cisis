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
    },

    // ─── Шапка ───
    _renderHeader(hd) {
        const fields = [
            {key: 'identification_number', label: 'Идентификационный номер', ro: true},
            {key: 'conditions',            label: 'Условия испытаний'},
            {key: 'force_sensor',          label: 'Датчик силы'},
            {key: 'traverse_speed',        label: 'Скорость траверсы'},
            {key: 'specimen_count',        label: 'Кол-во образцов', type: 'number'},
            {key: 'notes',                 label: 'Примечания'},
            {key: 'room',                  label: 'Помещение'},
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

        // Оборудование
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
            const cls = (c.type === 'CALCULATED' || c.type === 'SUB_AVG') ? ' tr-th-calc' : '';
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
                    html += `<td class="tr-td-calc" data-row="${i}" data-col="${c.code}">${val !== '' && val !== null ? val : ''}</td>`;
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

    // ─── Статистика (ИСПРАВЛЕННАЯ) ───
    _renderStatistics(formConfig, cols, existing) {
        const statsConfig = formConfig.statistics_config;
        if (!statsConfig || statsConfig.length === 0) return '';

        const statsData = existing ? existing.statistics_data : {};

        const labels = {
            'MEAN':       'Среднее арифметическое',
            'STDEV':      'Стандартное отклонение',
            'CV':         'Коэффициент вариации, %',
            'CONFIDENCE': 'Доверительный интервал',
        };

        // Считаем, сколько столбцов в начале — текстовые/нумерация (для объединения в label)
        let labelSpan = 0;
        for (const c of cols) {
            if (['specimen_number', 'marking'].includes(c.code)) {
                labelSpan++;
            } else {
                break;
            }
        }
        if (labelSpan < 1) labelSpan = 1;

        // Столбцы данных (после labelSpan)
        const dataCols = cols.slice(labelSpan);

        let html = '<tfoot>';
        statsConfig.forEach((s, si) => {
            const rowCls = si === 0 ? ' tr-stat-first' : '';
            html += `<tr class="tr-stat-row tr-stat-${s.type.toLowerCase()}${rowCls}">`;

            // Ячейка с названием — объединяем первые столбцы
            html += `<td colspan="${labelSpan}" class="tr-stat-label">${labels[s.type] || s.type}</td>`;

            // Ячейки с значениями — ровно по одной на каждый оставшийся столбец
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

    // ─── Промежуточные замеры ───
    _renderSubMeasurements(formConfig, specimens, specCount) {
        const sub = formConfig.sub_measurements_config;
        if (!sub || !sub.columns) return '';

        const mpp = sub.measurements_per_specimen || 3;

        let html = '<div class="tr-section"><div class="tr-section-title">Промежуточные замеры</div>';
        html += '<table class="tr-table tr-table-sub"><thead><tr>';
        html += '<th>№</th>';
        sub.columns.forEach(c => {
            const title = c.unit ? `${c.name}, ${c.unit}` : c.name;
            for (let m = 0; m < mpp; m++) {
                html += `<th>${title}<sub>${m + 1}</sub></th>`;
            }
        });
        html += '</tr></thead><tbody>';

        for (let i = 0; i < specCount; i++) {
            const spec = specimens[i] || {};
            const subData = spec.sub_measurements || {};

            html += `<tr><td class="tr-td-num">${i + 1}</td>`;
            sub.columns.forEach(c => {
                const measurements = subData[c.code] || [];
                for (let m = 0; m < mpp; m++) {
                    const val = measurements[m] ?? '';
                    html += `<td><input type="number" step="any" class="tr-inp tr-inp-num tr-inp-sub"
                             data-row="${i}" data-sub="${c.code}" data-meas="${m}" value="${val}"
                             oninput="TestReport._onSubChange(${i},'${c.code}',${m},this.value)"></td>`;
                }
            });
            html += '</tr>';
        }

        html += '</tbody></table></div>';
        return html;
    },

    // ─── Вставка из Excel (Ctrl+V) ───
    _initPasteHandler() {
        const container = document.getElementById('tr-form-area') || document.getElementById('test-report-container');
        if (!container) return;

        container.addEventListener('paste', (e) => {
            const target = e.target;
            if (!target.matches || !target.matches('.tr-inp')) return;

            const clipText = (e.clipboardData || window.clipboardData).getData('text');
            if (!clipText) return;

            // Парсим: строки по \n, столбцы по автоматическому разделителю
            const lines = clipText.trim().split(/\r?\n/);
            const delimiter = this._detectDelimiter(lines[0]);
            const rows = lines.map(r => r.split(delimiter).map(v => v.trim()));

            // Если одна ячейка — стандартное поведение браузера
            if (rows.length === 1 && rows[0].length === 1) return;

            e.preventDefault();

            const startRow = parseInt(target.dataset.row);
            const startCol = target.dataset.col;
            const isSub = !!target.dataset.sub;

            if (isSub) {
                // Вставка в таблицу промежуточных замеров
                this._pasteIntoSub(target, rows);
            } else {
                // Вставка в основную таблицу
                this._pasteIntoMain(startRow, startCol, rows);
            }

            this._localRecalculate();
        });
    },

    _pasteIntoMain(startRow, startCol, rows) {
        const cols = (this.activeForm.column_config || []).filter(c => c.code !== 'br');
        // Находим индекс стартового столбца
        const startColIdx = cols.findIndex(c => c.code === startCol);
        if (startColIdx === -1) return;

        rows.forEach((rowData, ri) => {
            const targetRow = startRow + ri;

            rowData.forEach((cellVal, ci) => {
                const colIdx = startColIdx + ci;
                if (colIdx >= cols.length) return;

                const col = cols[colIdx];
                // Пропускаем вычисляемые и системные
                if (['CALCULATED', 'SUB_AVG'].includes(col.type)) return;
                if (col.code === 'specimen_number') return;

                const input = document.querySelector(
                    `input[data-row="${targetRow}"][data-col="${col.code}"]`
                );
                if (input) {
                    const trimmed = cellVal.trim().replace(/,/g, '.');
                    input.value = trimmed;
                    // Подсветка вставленной ячейки
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

        // Собираем все sub-столбцы по порядку: h(0), h(1), h(2), b(0), b(1), b(2)...
        const mpp = sub.measurements_per_specimen || 3;
        const allSubInputs = []; // [{code, meas}]
        sub.columns.forEach(sc => {
            for (let m = 0; m < mpp; m++) {
                allSubInputs.push({ code: sc.code, meas: m });
            }
        });

        // Находим стартовый индекс
        const startIdx = allSubInputs.findIndex(
            si => si.code === startSub && si.meas === startMeas
        );
        if (startIdx === -1) return;

        rows.forEach((rowData, ri) => {
            const targetRow = startRow + ri;

            rowData.forEach((cellVal, ci) => {
                const idx = startIdx + ci;
                if (idx >= allSubInputs.length) return;

                const si = allSubInputs[idx];
                const input = document.querySelector(
                    `input[data-row="${targetRow}"][data-sub="${si.code}"][data-meas="${si.meas}"]`
                );
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

    // ─── Локальный пересчёт (SUB_AVG + статистика, без сервера) ───
    _localRecalculate() {
        if (!this.activeForm) return;
        const sub = this.activeForm.sub_measurements_config;
        const cols = this.activeForm.column_config || [];
        const specCount = parseInt(document.getElementById('tr-spec-count')?.value) || 6;

        // 1. Пересчёт SUB_AVG (среднее из промежуточных замеров)
        for (let i = 0; i < specCount; i++) {
            if (sub && sub.columns) {
                sub.columns.forEach(sc => {
                    const inputs = document.querySelectorAll(`input[data-row="${i}"][data-sub="${sc.code}"]`);
                    const vals = [];
                    inputs.forEach(inp => {
                        const v = parseFloat(inp.value);
                        if (!isNaN(v)) vals.push(v);
                    });

                    if (vals.length > 0) {
                        const avg = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2);
                        const cell1 = document.querySelector(`td[data-row="${i}"][data-col="${sc.code}_avg"]`);
                        const cell2 = document.querySelector(`td[data-row="${i}"][data-col="${sc.code}"]`);
                        if (cell1) cell1.textContent = avg;
                        if (cell2 && cell2.classList.contains('tr-td-calc')) cell2.textContent = avg;
                    }
                });
            }
        }

        // 2. Пересчёт статистики
        const numericCodes = cols
            .filter(c => c.type !== 'TEXT' && !['specimen_number', 'marking', 'br', 'failure_mode', 'notes'].includes(c.code))
            .map(c => c.code);

        numericCodes.forEach(code => {
            // Собираем значения по всем образцам
            const values = [];
            for (let i = 0; i < specCount; i++) {
                // Сначала пробуем input
                const inp = document.querySelector(`input[data-row="${i}"][data-col="${code}"]`);
                if (inp && inp.value !== '') {
                    const v = parseFloat(inp.value);
                    if (!isNaN(v)) values.push(v);
                    continue;
                }
                // Потом td (вычисляемые)
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

                    // t-таблица (α=0.05, двустор.)
                    const tTable = {2:12.706, 3:4.303, 4:3.182, 5:2.776, 6:2.571,
                                    7:2.447, 8:2.365, 9:2.306, 10:2.262, 15:2.145, 20:2.093};
                    const tVal = tTable[n] || 2.0;
                    const margin = tVal * s / Math.sqrt(n);
                    ciLo = (m - margin).toFixed(2);
                    ciHi = (m + margin).toFixed(2);
                }
            }

            // Обновляем ячейки tfoot
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
            // Отчёт сохранён — скачиваем с данными
            window.location.href = `/api/test-report/${existing.id}/export-xlsx/`;
        } else {
            // Отчёт ещё не сохранён — скачиваем пустой шаблон с шапкой
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

        for (let i = 0; i < specCount; i++) {
            const spec = {number: i + 1, values: {}, sub_measurements: {}};

            cols.forEach(c => {
                if (c.code === 'specimen_number') return;
                const input = document.querySelector(`input[data-row="${i}"][data-col="${c.code}"]`);
                if (input) {
                    spec.values[c.code] = c.type === 'TEXT' ? input.value : (parseFloat(input.value) || null);
                }
                const cell = document.querySelector(`td[data-row="${i}"][data-col="${c.code}"]`);
                if (cell && !input) {
                    const v = parseFloat(cell.textContent);
                    if (!isNaN(v)) spec.values[c.code] = v;
                }
            });

            const markInput = document.querySelector(`input[data-row="${i}"][data-col="marking"]`);
            if (markInput) spec.marking = markInput.value;

            if (sub && sub.columns) {
                sub.columns.forEach(sc => {
                    const measurements = [];
                    document.querySelectorAll(`input[data-row="${i}"][data-sub="${sc.code}"]`).forEach(inp => {
                        const v = parseFloat(inp.value);
                        measurements.push(isNaN(v) ? null : v);
                    });
                    spec.sub_measurements[sc.code] = measurements;
                });
            }

            specimens.push(spec);
        }

        return {header_data: this._collectHeaderData(), table_data: {specimens}};
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
        // Приоритет: таб → точка с запятой → множественные пробелы
        if (line.includes('\t')) return /\t/;
        if (line.includes(';')) return /;/;
        // 2+ пробелов подряд = разделитель (чтобы не ломать "Ult. Force(N)")
        if (/\s{2,}/.test(line)) return /\s{2,}/;
        // Один пробел — фоллбэк (только числовые данные без текста)
        return /\t/; // по умолчанию таб
    },
};
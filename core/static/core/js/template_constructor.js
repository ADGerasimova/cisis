/* ═══════════════════════════════════════════════════════════════
   template_constructor.js — v2.0.0
   Конструктор шаблона таблицы отчёта на странице стандарта.

   Использование:
     TemplateConstructor.init(standardId, canEdit);

   Зависимости: journals.css (уже подключён на странице)
   ═══════════════════════════════════════════════════════════════ */

const TemplateConstructor = {

    standardId: null,
    canEdit: false,
    template: null,

    // рабочие копии
    _columns: [],
    _headerConfig: {},
    _subConfig: null,
    _layoutType: 'A',

    // ─── Инициализация ──────────────────────────────────────────
    async init(standardId, canEdit) {
        this.standardId = standardId;
        this.canEdit = canEdit;
        this._injectStyles();
        await this._load();
    },

    async _load() {
        const block = document.getElementById('tc-block');
        if (!block) return;
        block.innerHTML = '<div class="tc-loading">Загрузка…</div>';
        try {
            const resp = await fetch(`/api/report-templates/config/${this.standardId}/`);
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'Ошибка сервера');
            this.template = data.template;
            this._initWorkingCopies();
            this._render();
        } catch (e) {
            console.error('TemplateConstructor._load:', e);
            document.getElementById('tc-block').innerHTML =
                `<div class="tc-msg-err">Ошибка загрузки: ${e.message}</div>`;
        }
    },

    _initWorkingCopies() {
        if (this.template) {
            this._columns     = JSON.parse(JSON.stringify(this.template.column_config || []));
            this._headerConfig = JSON.parse(JSON.stringify(this.template.header_config || {}));
            this._subConfig   = this.template.sub_measurements_config
                ? JSON.parse(JSON.stringify(this.template.sub_measurements_config))
                : null;
            this._layoutType  = this.template.layout_type || 'A';
        } else {
            this._columns     = [];
            this._headerConfig = this._defaultHeaderConfig();
            this._subConfig   = null;
            this._layoutType  = 'A';
        }
    },

    _defaultHeaderConfig() {
        return {
            date:                  { label: 'Дата:',                    type: 'DATE'    },
            operator:              { label: 'Оператор:',                type: 'TEXT'    },
            identification_number: { label: 'Идентификационный номер:', type: 'TEXT'    },
            force_sensor:          { label: 'Датчик силы:',             type: 'TEXT'    },
            traverse_speed:        { label: 'Скорость траверсы:',       type: 'TEXT'    },
            specimen_count:        { label: 'Кол-во образцов:',         type: 'NUMERIC' },
            conditions:            { label: 'Условия испытаний:',       type: 'TEXT'    },
        };
    },

    // ─── Рендер сводки (view-режим) ─────────────────────────────
    _render() {
        const block = document.getElementById('tc-block');
        if (!block) return;

        const has = !!this.template;
        let html = '<div class="tc-inner">';

        // шапка
        html += '<div class="tc-header-row">';
        if (has) {
            html += `<span class="tc-version-label">v${this.template.version}
                <span class="tc-badge-ok">текущая</span></span>`;
        } else {
            html += '<span class="tc-no-tpl">Шаблон не настроен</span>';
        }
        if (this.canEdit) {
            html += '<div class="tc-header-btns">';
            if (has) {
                html += `<button class="btn btn-outline tc-sm-btn" onclick="TemplateConstructor._showVersions()">
                    <i class="fas fa-history"></i> История</button>
                <button class="btn btn-outline tc-sm-btn" onclick="TemplateConstructor._openPreview()">
                    <i class="fas fa-eye"></i> Предпросмотр</button>
                <button class="btn btn-primary tc-sm-btn" onclick="TemplateConstructor._openEditor()">
                    <i class="fas fa-pen"></i> Редактировать</button>`;
            } else {
                html += `<button class="btn btn-primary tc-sm-btn" onclick="TemplateConstructor._openEditor()">
                    <i class="fas fa-plus"></i> Создать шаблон</button>`;
            }
            html += '</div>';
        }
        html += '</div>'; // tc-header-row

        // сводка
        if (has) {
            html += this._renderSummary();
        } else {
            html += `<div class="tc-empty">
                <div style="font-size:32px;margin-bottom:8px;">📋</div>
                <div style="color:#aaa;font-size:14px;">Шаблон таблицы отчёта не создан</div>
                ${this.canEdit ? '<div style="color:#bbb;font-size:12px;margin-top:4px;">Нажмите «Создать шаблон», чтобы настроить столбцы</div>' : ''}
            </div>`;
        }

        html += '</div>'; // tc-inner
        block.innerHTML = html;

        // вставляем модалки в body (не в card — так они не перекрываются)
        this._ensureModals();
    },

    _renderSummary() {
        const cols = this._columns;
        const TYPE_INFO = {
            INPUT:   { label: 'Ввод',        cls: 'tc-pill-input'  },
            TEXT:    { label: 'Текст',        cls: 'tc-pill-text'   },
            SUB_AVG: { label: 'Ср. замеров',  cls: 'tc-pill-subavg' },
            CALC:    { label: 'Расчёт',       cls: 'tc-pill-calc'   },
            NORM:    { label: 'Норм.',        cls: 'tc-pill-norm'   },
        };

        // счётчики
        const counts = {};
        cols.forEach(c => counts[c.type] = (counts[c.type] || 0) + 1);

        let html = '<div class="tc-summary">';
        html += '<div class="tc-pills">';
        Object.entries(counts).forEach(([t, n]) => {
            const info = TYPE_INFO[t] || { label: t, cls: 'tc-pill-input' };
            html += `<span class="tc-pill ${info.cls}">${info.label}: ${n}</span>`;
        });
        if (this._subConfig) {
            const n = this._subConfig.measurements_per_specimen || 3;
            const names = (this._subConfig.columns || []).map(c => c.name).join(', ');
            html += `<span class="tc-pill tc-pill-sub">Подзамеры ${n}× (${names})</span>`;
        }
        html += '</div>';

        // таблица столбцов
        html += `<table class="tc-summary-table">
            <thead><tr>
                <th>#</th><th>Код</th><th>Название</th>
                <th>Ед.</th><th>Тип</th><th>Формула</th><th>Стат.</th>
            </tr></thead><tbody>`;
        cols.forEach((c, i) => {
            const info = TYPE_INFO[c.type] || { label: c.type, cls: '' };
            const formula = c.formula
                ? `<code class="tc-code-formula">${this._esc(c.formula)}</code>`
                : '<span style="color:#ddd">—</span>';
            const stats = c.has_stats
                ? '<span class="tc-badge-ok" style="font-size:11px;">✓</span>'
                : '<span style="color:#ddd;font-size:12px;">—</span>';
            const isCalc = ['CALC','SUB_AVG','NORM'].includes(c.type);
            html += `<tr${isCalc ? ' class="tc-row-calc"' : ''}>
                <td style="color:#ccc;font-size:12px;">${i+1}</td>
                <td><code class="tc-code">${this._esc(c.code)}</code></td>
                <td>${this._esc(c.name)}</td>
                <td style="color:#999;font-size:12px;">${this._esc(c.unit||'')}</td>
                <td><span class="tc-type-badge ${info.cls}">${info.label}</span></td>
                <td>${formula}</td>
                <td style="text-align:center">${stats}</td>
            </tr>`;
        });
        html += '</tbody></table></div>';
        return html;
    },

    // ─── Вставка модалок в <body> ────────────────────────────────
    _ensureModals() {
        if (!document.getElementById('tc-editor-modal')) {
            const div = document.createElement('div');
            div.innerHTML = this._editorModalHtml() + this._previewModalHtml() + this._versionsModalHtml();
            document.body.appendChild(div);
            this._bindModalEvents();
        }
    },

    // ─── HTML редактора ──────────────────────────────────────────
    _editorModalHtml() {
        return `
        <div id="tc-editor-modal" class="tc-fullscreen-modal">
          <div class="tc-fs-inner">

            <!-- Боковая панель -->
            <div class="tc-sidebar">
              <div class="tc-sidebar-title">Настройка шаблона</div>

              <!-- Тип -->
              <div class="tc-sidebar-section">
                <div class="tc-sidebar-label">Тип шаблона</div>
                <label class="tc-radio-card" id="tc-layout-card-A">
                  <input type="radio" name="tc-layout" value="A">
                  <div class="tc-radio-content">
                    <span class="tc-radio-icon">📋</span>
                    <span class="tc-radio-text">Тип A<br><small>Только основная таблица</small></span>
                  </div>
                </label>
                <label class="tc-radio-card" id="tc-layout-card-B">
                  <input type="radio" name="tc-layout" value="B">
                  <div class="tc-radio-content">
                    <span class="tc-radio-icon">📐</span>
                    <span class="tc-radio-text">Тип B<br><small>С подзамерами (h, b…)</small></span>
                  </div>
                </label>
              </div>

              <!-- Навигация по секциям -->
              <div class="tc-sidebar-section" style="margin-top:8px;">
                <div class="tc-sidebar-label">Разделы</div>
                <button class="tc-nav-btn active" data-section="columns" onclick="TemplateConstructor._switchSection('columns')">
                  <i class="fas fa-table"></i> Столбцы таблицы
                </button>
                <button class="tc-nav-btn" data-section="sub" id="tc-nav-sub" onclick="TemplateConstructor._switchSection('sub')" style="display:none">
                  <i class="fas fa-ruler"></i> Подзамеры
                </button>
                <button class="tc-nav-btn" data-section="header" onclick="TemplateConstructor._switchSection('header')">
                  <i class="fas fa-sliders-h"></i> Параметры шапки
                </button>
              </div>

              <!-- Подсказки формул -->
              <div class="tc-sidebar-section tc-formula-help">
                <div class="tc-sidebar-label">Формулы</div>
                <div class="tc-help-row"><code>{код}</code> — ссылка на другой столбец</div>
                <div class="tc-help-examples">
                  <div class="tc-help-ex" onclick="TemplateConstructor._insertFormula('{Pmax} / {b} / {h} * 1000')">
                    <code>{Pmax} / {b} / {h} * 1000</code>
                    <span>σ из нагрузки</span>
                  </div>
                  <div class="tc-help-ex" onclick="TemplateConstructor._insertFormula('MIN({h1}, {h2}, {h3})')">
                    <code>MIN({h1}, {h2}, {h3})</code>
                    <span>минимум</span>
                  </div>
                  <div class="tc-help-ex" onclick="TemplateConstructor._insertFormula('MAX({a}, {b})')">
                    <code>MAX({a}, {b})</code>
                    <span>максимум</span>
                  </div>
                  <div class="tc-help-ex" onclick="TemplateConstructor._insertFormula('{sigma} * {h} / {tply}')">
                    <code>{sigma} * {h} / {tply}</code>
                    <span>норм. (параметр шапки)</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Основная область -->
            <div class="tc-main">
              <div class="tc-main-header">
                <h2 id="tc-editor-title">Шаблон таблицы отчёта</h2>
                <button class="tc-close-btn" onclick="TemplateConstructor._closeEditor()" title="Закрыть">✕</button>
              </div>

              <!-- Секция: Столбцы -->
              <div id="tc-section-columns" class="tc-section active">
                <div class="tc-section-head">
                  <div>
                    <div class="tc-section-title">Столбцы основной таблицы</div>
                    <div class="tc-section-hint">Определяют, какие данные вводит испытатель для каждого образца</div>
                  </div>
                  <button class="btn btn-primary tc-sm-btn" onclick="TemplateConstructor._addColumn()">
                    <i class="fas fa-plus"></i> Добавить столбец
                  </button>
                </div>

                <!-- Легенда типов -->
                <div class="tc-type-legend">
                  <span class="tc-legend-item"><span class="tc-type-badge tc-pill-input">INPUT</span> — оператор вводит число вручную</span>
                  <span class="tc-legend-item"><span class="tc-type-badge tc-pill-text">TEXT</span> — оператор вводит текст (характер разрушения и т.п.)</span>
                  <span class="tc-legend-item"><span class="tc-type-badge tc-pill-subavg">SUB_AVG</span> — автоматически = среднее из подзамеров</span>
                  <span class="tc-legend-item"><span class="tc-type-badge tc-pill-calc">CALC</span> — вычисляется по формуле из других столбцов</span>
                  <span class="tc-legend-item"><span class="tc-type-badge tc-pill-norm">NORM</span> — как CALC, но использует параметры из шапки</span>
                </div>

                <!-- Заголовок таблицы -->
                <div class="tc-cols-head">
                  <div class="tc-col-drag-ph"></div>
                  <div class="tc-col-f tc-col-f-code">Код <span class="tc-field-hint">(уникальный)</span></div>
                  <div class="tc-col-f tc-col-f-name">Название столбца</div>
                  <div class="tc-col-f tc-col-f-unit">Ед. изм.</div>
                  <div class="tc-col-f tc-col-f-type">Тип</div>
                  <div class="tc-col-f tc-col-f-formula">Формула <span class="tc-field-hint">(для CALC/NORM)</span></div>
                  <div class="tc-col-f tc-col-f-stats">Стат.</div>
                  <div style="width:28px"></div>
                </div>

                <div id="tc-cols-list" class="tc-cols-list"></div>
                <div class="tc-cols-hint">⠿ — перетащите строку для изменения порядка</div>
              </div>

              <!-- Секция: Подзамеры -->
              <div id="tc-section-sub" class="tc-section">
                <div class="tc-section-head">
                  <div>
                    <div class="tc-section-title">Боковая таблица подзамеров</div>
                    <div class="tc-section-hint">Несколько замеров одного параметра на образец (например, h₁, h₂, h₃ → hср)</div>
                  </div>
                </div>

                <div class="tc-sub-settings">
                  <label class="tc-field-label">Количество замеров на образец</label>
                  <input type="number" id="tc-sub-count" min="1" max="10" value="3" class="tc-input-sm">
                </div>

                <div class="tc-section-subtitle">Измеряемые параметры
                  <button class="btn tc-sm-btn tc-btn-ghost" onclick="TemplateConstructor._addSubColumn()" style="margin-left:10px">＋ Добавить</button>
                </div>
                <div class="tc-cols-head tc-sub-head">
                <div class="tc-drag-handle" style="visibility:hidden; width:20px; flex-shrink:0;">⠿</div>
                <div class="tc-col-f tc-col-f-code">Код</div>
                <div class="tc-col-f tc-col-f-name">Название</div>
                <div class="tc-col-f tc-col-f-unit">Ед. изм.</div>
                <div style="width:28px"></div>
                </div>
                <div id="tc-sub-cols-list" class="tc-cols-list"></div>

                <div class="tc-section-subtitle" style="margin-top:20px">Производные (вычисляются по замерам)
                  <button class="btn tc-sm-btn tc-btn-ghost" onclick="TemplateConstructor._addDerivedColumn()" style="margin-left:10px">＋ Добавить</button>
                </div>
               <div class="tc-cols-head tc-sub-head">
                    <div class="tc-drag-handle" style="visibility:hidden; width:20px; flex-shrink:0;">⠿</div>
                    <div class="tc-col-f tc-col-f-code">Код</div>
                    <div class="tc-col-f tc-col-f-name">Название</div>
                    <div class="tc-col-f tc-col-f-unit">Ед. изм.</div>
                    <div class="tc-col-f tc-col-f-formula">Формула</div>
                    <div style="width:28px"></div>
                    </div>
                <div id="tc-derived-cols-list" class="tc-cols-list"></div>
                <div class="tc-info-box" style="margin-top:16px;">
                  <b>Как работает:</b> для каждого образца оператор вводит N замеров каждого параметра.
                  Столбцы с типом <code>SUB_AVG</code> в основной таблице автоматически получают среднее.
                  Производные (например, <code>S = h * b</code>) считаются поэлементно для каждого замера.
                  <code>MIN({S})</code> — минимум из всех S одного образца.
                </div>
              </div>

              <!-- Секция: Параметры шапки -->
              <div id="tc-section-header" class="tc-section">
                <div class="tc-section-head">
                  <div>
                    <div class="tc-section-title">Параметры шапки отчёта</div>
                    <div class="tc-section-hint">Стандартные поля заполняются автоматически. Добавьте числовые параметры если они нужны в формулах NORM-столбцов.</div>
                  </div>
                </div>

                <div class="tc-header-fixed">
                  <div class="tc-info-box">Эти поля присутствуют в каждом отчёте автоматически:
                    <b>Дата, Оператор, Идентификационный номер, Датчик силы, Скорость траверсы, Условия испытаний, СИ, ИО</b>
                  </div>
                </div>

                <div class="tc-section-subtitle" style="margin-top:16px;">Дополнительные числовые параметры
                  <button class="btn tc-sm-btn tc-btn-ghost" onclick="TemplateConstructor._addHeaderParam()" style="margin-left:10px">＋ Добавить</button>
                </div>
                <div class="tc-cols-head tc-sub-head">
                <div class="tc-drag-handle" style="visibility:hidden; width:20px; flex-shrink:0;">⠿</div>
                <div class="tc-col-f tc-col-f-code">Ключ <span class="tc-field-hint">(в формуле: {ключ})</span></div>
                <div class="tc-col-f tc-col-f-name">Подпись в шапке</div>
                <div class="tc-col-f tc-col-f-unit">Ед. изм.</div>
                <div style="width:28px"></div>
                </div>
                <div id="tc-header-params-list" class="tc-cols-list"></div>
                <div class="tc-info-box" style="margin-top:12px;">
                  Числовые параметры можно использовать в формулах NORM-столбцов: <code>{tply}</code>, <code>{n_layers}</code> и т.п.
                </div>
              </div>

              <!-- Футер редактора -->
              <div class="tc-editor-footer">
                <div id="tc-save-error" class="tc-save-error" style="display:none"></div>
                <div class="tc-footer-row">
                  <div id="tc-changes-wrap" style="display:none;flex:1;margin-right:12px;">
                    <input type="text" id="tc-changes-desc" class="tc-input-full"
                           placeholder="Описание изменений (для истории версий)…">
                  </div>
                  <button class="btn" style="background:#f5f5f5;color:#666;"
                          onclick="TemplateConstructor._closeEditor()">Отмена</button>
                  <button class="btn btn-primary" id="tc-save-btn"
                          onclick="TemplateConstructor._save()">
                    <i class="fas fa-save"></i> Сохранить шаблон
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>`;
    },

    _previewModalHtml() {
        return `
        <div id="tc-preview-modal" class="tc-modal-overlay">
          <div class="tc-modal-box" style="width:860px;max-height:85vh;overflow-y:auto;">
            <h2>Предпросмотр таблицы</h2>
            <div id="tc-preview-content"><div class="tc-loading">Загрузка…</div></div>
            <div class="modal-actions">
              <button class="btn" style="background:#f5f5f5;color:#666;"
                      onclick="TemplateConstructor._closePreview()">Закрыть</button>
            </div>
          </div>
        </div>`;
    },

    _versionsModalHtml() {
        return `
        <div id="tc-versions-modal" class="tc-modal-overlay">
          <div class="tc-modal-box" style="width:640px;max-height:80vh;overflow-y:auto;">
            <h2>История версий шаблона</h2>
            <div id="tc-versions-content"><div class="tc-loading">Загрузка…</div></div>
            <div class="modal-actions">
              <button class="btn" style="background:#f5f5f5;color:#666;"
                      onclick="TemplateConstructor._closeVersions()">Закрыть</button>
            </div>
          </div>
        </div>`;
    },

    // ─── Открытие редактора ──────────────────────────────────────
    _openEditor() {
        this._initWorkingCopies();
        const modal = document.getElementById('tc-editor-modal');
        document.getElementById('tc-editor-title').textContent = this.template
            ? 'Редактировать шаблон'
            : 'Создать шаблон таблицы отчёта';
        document.getElementById('tc-changes-wrap').style.display = this.template ? 'block' : 'none';

        // тип лэйаута
        document.querySelector(`input[name="tc-layout"][value="${this._layoutType}"]`).checked = true;
        this._applyLayoutUI(this._layoutType);

        // рендерим содержимое
        this._renderColumnsList();
        this._renderSubColumnsList();
        this._renderDerivedColumnsList();
        this._renderHeaderParamsList();

        // показываем первую секцию
        this._switchSection('columns');

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    },

    _closeEditor() {
        document.getElementById('tc-editor-modal').classList.remove('active');
        document.getElementById('tc-save-error').style.display = 'none';
        document.body.style.overflow = '';
    },

    // ─── Переключение секций ─────────────────────────────────────
    _switchSection(name) {
        document.querySelectorAll('.tc-section').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.tc-nav-btn').forEach(b => b.classList.remove('active'));
        const section = document.getElementById(`tc-section-${name}`);
        if (section) section.classList.add('active');
        const btn = document.querySelector(`.tc-nav-btn[data-section="${name}"]`);
        if (btn) btn.classList.add('active');
    },

    // ─── Layout A/B ──────────────────────────────────────────────
    _applyLayoutUI(type) {
        this._layoutType = type;
        const navSub = document.getElementById('tc-nav-sub');
        if (navSub) navSub.style.display = type === 'B' ? '' : 'none';

        // Подсветка карточек
        document.querySelectorAll('.tc-radio-card').forEach(c => c.classList.remove('tc-radio-selected'));
        const card = document.getElementById(`tc-layout-card-${type}`);
        if (card) card.classList.add('tc-radio-selected');

        if (type === 'B' && !this._subConfig) {
            this._subConfig = {
                measurements_per_specimen: 3,
                columns: [
                    { code: 'h', name: 'h', unit: 'мм' },
                    { code: 'b', name: 'b', unit: 'мм' },
                ],
                derived: [],
            };
            this._renderSubColumnsList();
            this._renderDerivedColumnsList();
        }
    },

    // ─── Рендер списков столбцов ─────────────────────────────────
    _renderColumnsList() {
        const list = document.getElementById('tc-cols-list');
        if (!list) return;
        if (!this._columns.length) {
            list.innerHTML = '<div class="tc-empty-list">Нет столбцов. Нажмите «＋ Добавить столбец».</div>';
            return;
        }
        list.innerHTML = this._columns.map((col, i) => this._mainColRowHtml(col, i)).join('');
        this._initDragDrop(list, this._columns, () => this._renderColumnsList());
    },

   

   

    // ─── HTML строк столбцов ─────────────────────────────────────
    _mainColRowHtml(col, i) {
        const TYPES = ['INPUT','TEXT','SUB_AVG','CALC','NORM'];
        const typeOpts = TYPES.map(t =>
            `<option value="${t}" ${col.type === t ? 'selected' : ''}>${t}</option>`
        ).join('');
        const showFormula = ['CALC','NORM'].includes(col.type);

        return `<div class="tc-col-row" data-index="${i}" draggable="true">
            <div class="tc-drag-handle">⠿</div>
            <input class="tc-input tc-col-f-code" type="text" placeholder="код"
                   value="${this._esc(col.code || '')}"
                   oninput="TemplateConstructor._updateMainCol(${i},'code',this.value)">
            <input class="tc-input tc-col-f-name" type="text" placeholder="Название"
                   value="${this._esc(col.name || '')}"
                   oninput="TemplateConstructor._updateMainCol(${i},'name',this.value)">
            <input class="tc-input tc-col-f-unit" type="text" placeholder="МПа"
                   value="${this._esc(col.unit || '')}"
                   oninput="TemplateConstructor._updateMainCol(${i},'unit',this.value)">
            <select class="tc-select tc-col-f-type"
                    onchange="TemplateConstructor._onMainTypeChange(${i},this.value)">${typeOpts}</select>
            <input class="tc-input tc-col-f-formula ${showFormula ? '' : 'tc-formula-hidden'}"
                   id="tc-formula-${i}"
                   type="text" placeholder="{A} / {B} * 1000"
                   value="${this._esc(col.formula || '')}"
                   oninput="TemplateConstructor._updateMainCol(${i},'formula',this.value)"
                   onfocus="TemplateConstructor._setActiveFormulaField(this)">
            <label class="tc-stats-chk" title="Считать среднее, стандартное отклонение, CV% и доверительный интервал по этому столбцу">
              <input type="checkbox" ${col.has_stats ? 'checked' : ''}
                     onchange="TemplateConstructor._updateMainCol(${i},'has_stats',this.checked)">
            </label>
            <button class="tc-del-btn" onclick="TemplateConstructor._deleteMainCol(${i})">✕</button>
        </div>`;
    },

    _simpleColRowHtml(col, i, group) {
        return `<div class="tc-col-row">
            <input class="tc-input tc-col-f-code" type="text" placeholder="код"
                   value="${this._esc(col.code || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'code',this.value)">
            <input class="tc-input tc-col-f-name" type="text" placeholder="Название"
                   value="${this._esc(col.name || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'name',this.value)">
            <input class="tc-input tc-col-f-unit" type="text" placeholder="мм"
                   value="${this._esc(col.unit || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'unit',this.value)">
            <button class="tc-del-btn" onclick="TemplateConstructor._deleteSimpleCol('${group}',${i})">✕</button>
        </div>`;
    },

    _derivedColRowHtml(col, i) {
        return `<div class="tc-col-row">
            <input class="tc-input tc-col-f-code" type="text" placeholder="код"
                   value="${this._esc(col.code || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('derived',${i},'code',this.value)">
            <input class="tc-input tc-col-f-name" type="text" placeholder="Название"
                   value="${this._esc(col.name || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('derived',${i},'name',this.value)">
            <input class="tc-input tc-col-f-unit" type="text" placeholder="мм²"
                   value="${this._esc(col.unit || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('derived',${i},'unit',this.value)">
            <input class="tc-input tc-col-f-formula" type="text" placeholder="{h} * {b}"
                   value="${this._esc(col.formula || '')}"
                   oninput="TemplateConstructor._updateSimpleCol('derived',${i},'formula',this.value)"
                   onfocus="TemplateConstructor._setActiveFormulaField(this)">
            <button class="tc-del-btn" onclick="TemplateConstructor._deleteSimpleCol('derived',${i})">✕</button>
        </div>`;
    },

    // ─── Мутации данных ──────────────────────────────────────────
    _updateMainCol(i, field, value) {
        if (!this._columns[i]) return;
        this._columns[i][field] = value;
    },

    _onMainTypeChange(i, newType) {
        if (!this._columns[i]) return;
        this._columns[i].type = newType;
        // Показать/скрыть поле формулы без полного перерендера
        const formulaInput = document.getElementById(`tc-formula-${i}`);
        if (formulaInput) {
            if (['CALC','NORM'].includes(newType)) {
                formulaInput.classList.remove('tc-formula-hidden');
            } else {
                formulaInput.classList.add('tc-formula-hidden');
                formulaInput.value = '';
                this._columns[i].formula = '';
            }
        }
    },

    _updateSimpleCol(group, i, field, value) {
        const arr = group === 'sub'
            ? (this._subConfig?.columns || [])
            : (this._subConfig?.derived || []);
        if (arr[i]) arr[i][field] = value;
    },

    _addColumn() {
        this._columns.push({ code: '', name: '', unit: '', type: 'INPUT', has_stats: false });
        this._renderColumnsList();
        // Скроллим к новой строке
        const list = document.getElementById('tc-cols-list');
        if (list) list.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    },

    _deleteMainCol(i) {
        this._columns.splice(i, 1);
        this._renderColumnsList();
    },

    _addSubColumn() {
        if (!this._subConfig) return;
        if (!this._subConfig.columns) this._subConfig.columns = [];
        this._subConfig.columns.push({ code: '', name: '', unit: '' });
        this._renderSubColumnsList();
    },

    _addDerivedColumn() {
        if (!this._subConfig) return;
        if (!this._subConfig.derived) this._subConfig.derived = [];
        this._subConfig.derived.push({ code: '', name: '', unit: '', formula: '' });
        this._renderDerivedColumnsList();
    },

    _deleteSimpleCol(group, i) {
        const arr = group === 'sub'
            ? this._subConfig?.columns
            : this._subConfig?.derived;
        if (arr) arr.splice(i, 1);
        if (group === 'sub') this._renderSubColumnsList();
        else this._renderDerivedColumnsList();
    },

    _addHeaderParam() {
        const key = `param_${Date.now()}`;
        this._headerConfig[key] = { label: '', type: 'NUMERIC', unit: '' };
        this._renderHeaderParamsList();
    },

    _updateHeaderParam(key, field, value) {
        if (this._headerConfig[key]) this._headerConfig[key][field] = value;
    },

    _renameHeaderParam(oldKey, newKey) {
        newKey = newKey.trim();
        if (!newKey || newKey === oldKey || !this._headerConfig[oldKey]) return;
        this._headerConfig[newKey] = this._headerConfig[oldKey];
        delete this._headerConfig[oldKey];
        this._columns.forEach(col => {
            if (col.type === 'NORM' && Array.isArray(col.params)) {
                col.params = col.params.map(p => p === oldKey ? newKey : p);
            }
        });
    },

    _deleteHeaderParam(key) {
        delete this._headerConfig[key];
        this._renderHeaderParamsList();
    },

    // ─── Вставка формулы из подсказок ───────────────────────────
    _activeFormulaField: null,

    _setActiveFormulaField(el) {
        this._activeFormulaField = el;
    },

    _insertFormula(formula) {
        if (this._activeFormulaField) {
            this._activeFormulaField.value = formula;
            this._activeFormulaField.dispatchEvent(new Event('input'));
            this._activeFormulaField.focus();
        }
    },

    // ─── Drag & Drop ─────────────────────────────────────────────
    _initDragDrop(container, arr, onReorder) {
        let dragIdx = null;
        container.querySelectorAll('.tc-col-row[draggable="true"]').forEach(row => {
            row.addEventListener('dragstart', e => {
                dragIdx = parseInt(row.dataset.index);
                row.classList.add('tc-dragging');
                e.dataTransfer.effectAllowed = 'move';
            });
            row.addEventListener('dragend', () => {
                row.classList.remove('tc-dragging');
                container.querySelectorAll('.tc-col-row').forEach(r => r.classList.remove('tc-drag-over'));
            });
            row.addEventListener('dragover', e => {
                e.preventDefault();
                container.querySelectorAll('.tc-col-row').forEach(r => r.classList.remove('tc-drag-over'));
                row.classList.add('tc-drag-over');
            });
            row.addEventListener('drop', e => {
                e.preventDefault();
                const targetIdx = parseInt(row.dataset.index);
                if (dragIdx !== null && dragIdx !== targetIdx) {
                    const [moved] = arr.splice(dragIdx, 1);
                    arr.splice(targetIdx, 0, moved);
                    onReorder();
                }
                dragIdx = null;
            });
        });
    },

    // ─── Привязка событий модалок ────────────────────────────────
    _bindModalEvents() {
        // Закрытие по Escape
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                this._closeEditor();
                this._closePreview();
                this._closeVersions();
            }
        });

        // Переключение layout-радио
        document.querySelectorAll('input[name="tc-layout"]').forEach(radio => {
            radio.addEventListener('change', () => this._applyLayoutUI(radio.value));
        });
    },

    // ─── Сохранение ─────────────────────────────────────────────
    async _save() {
        const errEl = document.getElementById('tc-save-error');
        errEl.style.display = 'none';

        if (this._subConfig) {
            const cnt = parseInt(document.getElementById('tc-sub-count')?.value) || 3;
            this._subConfig.measurements_per_specimen = cnt;
        }

        const colErr = this._validateColumns();
        if (colErr) {
            errEl.textContent = colErr;
            errEl.style.display = '';
            return;
        }

        const btn = document.getElementById('tc-save-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохранение…';

        const changesDesc = document.getElementById('tc-changes-desc')?.value.trim() || '';

        try {
            const resp = await fetch('/api/report-templates/config/save/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': TC_CSRF },
                body: JSON.stringify({
                    standard_id:             this.standardId,
                    layout_type:             this._layoutType,
                    column_config:           this._columns,
                    header_config:           this._headerConfig,
                    sub_measurements_config: this._layoutType === 'B' ? this._subConfig : null,
                    changes_description:     changesDesc,
                }),
            });
            const data = await resp.json();
            if (!data.success) {
                errEl.textContent = data.error || 'Ошибка сервера';
                errEl.style.display = '';
                return;
            }
            this._closeEditor();
            tcShowToast(data.message || 'Шаблон сохранён', 'success');
            await this._load();
        } catch (e) {
            errEl.textContent = 'Ошибка сети: ' + e.message;
            errEl.style.display = '';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-save"></i> Сохранить шаблон';
        }
    },

    _validateColumns() {
        if (!this._columns.length) return 'Добавьте хотя бы один столбец';
        const codes = new Set();
        for (let i = 0; i < this._columns.length; i++) {
            const c = this._columns[i];
            if (!c.code?.trim()) return `Строка ${i+1}: заполните поле «Код»`;
            if (!c.name?.trim()) return `Строка ${i+1}: заполните поле «Название»`;
            if (codes.has(c.code.trim())) return `Дублирующийся код: «${c.code}»`;
            codes.add(c.code.trim());
            if (['CALC','NORM'].includes(c.type) && !c.formula?.trim())
                return `Столбец «${c.code}» (${c.type}): заполните поле «Формула»`;
        }
        if (this._layoutType === 'B' && this._subConfig) {
            const subCols = this._subConfig.columns || [];
            if (!subCols.length) return 'Тип B: добавьте хотя бы один параметр подзамеров';
            for (let i = 0; i < subCols.length; i++) {
                if (!subCols[i].code?.trim()) return `Подзамер ${i+1}: заполните код`;
                if (!subCols[i].name?.trim()) return `Подзамер ${i+1}: заполните название`;
            }
        }
        return null;
    },

    // ─── Предпросмотр ───────────────────────────────────────────
    async _openPreview() {
        if (!this.template) return;
        document.getElementById('tc-preview-modal').classList.add('active');
        document.getElementById('tc-preview-content').innerHTML = '<div class="tc-loading">Загрузка…</div>';
        try {
            const resp = await fetch(`/api/report-templates/config/preview/${this.template.id}/`);
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            document.getElementById('tc-preview-content').innerHTML =
                this._buildPreviewTable(data.template, data.preview_row);
        } catch (e) {
            document.getElementById('tc-preview-content').innerHTML =
                `<div class="tc-msg-err">Ошибка: ${e.message}</div>`;
        }
    },

    _closePreview() {
        document.getElementById('tc-preview-modal')?.classList.remove('active');
    },

    _buildPreviewTable(tmpl, row) {
        const cols = (tmpl.column_config || []).filter(c => c.code !== 'br');
        const TYPE_INFO = { INPUT:'Ввод', TEXT:'Текст', SUB_AVG:'Ср.', CALC:'Расч.', NORM:'Норм.' };
        let html = '<div style="overflow-x:auto"><table class="tc-summary-table">';
        html += '<thead><tr>';
        cols.forEach(c => {
            const isCalc = ['CALC','SUB_AVG','NORM'].includes(c.type);
            html += `<th ${isCalc ? 'style="background:#f0f4ff"' : ''}>
                ${this._esc(c.unit ? `${c.name}, ${c.unit}` : c.name)}
                <div style="font-size:10px;color:#aaa;font-weight:400">${TYPE_INFO[c.type]||c.type}</div>
            </th>`;
        });
        html += '</tr></thead><tbody><tr>';
        cols.forEach(c => {
            const val = row[c.code];
            const isCalc = ['CALC','SUB_AVG','NORM'].includes(c.type);
            html += `<td ${isCalc ? 'style="background:#f8f9ff"' : ''}>${this._esc(String(val ?? '—'))}</td>`;
        });
        html += '</tr></tbody></table></div>';
        if (tmpl.sub_measurements_config) {
            const sub = tmpl.sub_measurements_config;
            html += `<p style="color:#888;font-size:13px;margin-top:12px">
                Подзамеры: ${sub.measurements_per_specimen||3} замера × 
                (${(sub.columns||[]).map(c=>c.name).join(', ')})
            </p>`;
        }
        return html;
    },

    // ─── История версий ─────────────────────────────────────────
    async _showVersions() {
        document.getElementById('tc-versions-modal').classList.add('active');
        document.getElementById('tc-versions-content').innerHTML = '<div class="tc-loading">Загрузка…</div>';
        try {
            const resp = await fetch(`/api/report-templates/config/${this.standardId}/versions/`);
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            const rows = data.versions.map(v => `<tr>
                <td>v${v.version}</td>
                <td>${v.is_current ? '<span class="tc-badge-ok">текущая</span>' : '<span style="color:#ccc;font-size:12px">архив</span>'}</td>
                <td style="color:#999;font-size:12px">${v.created_at ? v.created_at.slice(0,16).replace('T',' ') : '—'}</td>
                <td style="color:#999;font-size:12px">${this._esc(v.created_by||'—')}</td>
                <td style="color:#777;font-size:13px">${this._esc(v.changes_description||'—')}</td>
            </tr>`).join('');
            document.getElementById('tc-versions-content').innerHTML = `
                <table class="tc-summary-table">
                    <thead><tr><th>Версия</th><th>Статус</th><th>Дата</th><th>Автор</th><th>Изменения</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>`;
        } catch (e) {
            document.getElementById('tc-versions-content').innerHTML = `<div class="tc-msg-err">Ошибка: ${e.message}</div>`;
        }
    },

    _closeVersions() {
        document.getElementById('tc-versions-modal')?.classList.remove('active');
    },

    // ─── Утилиты ────────────────────────────────────────────────
    _esc(str) {
        if (str == null) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    },

    // Добавьте эти методы в объект TemplateConstructor (после существующих методов)

// ─── Рендер списков с drag&drop ─────────────────────────────────
_renderSubColumnsList() {
    const list = document.getElementById('tc-sub-cols-list');
    if (!list || !this._subConfig) return;
    const cols = this._subConfig.columns || [];
    if (!cols.length) {
        list.innerHTML = '<div class="tc-empty-list">Нет параметров.</div>';
        return;
    }
    list.innerHTML = cols.map((col, i) => this._simpleColRowHtml(col, i, 'sub', true)).join('');
    this._initDragDropSimple(list, this._subConfig.columns, () => this._renderSubColumnsList());
},

_renderDerivedColumnsList() {
    const list = document.getElementById('tc-derived-cols-list');
    if (!list || !this._subConfig) return;
    const cols = this._subConfig.derived || [];
    if (!cols.length) {
        list.innerHTML = '<div class="tc-empty-list">Нет производных.</div>';
        return;
    }
    list.innerHTML = cols.map((col, i) => this._derivedColRowHtml(col, i, true)).join('');
    this._initDragDropSimple(list, this._subConfig.derived, () => this._renderDerivedColumnsList());
},

_renderHeaderParamsList() {
    const list = document.getElementById('tc-header-params-list');
    if (!list) return;
    const numericParams = Object.entries(this._headerConfig)
        .filter(([, cfg]) => cfg.type === 'NUMERIC');

    if (!numericParams.length) {
        list.innerHTML = '<div class="tc-empty-list">Нет дополнительных параметров.</div>';
        return;
    }
    
    // Преобразуем в массив для drag&drop
    const paramsArray = numericParams.map(([key, cfg]) => ({ key, ...cfg }));
    list.innerHTML = paramsArray.map((item, i) => this._headerParamRowHtml(item, i)).join('');
    this._initDragDropHeaderParams(list, paramsArray, () => this._renderHeaderParamsList());
},

// HTML строки с drag handle
_simpleColRowHtml(col, i, group, withDrag = false) {
    const dragHtml = withDrag ? `<div class="tc-drag-handle">⠿</div>` : '';
    return `<div class="tc-col-row" data-index="${i}" ${withDrag ? 'draggable="true"' : ''}>
        ${dragHtml}
        <input class="tc-input tc-col-f-code" type="text" placeholder="код"
               value="${this._esc(col.code || '')}"
               oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'code',this.value)">
        <input class="tc-input tc-col-f-name" type="text" placeholder="Название"
               value="${this._esc(col.name || '')}"
               oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'name',this.value)">
        <input class="tc-input tc-col-f-unit" type="text" placeholder="мм"
               value="${this._esc(col.unit || '')}"
               oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'unit',this.value)">
        ${group === 'derived' ? `
        <input class="tc-input tc-col-f-formula" type="text" placeholder="{h} * {b}"
               value="${this._esc(col.formula || '')}"
               oninput="TemplateConstructor._updateSimpleCol('${group}',${i},'formula',this.value)"
               onfocus="TemplateConstructor._setActiveFormulaField(this)">` : ''}
        <button class="tc-del-btn" onclick="TemplateConstructor._deleteSimpleCol('${group}',${i})">✕</button>
    </div>`;
},

_derivedColRowHtml(col, i, withDrag = false) {
    const dragHtml = withDrag ? `<div class="tc-drag-handle">⠿</div>` : '';
    return `<div class="tc-col-row" data-index="${i}" ${withDrag ? 'draggable="true"' : ''}>
        ${dragHtml}
        <input class="tc-input tc-col-f-code" type="text" placeholder="код"
               value="${this._esc(col.code || '')}"
               oninput="TemplateConstructor._updateSimpleCol('derived',${i},'code',this.value)">
        <input class="tc-input tc-col-f-name" type="text" placeholder="Название"
               value="${this._esc(col.name || '')}"
               oninput="TemplateConstructor._updateSimpleCol('derived',${i},'name',this.value)">
        <input class="tc-input tc-col-f-unit" type="text" placeholder="мм²"
               value="${this._esc(col.unit || '')}"
               oninput="TemplateConstructor._updateSimpleCol('derived',${i},'unit',this.value)">
        <input class="tc-input tc-col-f-formula" type="text" placeholder="{h} * {b}"
               value="${this._esc(col.formula || '')}"
               oninput="TemplateConstructor._updateSimpleCol('derived',${i},'formula',this.value)"
               onfocus="TemplateConstructor._setActiveFormulaField(this)">
        <button class="tc-del-btn" onclick="TemplateConstructor._deleteSimpleCol('derived',${i})">✕</button>
    </div>`;
},

_headerParamRowHtml(item, i) {
    return `<div class="tc-col-row" data-index="${i}" draggable="true">
        <div class="tc-drag-handle">⠿</div>
        <input class="tc-input tc-col-f-code" type="text" placeholder="ключ"
               value="${this._esc(item.key)}"
               onchange="TemplateConstructor._renameHeaderParamWithIndex(${i}, this.value)">
        <input class="tc-input tc-col-f-name" type="text" placeholder="Подпись в шапке"
               value="${this._esc(item.label || '')}"
               oninput="TemplateConstructor._updateHeaderParamByIndex(${i}, 'label', this.value)">
        <input class="tc-input tc-col-f-unit" type="text" placeholder="Ед."
               value="${this._esc(item.unit || '')}"
               oninput="TemplateConstructor._updateHeaderParamByIndex(${i}, 'unit', this.value)">
        <button class="tc-del-btn" onclick="TemplateConstructor._deleteHeaderParamByIndex(${i})">✕</button>
    </div>`;
},

// Drag & Drop для простых списков
_initDragDropSimple(container, arr, onReorder) {
    let dragIdx = null;
    const rows = container.querySelectorAll('.tc-col-row[draggable="true"]');
    rows.forEach(row => {
        row.addEventListener('dragstart', e => {
            dragIdx = parseInt(row.dataset.index);
            row.classList.add('tc-dragging');
            e.dataTransfer.effectAllowed = 'move';
        });
        row.addEventListener('dragend', () => {
            row.classList.remove('tc-dragging');
            container.querySelectorAll('.tc-col-row').forEach(r => r.classList.remove('tc-drag-over'));
        });
        row.addEventListener('dragover', e => {
            e.preventDefault();
            container.querySelectorAll('.tc-col-row').forEach(r => r.classList.remove('tc-drag-over'));
            row.classList.add('tc-drag-over');
        });
        row.addEventListener('drop', e => {
            e.preventDefault();
            const targetIdx = parseInt(row.dataset.index);
            if (dragIdx !== null && dragIdx !== targetIdx) {
                const [moved] = arr.splice(dragIdx, 1);
                arr.splice(targetIdx, 0, moved);
                onReorder();
            }
            dragIdx = null;
        });
    });
},

// Drag & Drop для параметров шапки (работа с объектом)
_initDragDropHeaderParams(container, paramsArray, onReorder) {
    let dragIdx = null;
    const rows = container.querySelectorAll('.tc-col-row[draggable="true"]');
    rows.forEach(row => {
        row.addEventListener('dragstart', e => {
            dragIdx = parseInt(row.dataset.index);
            row.classList.add('tc-dragging');
            e.dataTransfer.effectAllowed = 'move';
        });
        row.addEventListener('dragend', () => {
            row.classList.remove('tc-dragging');
            container.querySelectorAll('.tc-col-row').forEach(r => r.classList.remove('tc-drag-over'));
        });
        row.addEventListener('dragover', e => {
            e.preventDefault();
            container.querySelectorAll('.tc-col-row').forEach(r => r.classList.remove('tc-drag-over'));
            row.classList.add('tc-drag-over');
        });
        row.addEventListener('drop', e => {
            e.preventDefault();
            const targetIdx = parseInt(row.dataset.index);
            if (dragIdx !== null && dragIdx !== targetIdx) {
                // Перестраиваем _headerConfig на основе paramsArray
                const newConfig = {};
                const [moved] = paramsArray.splice(dragIdx, 1);
                paramsArray.splice(targetIdx, 0, moved);
                paramsArray.forEach(item => {
                    newConfig[item.key] = {
                        label: item.label,
                        type: 'NUMERIC',
                        unit: item.unit
                    };
                });
                this._headerConfig = newConfig;
                onReorder();
            }
            dragIdx = null;
        });
    });
},

// Вспомогательные методы для работы с параметрами шапки по индексу
_updateHeaderParamByIndex(index, field, value) {
    const paramsArray = Object.entries(this._headerConfig)
        .filter(([, cfg]) => cfg.type === 'NUMERIC')
        .map(([key, cfg]) => ({ key, ...cfg }));
    if (paramsArray[index]) {
        const item = paramsArray[index];
        this._headerConfig[item.key][field] = value;
    }
},

_renameHeaderParamWithIndex(index, newKey) {
    newKey = newKey.trim();
    if (!newKey) return;
    
    const paramsArray = Object.entries(this._headerConfig)
        .filter(([, cfg]) => cfg.type === 'NUMERIC')
        .map(([key, cfg]) => ({ key, ...cfg }));
    
    if (paramsArray[index]) {
        const oldKey = paramsArray[index].key;
        if (oldKey === newKey) return;
        
        this._headerConfig[newKey] = this._headerConfig[oldKey];
        delete this._headerConfig[oldKey];
        
        // Обновляем ссылки в NORM столбцах
        this._columns.forEach(col => {
            if (col.type === 'NORM' && Array.isArray(col.params)) {
                col.params = col.params.map(p => p === oldKey ? newKey : p);
            }
        });
        this._renderHeaderParamsList();
    }
},

_deleteHeaderParamByIndex(index) {
    const paramsArray = Object.entries(this._headerConfig)
        .filter(([, cfg]) => cfg.type === 'NUMERIC')
        .map(([key, cfg]) => ({ key, ...cfg }));
    
    if (paramsArray[index]) {
        delete this._headerConfig[paramsArray[index].key];
        this._renderHeaderParamsList();
    }
},

    // ─── Инжект стилей ──────────────────────────────────────────
    _injectStyles() {
        if (document.getElementById('tc-styles')) return;
        const style = document.createElement('style');
        style.id = 'tc-styles';
        style.textContent = `
/* ══ Обёртка блока ══ */
.tc-inner { }
.tc-loading { color:#aaa;font-size:13px;padding:12px 0; }
.tc-msg-err { color:#dc3545;font-size:13px;padding:8px 0; }

/* ══ Шапка сводки ══ */
.tc-header-row {
    display:flex; justify-content:space-between; align-items:center;
    margin-bottom:14px; flex-wrap:wrap; gap:8px;
}
.tc-header-btns { display:flex; gap:8px; }
.tc-sm-btn { font-size:12px !important; padding:5px 12px !important; }
.tc-btn-ghost { background:#f5f5f5 !important; color:#555 !important; }
.tc-version-label { font-size:13px;color:#667eea;font-weight:600;display:flex;align-items:center;gap:8px; }
.tc-no-tpl { font-size:13px;color:#bbb; }
.tc-badge-ok { display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500;background:#d4edda;color:#28a745; }

/* ══ Сводка ══ */
.tc-summary { }
.tc-pills { display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px; }
.tc-pill { display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500; }
.tc-pill-input  { background:#e3f2fd;color:#1565c0; }
.tc-pill-text   { background:#f3e5f5;color:#6a1b9a; }
.tc-pill-subavg { background:#e8f5e9;color:#2e7d32; }
.tc-pill-calc   { background:#fff3e0;color:#e65100; }
.tc-pill-norm   { background:#fce4ec;color:#880e4f; }
.tc-pill-sub    { background:#f1f8e9;color:#33691e; }

.tc-summary-table { width:100%;border-collapse:collapse;font-size:13px; }
.tc-summary-table th {
    text-align:left;padding:7px 10px;background:#f8f9fa;
    color:#888;font-weight:600;font-size:11px;text-transform:uppercase;
    border-bottom:1px solid #eee;
}
.tc-summary-table td { padding:7px 10px;border-bottom:1px solid #f5f5f5;vertical-align:middle; }
.tc-summary-table tr:last-child td { border-bottom:none; }
.tc-row-calc td { background:#fafbff; }
.tc-code { background:#f4f4f4;padding:1px 5px;border-radius:3px;font-size:12px; }
.tc-code-formula { color:#e65100;font-size:11px;background:#fff3e0;padding:1px 5px;border-radius:3px; }
.tc-type-badge { display:inline-block;padding:2px 7px;border-radius:8px;font-size:11px;font-weight:500; }

.tc-empty { text-align:center;padding:24px 0;color:#bbb; }

/* ══ ПОЛНОЭКРАННЫЙ РЕДАКТОР ══ */
.tc-fullscreen-modal {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 99999;
    background: rgba(0,0,0,0.5);
    align-items: stretch;
    justify-content: stretch;
}
.tc-fullscreen-modal.active {
    display: flex;
}
.tc-fs-inner {
    display: flex;
    width: 100%;
    height: 100%;
    background: #fff;
}

/* ── Боковая панель ── */
.tc-sidebar {
    width: 260px;
    min-width: 260px;
    background: #1e1e2e;
    color: #cdd6f4;
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow-y: auto;
    flex-shrink: 0;
}
.tc-sidebar-title {
    padding: 20px 20px 14px;
    font-size: 13px;
    font-weight: 700;
    color: #89b4fa;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
.tc-sidebar-section {
    padding: 14px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.tc-sidebar-label {
    font-size: 11px;
    font-weight: 600;
    color: #6c7086;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.tc-radio-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 8px;
    cursor: pointer;
    margin-bottom: 6px;
    border: 1.5px solid rgba(255,255,255,0.08);
    transition: all 0.15s;
}
.tc-radio-card:hover { background: rgba(255,255,255,0.05); }
.tc-radio-selected { background: rgba(137,180,250,0.15) !important; border-color: #89b4fa !important; }
.tc-radio-content { display:flex;align-items:center;gap:8px; }
.tc-radio-icon { font-size:18px; }
.tc-radio-text { font-size:12px;color:#cdd6f4;line-height:1.4; }
.tc-radio-text small { color:#6c7086; }
.tc-radio-card input[type=radio] { accent-color:#89b4fa; flex-shrink:0; }

.tc-nav-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 9px 12px;
    background: none;
    border: none;
    border-radius: 7px;
    color: #9399b2;
    font-size: 13px;
    cursor: pointer;
    text-align: left;
    margin-bottom: 3px;
    transition: all 0.15s;
}
.tc-nav-btn:hover { background: rgba(255,255,255,0.06); color:#cdd6f4; }
.tc-nav-btn.active { background: rgba(137,180,250,0.18); color:#89b4fa; font-weight:600; }
.tc-nav-btn i { width:16px;text-align:center; }

/* Подсказки формул */
.tc-formula-help { flex: 1; }
.tc-help-row { font-size:12px;color:#6c7086;margin-bottom:8px; }
.tc-help-row code { background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:3px;color:#a6e3a1; }
.tc-help-examples { display:flex;flex-direction:column;gap:4px; }
.tc-help-ex {
    padding: 7px 10px;
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.1s;
}
.tc-help-ex:hover { background: rgba(137,180,250,0.12); }
.tc-help-ex code { display:block;font-size:11px;color:#a6e3a1;margin-bottom:2px; }
.tc-help-ex span { font-size:11px;color:#6c7086; }

/* ── Главная область ── */
.tc-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #f8f9fa;
}
.tc-main-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 28px;
    background: #fff;
    border-bottom: 1px solid #eee;
    flex-shrink: 0;
}
.tc-main-header h2 { margin:0;font-size:18px;color:#1a1a2e; }
.tc-close-btn {
    width:34px;height:34px;border-radius:50%;border:none;
    background:#f5f5f5;color:#999;font-size:18px;cursor:pointer;
    display:flex;align-items:center;justify-content:center;
    transition:all 0.15s;
}
.tc-close-btn:hover { background:#fee;color:#dc3545; }

/* ── Секции ── */
.tc-section {
    display: none;
    flex: 1;
    overflow-y: auto;
    padding: 24px 28px;
}
.tc-section.active { display: flex; flex-direction: column; }
.tc-section-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
}
.tc-section-title { font-size:16px;font-weight:600;color:#1a1a2e;margin-bottom:3px; }
.tc-section-hint { font-size:13px;color:#999; }
.tc-section-subtitle {
    font-size:13px;font-weight:600;color:#555;
    margin-bottom:8px;display:flex;align-items:center;
}

/* Легенда типов */
.tc-type-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #fff;
    border-radius: 8px;
    border: 1px solid #eee;
}
.tc-legend-item { font-size:12px;color:#666;display:flex;align-items:center;gap:6px; }

/* Заголовок таблицы столбцов */
.tc-cols-head {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px 6px 38px;
    font-size: 11px;
    font-weight: 600;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.tc-sub-head { padding-left: 8px; }
.tc-col-drag-ph { width: 20px; flex-shrink: 0; }
.tc-field-hint { font-weight:400;color:#ccc;text-transform:none;font-size:10px; }

/* Фиксированные ширины полей */
.tc-col-f-code    { width: 110px; flex-shrink: 0; }
.tc-col-f-name    { flex: 1; min-width: 120px; }
.tc-col-f-unit    { width: 70px; flex-shrink: 0; }
.tc-col-f-type    { width: 90px; flex-shrink: 0; }
.tc-col-f-formula { flex: 1.5; min-width: 160px; }
.tc-col-f-stats   { width: 44px; flex-shrink: 0; text-align: center; }

/* ── Строка столбца ── */
.tc-cols-list { display:flex;flex-direction:column;gap:5px; margin-bottom:8px; }
.tc-col-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 10px;
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    transition: border-color 0.1s, box-shadow 0.1s;
}
.tc-col-row:hover { border-color:#c5d0e6; }
.tc-col-row.tc-dragging { opacity:0.4; }
.tc-col-row.tc-drag-over { border-color:#667eea; box-shadow:0 0 0 2px #667eea33; }

.tc-drag-handle { color:#ccc;cursor:grab;font-size:16px;user-select:none;flex-shrink:0;width:20px;text-align:center; }
.tc-drag-handle:active { cursor:grabbing; }

.tc-input {
    padding: 5px 8px;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
    font-size: 12px;
    background: #fff;
    transition: border-color 0.15s;
    height: 30px;
    box-sizing: border-box;
}
.tc-input:focus { outline:none;border-color:#667eea;box-shadow:0 0 0 2px #667eea1a; }
.tc-input-sm { width:60px; }
.tc-input-full { width:100%;padding:7px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px; }
.tc-input-full:focus { outline:none;border-color:#667eea; }

.tc-select {
    padding: 5px 6px;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
    font-size: 11px;
    background: #fff;
    height: 30px;
    cursor: pointer;
}
.tc-select:focus { outline:none;border-color:#667eea; }

.tc-formula-hidden { opacity:0.25;pointer-events:none; }

.tc-stats-chk { cursor:pointer;display:flex;align-items:center;justify-content:center;width:44px;flex-shrink:0; }
.tc-stats-chk input { accent-color:#667eea;width:15px;height:15px;cursor:pointer; }

.tc-del-btn {
    width:26px;height:26px;border:none;border-radius:5px;
    background:none;color:#ccc;font-size:14px;cursor:pointer;
    display:flex;align-items:center;justify-content:center;
    flex-shrink:0;transition:all 0.15s;
}
.tc-del-btn:hover { background:#fee;color:#dc3545; }

.tc-empty-list { color:#bbb;font-size:13px;padding:10px 0; }
.tc-cols-hint { font-size:11px;color:#ccc;margin-top:4px; }

/* Подзамеры */
.tc-sub-settings { display:flex;align-items:center;gap:10px;margin-bottom:16px;font-size:13px;color:#555; }

/* Инфобокс */
.tc-info-box {
    padding: 12px 16px;
    background: #f0f4ff;
    border-radius: 8px;
    font-size: 13px;
    color: #555;
    line-height: 1.5;
}
.tc-info-box code { background:#e0e8ff;padding:1px 5px;border-radius:3px;font-size:12px;color:#4a3fc7; }
.tc-header-fixed { margin-bottom:4px; }

/* ── Футер редактора ── */
.tc-editor-footer {
    padding: 14px 28px;
    background: #fff;
    border-top: 1px solid #eee;
    flex-shrink: 0;
}
.tc-footer-row { display:flex;align-items:center;gap:10px;justify-content:flex-end; }
.tc-save-error { color:#dc3545;font-size:13px;margin-bottom:8px;padding:8px 12px;background:#fff0f0;border-radius:6px; }

/* ══ Обычные модалки (предпросмотр, история) ══ */
.tc-modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 99998;
    align-items: center;
    justify-content: center;
}
.tc-modal-overlay.active { display:flex; }
.tc-modal-box {
    background: #fff;
    border-radius: 12px;
    padding: 28px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
    max-width: 95vw;
}
.tc-modal-box h2 { margin:0 0 20px;font-size:18px;color:#1a1a2e; }
        `;
        document.head.appendChild(style);
    },
};

function tcShowToast(msg, type) {
    if (typeof showToast === 'function') { showToast(msg, type); return; }
    const t = document.getElementById('toast');
    if (t) { t.textContent = msg; t.className = `toast ${type||''} active`; setTimeout(() => t.classList.remove('active'), 3000); }
}
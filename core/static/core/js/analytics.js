/* ============================================================
   ANALYTICS v4 — логика дашборда
   ============================================================ */

const API = {
    laboratories:       '/workspace/analytics/api/laboratories',
    kpi:                '/workspace/analytics/api/kpi',
    funnel:             '/workspace/analytics/api/funnel',
    stageDurations:     '/workspace/analytics/api/stage-durations',
    dailyDynamics:      '/workspace/analytics/api/daily-dynamics',
    monthlyLabor:       '/workspace/analytics/api/monthly-labor',
    labDistribution:    '/workspace/analytics/api/laboratory-distribution',
    statusDistribution: '/workspace/analytics/api/status-distribution',
    testTypeDist:       '/workspace/analytics/api/test-type-distribution',
    reportTypeDist:     '/workspace/analytics/api/report-type-distribution',
    topClients:         '/workspace/analytics/api/top-clients',
    topStandards:       '/workspace/analytics/api/top-standards',
    riskStuck:          '/workspace/analytics/api/risk/stuck',
    riskEquipment:      '/workspace/analytics/api/risk/equipment-expiring',
    riskReplacement:    '/workspace/analytics/api/risk/replacement-protocols',
    drillDown:          '/workspace/analytics/api/samples/drill-down',
};

const STATE = {
    period: 'month',
    dateFrom: null,
    dateTo: null,
    labId: 0,
    charts: {},
    lastLoadedAt: null,
};

/* ────── Утилиты ────── */
const fmt = new Intl.NumberFormat('ru-RU');
const fmtNum = (n) => (n == null ? '—' : fmt.format(n));
const fmtFloat = (n, d = 1) =>
    (n == null ? '—' : Number(n).toFixed(d).replace('.', ','));
const fmtDate = (s) => {
    if (!s) return '—';
    const d = new Date(s);
    return isNaN(d) ? s : d.toLocaleDateString('ru-RU');
};

const STATUS_LABEL = {
    PENDING_VERIFICATION:  'Ждёт проверки',
    REGISTERED:            'Зарегистрирован',
    CANCELLED:             'Отменён',
    MANUFACTURING:         'Изготавливается',
    MANUFACTURED:          'Изготовлено',
    TRANSFERRED:           'Передан в лабораторию',
    UZK_TESTING:           'На УЗК',
    UZK_READY:             'Готов после УЗК',
    MOISTURE_CONDITIONING: 'На влагонасыщении',
    MOISTURE_READY:        'Готов после УКИ',
    ACCEPTED_IN_LAB:       'Принят в лаборатории',
    CONDITIONING:          'Кондиционирование',
    READY_FOR_TEST:        'Ждёт испытания',
    IN_TESTING:            'На испытании',
    TESTED:                'Испытан',
    DRAFT_READY:           'Черновик готов',
    RESULTS_UPLOADED:      'Результаты выложены',
    PROTOCOL_ISSUED:       'Протокол готов',
    COMPLETED:             'Готово',
    REPLACEMENT_PROTOCOL:  'Замещающий протокол',
};

async function apiGet(url, params = {}) {
    const qs = new URLSearchParams(params).toString();
    const full = qs ? `${url}?${qs}` : url;
    const res = await fetch(full, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${full}`);
    return res.json();
}

function currentParams() {
    const p = { period: STATE.period };
    if (STATE.period === 'custom' && STATE.dateFrom && STATE.dateTo) {
        p.date_from = STATE.dateFrom;
        p.date_to = STATE.dateTo;
    }
    if (STATE.labId) p.lab_id = STATE.labId;
    return p;
}

/* ────── ФИЛЬТРЫ ────── */
async function loadLaboratories() {
    const { data } = await apiGet(API.laboratories);
    const sel = document.getElementById('lab-select');
    sel.innerHTML = data.map(l =>
        `<option value="${l.id}">${l.name}</option>`
    ).join('');
}

function initFilters() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            STATE.period = btn.dataset.period;
            document.getElementById('custom-range').style.display =
                (STATE.period === 'custom') ? 'flex' : 'none';
            if (STATE.period !== 'custom') loadAll();
        });
    });

    document.getElementById('date-from').addEventListener('change', (e) => {
        STATE.dateFrom = e.target.value;
        if (STATE.dateTo) loadAll();
    });
    document.getElementById('date-to').addEventListener('change', (e) => {
        STATE.dateTo = e.target.value;
        if (STATE.dateFrom) loadAll();
    });

    document.getElementById('lab-select').addEventListener('change', (e) => {
        STATE.labId = parseInt(e.target.value, 10) || 0;
        loadAll();
    });

    document.getElementById('refresh-btn').addEventListener('click', loadAll);
}

/* ────── KPI ────── */
const KPI_META = {
    total_samples:         { label: 'Всего образцов',    icon: 'fa-vials',         color: 'blue',   deltaGood: 'up' },
    completed:             { label: 'Завершено',         icon: 'fa-check-circle',  color: 'green',  deltaGood: 'up' },
    active_samples:        { label: 'В работе',          icon: 'fa-cog',           color: 'blue' },
    overdue_samples:       { label: 'Просрочено',        icon: 'fa-clock',         color: 'red',    deltaGood: 'down', alert: true },
    sla_pct:               { label: 'В срок, %',         icon: 'fa-bullseye',      color: 'green',  deltaGood: 'up',   suffix: '%' },
    median_test_hours:     { label: 'Медиана часов',     icon: 'fa-hourglass-half',color: 'purple', deltaGood: 'down', suffix: ' ч' },
    cancelled:             { label: 'Отменено',          icon: 'fa-ban',           color: 'orange', deltaGood: 'down' },
    replacement_samples:   { label: 'С ЗАМ-протоколом',  icon: 'fa-redo',          color: 'orange', deltaGood: 'down' },
    active_employees:      { label: 'Сотрудников',       icon: 'fa-users',         color: 'cyan' },
    equipment_operational: { label: 'Оборудования',      icon: 'fa-tools',         color: 'cyan' },
    equipment_expiring:    { label: 'Истекают поверки',  icon: 'fa-exclamation',   color: 'red',    deltaGood: 'down', alert: true },
    active_contracts:      { label: 'Активных договоров',icon: 'fa-file-contract', color: 'blue' },
    unique_clients:        { label: 'Заказчиков',        icon: 'fa-building',      color: 'purple', deltaGood: 'up' },
};

const DRILL_BY_KPI = {
    total_samples:       { title: 'Всего образцов',          params: {} },
    completed:           { title: 'Завершённые образцы',     params: { status: 'COMPLETED' } },
    active_samples:      { title: 'Образцы в работе',        params: { status_group: 'Испытание' } },
    overdue_samples:     { title: 'Просроченные образцы',    params: { overdue: '1' } },
    cancelled:           { title: 'Отменённые образцы',      params: { status: 'CANCELLED' } },
    replacement_samples: { title: 'Образцы с ЗАМ-протоколом',params: { replacement: '1' } },
};

function renderKpiCard(key, card) {
    const meta = KPI_META[key];
    if (!meta) return '';

    const v = card.value;
    const prev = card.previous;
    const delta = card.delta_pct;

    let valueStr;
    if (key === 'median_test_hours' || key === 'sla_pct') {
        valueStr = fmtFloat(v, 1) + (meta.suffix || '');
    } else {
        valueStr = fmtNum(v);
    }

    // Дельта: good / bad / flat — сопоставляем направление с deltaGood
    let deltaHtml = '';
    if (delta != null && prev != null) {
        const isFlat = Math.abs(delta) < 0.1;
        const isUp = delta > 0;
        let cls;
        if (isFlat) {
            cls = 'flat';
        } else if (meta.deltaGood === 'up') {
            cls = isUp ? 'good' : 'bad';
        } else if (meta.deltaGood === 'down') {
            cls = isUp ? 'bad' : 'good';
        } else {
            cls = 'flat';
        }
        const arrow = isFlat ? '→' : (isUp ? '↑' : '↓');
        deltaHtml = `<span class="kpi-delta ${cls}">${arrow} ${Math.abs(delta).toFixed(1)}%</span>`;
    }

    // Строка «было N» — показываем только для метрик с deltaGood (где сравнение имеет смысл)
    let previousHtml = '';
    if (prev != null && meta.deltaGood) {
        let prevStr;
        if (key === 'median_test_hours' || key === 'sla_pct') {
            prevStr = fmtFloat(prev, 1) + (meta.suffix || '');
        } else {
            prevStr = fmtNum(prev);
        }
        previousHtml = `<div class="kpi-previous">было ${prevStr}</div>`;
    }

    // Цветная иконка-бейдж (вариант Б — блок над label)
    const iconHtml = meta.icon
        ? `<div class="kpi-icon ${meta.color}"><i class="fas ${meta.icon}"></i></div>`
        : '';

    // Классы карточки: is-alert — красная вертикаль слева для тревожных метрик
    const clickable = !!DRILL_BY_KPI[key];
    const classes = ['kpi-card'];
    if (!clickable)  classes.push('non-clickable');
    if (meta.alert)  classes.push('is-alert');
    const dataAttr = clickable ? `data-drill-kpi="${key}"` : '';

    return `
        <div class="${classes.join(' ')}" ${dataAttr}>
            ${deltaHtml}
            ${iconHtml}
            <div class="kpi-label">${meta.label}</div>
            <div class="kpi-value">${valueStr}</div>
            ${previousHtml}
        </div>
    `;
}

async function loadKpi() {
    try {
        const { data } = await apiGet(API.kpi, currentParams());
        const container = document.getElementById('kpi-cards');
        // 10 карточек = 2 ряда по 5. Порядок: объём → производительность → ресурсы.
        const order = [
            // Ряд 1 — объём и SLA
            'total_samples', 'completed', 'active_samples', 'overdue_samples', 'sla_pct',
            // Ряд 2 — скорость и ресурсы
            'median_test_hours', 'replacement_samples',
            'active_employees', 'equipment_operational', 'equipment_expiring',
        ];
        container.innerHTML = order
            .filter(k => data[k])
            .map(k => renderKpiCard(k, data[k]))
            .join('');

        container.querySelectorAll('[data-drill-kpi]').forEach(el => {
            el.addEventListener('click', () => {
                const key = el.dataset.drillKpi;
                openDrillDown(DRILL_BY_KPI[key].title, DRILL_BY_KPI[key].params);
            });
        });
    } catch (e) {
        console.error('KPI error:', e);
    }
}

/* ────── ВОРОНКА ────── */
async function loadFunnel() {
    try {
        const { data } = await apiGet(API.funnel, currentParams());
        const max = Math.max(...data.map(s => s.count), 1);
        const container = document.getElementById('funnel-container');
        container.innerHTML = data.map(s => {
            const width = Math.max((s.count / max) * 100, 0);
            return `
                <div class="funnel-stage" data-stage="${s.stage}"
                     data-statuses='${JSON.stringify(s.statuses)}'>
                    <div class="funnel-label">${s.stage}</div>
                    <div class="funnel-bar-wrap">
                        <div class="funnel-bar" style="width: ${width}%"></div>
                        <div class="funnel-bar-value">${fmtNum(s.count)}</div>
                    </div>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.funnel-stage').forEach(el => {
            el.addEventListener('click', () => {
                const stage = el.dataset.stage;
                openDrillDown(`Этап: ${stage}`, { status_group: stage });
            });
        });
    } catch (e) {
        console.error('Funnel error:', e);
    }
}

/* ────── ГРАФИКИ ────── */
function destroyChart(key) {
    if (STATE.charts[key]) {
        STATE.charts[key].destroy();
        delete STATE.charts[key];
    }
}

const CHART_BASE = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { labels: { font: { size: 11 }, color: '#64748b' } },
        tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.92)',
            titleFont: { size: 12 },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 6,
        },
    },
    scales: {
        x: { ticks: { font: { size: 10 }, color: '#64748b' }, grid: { display: false } },
        y: { ticks: { font: { size: 10 }, color: '#64748b' }, grid: { color: 'rgba(0,0,0,0.05)' } },
    },
};

async function loadStageDurations() {
    // Пояснения к этапам — показываются в tooltip'е и в HTML-легенде под графиком
    const STAGE_HINT = {
        'Изготовление': 'От регистрации до завершения работы мастерской',
        'Испытание':    'Чистое время на стенде (start → end)',
        'Отчёт':        'От конца испытания до готового черновика',
        'Проверка СМК': 'Пока СМК проверяет протокол',
        'Оформление':   'От проверки СМК до выдачи протокола',
    };

    try {
        const { data } = await apiGet(API.stageDurations, currentParams());
        destroyChart('stage');
        STATE.charts.stage = new Chart(document.getElementById('stageDurationsChart'), {
            type: 'bar',
            data: {
                labels: data.map(r => r.stage),
                datasets: [{
                    label: 'Дней (медиана)',
                    data: data.map(r => Number(r.median_days) || 0),
                    backgroundColor: 'rgba(139, 92, 246, 0.7)',
                    borderRadius: 6,
                }],
            },
            options: {
                ...CHART_BASE,
                indexAxis: 'y',
                plugins: {
                    ...CHART_BASE.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...CHART_BASE.plugins.tooltip,
                        callbacks: {
                            title: (items) => items[0].label,
                            label: (ctx) => `Медиана: ${ctx.parsed.x} дн.`,
                            afterLabel: (ctx) => STAGE_HINT[ctx.label] || '',
                        },
                    },
                },
            },
        });
    } catch (e) { console.error('Stage durations error:', e); }
}

async function loadDailyDynamics() {
    try {
        const { data } = await apiGet(API.dailyDynamics, currentParams());
        destroyChart('daily');
        STATE.charts.daily = new Chart(document.getElementById('dailyDynamicsChart'), {
            type: 'line',
            data: {
                labels: data.map(r => r.date),
                datasets: [
                    {
                        label: 'Регистрации',
                        data: data.map(r => r.registrations),
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Завершения',
                        data: data.map(r => r.completions),
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.08)',
                        fill: true,
                        tension: 0.3,
                    },
                ],
            },
            options: CHART_BASE,
        });
    } catch (e) { console.error('Daily dynamics error:', e); }
}

async function loadMonthlyLabor() {
    try {
        const { data } = await apiGet(API.monthlyLabor, currentParams());
        destroyChart('monthly');
        STATE.charts.monthly = new Chart(document.getElementById('monthlyLaborChart'), {
            type: 'bar',
            data: {
                labels: data.map(r => r.month),
                datasets: [{
                    label: 'Образцов',
                    data: data.map(r => r.samples_count),
                    backgroundColor: 'rgba(0, 123, 255, 0.7)',
                    borderRadius: 6,
                }],
            },
            options: { ...CHART_BASE,
                plugins: { ...CHART_BASE.plugins, legend: { display: false } } },
        });
    } catch (e) { console.error('Monthly labor error:', e); }
}

async function loadStatusChart() {
    try {
        const { data } = await apiGet(API.funnel, currentParams());
        const palette = ['#60a5fa','#818cf8','#a78bfa','#06b6d4','#14b8a6','#10b981','#22c55e','#94a3b8','#f59e0b'];
        destroyChart('status');
        STATE.charts.status = new Chart(document.getElementById('statusChart'), {
            type: 'doughnut',
            data: {
                labels: data.map(r => r.stage),
                datasets: [{
                    data: data.map(r => r.count),
                    backgroundColor: palette,
                    borderWidth: 2,
                    borderColor: '#ffffff',
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { font: { size: 11 } } },
                    tooltip: CHART_BASE.plugins.tooltip,
                },
                cutout: '58%',
            },
        });
    } catch (e) { console.error('Status chart error:', e); }
}

async function loadReportTypeChart() {
    try {
        const { data } = await apiGet(API.reportTypeDist, currentParams());
        const LABEL = {
            PROTOCOL: 'Протокол',
            RESULTS_CLIENT: 'Результаты заказчику',
            PHOTO: 'Фото',
            GRAPHICS: 'Графики',
            RESULTS_SCIENCE: 'Результаты наука',
            WITHOUT_REPORT: 'Без отчётности',
        };
        destroyChart('reportType');
        STATE.charts.reportType = new Chart(document.getElementById('reportTypeChart'), {
            type: 'doughnut',
            data: {
                labels: data.map(r => LABEL[r.report_type] || r.report_type),
                datasets: [{
                    data: data.map(r => r.count),
                    backgroundColor: ['#007bff','#06b6d4','#8b5cf6','#10b981','#f59e0b','#94a3b8'],
                    borderWidth: 2,
                    borderColor: '#ffffff',
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { font: { size: 11 } } },
                    tooltip: {
                        ...CHART_BASE.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => ` ${ctx.label}: ${ctx.parsed} образцов`,
                            afterLabel: () => 'один образец может требовать несколько типов',
                        },
                    },
                },
                cutout: '58%',
            },
        });
    } catch (e) { console.error('Report type chart error:', e); }
}

/* ────── СПИСКИ РАСПРЕДЕЛЕНИЙ ────── */
function slaBadge(pct) {
    if (pct >= 90) return `<span class="sla-badge good">SLA ${pct.toFixed(0)}%</span>`;
    if (pct >= 70) return `<span class="sla-badge mid">SLA ${pct.toFixed(0)}%</span>`;
    return `<span class="sla-badge bad">SLA ${pct.toFixed(0)}%</span>`;
}

async function loadLabDistribution() {
    try {
        const { data } = await apiGet(API.labDistribution, currentParams());
        const max = Math.max(...data.map(r => r.samples_count), 1);
        const c = document.getElementById('lab-distribution');
        c.innerHTML = data.map(r => `
            <div class="dist-row" data-lab-id="${r.lab_id || 0}">
                <div class="dist-main">
                    <div class="dist-label">
                        <strong>${r.laboratory}</strong>
                        ${r.completed ? slaBadge(r.sla_pct) : ''}
                        <small>${r.code || ''}</small>
                    </div>
                    <div class="dist-bar-wrap">
                        <div class="dist-bar" style="width:${(r.samples_count/max)*100}%"></div>
                    </div>
                </div>
                <div class="dist-meta">
                    ${fmtNum(r.samples_count)}
                    <small>${r.median_test_hours ? `${fmtFloat(r.median_test_hours)} ч` : ''}</small>
                </div>
            </div>
        `).join('') || '<div class="empty-risk">Нет данных</div>';

        c.querySelectorAll('.dist-row').forEach(el => {
            el.addEventListener('click', () => {
                const labId = el.dataset.labId;
                const labName = el.querySelector('strong').textContent;
                openDrillDown(`Лаборатория: ${labName}`, labId !== '0' ? { lab_id: labId } : {});
            });
        });
    } catch (e) { console.error('Lab distribution error:', e); }
}

async function loadTestTypeDistribution() {
    try {
        const { data } = await apiGet(API.testTypeDist, currentParams());
        const max = Math.max(...data.map(r => r.count), 1);
        const c = document.getElementById('test-type-distribution');
        c.innerHTML = data.map(r => `
            <div class="dist-row" data-test-code="${r.test_code}">
                <div class="dist-main">
                    <div class="dist-label">
                        <strong>${r.test_code}</strong>
                        <small>${r.test_type}</small>
                    </div>
                    <div class="dist-bar-wrap">
                        <div class="dist-bar" style="width:${(r.count/max)*100}%"></div>
                    </div>
                </div>
                <div class="dist-meta">
                    ${fmtNum(r.count)}
                    <small>${r.median_test_hours ? `${fmtFloat(r.median_test_hours)} ч` : ''}</small>
                </div>
            </div>
        `).join('') || '<div class="empty-risk">Нет данных</div>';

        c.querySelectorAll('.dist-row').forEach(el => {
            el.addEventListener('click', () => {
                const code = el.dataset.testCode;
                openDrillDown(`Тип испытания: ${code}`, code !== '—' ? { test_code: code } : {});
            });
        });
    } catch (e) { console.error('Test type error:', e); }
}

/* ────── ТОПЫ ────── */
async function loadTopClients() {
    try {
        const { data } = await apiGet(API.topClients, { ...currentParams(), limit: 10 });
        const tbody = document.getElementById('top-clients-tbody');
        tbody.innerHTML = data.map(r => `
            <tr data-client-id="${r.client_id}" data-client-name="${r.client_name}">
                <td>${r.client_name}</td>
                <td class="num">${fmtNum(r.samples_count)}</td>
                <td class="num">${fmtNum(r.completed)}</td>
                <td class="num">${r.overdue ? `<span style="color:var(--red)">${fmtNum(r.overdue)}</span>` : '0'}</td>
            </tr>
        `).join('') || '<tr><td colspan="4" class="text-center text-muted">Нет данных</td></tr>';

        tbody.querySelectorAll('tr[data-client-id]').forEach(el => {
            el.addEventListener('click', () => {
                openDrillDown(`Заказчик: ${el.dataset.clientName}`,
                    { client_id: el.dataset.clientId });
            });
        });
    } catch (e) { console.error('Top clients error:', e); }
}

async function loadTopStandards() {
    try {
        const { data } = await apiGet(API.topStandards, { ...currentParams(), limit: 10 });
        const tbody = document.getElementById('top-standards-tbody');
        tbody.innerHTML = data.map(r => `
            <tr>
                <td style="font-family:var(--font-mono);font-size:11px">${r.standard_code}</td>
                <td>${r.standard_name}</td>
                <td class="num">${fmtNum(r.samples_count)}</td>
            </tr>
        `).join('') || '<tr><td colspan="3" class="text-center text-muted">Нет данных</td></tr>';
    } catch (e) { console.error('Top standards error:', e); }
}

/* ────── РИСКИ ────── */
function setRiskCount(elId, n) {
    const el = document.getElementById(elId);
    el.textContent = fmtNum(n);
    el.classList.toggle('zero', n === 0);
}

async function loadRisks() {
    const labParam = STATE.labId ? { lab_id: STATE.labId } : {};

    try {
        const { data } = await apiGet(API.riskStuck, { ...labParam, threshold: 30 });
        setRiskCount('stuck-count', data.length);
        const c = document.getElementById('risk-stuck');
        c.innerHTML = data.length ? data.map(r => `
            <div class="risk-row" data-sample-id="${r.id}">
                <div class="risk-row-main">
                    <div class="risk-row-title">${r.cipher}</div>
                    <div class="risk-row-sub">${r.lab_code} · ${STATUS_LABEL[r.status] || r.status}</div>
                </div>
                <div class="risk-row-num">${r.age_days} дн.</div>
            </div>
        `).join('') : '<div class="empty-risk"><i class="fas fa-check-circle"></i>Нет застрявших</div>';

        c.querySelectorAll('.risk-row').forEach(el => {
            el.addEventListener('click', () => {
                window.location.href = window.ANALYTICS_CONFIG.sampleDetailUrlTemplate
                    .replace('{id}', el.dataset.sampleId);
            });
        });
    } catch (e) { console.error('Stuck error:', e); }

    try {
        const { data } = await apiGet(API.riskEquipment, { ...labParam, days: 30 });
        setRiskCount('expiring-count', data.length);
        const c = document.getElementById('risk-equipment');
        c.innerHTML = data.length ? data.map(r => `
            <div class="risk-row">
                <div class="risk-row-main">
                    <div class="risk-row-title">${r.name}</div>
                    <div class="risk-row-sub">${r.accounting_number} · ${r.lab_code || '—'}</div>
                </div>
                <div class="risk-row-num">${r.days_left} дн.</div>
            </div>
        `).join('') : '<div class="empty-risk"><i class="fas fa-check-circle"></i>Все поверки актуальны</div>';
    } catch (e) { console.error('Equipment risk error:', e); }

    try {
        const { data } = await apiGet(API.riskReplacement, currentParams());
        setRiskCount('replacement-count', data.length);
        const c = document.getElementById('risk-replacement');
        c.innerHTML = data.length ? data.map(r => `
            <div class="risk-row" data-sample-id="${r.id}">
                <div class="risk-row-main">
                    <div class="risk-row-title">${r.cipher}</div>
                    <div class="risk-row-sub">${r.lab_code} · ${r.client_name}</div>
                </div>
                <div class="risk-row-num">×${r.replacement_count}</div>
            </div>
        `).join('') : '<div class="empty-risk"><i class="fas fa-check-circle"></i>Нет ЗАМ-протоколов</div>';

        c.querySelectorAll('.risk-row').forEach(el => {
            el.addEventListener('click', () => {
                window.location.href = window.ANALYTICS_CONFIG.sampleDetailUrlTemplate
                    .replace('{id}', el.dataset.sampleId);
            });
        });
    } catch (e) { console.error('Replacement error:', e); }
}

/* ────── DRILL-DOWN ПАНЕЛЬ ────── */
function initDrillDown() {
    document.getElementById('drilldown-close').addEventListener('click', closeDrillDown);
    document.getElementById('drilldown-overlay').addEventListener('click', closeDrillDown);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDrillDown();
    });
}

function closeDrillDown() {
    document.getElementById('drilldown-panel').classList.remove('open');
    document.getElementById('drilldown-overlay').classList.remove('open');
    document.body.style.overflow = '';
}

async function openDrillDown(title, extraParams = {}) {
    const panel = document.getElementById('drilldown-panel');
    const overlay = document.getElementById('drilldown-overlay');
    const titleEl = document.getElementById('drilldown-title');
    const subtitleEl = document.getElementById('drilldown-subtitle');
    const body = document.getElementById('drilldown-body');
    const footer = document.getElementById('drilldown-footer');

    titleEl.textContent = title;
    subtitleEl.textContent = 'Загрузка...';
    body.innerHTML = '<div class="loading-placeholder">Загрузка...</div>';
    footer.textContent = '';

    panel.classList.add('open');
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';

    const params = { ...currentParams(), ...extraParams, limit: 50 };

    try {
        const { data, meta } = await apiGet(API.drillDown, params);
        subtitleEl.textContent =
            `${fmtDate(meta.date_from)} — ${fmtDate(meta.date_to)} · всего: ${fmtNum(meta.total)}`;

        if (!data.length) {
            body.innerHTML = '<div class="empty-risk">Образцов не найдено</div>';
            return;
        }

        body.innerHTML = data.map(s => {
            const url = window.ANALYTICS_CONFIG.sampleDetailUrlTemplate.replace('{id}', s.id);
            return `
                <a href="${url}" class="drill-sample">
                    <div class="drill-sample-flag ${s.sla_flag}"></div>
                    <div class="drill-sample-body">
                        <div class="drill-sample-title">${s.cipher}</div>
                        <div class="drill-sample-meta">
                            <span>${s.lab_code}</span>
                            <span>${s.client_name}</span>
                            <span>рег: ${fmtDate(s.registration_date)}</span>
                            ${s.deadline ? `<span>до: ${fmtDate(s.deadline)}</span>` : ''}
                        </div>
                    </div>
                    <div class="drill-sample-status">${STATUS_LABEL[s.status] || s.status}</div>
                </a>
            `;
        }).join('');

        footer.textContent = `Показано ${data.length} из ${meta.total}${meta.total > 50 ? ' (первые 50)' : ''}`;
    } catch (e) {
        body.innerHTML = `<div class="empty-risk">Ошибка: ${e.message}</div>`;
    }
}

/* ────── ЗАГРУЗКА ВСЕГО ────── */
function updateLastUpdated() {
    STATE.lastLoadedAt = new Date();
    tickLastUpdated();
}

function tickLastUpdated() {
    if (!STATE.lastLoadedAt) return;
    const s = Math.round((Date.now() - STATE.lastLoadedAt.getTime()) / 1000);
    const el = document.getElementById('last-updated');
    if (s < 60) el.textContent = `обновлено ${s}с назад`;
    else if (s < 3600) el.textContent = `обновлено ${Math.round(s/60)}м назад`;
    else el.textContent = `обновлено ${Math.round(s/3600)}ч назад`;
}

async function loadAll() {
    await Promise.all([
        loadKpi(),
        loadFunnel(),
        loadStageDurations(),
        loadDailyDynamics(),
        loadMonthlyLabor(),
        loadStatusChart(),
        loadReportTypeChart(),
        loadLabDistribution(),
        loadTestTypeDistribution(),
        loadTopClients(),
        loadTopStandards(),
        loadRisks(),
    ]);
    updateLastUpdated();
}

/* ────── ИНИЦИАЛИЗАЦИЯ ────── */
document.addEventListener('DOMContentLoaded', async () => {
    initFilters();
    initDrillDown();
    await loadLaboratories();
    await loadAll();
    setInterval(tickLastUpdated, 15000);
});
/* ============================================================
   ANALYTICS EMPLOYEES — страница производительности сотрудников
   ============================================================ */

const API = {
    laboratories:  '/workspace/analytics/api/laboratories',
    overview:      '/workspace/analytics/api/employees/overview',
    leaderboard:   '/workspace/analytics/api/employees/leaderboard',
    heatmap:       '/workspace/analytics/api/employees/heatmap',
};

const STATE = {
    period: 'month',
    dateFrom: null,
    dateTo: null,
    labId: 0,
    role: 'TESTER',
    hideTrainees: false,
    heatmapMode: 'testing',             // testing | registration | verification | protocols
    heatmapGranularity: 'week',         // week | day
    lastLoadedAt: null,
    currentRows: [],
    sortBy: null,
    sortDir: 'desc',
};

/* ────── Утилиты ────── */
const fmt = new Intl.NumberFormat('ru-RU');
const fmtNum = (n) => (n == null ? '—' : fmt.format(n));
const fmtFloat = (n, d = 1) =>
    (n == null ? '—' : Number(n).toFixed(d).replace('.', ','));
const fmtPct = (n) => (n == null ? '—' : Number(n).toFixed(1).replace('.', ',') + '%');

/* ────── Хелперы для подписей дат в heatmap ────── */
// Родительный падеж («3 мая», «23 апреля» — так говорят по-русски)
const MONTHS_SHORT_RU = [
    'янв.', 'фев.', 'мар.', 'апр.', 'мая', 'июня',
    'июля', 'авг.', 'сен.', 'окт.', 'ноя.', 'дек.',
];

/**
 * Подпись одной ячейки heatmap.
 * bucket — строка 'YYYY-MM-DD' (понедельник недели ИЛИ сам день).
 * granularity — 'week' | 'day'.
 *
 *   week:  '2026-04-20' → '20 — 26 апр'       (понедельник → воскресенье)
 *          '2026-04-27' → '27 апр — 3 мая'    (пересекает границу месяца)
 *   day:   '2026-04-23' → '23 апр'
 */
function formatBucketLabel(bucket, granularity) {
    if (!bucket) return '—';
    const parts = bucket.split('-');
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const start = new Date(Date.UTC(year, month, day));

    if (granularity === 'day') {
        return `${start.getUTCDate()} ${MONTHS_SHORT_RU[start.getUTCMonth()]}`;
    }

    // Неделя: начало (bucket) + 6 дней = воскресенье
    const end = new Date(start);
    end.setUTCDate(end.getUTCDate() + 6);

    const d1 = start.getUTCDate();
    const m1 = start.getUTCMonth();
    const d2 = end.getUTCDate();
    const m2 = end.getUTCMonth();

    if (m1 === m2) {
        // В рамках одного месяца: '20 — 26 апр'
        return `${d1} — ${d2} ${MONTHS_SHORT_RU[m2]}`;
    }
    // Пересекает границу месяца: '27 апр — 3 мая'
    return `${d1} ${MONTHS_SHORT_RU[m1]} — ${d2} ${MONTHS_SHORT_RU[m2]}`;
}

function fullName(u) {
    const parts = [u.last_name, u.first_name].filter(Boolean);
    const s = parts.join(' ');
    return u.sur_name ? `${s} ${u.sur_name}` : s;
}
function shortName(u) {
    return u.last_name + (u.first_name ? ' ' + u.first_name[0] + '.' : '');
}

async function apiGet(url, params = {}) {
    const qs = new URLSearchParams(params).toString();
    const full = qs ? `${url}?${qs}` : url;
    const res = await fetch(full, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${full}`);
    return res.json();
}

function currentParams() {
    const p = { period: STATE.period, role: STATE.role };
    if (STATE.period === 'custom' && STATE.dateFrom && STATE.dateTo) {
        p.date_from = STATE.dateFrom;
        p.date_to = STATE.dateTo;
    }
    if (STATE.labId) p.lab_id = STATE.labId;
    if (STATE.hideTrainees) p.hide_trainees = '1';
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

    document.getElementById('hide-trainees').addEventListener('change', (e) => {
        STATE.hideTrainees = e.target.checked;
        loadAll();
    });

    document.getElementById('refresh-btn').addEventListener('click', loadAll);
}

/* ────── ТАБЫ РОЛЕЙ ────── */
const ROLE_TITLES = {
    TESTER:   'Испытатели',
    WORKSHOP: 'Мастерская',
    CLIENT:   'Отдел клиентов',
    LAB_HEAD: 'Заведующие лабораториями',
};

// Наборы кнопок режима heatmap по роли. Первый элемент — режим по умолчанию.
const HEATMAP_MODES_BY_ROLE = {
    TESTER: [
        { mode: 'testing',   label: 'Испытания' },
        { mode: 'protocols', label: 'Протоколы' },
    ],
    CLIENT: [
        { mode: 'registration', label: 'Регистрации' },
        { mode: 'verification', label: 'Проверки' },
    ],
};

// Подписи: ядро названия метрики (без слова «неделя»/«день») — склеиваем на лету
const HEATMAP_LABELS = {
    testing:      { noun: 'Завершённые испытания',    unit: 'испытаний' },
    protocols:    { noun: 'Подготовленные протоколы', unit: 'готовых протоколов' },
    registration: { noun: 'Регистрации образцов',     unit: 'зарегистрированных образцов' },
    verification: { noun: 'Проверки регистрации',     unit: 'проверенных регистраций' },
};

function updateHeatmapForRole() {
    const modeSwitch = document.getElementById('heatmap-mode');
    const section = document.getElementById('heatmap-section');

    const modes = HEATMAP_MODES_BY_ROLE[STATE.role];
    if (!modes) {
        // Роли без heatmap (мастерская, завлабы) — прячем всю секцию
        section.style.display = 'none';
        return;
    }

    section.style.display = '';
    STATE.heatmapMode = modes[0].mode;

    // Отрисовываем кнопки переключателя
    modeSwitch.innerHTML = modes.map((m, i) =>
        `<button class="preset-btn${i === 0 ? ' active' : ''}" data-mode="${m.mode}">${m.label}</button>`
    ).join('');
    modeSwitch.style.display = 'flex';

    updateHeatmapHeader();
}

function updateHeatmapHeader() {
    const header = document.getElementById('heatmap-header');
    const hint = document.getElementById('heatmap-hint');
    const labels = HEATMAP_LABELS[STATE.heatmapMode] || HEATMAP_LABELS.testing;
    const unit = STATE.heatmapGranularity === 'day' ? 'дням' : 'неделям';
    const cellUnit = STATE.heatmapGranularity === 'day' ? 'день' : 'неделю';
    header.innerHTML = `<i class="fas fa-th"></i> ${labels.noun} по ${unit}`;
    hint.textContent = `Клеточка — число ${labels.unit} за ${cellUnit}`;
}

function initRoleTabs() {
    document.querySelectorAll('.role-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.role-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            STATE.role = tab.dataset.role;
            STATE.sortBy = null;
            document.getElementById('leaderboard-title').innerHTML =
                `<i class="fas fa-list-ol"></i> ${ROLE_TITLES[STATE.role] || STATE.role}`;
            updateHeatmapForRole();
            loadAll();
        });
    });

    // Делегирование: обработчик на контейнере ловит клики по любым .preset-btn
    // внутри, в том числе по динамически создаваемым
    document.getElementById('heatmap-mode').addEventListener('click', (e) => {
        const btn = e.target.closest('.preset-btn');
        if (!btn) return;
        document.querySelectorAll('#heatmap-mode .preset-btn')
            .forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        STATE.heatmapMode = btn.dataset.mode;
        updateHeatmapHeader();
        loadHeatmap();
    });

    // Переключатель гранулярности «Недели / Дни»
    document.getElementById('heatmap-granularity').addEventListener('click', (e) => {
        const btn = e.target.closest('.preset-btn');
        if (!btn) return;
        document.querySelectorAll('#heatmap-granularity .preset-btn')
            .forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        STATE.heatmapGranularity = btn.dataset.granularity;
        updateHeatmapHeader();
        loadHeatmap();
    });
}

/* ────── ОВЕРВЬЮ (5 KPI) ────── */
async function loadOverview() {
    try {
        const { data } = await apiGet(API.overview, currentParams());
        const container = document.getElementById('overview-kpi');

        if (data.role === 'CLIENT') {
            container.innerHTML = `
                ${renderKpi('blue',   'fa-users',           'Всего в отделе',          fmtNum(data.total_in_dept))}
                ${renderKpi('green',  'fa-user-check',      'Активных за период',      fmtNum(data.active_in_period))}
                ${renderKpi('purple', 'fa-clipboard-list',  'Зарегистрировано',        fmtNum(data.samples_registered))}
                ${renderKpi('cyan',   'fa-clipboard-check', 'Проверок регистрации',    fmtNum(data.verifications_done))}
            `;
            return;
        }

        // TESTER и все остальные — испытательский набор
        const cvLabel = cvDescription(data.load_cv);
        container.innerHTML = `
            ${renderKpi('blue',   'fa-users',          'Всего испытателей',       fmtNum(data.total_testers))}
            ${renderKpi('green',  'fa-user-check',     'Активных за период',      fmtNum(data.active_testers))}
            ${renderKpi('purple', 'fa-chart-bar',      'Медиана образцов / чел.', fmtFloat(data.median_samples_per_tester, 1))}
            ${renderKpi('cyan',   'fa-bullseye',       'Средний SLA',             fmtPct(data.avg_sla_pct))}
            ${renderKpi('orange', 'fa-balance-scale',  'Равномерность загрузки',  fmtFloat(data.load_cv, 2), cvLabel)}
        `;
    } catch (e) {
        console.error('Overview error:', e);
    }
}

function renderKpi(color, icon, label, value, hint = '') {
    const hintHtml = hint ? `<div class="kpi-previous">${hint}</div>` : '';
    return `
        <div class="kpi-card non-clickable">
            <div class="kpi-icon ${color}"><i class="fas ${icon}"></i></div>
            <div class="kpi-label">${label}</div>
            <div class="kpi-value">${value}</div>
            ${hintHtml}
        </div>
    `;
}

function cvDescription(cv) {
    if (cv == null) return '';
    if (cv < 0.3)  return 'равномерно';
    if (cv < 0.6)  return 'умеренно';
    if (cv < 1.0)  return 'неравномерно';
    return 'очень неравномерно';
}

/* ────── ЛИДЕРБОРД ────── */

// Описания колонок для каждой роли: ключ поля + заголовок + тип + сортировка
const COLUMNS_BY_ROLE = {
    TESTER: [
        { key: 'name',                     label: 'Сотрудник',     sortable: true,  type: 'name' },
        { key: 'lab_code',                 label: 'Лаб',           sortable: true,  type: 'text' },
        { key: 'samples_total',            label: 'Образцов',      sortable: true,  type: 'num' },
        { key: 'samples_protocols_ready',  label: 'Протоколов',    sortable: true,  type: 'num' },
        { key: 'sla_pct',                  label: 'SLA',           sortable: true,  type: 'sla' },
        { key: 'median_test_hours',        label: 'Медиана часов', sortable: true,  type: 'float' },
        { key: 'samples_with_replacement', label: 'С ЗАМ',         sortable: true,  type: 'num' },
        { key: 'unique_standards',         label: 'Стандартов',    sortable: true,  type: 'num' },
    ],
    WORKSHOP: [
        { key: 'name',                      label: 'Сотрудник',       sortable: true,  type: 'name' },
        { key: 'lab_code',                  label: 'Лаб',             sortable: true,  type: 'text' },
        { key: 'samples_manufactured',      label: 'Изготовлено',     sortable: true,  type: 'num' },
        { key: 'median_manufacturing_days', label: 'Медиана дней',    sortable: true,  type: 'float' },
    ],
    CLIENT: [
        { key: 'name',                       label: 'Сотрудник',             sortable: true,  type: 'name' },
        { key: 'samples_registered',         label: 'Зарегистрировано',      sortable: true,  type: 'num' },
        { key: 'verifications_done',         label: 'Проверок',              sortable: true,  type: 'num' },
        { key: 'median_verification_hours',  label: 'Медиана часов проверки', sortable: true,  type: 'float' },
        { key: 'cancelled_after',            label: 'Отменено после',        sortable: true,  type: 'num' },
    ],
    LAB_HEAD: [
        { key: 'name',                     label: 'Сотрудник',     sortable: true,  type: 'name' },
        { key: 'lab_code',                 label: 'Лаб',           sortable: true,  type: 'text' },
        { key: 'samples_total',            label: 'Образцов',      sortable: true,  type: 'num' },
        { key: 'samples_completed',        label: 'Готово',        sortable: true,  type: 'num' },
        { key: 'sla_pct',                  label: 'SLA',           sortable: true,  type: 'sla' },
    ],
};

function renderTableHead(columns) {
    return '<tr>' + columns.map(c => {
        const isActive = STATE.sortBy === c.key;
        const cls = [
            c.type === 'num' || c.type === 'float' || c.type === 'sla' ? 'num' : '',
            isActive ? 'sort-active' : '',
        ].filter(Boolean).join(' ');
        const arrow = isActive ? (STATE.sortDir === 'asc' ? ' ↑' : ' ↓') : '';
        return `<th class="${cls}" data-sort-key="${c.key}">${c.label}${arrow}</th>`;
    }).join('') + '</tr>';
}

function cellHtml(row, col) {
    if (col.type === 'name') {
        const name = fullName(row) || '—';
        const badge = row.is_trainee ? '<span class="trainee-badge">стажёр</span>' : '';
        return `<td>${name}${badge}${row.position ? `<div class="small-text">${row.position}</div>` : ''}</td>`;
    }
    if (col.type === 'text') {
        return `<td>${row[col.key] ?? '—'}</td>`;
    }
    if (col.type === 'num') {
        const v = row[col.key];
        if (v == null || v === 0) return `<td class="num dim">${v === 0 ? '0' : '—'}</td>`;
        return `<td class="num">${fmtNum(v)}</td>`;
    }
    if (col.type === 'float') {
        const v = row[col.key];
        return `<td class="num">${v == null ? '<span class="dim">—</span>' : fmtFloat(v, 1)}</td>`;
    }
    if (col.type === 'sla') {
        const v = row[col.key];
        if (v == null) return '<td class="num dim">—</td>';
        const bucket = v >= 90 ? 'good' : v >= 70 ? 'mid' : 'bad';
        return `
            <td class="num">
                <span class="sla-cell">
                    <span class="sla-bar"><span class="sla-bar-fill ${bucket}" style="width:${Math.min(100, v)}%"></span></span>
                    ${fmtPct(v)}
                </span>
            </td>
        `;
    }
    return `<td>${row[col.key] ?? '—'}</td>`;
}

function sortRows(rows, key, dir) {
    const multiplier = dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
        let av = (key === 'name') ? fullName(a) : a[key];
        let bv = (key === 'name') ? fullName(b) : b[key];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;   // NULL в конец при любой сортировке
        if (bv == null) return -1;
        if (typeof av === 'string') return av.localeCompare(bv, 'ru') * multiplier;
        return (av - bv) * multiplier;
    });
}

function renderLeaderboard() {
    const columns = COLUMNS_BY_ROLE[STATE.role];
    document.getElementById('employees-thead').innerHTML = renderTableHead(columns);

    let rows = STATE.currentRows;
    if (STATE.sortBy) {
        rows = sortRows(rows, STATE.sortBy, STATE.sortDir);
    }

    const tbody = document.getElementById('employees-tbody');
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="${columns.length}" class="text-center dim" style="padding: 40px 16px;">Нет данных за выбранный период</td></tr>`;
        return;
    }

    tbody.innerHTML = rows.map(r => {
        const cells = columns.map(c => cellHtml(r, c)).join('');
        return `<tr data-user-id="${r.id}">${cells}</tr>`;
    }).join('');

    // Клик на строку — переход в профиль
    tbody.querySelectorAll('tr[data-user-id]').forEach(el => {
        el.addEventListener('click', () => {
            const id = el.dataset.userId;
            window.location.href =
                window.ANALYTICS_CONFIG.employeeDetailUrlTemplate.replace('{id}', id);
        });
    });

    // Клик на заголовок — сортировка
    document.querySelectorAll('#employees-thead th[data-sort-key]').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.dataset.sortKey;
            if (STATE.sortBy === key) {
                STATE.sortDir = STATE.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                STATE.sortBy = key;
                STATE.sortDir = 'desc';
            }
            renderLeaderboard();
        });
    });
}

async function loadLeaderboard() {
    try {
        const { data } = await apiGet(API.leaderboard, currentParams());
        STATE.currentRows = data || [];
        renderLeaderboard();
    } catch (e) {
        console.error('Leaderboard error:', e);
        document.getElementById('employees-tbody').innerHTML =
            `<tr><td colspan="8" class="text-center dim">Ошибка: ${e.message}</td></tr>`;
    }
}

/* ────── HEATMAP ────── */
async function loadHeatmap() {
    // Heatmap — для TESTER (испытания/протоколы) и CLIENT (регистрации/проверки).
    // Остальные роли его не показывают.
    if (STATE.role !== 'TESTER' && STATE.role !== 'CLIENT') return;
    try {
        const { data } = await apiGet(API.heatmap, {
            ...currentParams(),
            granularity: STATE.heatmapGranularity,
            mode: STATE.heatmapMode,
        });
        renderHeatmap(data);
    } catch (e) {
        console.error('Heatmap error:', e);
    }
}

function renderHeatmap(rows) {
    const grid = document.getElementById('heatmap-grid');

    if (!rows.length) {
        grid.innerHTML = '<div class="empty-risk" style="grid-column: 1/-1">Нет данных за период</div>';
        grid.style.gridTemplateColumns = '1fr';
        return;
    }

    // Собираем уникальных пользователей и недели
    const userMap = new Map();
    const weekSet = new Set();
    rows.forEach(r => {
        if (!userMap.has(r.user_id)) {
            userMap.set(r.user_id, {
                id: r.user_id,
                name: r.display_name,
                is_trainee: r.is_trainee,
                cells: {},
            });
        }
        userMap.get(r.user_id).cells[r.bucket] = r.samples;
        weekSet.add(r.bucket);
    });

    const users = [...userMap.values()].sort((a, b) => {
        const sumA = Object.values(a.cells).reduce((s, v) => s + v, 0);
        const sumB = Object.values(b.cells).reduce((s, v) => s + v, 0);
        return sumB - sumA;
    });
    const weeks = [...weekSet].sort();

    // Определяем максимум для раскраски (по квантилям — чтобы выбросы не съели шкалу)
    const allValues = rows.map(r => r.samples).filter(v => v > 0).sort((a, b) => a - b);
    const max = allValues.length
        ? allValues[Math.floor(allValues.length * 0.95)]  // 95-й процентиль
        : 10;

    // Формируем grid: 1 колонка имени + N колонок периодов.
    // Для дневной гранулярности колонкам нужна большая минимальная ширина
    // (подпись «23 апр» шире, чем «20 — 26»).
    const colMinWidth = STATE.heatmapGranularity === 'day' ? '48px' : '64px';
    grid.style.gridTemplateColumns = `auto repeat(${weeks.length}, minmax(${colMinWidth}, 1fr))`;

    let html = '';

    // Header row: пустой угол + подписи периодов
    html += '<div class="heatmap-name" style="font-weight: 600; background: var(--surface)">Сотрудник</div>';
    weeks.forEach(w => {
        const label = formatBucketLabel(w, STATE.heatmapGranularity);
        html += `<div class="heatmap-header">${label}</div>`;
    });

    // Rows: имя сотрудника + ячейки
    users.forEach(u => {
        const traineeBadge = u.is_trainee ? ' <span class="trainee-badge">стажёр</span>' : '';
        html += `<div class="heatmap-name">${u.name}${traineeBadge}</div>`;
        weeks.forEach(w => {
            const label = formatBucketLabel(w, STATE.heatmapGranularity);
            const v = u.cells[w] || 0;
            if (v === 0) {
                html += `<div class="heatmap-cell empty" title="${u.name}, ${label}: 0"></div>`;
            } else {
                const pct = Math.min(1, v / max);
                let level = 'h1';
                if (pct > 0.8) level = 'h5';
                else if (pct > 0.6) level = 'h4';
                else if (pct > 0.4) level = 'h3';
                else if (pct > 0.2) level = 'h2';
                const tooltipPrefix = STATE.heatmapGranularity === 'day' ? 'день' : 'неделя';
                html += `<div class="heatmap-cell ${level}" title="${u.name}, ${tooltipPrefix} ${label}: ${v}">${v}</div>`;
            }
        });
    });

    grid.innerHTML = html;
}

/* ────── LAST-UPDATED ТИКЕР ────── */
function updateLastUpdated() {
    STATE.lastLoadedAt = new Date();
    tickLastUpdated();
}
function tickLastUpdated() {
    if (!STATE.lastLoadedAt) return;
    const s = Math.round((Date.now() - STATE.lastLoadedAt.getTime()) / 1000);
    const el = document.getElementById('last-updated');
    if (s < 60) el.textContent = `обновлено ${s} с назад`;
    else if (s < 3600) el.textContent = `обновлено ${Math.round(s/60)} мин назад`;
    else el.textContent = `обновлено ${Math.round(s/3600)} ч назад`;
}

/* ────── ЗАГРУЗКА ВСЕГО ────── */
async function loadAll() {
    await Promise.all([
        loadOverview(),
        loadLeaderboard(),
        loadHeatmap(),
    ]);
    updateLastUpdated();
}

/* ────── ИНИЦИАЛИЗАЦИЯ ────── */
document.addEventListener('DOMContentLoaded', async () => {
    initFilters();
    initRoleTabs();
    updateHeatmapForRole();           // сразу отрисовать переключатель для дефолтной роли
    await loadLaboratories();
    await loadAll();
    setInterval(tickLastUpdated, 15000);
});
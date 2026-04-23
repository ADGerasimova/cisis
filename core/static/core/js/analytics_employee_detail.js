/* ============================================================
   ANALYTICS EMPLOYEE DETAIL — страница профиля сотрудника
   ============================================================ */

const API = {
    detail: '/workspace/analytics/api/employees',  // + /{id}/detail
};

const STATE = {
    userId: window.ANALYTICS_CONFIG.targetUserId,
    period: 'month',
    dateFrom: null,
    dateTo: null,
    chart: null,
    lastLoadedAt: null,
};

/* ────── Утилиты ────── */
const fmt = new Intl.NumberFormat('ru-RU');
const fmtNum = (n) => (n == null ? '—' : fmt.format(n));
const fmtFloat = (n, d = 1) =>
    (n == null ? '—' : Number(n).toFixed(d).replace('.', ','));
const fmtPct = (n) => (n == null ? '—' : Number(n).toFixed(1).replace('.', ',') + '%');

const ROLE_LABEL = {
    CEO: 'Генеральный директор',
    CTO: 'Технический директор',
    SYSADMIN: 'Системный администратор',
    LAB_HEAD: 'Заведующий лабораторией',
    TESTER: 'Испытатель',
    CLIENT_DEPT_HEAD: 'Руководитель отдела заказчиков',
    CLIENT_MANAGER: 'Специалист по работе с заказчиками',
    CONTRACT_SPEC: 'Специалист по договорам',
    QMS_HEAD: 'Руководитель СМК',
    QMS_ADMIN: 'Администратор СМК',
    METROLOGIST: 'Метролог',
    WORKSHOP_HEAD: 'Начальник мастерской',
    WORKSHOP: 'Сотрудник мастерской',
    ACCOUNTANT: 'Бухгалтер',
    OTHER: 'Прочий',
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
    return p;
}

function initFilters() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            STATE.period = btn.dataset.period;
            document.getElementById('custom-range').style.display =
                (STATE.period === 'custom') ? 'flex' : 'none';
            if (STATE.period !== 'custom') loadDetail();
        });
    });

    document.getElementById('date-from').addEventListener('change', (e) => {
        STATE.dateFrom = e.target.value;
        if (STATE.dateTo) loadDetail();
    });
    document.getElementById('date-to').addEventListener('change', (e) => {
        STATE.dateTo = e.target.value;
        if (STATE.dateFrom) loadDetail();
    });

    document.getElementById('refresh-btn').addEventListener('click', loadDetail);
}

/* ────── Инициалы в аватар ────── */
function initials(lastName, firstName) {
    const a = (firstName || '').trim()[0] || '';
    const b = (lastName || '').trim()[0] || '';
    return (a + b).toUpperCase() || '?';
}

/* ────── РЕНДЕР ────── */
function renderProfile(user) {
    document.title = `${user.last_name || ''} ${user.first_name || ''} — Профиль`;

    document.getElementById('employee-avatar').textContent =
        initials(user.last_name, user.first_name);

    const full = [user.last_name, user.first_name, user.sur_name]
        .filter(Boolean).join(' ');

    const nameHtml = full + (user.is_trainee
        ? ' <span class="trainee-badge">стажёр</span>'
        : '');
    document.getElementById('employee-fullname').innerHTML = nameHtml;

    const meta = [];
    if (user.position) meta.push(`<span class="employee-meta-item">${user.position}</span>`);
    if (user.role) meta.push(`<span class="employee-meta-item">${ROLE_LABEL[user.role] || user.role}</span>`);
    if (user.lab_name) meta.push(`<span class="employee-meta-item">${user.lab_code || ''} · ${user.lab_name}</span>`);
    if (!user.is_active) meta.push('<span class="employee-meta-item" style="color:var(--red)">Неактивен</span>');

    document.getElementById('employee-meta').innerHTML = meta.join('');
    document.getElementById('breadcrumb').textContent = full;
}

function renderKpi(color, icon, label, value) {
    return `
        <div class="kpi-card non-clickable">
            <div class="kpi-icon ${color}"><i class="fas ${icon}"></i></div>
            <div class="kpi-label">${label}</div>
            <div class="kpi-value">${value}</div>
        </div>
    `;
}

function renderTotals(totals) {
    const container = document.getElementById('employee-kpi');
    container.innerHTML = `
        ${renderKpi('blue',   'fa-vials',           'Образцов',         fmtNum(totals.samples_total))}
        ${renderKpi('green',  'fa-file-signature', 'Протоколов',       fmtNum(totals.protocols_ready))}
        ${renderKpi('cyan',   'fa-bullseye',       'SLA',              fmtPct(totals.sla_pct))}
        ${renderKpi('purple', 'fa-hourglass-half', 'Медиана часов',    fmtFloat(totals.median_test_hours))}
        ${renderKpi('orange', 'fa-redo',           'С ЗАМ-протоколом', fmtNum(totals.with_replacement))}
    `;
}

function renderDynamics(rows) {
    if (STATE.chart) { STATE.chart.destroy(); STATE.chart = null; }

    if (!rows.length) {
        const canvas = document.getElementById('dynamicsChart');
        const parent = canvas.parentElement;
        parent.innerHTML = '<div class="empty-risk">Нет данных за последние 6 месяцев</div>';
        return;
    }

    STATE.chart = new Chart(document.getElementById('dynamicsChart'), {
        type: 'line',
        data: {
            labels: rows.map(r => r.month),
            datasets: [{
                label: 'Образцов',
                data: rows.map(r => r.samples),
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.10)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#2563eb',
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.92)',
                    padding: 10, cornerRadius: 6,
                },
            },
            scales: {
                x: { ticks: { font: { size: 10 }, color: '#64748b' }, grid: { display: false } },
                y: {
                    ticks: { font: { size: 10 }, color: '#64748b' },
                    grid: { color: 'rgba(0, 0, 0, 0.05)' },
                    beginAtZero: true,
                },
            },
        },
    });
}

function renderStandards(rows) {
    const tbody = document.getElementById('top-standards-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center dim" style="padding: 24px;">Нет данных</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => `
        <tr>
            <td style="font-family: var(--font-mono); font-size: 11px;">${r.code}</td>
            <td>${r.name}</td>
            <td class="num">${fmtNum(r.samples_count)}</td>
        </tr>
    `).join('');
}

function renderLongest(rows) {
    const tbody = document.getElementById('longest-samples-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center dim" style="padding: 24px;">Нет данных</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => {
        const overDl = r.days_over_deadline;
        const overDlHtml = (overDl == null || overDl <= 0)
            ? '<span class="dim">—</span>'
            : `<span style="color: var(--red); font-weight: 600">+${overDl} дн.</span>`;
        return `
            <tr data-sample-id="${r.id}">
                <td style="font-family: var(--font-mono); font-size: 11px;">${r.cipher}</td>
                <td class="num">${fmtFloat(r.test_hours)}</td>
                <td class="num">${overDlHtml}</td>
            </tr>
        `;
    }).join('');

    tbody.querySelectorAll('tr[data-sample-id]').forEach(el => {
        el.addEventListener('click', () => {
            window.location.href = window.ANALYTICS_CONFIG.sampleDetailUrlTemplate
                .replace('{id}', el.dataset.sampleId);
        });
    });
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

/* ────── ЗАГРУЗКА ─── */
async function loadDetail() {
    try {
        const url = `${API.detail}/${STATE.userId}/detail`;
        const { data } = await apiGet(url, currentParams());
        renderProfile(data.user);

        if (data.kind === 'client') {
            document.getElementById('tester-details').style.display = 'none';
            document.getElementById('client-details').style.display = '';
            renderTotalsClient(data.totals || {});
            renderDynamicsClient(data.monthly_dynamics || []);
            renderRecent(data.recent_samples || []);
        } else {
            document.getElementById('tester-details').style.display = '';
            document.getElementById('client-details').style.display = 'none';
            renderTotals(data.totals || {});
            renderDynamics(data.monthly_dynamics || []);
            renderStandards(data.top_standards || []);
            renderLongest(data.longest_samples || []);
        }

        updateLastUpdated();
    } catch (e) {
        console.error('Detail error:', e);
        document.getElementById('employee-fullname').textContent = 'Ошибка загрузки';
        document.getElementById('employee-meta').innerHTML =
            `<span class="employee-meta-item">${e.message}</span>`;
    }
}

/* ────── CLIENT-версии рендеров ────── */

function renderTotalsClient(totals) {
    const container = document.getElementById('employee-kpi');
    const medHint = totals.median_verification_hours != null
        ? `${fmtFloat(totals.median_verification_hours, 1)} ч медиана проверки`
        : '';

    container.innerHTML = `
        ${renderKpi('blue',   'fa-clipboard-list',  'Зарегистрировано',       fmtNum(totals.registrations))}
        ${renderKpi('green',  'fa-clipboard-check', 'Проверок регистрации',   fmtNum(totals.verifications))}
        ${renderKpiWithHint('purple', 'fa-hourglass-half', 'Скорость проверки',
            totals.median_verification_hours != null
                ? fmtFloat(totals.median_verification_hours, 1) + ' ч'
                : '—',
            'медиана от регистрации до проверки')}
        ${renderKpi('orange', 'fa-ban',             'Отменено после',         fmtNum(totals.cancelled_after))}
    `;
}

function renderKpiWithHint(color, icon, label, value, hint) {
    return `
        <div class="kpi-card non-clickable">
            <div class="kpi-icon ${color}"><i class="fas ${icon}"></i></div>
            <div class="kpi-label">${label}</div>
            <div class="kpi-value">${value}</div>
            <div class="kpi-previous">${hint}</div>
        </div>
    `;
}

function renderDynamicsClient(rows) {
    if (STATE.chart) { STATE.chart.destroy(); STATE.chart = null; }

    if (!rows.length) {
        const canvas = document.getElementById('dynamicsChart');
        const parent = canvas.parentElement;
        parent.innerHTML = '<div class="empty-risk">Нет данных за последние 6 месяцев</div>';
        return;
    }

    STATE.chart = new Chart(document.getElementById('dynamicsChart'), {
        type: 'line',
        data: {
            labels: rows.map(r => r.month),
            datasets: [
                {
                    label: 'Регистрации',
                    data: rows.map(r => r.registrations),
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.10)',
                    fill: true, tension: 0.3,
                    pointRadius: 4, pointBackgroundColor: '#2563eb',
                },
                {
                    label: 'Проверки',
                    data: rows.map(r => r.verifications),
                    borderColor: '#16a34a',
                    backgroundColor: 'rgba(22, 163, 74, 0.10)',
                    fill: true, tension: 0.3,
                    pointRadius: 4, pointBackgroundColor: '#16a34a',
                },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
                tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.92)', padding: 10, cornerRadius: 6 },
            },
            scales: {
                x: { ticks: { font: { size: 10 }, color: '#64748b' }, grid: { display: false } },
                y: { ticks: { font: { size: 10 }, color: '#64748b' },
                     grid: { color: 'rgba(0, 0, 0, 0.05)' }, beginAtZero: true },
            },
        },
    });
}

const STATUS_LABEL_SHORT = {
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
    ACCEPTED_IN_LAB:       'Принят',
    CONDITIONING:          'Кондиционирование',
    READY_FOR_TEST:        'Ждёт испытания',
    IN_TESTING:            'На испытании',
    TESTED:                'Испытан',
    DRAFT_READY:           'Черновик готов',
    RESULTS_UPLOADED:      'Результаты выложены',
    PROTOCOL_ISSUED:       'Протокол готов',
    COMPLETED:             'Готово',
    REPLACEMENT_PROTOCOL:  'Замещающий',
};

function renderRecent(rows) {
    const tbody = document.getElementById('recent-tbody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center dim" style="padding: 24px;">Нет данных за период</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => {
        // Какое действие этот сотрудник сделал по этому образцу
        const actions = [];
        if (r.did_register) actions.push('<span class="trainee-badge" style="background:#dbeafe;color:#1e40af">регистрация</span>');
        if (r.did_verify)   actions.push('<span class="trainee-badge" style="background:#dcfce7;color:#15803d">проверка</span>');
        const actionHtml = actions.join(' ') || '<span class="dim">—</span>';

        // Какая дата более релевантна — проверки (если есть) или регистрации
        const displayDate = r.verified_at
            ? new Date(r.verified_at).toLocaleDateString('ru-RU')
            : (r.registration_date
                ? new Date(r.registration_date).toLocaleDateString('ru-RU')
                : '—');

        return `
            <tr data-sample-id="${r.id}">
                <td style="font-family: var(--font-mono); font-size: 11px;">${r.cipher}</td>
                <td>${r.client_name || '—'}</td>
                <td>${r.lab_code || '—'}</td>
                <td>${actionHtml}</td>
                <td>${STATUS_LABEL_SHORT[r.status] || r.status}</td>
                <td class="num">${displayDate}</td>
            </tr>
        `;
    }).join('');

    tbody.querySelectorAll('tr[data-sample-id]').forEach(el => {
        el.addEventListener('click', () => {
            window.location.href = window.ANALYTICS_CONFIG.sampleDetailUrlTemplate
                .replace('{id}', el.dataset.sampleId);
        });
    });
}

/* ────── ИНИЦИАЛИЗАЦИЯ ────── */
document.addEventListener('DOMContentLoaded', async () => {
    if (!STATE.userId) {
        document.getElementById('employee-fullname').textContent = 'ID сотрудника не указан';
        return;
    }
    initFilters();
    await loadDetail();
    setInterval(tickLastUpdated, 15000);
});

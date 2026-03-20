// frontend/dashboard.js — LIGHT GLASSMORPHISM

const API_BASE = '/workspace/analytics/api';

let currentFilters = { days: 30, lab_id: 0 };
let charts = {};

// ========== CHART PALETTE (light-friendly) ==========
const PALETTE = [
    'rgba(0, 123, 255, 0.75)',   // blue (accent)
    'rgba(16, 185, 129, 0.75)',  // green
    'rgba(245, 158, 11, 0.75)',  // orange
    'rgba(239, 68, 68, 0.72)',   // red
    'rgba(139, 92, 246, 0.75)',  // purple
    'rgba(6, 182, 212, 0.75)',   // cyan
    'rgba(236, 72, 153, 0.72)',  // pink
    'rgba(132, 204, 22, 0.72)',  // lime
];

// Chart.js global defaults
Chart.defaults.color = '#64748b';
Chart.defaults.borderColor = 'rgba(0, 0, 0, 0.06)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.weight = 500;
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(30, 41, 59, 0.92)';
Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.1)';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.titleColor = '#fff';
Chart.defaults.plugins.tooltip.bodyColor = 'rgba(255,255,255,0.85)';
Chart.defaults.plugins.tooltip.titleFont = { family: "'Inter', sans-serif", weight: 600, size: 13 };
Chart.defaults.plugins.tooltip.bodyFont = { family: "'JetBrains Mono', monospace", weight: 500, size: 12 };

// ========== INIT ==========
document.addEventListener('DOMContentLoaded', function() {
    currentFilters = { days: 30, lab_id: 0 };

    loadLaboratories();
    loadKPI();
    loadMonthlyLabor();
    loadLabDistribution();
    loadStatusDistribution();
    loadDailyRegistrations();
    loadEmployeeStats();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => refreshAllCharts());

    const periodSelect = document.getElementById('period-select');
    if (periodSelect) {
        periodSelect.value = '30';
        periodSelect.addEventListener('change', function(e) {
            currentFilters.days = parseInt(e.target.value);
            refreshAllCharts();
        });
    }

    updateLastUpdateTime();
});

function refreshAllCharts() {
    loadKPI();
    loadMonthlyLabor();
    loadLabDistribution();
    loadStatusDistribution();
    loadEmployeeStats();
    loadDailyRegistrations();
    updateLastUpdateTime();
}

function updateLastUpdateTime() {
    const el = document.getElementById('last-update');
    if (el) el.innerHTML = `<i class="far fa-clock"></i> Обновлено: ${new Date().toLocaleString('ru-RU')}`;
}

// ========== ЛАБОРАТОРИИ ==========
async function loadLaboratories() {
    try {
        const response = await fetch(`${API_BASE}/laboratories`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const labs = await response.json();

        const select = document.getElementById('lab-select');
        if (!select) return;

        select.innerHTML = '<option value="0">Все лаборатории</option>';
        labs.forEach(lab => {
            if (lab.id !== 0) {
                const opt = document.createElement('option');
                opt.value = lab.id;
                opt.textContent = lab.name;
                select.appendChild(opt);
            }
        });

        select.addEventListener('change', function(e) {
            currentFilters.lab_id = parseInt(e.target.value);
            refreshAllCharts();
        });
    } catch (err) {
        console.error('Ошибка загрузки лабораторий:', err);
        const select = document.getElementById('lab-select');
        if (select) select.innerHTML = '<option value="0">Все лаборатории</option>';
    }
}

// ========== KPI ==========
async function loadKPI() {
    try {
        const response = await fetch(`${API_BASE}/kpi?lab_id=${currentFilters.lab_id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const grid = document.getElementById('kpi-cards');
        if (!grid) return;

        const kpis = [
            { label: 'Всего образцов',     value: data.total_samples     || 0, icon: 'fas fa-flask',          color: 'blue' },
            { label: 'Активные',            value: data.active_samples    || 0, icon: 'fas fa-bolt',           color: 'green' },
            { label: 'Просрочено',          value: data.overdue_samples   || 0, icon: 'fas fa-clock',          color: 'orange' },
            { label: 'Отменено',            value: data.cancelled_samples || 0, icon: 'fas fa-ban',            color: 'red' },
            { label: 'Среднее время (дни)', value: data.avg_test_days     || 0, icon: 'fas fa-hourglass-half', color: 'cyan' },
            { label: 'Сотрудников',         value: data.total_employees   || 0, icon: 'fas fa-user-group',     color: 'purple' },
        ];

        grid.innerHTML = kpis.map(k => `
            <div class="kpi-card">
                <div class="kpi-icon ${k.color}"><i class="${k.icon}"></i></div>
                <div class="kpi-label">${k.label}</div>
                <div class="kpi-value"><span data-target="${k.value}">0</span></div>
            </div>
        `).join('');

        grid.querySelectorAll('.kpi-value span').forEach(span => {
            countUp(span, parseFloat(span.dataset.target));
        });
    } catch (err) {
        console.error('Ошибка KPI:', err);
    }
}

function countUp(span, target) {
    const isFloat = String(target).includes('.');
    const duration = 800;
    const start = performance.now();
    function step(now) {
        const p = Math.min((now - start) / duration, 1);
        const ease = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
        span.textContent = isFloat ? (ease * target).toFixed(1) : Math.round(ease * target);
        if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// ========== ТРУДОЕМКОСТЬ ПО МЕСЯЦАМ ==========
async function loadMonthlyLabor() {
    try {
        const response = await fetch(`${API_BASE}/monthly-labor?lab_id=${currentFilters.lab_id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const canvas = document.getElementById('monthlyChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (charts.monthly) charts.monthly.destroy();
        if (!data || data.length === 0) { showEmpty(canvas); return; }

        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight);
        gradient.addColorStop(0, 'rgba(0, 123, 255, 0.3)');
        gradient.addColorStop(1, 'rgba(0, 123, 255, 0.03)');

        charts.monthly = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(i => i.month),
                datasets: [{
                    label: 'Количество образцов',
                    data: data.map(i => i.samples_count),
                    backgroundColor: gradient,
                    borderColor: 'rgba(0, 123, 255, 0.5)',
                    borderWidth: 1.5,
                    borderRadius: 6,
                    borderSkipped: false,
                    hoverBackgroundColor: 'rgba(0, 123, 255, 0.35)',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { padding: 8 } },
                    x: { grid: { display: false }, ticks: { padding: 6 } }
                }
            }
        });
    } catch (err) { console.error('Ошибка monthly:', err); }
}

// ========== ЛАБОРАТОРИИ ==========
async function loadLabDistribution() {
    try {
        const response = await fetch(`${API_BASE}/laboratory-distribution`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const canvas = document.getElementById('labChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (charts.lab) charts.lab.destroy();
        if (!data || data.length === 0) { showEmpty(canvas); return; }

        charts.lab = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(i => i.laboratory),
                datasets: [{
                    data: data.map(i => i.samples_count),
                    backgroundColor: PALETTE,
                    borderColor: 'rgba(255,255,255,0.8)',
                    borderWidth: 2.5,
                    hoverOffset: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: { position: 'right', labels: { padding: 14, font: { size: 12 } } }
                }
            }
        });
    } catch (err) { console.error('Ошибка лабораторий:', err); }
}

// ========== СТАТУСЫ ==========
async function loadStatusDistribution() {
    try {
        const response = await fetch(`${API_BASE}/status-distribution?lab_id=${currentFilters.lab_id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const canvas = document.getElementById('statusChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (charts.status) charts.status.destroy();
        if (!data || data.length === 0) { showEmpty(canvas); return; }

        charts.status = new Chart(ctx, {
            type: 'polarArea',
            data: {
                labels: data.map(i => i.status),
                datasets: [{
                    data: data.map(i => i.count),
                    backgroundColor: PALETTE,
                    borderColor: 'rgba(255,255,255,0.7)',
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { padding: 14, font: { size: 12 } } }
                },
                scales: {
                    r: { grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { display: false } }
                }
            }
        });
    } catch (err) { console.error('Ошибка статусов:', err); }
}

// ========== ДИНАМИКА ==========
async function loadDailyRegistrations() {
    try {
        const response = await fetch(`${API_BASE}/daily-registrations?lab_id=${currentFilters.lab_id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        const canvas = document.getElementById('trendChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (charts.trend) charts.trend.destroy();
        if (!data || data.length === 0) { showEmpty(canvas); return; }

        canvas.style.display = 'block';

        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight);
        gradient.addColorStop(0, 'rgba(16, 185, 129, 0.2)');
        gradient.addColorStop(1, 'rgba(16, 185, 129, 0.01)');

        charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(i => {
                    const d = new Date(i.date);
                    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
                }),
                datasets: [{
                    label: 'Регистрации',
                    data: data.map(i => i.registrations),
                    borderColor: '#10b981',
                    backgroundColor: gradient,
                    borderWidth: 2.5,
                    pointBackgroundColor: '#10b981',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#10b981',
                    tension: 0.35,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `Регистраций: ${ctx.raw}`,
                            title: ctx => {
                                const d = new Date(data[ctx[0].dataIndex].date);
                                return d.toLocaleDateString('ru-RU');
                            }
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { stepSize: 1, precision: 0, padding: 8 } },
                    x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 45, maxTicksLimit: 18, padding: 6 } }
                },
                interaction: { intersect: false, mode: 'index' }
            }
        });
    } catch (err) {
        console.error('Ошибка daily:', err);
        showError('trendChart');
    }
}

// ========== СОТРУДНИКИ ==========
let employeeData = [];
let currentSort = { column: 'samples_tested', direction: 'desc' };

async function loadEmployeeStats() {
    try {
        const response = await fetch(`${API_BASE}/employee-stats?lab_id=${currentFilters.lab_id}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        employeeData = await response.json();
        displayEmployeeTable();
    } catch (err) {
        console.error('Ошибка сотрудников:', err);
        const tbody = document.getElementById('employees-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--red);padding:30px;">Ошибка загрузки</td></tr>';
    }
}

function displayEmployeeTable() {
    const tbody = document.getElementById('employees-tbody');
    if (!tbody) return;

    if (!employeeData || employeeData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--text-muted);">Нет данных</td></tr>';
        return;
    }

    const sorted = [...employeeData].sort((a, b) => {
        const key = currentSort.column === 'samples_tested' ? 'samples_tested' : 'protocols_made';
        return currentSort.direction === 'asc'
            ? (a[key] || 0) - (b[key] || 0)
            : (b[key] || 0) - (a[key] || 0);
    });

    updateSortIcons();

    tbody.innerHTML = sorted.map(e => {
        const name = `${e.last_name || ''} ${e.first_name || ''}`.trim() || 'Не указано';
        return `<tr>
            <td><strong>${name}</strong></td>
            <td>${e.role || '—'}</td>
            <td>${e.laboratory_name || '—'}</td>
            <td class="text-center" style="font-family:var(--font-mono);">${e.samples_tested || 0}</td>
            <td class="text-center" style="font-family:var(--font-mono);">${e.protocols_made || 0}</td>
        </tr>`;
    }).join('');
}

function updateSortIcons() {
    document.querySelectorAll('.sortable').forEach(th => {
        const col = th.dataset.sort;
        th.classList.remove('asc', 'desc');
        const icon = th.querySelector('.sort-icon');
        if (icon) {
            if (col === currentSort.column) {
                th.classList.add(currentSort.direction);
                icon.textContent = currentSort.direction === 'asc' ? '↑' : '↓';
            } else {
                icon.textContent = '↕';
            }
        }
    });
}

function initSorting() {
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', function() {
            const col = this.dataset.sort;
            if (currentSort.column === col) {
                currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.column = col;
                currentSort.direction = 'desc';
            }
            displayEmployeeTable();
        });
    });
}

// ========== HELPERS ==========
function showEmpty(canvas) {
    canvas.style.display = 'none';
    canvas.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:13px;">Нет данных за выбранный период</div>';
}

function showError(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (canvas && canvas.parentNode) {
        canvas.style.display = 'none';
        const div = document.createElement('div');
        div.style.cssText = 'display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);font-size:13px;';
        div.textContent = 'Ошибка загрузки данных';
        canvas.parentNode.appendChild(div);
    }
}
// ================================== 全局状态
window.CanteenApp = window.CanteenApp || {};

const API_BASE = '/api';
const state = {
    mode: 'single',
    view: 'canteen',
    activeCanteenId: null,
    activeFloorId: null,
    canteenOrder: [],
    lastData: null,
    timer: null,
    speed: 2,
    charts: {},
    studentPrev: {},  // student.id -> {x, y}，用于帧间插值实现"流动"动画
};

// ================================== 页面导航
const navLinks = document.querySelectorAll('.nav-link');
const pages = document.querySelectorAll('.page');

navLinks.forEach(link => {
    link.addEventListener('click', e => {
        e.preventDefault();
        showPage(link.dataset.page);
    });
});

function showPage(name) {
    pages.forEach(p => p.classList.toggle('active', p.id === `${name}-page`));
    navLinks.forEach(l => l.classList.toggle('active', l.dataset.page === name));
    if (name === 'history') loadHistoryList();
}

// ================================== 参数配置
const configForm = document.getElementById('config-form');
const resetBtn = document.getElementById('reset-btn');
const modeRadios = document.querySelectorAll('input[name="simulation_mode"]');
const singleModeForm = document.getElementById('single-mode-form');
const campusModeForm = document.getElementById('campus-mode-form');
const campusConfigJson = document.getElementById('campus-config-json');
const DEFAULT_CAMPUS_CONFIG = campusConfigJson ? campusConfigJson.value : '';
let campusPresetPayload = null;
let campusConfigDirty = false;

const DEFAULTS = {
    window_count: 6,
    seat_count: 200,
    avg_serve_time: 30,
    avg_eat_time: 15,
    arrival_rate: 5,
    total_time: 60,
};

resetBtn.addEventListener('click', () => {
    Object.entries(DEFAULTS).forEach(([k, v]) => {
        const input = document.getElementById(k);
        if (input) input.value = v;
    });
    if (campusConfigJson) campusConfigJson.value = DEFAULT_CAMPUS_CONFIG;
    campusPresetPayload = null;
    campusConfigDirty = false;
    const singleModeRadio = document.getElementById('simulation-mode-single');
    if (singleModeRadio) singleModeRadio.checked = true;
    renderPendingDataNote([]);
    syncModeForms();
});

if (campusConfigJson) {
    campusConfigJson.addEventListener('input', () => {
        campusConfigDirty = true;
        campusPresetPayload = null;
    });
}

document.querySelectorAll('[data-campus-preset]').forEach(btn => {
    btn.addEventListener('click', async () => {
        document.querySelectorAll('[data-campus-preset]').forEach(item => {
            item.classList.toggle('active', item === btn);
        });
        try {
            await loadDefaultCampusPreset();
        } catch (err) {
            console.error(err);
            alert(err.message || '校园预设加载失败');
        }
    });
});

modeRadios.forEach(radio => {
    radio.addEventListener('change', () => {
        syncModeForms();
    });
});

syncModeForms();

configForm.addEventListener('submit', async e => {
    e.preventDefault();
    const nextMode = selectedMode();

    try {
        const payload = nextMode === 'campus'
            ? await getCampusConfigForSubmit()
            : readSingleConfig();
        const apiBase = nextMode === 'campus' ? '/campus' : '/simulation';
        await resetActiveSession();
        const configRes = nextMode === 'campus'
            ? await apiPost('/campus/config', payload)
            : await apiPost('/config', payload);
        if (!configRes.ok) {
            alert(configRes.data.error || '参数提交失败');
            return;
        }
        const startRes = await apiPost(`${apiBase}/start`);
        if (!startRes.ok) {
            alert(startRes.data.error || '仿真启动失败');
            return;
        }
        state.mode = nextMode;
        resetSimulationState();
        applyViewState();
        showPage('simulation');
        startLoop();
    } catch (err) {
        console.error(err);
        alert(err.message || '无法连接后端服务，请检查 Flask 是否启动');
    }
});

function selectedMode() {
    const checked = document.querySelector('input[name="simulation_mode"]:checked');
    return checked ? checked.value : 'single';
}

function syncModeForms() {
    const isCampus = selectedMode() === 'campus';
    if (singleModeForm) singleModeForm.hidden = isCampus;
    if (campusModeForm) campusModeForm.hidden = !isCampus;
    if (isCampus && !campusPresetPayload && !campusConfigDirty) {
        loadDefaultCampusPreset().catch(err => console.error(err));
    }
}

function readSingleConfig() {
    return {
        window_count: parseInt(document.getElementById('window_count').value, 10),
        seat_count: parseInt(document.getElementById('seat_count').value, 10),
        avg_serve_time: parseFloat(document.getElementById('avg_serve_time').value),
        avg_eat_time: parseFloat(document.getElementById('avg_eat_time').value),
        arrival_rate: parseFloat(document.getElementById('arrival_rate').value),
        total_time: parseInt(document.getElementById('total_time').value, 10),
    };
}

function readCampusConfig() {
    try {
        return JSON.parse(campusConfigJson.value);
    } catch (err) {
        throw new Error('校园联合配置 JSON 格式错误');
    }
}

async function loadDefaultCampusPreset() {
    const res = await fetch(`${API_BASE}/campus/presets/default`);
    if (!res.ok) throw new Error('校园预设加载失败');
    const data = await res.json();
    campusPresetPayload = data.config;
    if (campusConfigJson) {
        campusConfigJson.value = JSON.stringify(data.config, null, 2);
        campusConfigDirty = false;
    }
    renderPendingDataNote(data.pending_canteens || []);
    return data.config;
}

function renderPendingDataNote(pending) {
    const node = document.getElementById('pending-data-note');
    if (!node) return;
    node.textContent = pending.length
        ? `待补数据：${pending.join(', ')}。演示中不伪造该食堂容量。`
        : '全部食堂数据已回填。';
}

async function getCampusConfigForSubmit() {
    if (campusConfigDirty) {
        return readCampusConfig();
    }
    if (campusPresetPayload) {
        return campusPresetPayload;
    }
    return await loadDefaultCampusPreset();
}

async function resetActiveSession() {
    try {
        const statusRes = await fetch(`${API_BASE}/simulation/status`);
        const status = statusRes.ok ? await statusRes.json() : {};
        const resetPath = status.mode === 'campus'
            ? '/campus/reset'
            : '/simulation/reset';
        await apiPost(resetPath);
    } catch (err) {
        await apiPost('/simulation/reset');
    }
}

// ================================== 仿真运行控制
const canvas = document.getElementById('canteen-canvas');
const ctx = canvas.getContext('2d');
const playPauseBtn = document.getElementById('play-pause-btn');
const endBtn = document.getElementById('end-btn');
const speedRange = document.getElementById('speed-range');
const speedLabel = document.getElementById('speed-label');
const viewSwitcher = document.getElementById('view-switcher');
const campusOverviewPanel = document.getElementById('campus-overview-panel');
const canteenSwitcher = document.getElementById('canteen-switcher');
const campusMapContainer = document.getElementById('campus-map-container');
const floorTabs = document.getElementById('floor-tabs');
const infoPanel = document.querySelector('.info-panel');
const SPEED_MAP = [1, 2, 5, 10];

if (viewSwitcher) {
    viewSwitcher.querySelectorAll('button[data-view]').forEach(btn => {
        btn.addEventListener('click', () => {
            state.view = btn.dataset.view;
            applyViewState();
            if (state.lastData && window.CanteenApp.refreshCampusView) {
                window.CanteenApp.refreshCampusView(state.lastData);
            }
        });
    });
}

playPauseBtn.addEventListener('click', () => {
    if (playPauseBtn.textContent === '开始' || playPauseBtn.textContent === '继续') {
        playPauseBtn.textContent = '暂停';
        startLoop();
    } else {
        playPauseBtn.textContent = '继续';
        stopLoop();
        apiPost(`${currentSimulationBase()}/pause`).catch(() => {});
    }
});

endBtn.addEventListener('click', async () => {
    stopLoop();
    endBtn.disabled = true;
    playPauseBtn.disabled = true;
    const prevLabel = endBtn.textContent;
    endBtn.textContent = '结算中...';
    try {
        // 让后端把剩余事件一次跑完，保证分析页拿到的是完整统计
        const res = await fetch(`${API_BASE}${currentSimulationBase()}/finish`, { method: 'POST' });
        if (!res.ok) {
            alert('结束仿真失败，请检查后端日志');
            return;
        }
        let stats = await res.json();
        if (state.mode === 'campus') {
            const statsRes = await fetch(`${API_BASE}/campus/statistics`);
            if (statsRes.ok) stats = await statsRes.json();
        }
        showPage('analysis');
        renderStatCards(stats);
        renderCharts(stats);
    } catch (err) {
        console.error(err);
        alert('无法连接后端服务');
    } finally {
        endBtn.textContent = prevLabel;
        endBtn.disabled = false;
        playPauseBtn.disabled = false;
        playPauseBtn.textContent = '开始';
    }
});

speedRange.addEventListener('input', () => {
    state.speed = SPEED_MAP[speedRange.value];
    speedLabel.textContent = `×${state.speed}`;
    if (state.timer) { stopLoop(); startLoop(); }
});

function resetSimulationState() {
    state.lastData = null;
    state.view = 'canteen';
    state.activeCanteenId = null;
    state.activeFloorId = null;
    state.canteenOrder = [];
    state.studentPrev = {};
    playPauseBtn.textContent = '暂停';
    document.getElementById('current-time').textContent = '00:00';
    document.getElementById('total-arrived').textContent = '0';
    document.getElementById('total-served').textContent = '0';
    document.getElementById('total-eating').textContent = '0';
    document.getElementById('total-in-queue').textContent = '0';
    document.getElementById('empty-seats').textContent = '0';
    document.getElementById('avg-waiting').textContent = '0.0 s';
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    applyViewState();
}

function startLoop() {
    stopLoop();
    state.timer = setInterval(tick, Math.max(80, 500 / state.speed));
}

function stopLoop() {
    if (state.timer) clearInterval(state.timer);
    state.timer = null;
}

async function tick() {
    try {
        const data = await dispatchStep();
        if (data.is_ended) {
            stopLoop();
            playPauseBtn.textContent = '开始';
            setTimeout(() => { showPage('analysis'); loadStatistics(); }, 300);
        }
    } catch (err) {
        console.error(err);
        stopLoop();
    }
}

async function dispatchStep() {
    const path = state.mode === 'campus'
        ? '/campus/step?display_tick_seconds=10'
        : '/simulation/step';
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error('step failed');
    const data = await res.json();
    state.lastData = data;

    if (data.mode === 'campus') {
        state.canteenOrder = data.canteen_order || Object.keys(data.canteens || {});
        if (!state.activeCanteenId) {
            state.activeCanteenId = state.canteenOrder[0] || null;
        }
        if (window.CanteenApp.refreshCampusView) {
            window.CanteenApp.refreshCampusView(data);
        } else {
            updateInfoPanel(campusInfoPanelData(data));
            const activeCanteen = activeCanteenSnapshot(data);
            if (activeCanteen) drawCanteen(activeCanteen);
        }
        applyViewState();
    } else {
        updateInfoPanel(data);
        drawCanteen(data);
    }
    return data;
}

function currentSimulationBase() {
    return state.mode === 'campus' ? '/campus' : '/simulation';
}

function applyViewState() {
    const isCampusMode = state.mode === 'campus';
    const isCampusView = isCampusMode && state.view === 'campus';
    if (viewSwitcher) viewSwitcher.hidden = !isCampusMode;
    if (campusOverviewPanel) campusOverviewPanel.hidden = !isCampusView;
    if (canteenSwitcher) canteenSwitcher.hidden = !isCampusMode || isCampusView;
    if (campusMapContainer) campusMapContainer.hidden = !isCampusView;
    if (canvas) canvas.hidden = isCampusView;
    if (floorTabs) floorTabs.hidden = !isCampusMode || isCampusView;
    if (infoPanel) infoPanel.hidden = isCampusView;
    if (viewSwitcher) {
        viewSwitcher.querySelectorAll('button[data-view]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === state.view);
        });
    }
}

function activeCanteenSnapshot(data) {
    if (!data || !data.canteens) return null;
    const activeId = state.activeCanteenId || data.canteen_order?.[0];
    return activeId ? data.canteens[activeId] : null;
}

function campusInfoPanelData(data) {
    const totals = data.campus_totals || {};
    return {
        current_time: data.current_time || 0,
        total_arrived: totals.total_arrived || 0,
        total_served: totals.total_served || 0,
        total_eating: totals.total_eating || 0,
        total_in_queue: totals.total_in_queue || 0,
        empty_seats: totals.empty_seats || 0,
        avg_waiting_time: totals.avg_waiting_time || 0,
    };
}

function updateInfoPanel(data) {
    const sec = Math.floor(data.current_time);
    const mm = String(Math.floor(sec / 60)).padStart(2, '0');
    const ss = String(sec % 60).padStart(2, '0');
    document.getElementById('current-time').textContent = `${mm}:${ss}`;
    document.getElementById('total-arrived').textContent = data.total_arrived;
    document.getElementById('total-served').textContent = data.total_served;
    document.getElementById('total-eating').textContent = data.total_eating;
    document.getElementById('total-in-queue').textContent = data.total_in_queue;
    document.getElementById('empty-seats').textContent = data.empty_seats;
    const avgW = data.avg_waiting_time != null ? data.avg_waiting_time.toFixed(1) : '0.0';
    document.getElementById('avg-waiting').textContent = `${avgW} s`;
}

// ================================== Canvas 食堂布局
function drawCanteen(data) {
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    drawBackground(W, H);
    const windowBoxes = drawWindows(data.windows, W);
    drawSeats(data.seats, W, H);
    drawWaitingQueueLabel(data.waiting_queue_length, W, H);
    // 用 data.students 驱动每个学生的圆点（含帧间插值），呈现"人员流动"
    drawStudentDots(data, windowBoxes, W, H);
}

function drawBackground(W, H) {
    // 外框
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 2;
    ctx.strokeRect(12, 12, W - 24, H - 24);
    ctx.font = '12px "PingFang SC", sans-serif';
    ctx.fillStyle = '#64748b';
    ctx.textAlign = 'left';
}

function drawWindows(windows, W) {
    if (!windows || !windows.length) return [];
    const count = windows.length;
    const winW = 80, winH = 50;
    const gap = Math.max(10, (W - 60 - count * winW) / (count + 1));
    const baseX = (W - (count * winW + (count - 1) * gap)) / 2;
    const y = 50;
    const boxes = [];

    windows.forEach((w, i) => {
        const x = baseX + i * (winW + gap);
        // 窗口框
        const color = w.is_serving ? '#b91c1c' : '#94a3b8';
        ctx.fillStyle = color;
        ctx.fillRect(x, y, winW, winH);
        ctx.strokeStyle = '#991b1b';
        ctx.strokeRect(x, y, winW, winH);
        ctx.fillStyle = '#fff';
        ctx.font = '13px "PingFang SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`窗口 ${w.id + 1}`, x + winW / 2, y + 22);
        ctx.font = '11px "PingFang SC", sans-serif';
        ctx.fillText(`已服务 ${w.total_served}`, x + winW / 2, y + 40);

        const queueX = x + winW / 2;
        const queueY = y + winH + 12;
        // 队列圆点改由 drawStudentDots 按 student.id 渲染；这里只补"+N"溢出标记
        if (w.queue_length > 12) {
            ctx.fillStyle = '#64748b';
            ctx.font = '11px sans-serif';
            ctx.fillText(`+${w.queue_length - 12}`, queueX, queueY + 14 + 12 * 14 + 4);
        }

        boxes.push({ id: w.id, x, y, w: winW, h: winH, queueX, queueY });
    });

    return boxes;
}

function drawSeats(seats, W, H) {
    if (!seats || !seats.length) return [];
    const total = seats.length;
    const cols = Math.min(20, Math.ceil(Math.sqrt(total * 1.8)));
    const rows = Math.ceil(total / cols);
    const size = 18;
    const gap = 5;
    const areaW = cols * (size + gap) - gap;
    const startX = (W - areaW) / 2;
    const startY = 260;

    seats.forEach((s, i) => {
        const r = Math.floor(i / cols);
        const c = i % cols;
        const x = startX + c * (size + gap);
        const y = startY + r * (size + gap);
        if (s.status === 'occupied') {
            // 颜色深浅表示剩余就餐时间（可视化热力）
            const intensity = Math.min(1, s.remaining_time / (30 * 60));
            const g = Math.floor(120 - 60 * intensity);
            ctx.fillStyle = `rgb(239, ${g}, 68)`;
        } else {
            ctx.fillStyle = '#d1fae5';
        }
        ctx.fillRect(x, y, size, size);
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x, y, size, size);
    });

    return { startX, startY, cols, size, gap };
}

function drawWaitingQueueLabel(count, W, H) {
    if (!count) return;
    ctx.fillStyle = '#64748b';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`等位队列：${count} 人`, W - 30, H - 40);
    if (count > 10) {
        ctx.fillText(`+${count - 10}`, W - 30, H - 4);
    }
}

// ----- 学生级渲染：把 backend 算好的 students payload 真正画出来 -----
function computeStudentTargets(students, windowBoxes, W, H) {
    if (!students) return {};
    const boxByWid = {};
    windowBoxes.forEach(b => { boxByWid[b.id] = b; });

    const targets = {};
    const queueIdxByWindow = {};
    for (const s of students) {
        if (s.position === 'window_queue') {
            const wid = s.position_detail;
            const idx = (queueIdxByWindow[wid] = (queueIdxByWindow[wid] || 0));
            queueIdxByWindow[wid] = idx + 1;
            const box = boxByWid[wid];
            if (!box || idx >= 12) continue;  // 超出 12 个由 +N 标记替代
            targets[s.id] = {
                x: box.queueX,
                y: box.queueY + 14 + idx * 14,
                color: '#ff9800',
            };
        } else if (s.position === 'being_served') {
            const box = boxByWid[s.position_detail];
            if (!box) continue;
            targets[s.id] = {
                x: box.x + box.w / 2,
                y: box.y + box.h - 8,
                color: '#fbbf24',
            };
        } else if (s.position === 'waiting_queue') {
            const idx = typeof s.position_detail === 'number' ? s.position_detail : 0;
            if (idx >= 10) continue;
            targets[s.id] = {
                x: W - 40 + (idx % 5) * 12,
                y: H - 28 + Math.floor(idx / 5) * 12,
                color: '#9333ea',
            };
        }
        // seated 由 drawSeats 渲染；left/unknown 不画
    }
    return targets;
}

function drawStudentDots(data, windowBoxes, W, H) {
    const targets = computeStudentTargets(data.students, windowBoxes, W, H);
    const prev = state.studentPrev;
    const next = {};
    const lerp = 0.4;  // 帧间插值系数：值越大动作越快
    for (const id in targets) {
        const t = targets[id];
        const p = prev[id];
        const x = p ? p.x + (t.x - p.x) * lerp : t.x;
        const y = p ? p.y + (t.y - p.y) * lerp : t.y;
        ctx.fillStyle = t.color;
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(15, 23, 42, 0.25)';
        ctx.lineWidth = 0.6;
        ctx.stroke();
        next[id] = { x, y };
    }
    state.studentPrev = next;
}


// ================================== 数据分析
const restartBtn = document.getElementById('restart-btn');
restartBtn.addEventListener('click', () => {
    apiPost(`${currentSimulationBase()}/reset`).finally(() => showPage('config'));
});

async function loadStatistics() {
    try {
        const path = state.mode === 'campus' ? '/campus/statistics' : '/statistics';
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) return;
        const stats = await res.json();
        renderStatCards(stats);
        renderCharts(stats);
    } catch (err) {
        console.error(err);
    }
}

function renderStatCards(s) {
    document.getElementById('stat-total-arrived').textContent = s.total_arrived;
    document.getElementById('stat-total-served').textContent = s.total_served;
    document.getElementById('stat-avg-waiting').textContent = `${s.avg_waiting_time.toFixed(1)} s`;
    document.getElementById('stat-avg-eating').textContent = `${(s.avg_eating_time / 60).toFixed(1)} min`;
    document.getElementById('stat-peak').textContent = s.peak_queue_length;
    document.getElementById('stat-seat-utilization').textContent = `${s.seat_utilization.toFixed(1)}%`;
}

function normalizeWindowServed(windowServed) {
    if (Array.isArray(windowServed)) {
        return windowServed.map((value, i) => ({ name: `窗口 ${i + 1}`, value }));
    }
    if (!windowServed || typeof windowServed !== 'object') return [];
    return Object.entries(windowServed).flatMap(([canteenId, values]) =>
        (values || []).map((value, i) => ({ name: `${canteenId} 窗口 ${i + 1}`, value }))
    );
}

function renderCharts(stats) {
    disposeCharts();
    const windowSeries = normalizeWindowServed(stats.window_served);

    state.charts.window = echarts.init(document.getElementById('window-chart'));
    state.charts.window.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: windowSeries.map(item => item.name) },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: windowSeries.map(item => item.value), itemStyle: { color: '#b91c1c' } }],
    });

    state.charts.pie = echarts.init(document.getElementById('pie-chart'));
    state.charts.pie.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            data: windowSeries.map(item => ({ value: item.value, name: item.name })),
        }],
    });

    const qt = stats.queue_timeline || { x: [], y: [] };
    state.charts.queue = echarts.init(document.getElementById('queue-chart'));
    state.charts.queue.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: qt.x.map(x => `${x}分`) },
        yAxis: { type: 'value' },
        series: [{
            type: 'line', smooth: true, data: qt.y,
            areaStyle: { color: 'rgba(255, 152, 0, 0.2)' },
            itemStyle: { color: '#ff9800' },
        }],
    });

    const st = stats.seat_util_timeline || { x: [], y: [] };
    state.charts.seat = echarts.init(document.getElementById('seat-chart'));
    state.charts.seat.setOption({
        tooltip: { trigger: 'axis', formatter: '{b}：{c}%' },
        grid: { left: 40, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: st.x.map(x => `${x}分`) },
        yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
        series: [{
            type: 'line', smooth: true, data: st.y,
            areaStyle: { color: 'rgba(76, 175, 80, 0.25)' },
            itemStyle: { color: '#4CAF50' },
        }],
    });
}

function disposeCharts() {
    Object.values(state.charts).forEach(c => c && c.dispose());
    state.charts = {};
}

window.addEventListener('resize', () => {
    Object.values(state.charts).forEach(c => c && c.resize());
    if (state.historyChart) state.historyChart.resize();
});

// ================================== 历史记录
const historyRefreshBtn = document.getElementById('history-refresh-btn');
const historyTbody = document.getElementById('history-tbody');
const historyDetail = document.getElementById('history-detail');
const historyDetailTitle = document.getElementById('history-detail-title');
const historyDetailChart = document.getElementById('history-detail-chart');

historyRefreshBtn.addEventListener('click', loadHistoryList);

async function loadHistoryList() {
    try {
        const path = state.mode === 'campus' ? '/campus/history/configs' : '/history/configs';
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) return;
        const configs = await res.json();
        renderHistoryTable(configs);
    } catch (err) {
        console.error(err);
    }
}

function renderHistoryTable(configs) {
    if (!configs || !configs.length) {
        historyTbody.innerHTML = '<tr><td colspan="11" class="history-empty">暂无历史记录，先跑一次仿真吧。</td></tr>';
        historyDetail.hidden = true;
        return;
    }
    historyTbody.innerHTML = configs.map(c => `
        <tr data-id="${c.id}">
            <td>${c.id}</td>
            <td>${c.created_at || '-'}</td>
            <td>${c.window_count}</td>
            <td>${c.seat_count}</td>
            <td>${c.avg_serve_time}</td>
            <td>${c.avg_eat_time}</td>
            <td>${c.arrival_rate}</td>
            <td>${c.total_time}</td>
            <td>${c.total_arrived ?? '-'}</td>
            <td>${c.total_served ?? '-'}</td>
            <td>${c.snapshot_count ?? 0}</td>
        </tr>
    `).join('');
    historyTbody.querySelectorAll('tr').forEach(tr => {
        tr.addEventListener('click', () => {
            historyTbody.querySelectorAll('tr').forEach(x => x.classList.remove('active'));
            tr.classList.add('active');
            const id = parseInt(tr.dataset.id, 10);
            loadHistoryDetail(id);
        });
    });
}

async function loadHistoryDetail(configId) {
    try {
        const path = state.mode === 'campus'
            ? `/campus/history?config_id=${configId}`
            : `/history?config_id=${configId}`;
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) return;
        const snapshots = await res.json();
        renderHistoryDetail(configId, snapshots);
    } catch (err) {
        console.error(err);
    }
}

function renderHistoryDetail(configId, snapshots) {
    historyDetail.hidden = false;
    historyDetailTitle.textContent = `配置 #${configId} —— 共 ${snapshots.length} 条快照`;

    if (state.historyChart) state.historyChart.dispose();
    state.historyChart = echarts.init(historyDetailChart);

    const minutes = snapshots.map(s => +(s.current_time / 60).toFixed(2));
    const arrived = snapshots.map(s => historyTotals(s).total_arrived);
    const served = snapshots.map(s => historyTotals(s).total_served);
    const queue = snapshots.map(s => historyTotals(s).total_in_queue);
    const eating = snapshots.map(s => historyTotals(s).total_eating);

    state.historyChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['累计到达', '完成就餐', '排队人数', '正在就餐'], top: 0 },
        grid: { left: 50, right: 30, top: 40, bottom: 40 },
        xAxis: { type: 'category', data: minutes, name: '分钟', nameLocation: 'middle', nameGap: 25 },
        yAxis: { type: 'value' },
        series: [
            { name: '累计到达', type: 'line', smooth: true, data: arrived, itemStyle: { color: '#b91c1c' } },
            { name: '完成就餐', type: 'line', smooth: true, data: served, itemStyle: { color: '#10b981' } },
            { name: '排队人数', type: 'line', smooth: true, data: queue, itemStyle: { color: '#ff9800' } },
            { name: '正在就餐', type: 'line', smooth: true, data: eating, itemStyle: { color: '#ef4444' } },
        ],
    });
}

function historyTotals(snapshot) {
    return snapshot.campus_totals || snapshot;
}

// ================================== 图例栏
const legendBar = document.getElementById('canvas-legend-bar');
if (legendBar) {
    const items = [
        { color: '#b91c1c', text: '占用窗口' },
        { color: '#94a3b8', text: '空闲窗口' },
        { color: '#ff9800', text: '排队' },
        { color: '#fbbf24', text: '打饭' },
        { color: '#9333ea', text: '等位' },
        { color: '#ef4444', text: '就餐中' },
        { color: '#d1fae5', text: '空座' },
        { color: 'linear-gradient(90deg,#ef4444,#fde68a)', text: '热力(剩余时间)' },
    ];
    legendBar.innerHTML = items.map(it =>
        `<span style="display:inline-flex;align-items:center;gap:4px;">` +
        `<span style="width:10px;height:10px;background:${it.color};border-radius:2px;"></span>${it.text}</span>`
    ).join('');
}

// ================================== 工具
async function apiPost(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* ignore */ }
    return { ok: res.ok, data };
}

window.CanteenApp.state = state;
window.CanteenApp.dispatchStep = dispatchStep;
window.CanteenApp.drawCanteen = drawCanteen;
window.CanteenApp.drawWindows = drawWindows;
window.CanteenApp.drawSeats = drawSeats;
window.CanteenApp.drawStudentDots = drawStudentDots;
window.CanteenApp.updateInfoPanel = updateInfoPanel;
window.CanteenApp.renderCharts = renderCharts;
window.CanteenApp.disposeCharts = disposeCharts;
window.CanteenApp.applyViewState = applyViewState;
window.CanteenApp.syncModeForms = syncModeForms;

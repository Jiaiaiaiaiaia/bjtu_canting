// ================================== 全局状态
window.CanteenApp = window.CanteenApp || {};

const API_BASE = '/api';
const state = {
    mode: 'single',
    view: 'canteen',
    activeCanteenId: null,
    activeFloorId: null,
    canteenOrder: [],
    visibleCanteens: [],
    pendingCanteens: [],
    campusPresetScale: null,
    renderMode: '2d',
    lastData: null,
    lastStatistics: null,
    lastSingleConfig: null,
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
    state.visibleCanteens = [];
    state.pendingCanteens = [];
    state.campusPresetScale = null;
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
        state.lastSingleConfig = nextMode === 'single' ? { ...payload } : null;
        state.lastStatistics = null;
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
    applyCampusPresetMetadata(data);
    if (campusConfigJson) {
        campusConfigJson.value = JSON.stringify(data.config, null, 2);
        campusConfigDirty = false;
    }
    renderPendingDataNote(data.pending_canteens || []);
    return data.config;
}

function applyCampusPresetMetadata(data) {
    state.visibleCanteens = data.visible_canteens || [];
    state.pendingCanteens = data.pending_canteens || [];
    state.campusPresetScale = data.source_scale || null;
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
        state.visibleCanteens = [];
        state.pendingCanteens = [];
        state.campusPresetScale = null;
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
const renderSwitcher = document.getElementById('render-switcher');
const threeStage = document.getElementById('three-stage');
const SPEED_MAP = [1, 2, 5, 10];

function rendererDeps() {
    return { canvas, ctx, state };
}

function chartDeps() {
    return { document, echarts, state };
}

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

if (renderSwitcher) {
    renderSwitcher.querySelectorAll('button[data-render]').forEach(btn => {
        btn.addEventListener('click', () => {
            state.renderMode = btn.dataset.render || '2d';
            applyViewState();
            if (
                state.renderMode === '3d' &&
                state.lastData &&
                window.CanteenApp3D
            ) {
                window.CanteenApp3D.init(threeStage);
                window.CanteenApp3D.render(state.lastData, state);
            } else if (state.lastData && window.CanteenApp.refreshCampusView) {
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
        const finishPath = state.mode === 'campus'
            ? '/campus/finish?display_tick_seconds=60'
            : '/simulation/finish';
        const res = await fetch(`${API_BASE}${finishPath}`, { method: 'POST' });
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
        showStatistics(stats);
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
    state.lastStatistics = null;
    state.view = 'canteen';
    state.activeCanteenId = null;
    state.activeFloorId = null;
    state.canteenOrder = [];
    state.renderMode = '2d';
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
    resetScenarioPanel();
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
        if (state.renderMode === '3d' && window.CanteenApp3D) {
            window.CanteenApp3D.init(threeStage);
            window.CanteenApp3D.render(data, state);
        } else if (window.CanteenApp.refreshCampusView) {
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
    const is3D = isCampusMode && state.renderMode === '3d';
    if (viewSwitcher) viewSwitcher.hidden = !isCampusMode;
    if (renderSwitcher) renderSwitcher.hidden = !isCampusMode;
    if (campusOverviewPanel) campusOverviewPanel.hidden = !isCampusView;
    if (canteenSwitcher) canteenSwitcher.hidden = !isCampusMode || isCampusView || is3D;
    if (campusMapContainer) campusMapContainer.hidden = !isCampusView || is3D;
    if (threeStage) threeStage.hidden = !is3D;
    if (canvas) canvas.hidden = isCampusView || is3D;
    if (floorTabs) floorTabs.hidden = !isCampusMode || isCampusView || is3D;
    if (infoPanel) infoPanel.hidden = isCampusView || is3D;
    if (viewSwitcher) {
        viewSwitcher.querySelectorAll('button[data-view]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === state.view);
        });
    }
    if (renderSwitcher) {
        renderSwitcher.querySelectorAll('button[data-render]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.render === state.renderMode);
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
    window.CanteenApp.CanvasRenderer.drawCanteen(data, rendererDeps());
}

function drawWindows(windows, W) {
    return window.CanteenApp.CanvasRenderer.drawWindows(windows, W, rendererDeps());
}

function drawSeats(seats, W, H) {
    return window.CanteenApp.CanvasRenderer.drawSeats(seats, W, H, rendererDeps());
}

function drawStudentDots(data, windowBoxes, W, H) {
    window.CanteenApp.CanvasRenderer.drawStudentDots(data, windowBoxes, W, H, rendererDeps());
}


// ================================== 数据分析
const restartBtn = document.getElementById('restart-btn');
restartBtn.addEventListener('click', () => {
    apiPost(`${currentSimulationBase()}/reset`).finally(() => showPage('config'));
});
const scenarioRunBtn = document.getElementById('scenario-run-btn');
const scenarioStatus = document.getElementById('scenario-status');
if (scenarioRunBtn) {
    scenarioRunBtn.addEventListener('click', runSuggestedScenario);
}

async function loadStatistics() {
    try {
        const path = state.mode === 'campus' ? '/campus/statistics' : '/statistics';
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) return;
        const stats = await res.json();
        showStatistics(stats);
    } catch (err) {
        console.error(err);
    }
}

function showStatistics(stats) {
    state.lastStatistics = stats;
    renderStatCards(stats);
    renderCharts(stats);
    updateScenarioActionState();
}

function renderStatCards(s) {
    window.CanteenApp.AnalysisCharts.renderStatCards(s, chartDeps());
}

function renderCharts(stats) {
    window.CanteenApp.AnalysisCharts.renderCharts(stats, chartDeps());
}

function disposeCharts() {
    window.CanteenApp.AnalysisCharts.disposeCharts(chartDeps());
}

function renderScenarioComparison(baselineStats, adjustedStats, summary) {
    window.CanteenApp.AnalysisCharts.renderScenarioComparison(
        baselineStats,
        adjustedStats,
        summary,
        chartDeps(),
    );
}

function setScenarioStatus(text) {
    if (scenarioStatus) scenarioStatus.textContent = text;
}

function resetScenarioPanel() {
    const box = document.getElementById('scenario-comparison');
    if (box) box.hidden = true;
    setScenarioStatus('完成单食堂仿真后可运行建议方案。');
    updateScenarioActionState();
}

function updateScenarioActionState() {
    if (!scenarioRunBtn) return;
    if (state.mode !== 'single') {
        scenarioRunBtn.disabled = true;
        setScenarioStatus('校园联合模式暂不自动重跑，建议先查看当前诊断和分流指标。');
        return;
    }
    if (!state.lastStatistics || !state.lastSingleConfig) {
        scenarioRunBtn.disabled = true;
        setScenarioStatus('完成单食堂仿真后可运行建议方案。');
        return;
    }

    const suggestion = window.CanteenApp.AnalysisCharts.buildSuggestedSingleConfig(
        state.lastSingleConfig,
        state.lastStatistics,
    );
    scenarioRunBtn.disabled = !suggestion.config;
    setScenarioStatus(suggestion.summary);
}

async function runSuggestedScenario() {
    if (state.mode !== 'single') {
        updateScenarioActionState();
        return;
    }

    const baselineStats = state.lastStatistics;
    const baselineConfig = state.lastSingleConfig;
    const suggestion = window.CanteenApp.AnalysisCharts.buildSuggestedSingleConfig(
        baselineConfig,
        baselineStats,
    );
    if (!suggestion.config) {
        setScenarioStatus(suggestion.summary);
        return;
    }

    const prevLabel = scenarioRunBtn.textContent;
    scenarioRunBtn.disabled = true;
    scenarioRunBtn.textContent = '运行中...';
    setScenarioStatus('正在按建议方案重跑单食堂仿真...');
    try {
        await apiPost('/simulation/reset');
        const configRes = await apiPost('/config', suggestion.config);
        if (!configRes.ok) throw new Error(configRes.data.error || '建议方案配置失败');
        const startRes = await apiPost('/simulation/start');
        if (!startRes.ok) throw new Error(startRes.data.error || '建议方案启动失败');
        const finishRes = await apiPost('/simulation/finish');
        if (!finishRes.ok) throw new Error(finishRes.data.error || '建议方案结算失败');

        const adjustedStats = finishRes.data;
        state.lastSingleConfig = suggestion.config;
        showStatistics(adjustedStats);
        renderScenarioComparison(baselineStats, adjustedStats, suggestion.summary);
        setScenarioStatus('建议方案已完成，可对照三项关键指标。');
    } catch (err) {
        console.error(err);
        setScenarioStatus(err.message || '建议方案运行失败');
    } finally {
        scenarioRunBtn.textContent = prevLabel;
        const nextSuggestion = window.CanteenApp.AnalysisCharts.buildSuggestedSingleConfig(
            state.lastSingleConfig,
            state.lastStatistics,
        );
        scenarioRunBtn.disabled = !nextSuggestion.config;
    }
}

window.addEventListener('resize', () => {
    window.CanteenApp.AnalysisCharts.resizeCharts(chartDeps());
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
window.CanteenApp.CanvasRenderer.renderLegendBar(legendBar);

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
window.CanteenApp.runSuggestedScenario = runSuggestedScenario;
window.CanteenApp.showStatistics = showStatistics;

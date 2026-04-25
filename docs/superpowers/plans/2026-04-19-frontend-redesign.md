# Frontend Redesign: A 学术简约 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply "A 学术简约" visual design system and add real-time avg_waiting_time to the dining simulation frontend.

**Architecture:** CSS-only visual overhaul (no framework change). One backend field addition to `_build_state()`. HTML/JS minimal structural changes for speed slider and 7th info panel item.

**Tech Stack:** Flask + native HTML/CSS/JS + Canvas + ECharts (unchanged)

**Spec:** `docs/superpowers/specs/2026-04-19-frontend-redesign-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/simulation/engine.py` | Modify (line 236-261) | Add `avg_waiting_time` to `_build_state()` return dict |
| `backend/tests/test_engine.py` | Modify (append) | Add test for `avg_waiting_time` field |
| `frontend/templates/index.html` | Modify | 7th info item, speed range, config subtitle, logo placeholder |
| `frontend/static/css/style.css` | Rewrite | Full A 学术简约 design system |
| `frontend/static/js/main.js` | Modify (lines 85, 126-129, 131-141, 176-186, 361-382) | Speed range handler, avg-waiting update, reset, legend colors |

---

### Task 1: Backend — Add avg_waiting_time to _build_state (TDD)

**Files:**
- Modify: `backend/simulation/engine.py:236-261`
- Test: `backend/tests/test_engine.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_engine.py`:

```python
def test_build_state_includes_avg_waiting_time(engine):
    """avg_waiting_time should appear in step data, be non-negative."""
    engine.start()
    # Run enough steps that some students start being served
    for _ in range(50):
        engine.step()
    state = engine.step()
    assert 'avg_waiting_time' in state, "step data must include avg_waiting_time"
    assert isinstance(state['avg_waiting_time'], (int, float))
    assert state['avg_waiting_time'] >= 0
```

Note: Uses existing `engine` fixture from conftest. Must call `engine.start()` first — the fixture does not auto-start.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sissi/PycharmProjects/Canteen/backend && python -m pytest tests/test_engine.py::test_build_state_includes_avg_waiting_time -v`

Expected: FAIL with `KeyError: 'avg_waiting_time'` or assertion error.

- [ ] **Step 3: Implement — add avg_waiting_time to _build_state()**

In `backend/simulation/engine.py`, inside `_build_state()`, add these lines just before the `return {` statement (before line 236):

```python
        # Real-time avg waiting: "已开始服务" population (differs from get_statistics which uses "已完成就餐")
        _served_rt = [s for s in self.students if s.start_service_time is not None]
        _wt = [s.start_service_time - s.arrival_time for s in _served_rt]
        _avg_waiting_rt = sum(_wt) / len(_wt) if _wt else 0.0
```

Then add to the return dict:

```python
            'avg_waiting_time': _avg_waiting_rt,
```

Place it after `'empty_seats': empty_seats,` line.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sissi/PycharmProjects/Canteen/backend && python -m pytest tests/test_engine.py::test_build_state_includes_avg_waiting_time -v`

Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/sissi/PycharmProjects/Canteen/backend && python -m pytest tests/ -v`

Expected: 39 passed (38 existing + 1 new)

- [ ] **Step 6: Commit**

```bash
cd /Users/sissi/PycharmProjects/Canteen
git add backend/simulation/engine.py backend/tests/test_engine.py
git commit -m "feat: add real-time avg_waiting_time to _build_state()"
```

---

### Task 2: HTML structural changes

**Files:**
- Modify: `frontend/templates/index.html`

- [ ] **Step 1: Add logo placeholder and subtitle to header**

Replace header section (lines 12-21):

```html
    <header>
        <div class="header-left">
            <div class="logo-block"></div>
            <h1>北京交通大学就餐仿真系统</h1>
        </div>
        <nav>
            <ul>
                <li><a href="#" class="nav-link active" data-page="config">参数配置</a></li>
                <li><a href="#" class="nav-link" data-page="simulation">仿真运行</a></li>
                <li><a href="#" class="nav-link" data-page="analysis">数据分析</a></li>
                <li><a href="#" class="nav-link" data-page="history">历史记录</a></li>
            </ul>
        </nav>
    </header>
```

- [ ] **Step 2: Add config page subtitle**

After `<h2>仿真参数配置</h2>` (line 27), add:

```html
            <p class="page-subtitle">配置完后点击开始仿真，自动跳转到仿真运行页</p>
```

- [ ] **Step 3: Add 7th info panel item (avg-waiting)**

After the empty-seats info-item (after line 70), add:

```html
                    <div class="info-item info-item-highlight"><span class="label">平均等待</span><span id="avg-waiting">0.0 s</span></div>
```

- [ ] **Step 4: Add canvas legend header**

Replace the canteen-layout div (lines 73-75) with:

```html
                <div class="canteen-layout">
                    <div class="canvas-header">
                        <span class="canvas-title">食堂平面布局</span>
                        <span class="canvas-legend-bar" id="canvas-legend-bar"></span>
                    </div>
                    <canvas id="canteen-canvas" width="900" height="640"></canvas>
                </div>
```

- [ ] **Step 5: Replace speed select with range slider**

Replace the speed-control div (lines 79-86) with:

```html
                    <div class="speed-control">
                        <label for="speed-range">速度</label>
                        <input type="range" id="speed-range" min="0" max="3" step="1" value="1">
                        <span id="speed-label">×2</span>
                    </div>
```

- [ ] **Step 6: Wrap config form in centered card**

Replace the config-page section (lines 26-58). Wrap the form inside a centering container:

```html
        <section id="config-page" class="page active">
            <div class="config-card">
                <h2>仿真参数配置</h2>
                <p class="page-subtitle">配置完后点击开始仿真，自动跳转到仿真运行页</p>
                <form id="config-form" class="config-form">
                    <!-- keep existing form-groups unchanged -->
                    <div class="form-group">
                        <label for="window_count">窗口数量</label>
                        <input type="number" id="window_count" name="window_count" value="6" min="1" max="20">
                    </div>
                    <div class="form-group">
                        <label for="seat_count">总座位数</label>
                        <input type="number" id="seat_count" name="seat_count" value="200" min="10" max="1000">
                    </div>
                    <div class="form-group">
                        <label for="avg_serve_time">平均打饭时长（秒）</label>
                        <input type="number" id="avg_serve_time" name="avg_serve_time" value="30" min="5" max="300" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="avg_eat_time">平均就餐时长（分钟）</label>
                        <input type="number" id="avg_eat_time" name="avg_eat_time" value="15" min="1" max="60" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="arrival_rate">每分钟到达人数</label>
                        <input type="number" id="arrival_rate" name="arrival_rate" value="5" min="0.1" max="50" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="total_time">仿真总时长（分钟）</label>
                        <input type="number" id="total_time" name="total_time" value="60" min="5" max="240">
                    </div>
                    <div class="form-buttons">
                        <button type="button" id="reset-btn">恢复默认值</button>
                        <button type="submit" id="start-btn">开始仿真</button>
                    </div>
                </form>
            </div>
        </section>
```

- [ ] **Step 7: Move restart-btn to right-aligned container**

Replace `<button id="restart-btn">重新仿真</button>` (line 136) with:

```html
            <div class="page-actions">
                <button id="restart-btn">重新仿真</button>
            </div>
```

- [ ] **Step 8: Commit**

```bash
cd /Users/sissi/PycharmProjects/Canteen
git add frontend/templates/index.html
git commit -m "feat: HTML structure for redesign (7th info item, speed slider, config card)"
```

---

### Task 3: CSS rewrite — A 学术简约 design system

**Files:**
- Rewrite: `frontend/static/css/style.css`

- [ ] **Step 1: Replace entire style.css**

Write the complete new CSS (replaces all 326 lines):

```css
/* ============================================
   北京交通大学就餐仿真系统 — A 学术简约 设计系统
   ============================================ */

/* --- Design Tokens --- */
:root {
    --c-primary: #b91c1c;
    --c-primary-light: #fef2f2;
    --c-primary-dark: #991b1b;
    --c-primary-border: #fecaca;
    --c-text: #111827;
    --c-text-secondary: #4b5563;
    --c-text-hint: #6b7280;
    --c-text-disabled: #9ca3af;
    --c-border: #e5e7eb;
    --c-border-dark: #d1d5db;
    --c-bg: #f9fafb;
    --c-card: #ffffff;
    --c-success: #059669;
    --c-warning: #f59e0b;
    --font-stack: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    --radius-sm: 6px;
    --radius-md: 8px;
    --radius-lg: 10px;
    --radius-xl: 12px;
}

* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: var(--font-stack);
    background: var(--c-bg);
    color: var(--c-text);
    font-size: 13px;
}

.container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 0;
}

/* --- Header & Nav --- */
header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: var(--c-card);
    border-bottom: 1px solid var(--c-border);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.logo-block {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    background: var(--c-primary);
}

header h1 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--c-text);
}

nav ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    gap: 4px;
}

nav a {
    color: var(--c-text-secondary);
    text-decoration: none;
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    transition: color 0.15s, background 0.15s;
}

nav a:hover {
    color: var(--c-primary);
    background: var(--c-primary-light);
}

nav a.active {
    color: var(--c-primary);
    font-weight: 600;
    border-bottom: 2px solid var(--c-primary);
    border-radius: 0;
    padding-bottom: 4px;
}

/* --- Pages --- */
main {
    padding: 16px 20px;
}

.page {
    display: none;
}

.page.active {
    display: block;
}

h2 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 600;
    color: var(--c-text);
}

.page-subtitle {
    font-size: 12px;
    color: var(--c-text-hint);
    margin: 0 0 20px;
}

/* --- Buttons --- */
button {
    padding: 8px 20px;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
    font-family: var(--font-stack);
}

button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-primary {
    background: var(--c-primary);
    color: #fff;
}
.btn-primary:hover:not(:disabled) { background: var(--c-primary-dark); }

.btn-secondary {
    background: var(--c-card);
    color: var(--c-text-secondary);
    border: 1px solid var(--c-border-dark);
}
.btn-secondary:hover:not(:disabled) { background: var(--c-bg); }

.btn-outline-danger {
    background: var(--c-card);
    color: var(--c-primary);
    border: 1px solid var(--c-primary);
}
.btn-outline-danger:hover:not(:disabled) { background: var(--c-primary-light); }

#start-btn, #play-pause-btn, #restart-btn, #history-refresh-btn { background: var(--c-primary); color: #fff; }
#start-btn:hover, #play-pause-btn:hover:not(:disabled), #restart-btn:hover, #history-refresh-btn:hover { background: var(--c-primary-dark); }

#reset-btn { background: var(--c-card); color: var(--c-text-secondary); border: 1px solid var(--c-border-dark); }
#reset-btn:hover { background: var(--c-bg); }

#end-btn { background: var(--c-card); color: var(--c-primary); border: 1px solid var(--c-primary); }
#end-btn:hover:not(:disabled) { background: var(--c-primary-light); }

#end-btn:disabled,
#play-pause-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* --- Config Page --- */
.config-card {
    max-width: 560px;
    margin: 30px auto;
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-xl);
    padding: 30px 40px;
}

.config-card h2 { margin-bottom: 4px; }
.config-card .page-subtitle { margin-bottom: 24px; }

.config-form {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px 20px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-group label {
    font-size: 11px;
    color: var(--c-text-secondary);
    font-weight: 500;
}

.form-group input {
    padding: 8px 12px;
    border: 1px solid var(--c-border-dark);
    border-radius: var(--radius-sm);
    font-size: 14px;
    font-family: var(--font-stack);
    color: var(--c-text);
    transition: border-color 0.15s;
}

.form-group input:focus {
    outline: none;
    border-color: var(--c-primary);
}

.form-buttons {
    grid-column: 1 / -1;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 8px;
}

/* --- Simulation Page --- */
.simulation-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.info-panel {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 10px;
}

.info-item {
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-md);
    padding: 10px 12px;
}

.info-item .label {
    font-size: 10px;
    color: var(--c-text-hint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
}

.info-item span:last-child {
    font-size: 20px;
    font-weight: 600;
    color: var(--c-text);
    display: block;
    margin-top: 2px;
}

.info-item-highlight {
    border-color: var(--c-primary-border);
}

.info-item-highlight .label {
    color: var(--c-primary);
}

.info-item-highlight span:last-child {
    color: var(--c-primary);
}

.canteen-layout {
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-lg);
    padding: 16px;
    overflow: hidden;
}

.canvas-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.canvas-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--c-text);
}

.canvas-legend-bar {
    display: flex;
    gap: 14px;
    font-size: 11px;
    color: var(--c-text-secondary);
}

#canteen-canvas {
    width: 100%;
    height: auto;
    background: #fafaf9;
    border: 1px dashed var(--c-border-dark);
    border-radius: var(--radius-sm);
}

.control-panel {
    display: flex;
    gap: 16px;
    align-items: center;
    padding: 12px 18px;
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-lg);
}

.speed-control {
    display: flex;
    align-items: center;
    gap: 10px;
}

.speed-control label {
    font-size: 12px;
    color: var(--c-text-hint);
}

.speed-control input[type="range"] {
    width: 100px;
    accent-color: var(--c-primary);
}

#speed-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--c-primary);
    min-width: 26px;
}

#end-btn {
    margin-left: auto;
}

/* --- Analysis Page --- */
.stats-overview {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.stat-card {
    padding: 14px;
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-md);
}

.stat-card h3 {
    margin: 0;
    font-size: 11px;
    color: var(--c-text-hint);
    font-weight: 400;
    letter-spacing: 0.05em;
}

.stat-card p {
    margin: 6px 0 0;
    font-size: 26px;
    font-weight: 700;
    color: var(--c-text);
}

.stat-card .stat-sub {
    font-size: 10px;
    color: var(--c-text-disabled);
    margin-top: 2px;
}

.charts-container {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.chart-item {
    padding: 16px;
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-lg);
}

.chart-item h3 {
    margin: 0 0 12px;
    font-size: 14px;
    font-weight: 600;
    color: var(--c-text);
}

.chart { width: 100%; height: 300px; }

.page-actions {
    display: flex;
    justify-content: flex-end;
}

#restart-btn {
    padding: 10px 28px;
    font-weight: 600;
}

/* --- History Page --- */
.history-toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
}

.history-toolbar button {
    padding: 8px 16px;
    font-size: 13px;
}

.history-hint {
    color: var(--c-text-hint);
    font-size: 12px;
}

.history-table-wrap {
    overflow-x: auto;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-lg);
}

.history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.history-table thead {
    background: var(--c-bg);
    color: var(--c-text-secondary);
}

.history-table th,
.history-table td {
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--c-border);
    white-space: nowrap;
}

.history-table tbody tr {
    cursor: pointer;
    transition: background 0.1s;
}

.history-table tbody tr:nth-child(odd) {
    background: var(--c-bg);
}

.history-table tbody tr:hover {
    background: var(--c-primary-light);
}

.history-table tbody tr.active {
    background: #dbeafe;
}

.history-empty {
    text-align: center !important;
    color: var(--c-text-disabled);
    padding: 24px !important;
}

.history-detail {
    margin-top: 20px;
    padding: 16px;
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-lg);
}

.history-detail h3 {
    margin: 0 0 12px;
    color: var(--c-text);
    font-size: 14px;
    font-weight: 600;
}

#history-detail-chart { height: 320px; }

/* --- Responsive --- */
@media (max-width: 900px) {
    .info-panel { grid-template-columns: repeat(3, 1fr); }
    .stats-overview { grid-template-columns: repeat(3, 1fr); }
    .charts-container { grid-template-columns: 1fr; }
    .config-card { margin: 16px; padding: 24px; }
}

@media (max-width: 640px) {
    .info-panel { grid-template-columns: 1fr; }
    .stats-overview { grid-template-columns: repeat(2, 1fr); }
    .config-form { grid-template-columns: 1fr; }
    header { flex-direction: column; gap: 12px; }
    nav ul { flex-wrap: wrap; justify-content: center; }
    .control-panel { flex-wrap: wrap; }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sissi/PycharmProjects/Canteen
git add frontend/static/css/style.css
git commit -m "feat: rewrite CSS with A 学术简约 design system"
```

---

### Task 4: JS adaptations

**Files:**
- Modify: `frontend/static/js/main.js`

- [ ] **Step 1: Replace speedSelect with speedRange + SPEED_MAP**

Replace lines 85 and 126-129:

Old (line 85):
```js
const speedSelect = document.getElementById('speed');
```

New:
```js
const speedRange = document.getElementById('speed-range');
const speedLabel = document.getElementById('speed-label');
const SPEED_MAP = [1, 2, 5, 10];
```

Old (lines 126-129):
```js
speedSelect.addEventListener('change', () => {
    state.speed = parseInt(speedSelect.value, 10);
    if (state.timer) { stopLoop(); startLoop(); }
});
```

New:
```js
speedRange.addEventListener('input', () => {
    state.speed = SPEED_MAP[speedRange.value];
    speedLabel.textContent = `×${state.speed}`;
    if (state.timer) { stopLoop(); startLoop(); }
});
```

- [ ] **Step 2: Add avg-waiting to updateInfoPanel**

Add to end of `updateInfoPanel()` function (after line 185):

```js
    const avgW = data.avg_waiting_time != null ? data.avg_waiting_time.toFixed(1) : '0.0';
    document.getElementById('avg-waiting').textContent = `${avgW} s`;
```

- [ ] **Step 3: Add avg-waiting to resetSimulationState**

Add after line 140 (`document.getElementById('empty-seats').textContent = '0';`):

```js
    document.getElementById('avg-waiting').textContent = '0.0 s';
```

- [ ] **Step 4: Remove Canvas-drawn legend (replaced by HTML legend bar)**

In `drawCanteen()` function (around line 200), remove the `drawLegend(W, H);` call. The HTML-based `.canvas-legend-bar` (see Step 7) replaces it.

Also in `drawBackground()` (line 211), remove the "食堂平面图（示意）" fillText call — the HTML `.canvas-title` already shows "食堂平面布局".

- [ ] **Step 5: Update drawWindows color to match primary**

In `drawWindows` function (line 226), change:

Old:
```js
        const color = w.is_serving ? '#2e50d4' : '#94a3b8';
```

New:
```js
        const color = w.is_serving ? '#b91c1c' : '#94a3b8';
```

Also update window text color references — change `'#1e3a8a'` stroke (line 229) to `'#991b1b'`.

- [ ] **Step 6: Update ECharts colors in renderCharts**

In `renderCharts()`, update bar chart color (line 420):

Old: `itemStyle: { color: '#2e50d4' }`
New: `itemStyle: { color: '#b91c1c' }`

In history chart (line 555), update arrived line color:

Old: `itemStyle: { color: '#2e50d4' }`
New: `itemStyle: { color: '#b91c1c' }`

- [ ] **Step 7: Populate canvas legend bar in HTML via JS**

Add to the end of the file (before the `apiPost` utility function):

```js
// Populate the HTML-based legend bar above canvas (replaces Canvas-drawn drawLegend)
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
```

- [ ] **Step 8: Commit**

```bash
cd /Users/sissi/PycharmProjects/Canteen
git add frontend/static/js/main.js
git commit -m "feat: JS adaptations for speed slider, avg-waiting, and design colors"
```

---

### Task 5: Integration verification

- [ ] **Step 1: Run pytest**

```bash
cd /Users/sissi/PycharmProjects/Canteen/backend && python -m pytest tests/ -v
```

Expected: 39 passed

- [ ] **Step 2: Start dev server**

```bash
cd /Users/sissi/PycharmProjects/Canteen/backend && python app.py &
```

- [ ] **Step 3: Manual walkthrough**

Open `http://localhost:5001` in browser and verify:

1. **参数配置页**: centered card, dual-column form, BJTU red button, subtitle visible
2. **开始仿真**: click "开始仿真", auto-navigates to simulation page
3. **仿真运行页**: 7 info cards in horizontal row (7th is "平均等待" with red border), canvas with legend bar above, speed slider works (drag to change speed label)
4. **平均等待**: updates each step, non-negative, NOT necessarily increasing
5. **Canvas**: student dots animate, seat heatmap colors visible, legend at bottom
6. **结束仿真**: click → auto-navigates to analysis page
7. **数据分析页**: 6 stat cards in single row, 4 charts (bar/pie/line/area), restart button bottom-right
8. **历史记录页**: zebra-striped table, hover highlights in light red, detail chart in card
9. **Responsive**: resize window below 900px → info panel wraps to 3 columns

- [ ] **Step 4: Stop dev server**

```bash
kill %1
```

- [ ] **Step 5: Final commit (if any tweaks needed)**

```bash
cd /Users/sissi/PycharmProjects/Canteen
git add -A
git commit -m "fix: visual tweaks from integration testing"
```

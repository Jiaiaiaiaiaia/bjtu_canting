// intervention_ui.js — 右侧三段竖排运维台（spec §4.3）
//
// 三段（顶/中/底）：
//  - 顶 = KPI 大数字：总览态显全局，下钻态显本层（全部读后端 snapshot/totals）。
//  - 中 = 按楼层分组的窗口开关网格：▣ 开 / ▢ 关，可点；点击调
//    POST /api/campus/canteens/<cid>/windows/<wid>/toggle {open:bool}（E3 端点），
//    用返回的 snapshot/interventions 反映结果。
//  - 底 = 干预事件流滚动日志（时间·层·窗·动作·结果），即 §3.4 interventions 的 UI 出口。
//
// 视觉：冷青监控——青字 KPI、深青底，与 3D 场景一致。纯 DOM 叠加，不引新库。

const API_BASE = '/api';
const PANEL_ID = 'three-ops-console';
const LEGEND_ID = 'twin-congestion-legend';

// 内联样式只保留结构必需项；颜色 / 玻璃质感由 style.css .twin-immersive 覆盖（V9 任务）。
// V7 冷青色值：bg #07111d / accent #2dd4bf / muted #8fb7b2 / border #2c5366。
const CSS = `
#${PANEL_ID}{position:absolute;top:12px;right:12px;width:268px;max-height:calc(100% - 24px);
 display:flex;flex-direction:column;gap:10px;color:#cfe9e6;
 background:rgba(7,17,29,.82);border:1px solid #315467;border-radius:8px;padding:12px;
 box-sizing:border-box;z-index:6;pointer-events:auto}
#${PANEL_ID} .ops-kpi{display:grid;grid-template-columns:1fr 1fr;gap:6px}
#${PANEL_ID} .ops-kpi .cell{background:rgba(45,212,191,.08);border:1px solid #2c5366;
 border-radius:6px;padding:5px 8px}
#${PANEL_ID} .ops-kpi .cell b{display:block;font-size:18px;color:#2dd4bf;line-height:1.1}
#${PANEL_ID} .ops-kpi .cell span{font-size:11px;color:#8fb7b2}
#${PANEL_ID} .ops-title{font-size:11px;color:#8fb7b2;letter-spacing:1px;margin:2px 0}
#${PANEL_ID} .ops-floor{margin-bottom:6px}
#${PANEL_ID} .ops-floor>label{font-size:11px;color:#9fc6c1}
#${PANEL_ID} .ops-win{display:flex;flex-wrap:wrap;gap:4px;margin-top:3px}
#${PANEL_ID} .ops-win button{font-size:11px;cursor:pointer;border-radius:4px;
 border:1px solid #2c5366;background:#0d2030;color:#cfe9e6;padding:2px 6px;min-width:34px}
#${PANEL_ID} .ops-win button.open{background:#16453a;border-color:#2dd4bf;color:#7df0dd}
#${PANEL_ID} .ops-win button.closed{background:#3a2b2f;border-color:#d64a55;color:#e7a3a8}
#${PANEL_ID} .ops-win button:disabled{opacity:.5;cursor:progress}
#${PANEL_ID} .ops-log{flex:1;overflow-y:auto;max-height:160px;font-size:11px;
 background:rgba(0,0,0,.25);border:1px solid #24414f;border-radius:6px;padding:6px}
#${PANEL_ID} .ops-log .row{padding:2px 0;border-bottom:1px dashed #1f3946}
#${PANEL_ID} .ops-log .row.rejected{color:#e7a3a8}
#${PANEL_ID} .ops-log .row.applied{color:#7df0dd}
`;

export class InterventionUI {
    constructor() {
        this.root = null;
        this.kpiEl = null;
        this.gridEl = null;
        this.logEl = null;
        this._canteenId = null;
        this._busy = new Set();         // 进行中的 toggle 键，防重复点击
        // 干预后端回包回调：scene3d 用返回 snapshot 立即刷新一帧。
        this.onSnapshot = null;
    }

    mount(container) {
        if (!container) return;
        if (!document.getElementById(`${PANEL_ID}-style`)) {
            const style = document.createElement('style');
            style.id = `${PANEL_ID}-style`;
            style.textContent = CSS;
            document.head.appendChild(style);
        }
        if (this.root && this.root.parentElement === container) return;
        this._teardownDom();
        // container 需是定位上下文；three-stage 已是块级，set relative 兜底。
        if (getComputedStyle(container).position === 'static') {
            container.style.position = 'relative';
        }
        const root = document.createElement('div');
        root.id = PANEL_ID;
        root.innerHTML = `
            <div>
              <div class="ops-title">KPI</div>
              <div class="ops-kpi"></div>
            </div>
            <div>
              <div class="ops-title">窗口开关</div>
              <div class="ops-grid"></div>
            </div>
            <div style="display:flex;flex-direction:column;flex:1;min-height:0">
              <div class="ops-title">干预事件流</div>
              <div class="ops-log"></div>
            </div>`;
        container.appendChild(root);
        // 拥堵图例（青→琥珀→红），与 canteen_scene heatColor 语义连续；
        // 仅 3D 运维台挂载时出现，纯展示、pointer-events 透传（见 .twin-legend CSS）。
        if (!container.querySelector(`#${LEGEND_ID}`)) {
            const legend = document.createElement('div');
            legend.id = LEGEND_ID;
            legend.className = 'twin-legend';
            legend.innerHTML = `
                <span class="twin-legend-title">拥堵</span>
                <div>
                  <div class="twin-legend-scale"></div>
                  <div class="twin-legend-ends">
                    <span class="twin-legend-min">畅通</span>
                    <span class="twin-legend-max">拥堵</span>
                  </div>
                </div>`;
            container.appendChild(legend);
        }
        this.root = root;
        this.kpiEl = root.querySelector('.ops-kpi');
        this.gridEl = root.querySelector('.ops-grid');
        this.logEl = root.querySelector('.ops-log');
    }

    _teardownDom() {
        const existing = document.getElementById(PANEL_ID);
        if (existing) existing.remove();
        const legend = document.getElementById(LEGEND_ID);
        if (legend) legend.remove();
        this.root = null;
    }

    dispose() {
        this._teardownDom();
        this._busy.clear();
    }

    // frame 来自 state_adapter.buildFrame；mode = 'overview' | 'focus'。
    render(frame, mode, focusFloorId) {
        if (!this.root || !frame) return;
        this._canteenId = frame.canteenId;
        this._renderKpi(frame, mode, focusFloorId);
        this._renderGrid(frame, focusFloorId);
        this._renderLog(frame.interventions || []);
    }

    _renderKpi(frame, mode, focusFloorId) {
        let cells;
        if (mode === 'focus' && focusFloorId != null) {
            const f = frame.perFloorKpi.find(k => k.floor_id === focusFloorId)
                || frame.perFloorKpi[0] || {};
            cells = [
                [`${focusFloorId}F 排队`, f.total_in_queue ?? 0],
                ['就餐', f.total_eating ?? 0],
                ['空座', f.empty_seats ?? 0],
                ['开放窗', `${f.open_windows ?? 0}/${f.window_count ?? 0}`],
            ];
        } else {
            const k = frame.kpi || {};
            cells = [
                ['累计到达', k.total_arrived ?? 0],
                ['累计完成', k.total_served ?? 0],
                ['排队中', k.total_in_queue ?? 0],
                ['就餐中', k.total_eating ?? 0],
            ];
        }
        this.kpiEl.innerHTML = cells.map(([label, val]) =>
            `<div class="cell"><b>${val}</b><span>${label}</span></div>`).join('');
    }

    _renderGrid(frame, focusFloorId) {
        const floors = (frame.floors || []).filter(f =>
            focusFloorId == null || f.floor_id === focusFloorId);
        this.gridEl.innerHTML = '';
        floors.forEach(floor => {
            const block = document.createElement('div');
            block.className = 'ops-floor';
            const label = document.createElement('label');
            label.textContent = `${floor.floor_id}F`;
            const row = document.createElement('div');
            row.className = 'ops-win';
            floor.windows.forEach(win => {
                const key = `${this._canteenId}#${win.id}`;
                const btn = document.createElement('button');
                const isOpen = win.is_open;
                btn.className = isOpen ? 'open' : 'closed';
                btn.textContent = `${isOpen ? '▣' : '▢'}${win.id}`;
                btn.title = isOpen
                    ? `窗口 ${win.id} 开放（点击关闭）`
                    : `窗口 ${win.id}${win.closing ? ' 关闭中' : ' 已关'}（点击开启）`;
                btn.disabled = this._busy.has(key);
                btn.addEventListener('click', () =>
                    this._toggle(win.id, !isOpen, key));
                row.appendChild(btn);
            });
            block.appendChild(label);
            block.appendChild(row);
            this.gridEl.appendChild(block);
        });
    }

    _renderLog(interventions) {
        // 倒序展示最近事件（滚动日志）。
        const rows = interventions.slice(-40).reverse().map(ev => {
            const t = Math.round(ev.time ?? 0);
            const cls = ev.status === 'rejected' ? 'rejected' : 'applied';
            const act = ev.action === 'open' ? '开窗' : '关窗';
            const res = ev.status === 'rejected'
                ? `拒绝(${ev.reason || ''})` : '已生效';
            const fl = ev.floor_id == null ? '-' : `${ev.floor_id}F`;
            return `<div class="row ${cls}">t=${t}s · ${fl} · 窗${ev.window_id}`
                + ` · ${act} · ${res}</div>`;
        });
        this.logEl.innerHTML = rows.join('') || '<div class="row">暂无干预</div>';
    }

    // 调 E3 端点；用返回 snapshot 立即刷新（不等下一 step 帧）。
    async _toggle(windowId, open, key) {
        if (this._busy.has(key) || !this._canteenId) return;
        this._busy.add(key);
        this._refreshDisabled();
        try {
            const res = await fetch(
                `${API_BASE}/campus/canteens/${encodeURIComponent(this._canteenId)}`
                + `/windows/${windowId}/toggle`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ open }),
                }
            );
            if (res.ok) {
                const snapshot = await res.json();
                if (typeof this.onSnapshot === 'function') {
                    this.onSnapshot(snapshot);
                }
            }
        } catch (err) {
            // 网络失败静默：下一帧 snapshot 会自然纠正显示状态。
        } finally {
            this._busy.delete(key);
            this._refreshDisabled();
        }
    }

    _refreshDisabled() {
        if (!this.gridEl) return;
        this.gridEl.querySelectorAll('button').forEach(btn => {
            // 按钮文本含窗口号，结合当前 canteenId 还原 busy 键。
            const wid = (btn.textContent || '').replace(/[▣▢]/g, '');
            btn.disabled = this._busy.has(`${this._canteenId}#${wid}`);
        });
    }
}

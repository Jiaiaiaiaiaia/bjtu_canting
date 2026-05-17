/**
 * immersive_ui.js — V6 glass overlay for #three-stage
 *
 * Pure DOM overlay module. No imports, no external libraries.
 * Wired into scene3d.js in V7 via new ImmersiveUI().mount/update/dispose.
 *
 * DOM reachability strategy:
 *   - "返回 2D"  → document.querySelector('#render-switcher [data-render="2d"]')?.click()
 *   - Nav pages  → document.querySelector('.nav-link[data-page="config"]')?.click()  etc.
 *   Both query selectors contain the literal substrings `data-render` and `data-page`
 *   required by test_immersive_ui_module_contract.
 */

export class ImmersiveUI {
    constructor() {
        this._root = null;       // injected root div (#twin-immersive-ui)
        this._statusEl = null;   // .twin-status element
        this._floorstrip = null; // .twin-floorstrip element
        this._cutaway = false;
        this._heat = false;
        this._sceneApi = null;
    }

    /**
     * mount(container) — idempotent: removes any pre-existing root first.
     * @param {HTMLElement} container  The #three-stage element.
     */
    mount(container) {
        // Idempotency: remove existing root if already mounted
        const existing = container.querySelector('#twin-immersive-ui');
        if (existing) existing.remove();

        const root = document.createElement('div');
        root.id = 'twin-immersive-ui';
        this._root = root;

        // ── Topbar ──────────────────────────────────────────────────────────
        const topbar = document.createElement('div');
        topbar.className = 'twin-topbar';

        const brand = document.createElement('span');
        brand.className = 'twin-topbar-brand';
        brand.textContent = '北交大食堂数字孪生';
        topbar.appendChild(brand);

        // 视图切换区段：校园视图 / 食堂视图（通过现有 render-switcher 实现）
        const viewSeg = document.createElement('div');
        viewSeg.className = 'twin-topbar-view-seg';

        const btn3D = document.createElement('button');
        btn3D.className = 'twin-topbar-view-btn active';
        btn3D.textContent = '3D 食堂';
        // 点击现有的 [data-render="3d"] 按钮（已在 main.js 绑定）
        btn3D.addEventListener('click', () => {
            document.querySelector('#render-switcher [data-render="3d"]')?.click();
        });

        const btn2D = document.createElement('button');
        btn2D.className = 'twin-topbar-view-btn';
        btn2D.textContent = '返回 2D';
        // 返回 2D：点击现有 [data-render="2d"] 按钮
        btn2D.addEventListener('click', () => {
            document.querySelector('#render-switcher [data-render="2d"]')?.click();
        });

        viewSeg.appendChild(btn3D);
        viewSeg.appendChild(btn2D);
        topbar.appendChild(viewSeg);

        // 导航快捷入口（复用现有 nav-link[data-page] → showPage）
        const navSeg = document.createElement('div');
        navSeg.className = 'twin-topbar-nav';

        const navPages = [
            { label: '参数', page: 'config' },
            { label: '分析', page: 'analysis' },
            { label: '历史', page: 'history' },
        ];
        navPages.forEach(({ label, page }) => {
            const a = document.createElement('button');
            a.className = 'twin-topbar-nav-btn';
            a.textContent = label;
            // 点击现有 .nav-link[data-page="..."] 按钮驱动 showPage
            a.addEventListener('click', () => {
                document.querySelector(`.nav-link[data-page="${page}"]`)?.click();
            });
            navSeg.appendChild(a);
        });

        topbar.appendChild(navSeg);
        root.appendChild(topbar);

        // ── Toolbar ─────────────────────────────────────────────────────────
        const toolbar = document.createElement('div');
        toolbar.className = 'twin-toolbar';

        // 剖 cutaway 切换
        const cutawayBtn = document.createElement('button');
        cutawayBtn.className = 'twin-toolbar-btn';
        cutawayBtn.title = '剖面视图';
        cutawayBtn.textContent = '剖';
        cutawayBtn.addEventListener('click', () => {
            this._cutaway = !this._cutaway;
            cutawayBtn.classList.toggle('active', this._cutaway);
            this._sceneApi?.setCutaway?.(this._cutaway);
        });
        toolbar.appendChild(cutawayBtn);

        // 热 heat toggle
        const heatBtn = document.createElement('button');
        heatBtn.className = 'twin-toolbar-btn';
        heatBtn.title = '热力图';
        heatBtn.textContent = '热';
        heatBtn.addEventListener('click', () => {
            this._heat = !this._heat;
            heatBtn.classList.toggle('active', this._heat);
            this._sceneApi?.setHeat?.(this._heat);
        });
        toolbar.appendChild(heatBtn);

        // 播放/暂停
        const pauseBtn = document.createElement('button');
        pauseBtn.className = 'twin-toolbar-btn';
        pauseBtn.title = '播放/暂停';
        pauseBtn.textContent = '▶';
        pauseBtn.addEventListener('click', () => {
            this._sceneApi?.togglePause?.();
            // 切换图标（视 API 是否有 paused 状态，这里乐观翻转）
            pauseBtn.textContent = pauseBtn.textContent === '▶' ? '⏸' : '▶';
        });
        toolbar.appendChild(pauseBtn);

        // 复位视角
        const resetBtn = document.createElement('button');
        resetBtn.className = 'twin-toolbar-btn';
        resetBtn.title = '复位视角';
        resetBtn.textContent = '⌂';
        resetBtn.addEventListener('click', () => {
            // resetCamera 优先，兜底 resetView
            if (this._sceneApi?.resetCamera) {
                this._sceneApi.resetCamera();
            } else {
                this._sceneApi?.resetView?.();
            }
        });
        toolbar.appendChild(resetBtn);

        root.appendChild(toolbar);

        // ── Floorstrip ───────────────────────────────────────────────────────
        const floorstrip = document.createElement('div');
        floorstrip.className = 'twin-floorstrip';

        const allFloorBtn = document.createElement('button');
        allFloorBtn.className = 'twin-floorstrip-btn active';
        allFloorBtn.textContent = '整栋';
        allFloorBtn.addEventListener('click', () => {
            this._sceneApi?.resetView?.();
            // 清除其他楼层按钮 active
            floorstrip.querySelectorAll('.twin-floorstrip-btn').forEach(b =>
                b.classList.remove('active'));
            allFloorBtn.classList.add('active');
        });
        floorstrip.appendChild(allFloorBtn);

        this._floorstrip = floorstrip;
        root.appendChild(floorstrip);

        // ── Status line ──────────────────────────────────────────────────────
        const status = document.createElement('div');
        status.className = 'twin-status';
        status.textContent = '就绪';
        this._statusEl = status;
        root.appendChild(status);

        // ── Tooltip ──────────────────────────────────────────────────────────
        const tooltip = document.createElement('div');
        tooltip.className = 'twin-tooltip';
        tooltip.style.display = 'none';
        root.appendChild(tooltip);

        container.appendChild(root);
    }

    /**
     * update(frame, sceneApi) — refresh floorstrip + status from latest frame.
     * Called each render cycle by scene3d; guards null frame (campus path).
     * @param {object|null} frame    仿真快照帧（可能为 null）
     * @param {object}      sceneApi scene3d 传入的 API 对象
     */
    update(frame, sceneApi) {
        // 保存最新 sceneApi 引用（toolbar 按钮点击时用）
        this._sceneApi = sceneApi;

        if (!this._root) return;

        // ── 更新 floorstrip 楼层按钮 ──────────────────────────────────────
        if (frame && Array.isArray(frame.floors)) {
            // 构建当前楼层 id 集合
            const ids = frame.floors.map(f => f.floor_id);
            const strip = this._floorstrip;

            // 对比已有按钮，避免频繁重建（以 data-floor 为 key）
            const existingBtns = new Map();
            strip.querySelectorAll('.twin-floorstrip-btn[data-floor]').forEach(b =>
                existingBtns.set(b.dataset.floor, b));

            const desiredSet = new Set(ids.map(String));

            // 移除已不存在的楼层按钮
            existingBtns.forEach((btn, id) => {
                if (!desiredSet.has(id)) btn.remove();
            });

            // 追加新楼层按钮（按顺序）
            ids.forEach(floorId => {
                const key = String(floorId);
                if (!existingBtns.has(key)) {
                    const btn = document.createElement('button');
                    btn.className = 'twin-floorstrip-btn';
                    btn.dataset.floor = key;
                    btn.textContent = `${floorId}F`;
                    btn.addEventListener('click', () => {
                        this._sceneApi?.focusFloor?.(floorId);
                        strip.querySelectorAll('.twin-floorstrip-btn').forEach(b =>
                            b.classList.remove('active'));
                        btn.classList.add('active');
                    });
                    strip.appendChild(btn);
                }
            });
        }
        // 若 frame 为 null（campus 路径），保留已有的空/中性 strip，不抛出

        // ── 更新 status 文本 ─────────────────────────────────────────────
        if (this._statusEl) {
            if (frame) {
                const time = frame.sim_time != null ? `T=${frame.sim_time}s` : '';
                const students = frame.students_in_canteen != null
                    ? `在场 ${frame.students_in_canteen} 人`
                    : '';
                this._statusEl.textContent = [time, students].filter(Boolean).join(' · ') || '运行中';
            } else {
                this._statusEl.textContent = '就绪';
            }
        }
    }

    /**
     * dispose() — remove injected root and clear all refs.
     */
    dispose() {
        if (this._root) {
            this._root.remove();
            this._root = null;
        }
        this._statusEl = null;
        this._floorstrip = null;
        this._sceneApi = null;
        this._cutaway = false;
        this._heat = false;
    }
}

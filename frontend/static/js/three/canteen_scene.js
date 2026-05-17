// canteen_scene.js — 单食堂多层 3D 构建 + A+C 混合相机状态机（spec §4.1）
//
// 职责：
//  - 把 state_adapter 给的稳定帧（floors[] + windows/seats/students）建成
//    「3 层竖向堆叠 + 正面剖面」的 3D 场景（spec §4.1 默认/总览态 A）。
//  - A+C 状态机（方案 2）：OVERVIEW（堆叠剖面环绕）↔ FOCUS（飞入某层、
//    非焦点层滑开收起，给焦点层最大屏幕）。点层/Tab 进 FOCUS，「全景」回 A。
//  - 「到达→窗口→座位→离场」发光路径高亮；可点名追踪单个学生。
//
// 视觉 identity = 冷青监控（spec §4.2）：沿用 scene3d 调色——深青底
// 0x07111d、青绿网格 0x315467/0x2dd4bf、拥堵热力青→琥珀→红、发光流线青、
// 关窗暗+「关闭中」、空关灰、KPI 青字。THREE 实例由 scene3d 注入（单一
// importmap 依赖），不在本模块重复 import three。

const FLOOR_GAP = 110;          // 增大到 110，三层堆叠清晰可读
const FLOOR_RISE = 0;           // 层间高差（场景已竖向展开，无需额外偏移）
const FOCUS_SLIDE = 520;        // FOCUS 态非焦点层滑开距离
const CAM_LERP = 0.08;          // 相机/层位移插值系数

// 食堂建筑尺寸（world-unit，与现有坐标系匹配）
const BASE_W = 260;
const BASE_D = 54;

// 冷青监控调色（与 scene3d / canvas_renderer 图例语义连续）。
const PALETTE = {
    deck: 0x263a50,
    windowOpen: 0xd64a55,
    windowIdle: 0x94a8b5,
    windowClosing: 0x3f5168,     // 关窗暗
    windowClosedEmpty: 0x55636f, // 空关灰
    seatOccupied: 0xe7bd63,
    seatEmpty: 0x77d993,
    studentQueue: 0x9333ea,
    studentMove: 0x52d6d1,
    flow: 0x2dd4bf,              // 发光流线青
    label: '#eef6f4',
    labelKpi: '#2dd4bf',
};

// 拥堵热力青→琥珀→红（按队列饱和度 0..1）。
function heatColor(THREE, t) {
    const x = Math.max(0, Math.min(1, t));
    const teal = new THREE.Color(0x2dd4bf);
    const amber = new THREE.Color(0xe7bd63);
    const red = new THREE.Color(0xd64a55);
    return x < 0.5
        ? teal.clone().lerp(amber, x / 0.5)
        : amber.clone().lerp(red, (x - 0.5) / 0.5);
}

export class CanteenScene {
    constructor(THREE, scene, camera, controls) {
        this.THREE = THREE;
        this.scene = scene;
        this.camera = camera;
        this.controls = controls;
        this.group = new THREE.Group();
        scene.add(this.group);

        // A+C 状态机
        this.mode = 'overview';        // 'overview' | 'focus'
        this.focusFloorId = null;
        this.trackedStudentId = null;
        this._floorGroups = new Map(); // floorId -> THREE.Group（用于滑开动画）
        this._floorSlide = new Map();  // floorId -> 当前插值位移
        this._floorCount = 0;

        // 剖切/热力模式（与 immersive_ui 绑定时赋值，默认剖切展示）
        this.cutaway = true;
        this.heatMode = false;

        // 相机目标（插值逼近，离散切换→平滑飞入）
        this._camTarget = { pos: new THREE.Vector3(160, 260, 560),
                            look: new THREE.Vector3(160, 80, 60) };
        this._lastFrame = null;
    }

    // 对外只读：最近一次 update 的稳定帧（animate() 复用，避免触达私有字段）。
    get lastFrame() {
        return this._lastFrame;
    }

    // 对外清场入口（campus 切换时由 core 调用），内部仍走 _clear()。
    clearScene() {
        this._clear();
    }

    // 点层 / 楼层 Tab → 飞入该层（非焦点层滑开）。
    focusFloor(floorId) {
        this.mode = 'focus';
        this.focusFloorId = floorId;
        this._recomputeCameraTarget();
    }

    // 空白处 / 「全景」→ 回 A 总览。
    resetView() {
        this.mode = 'overview';
        this.focusFloorId = null;
        this.trackedStudentId = null;
        this._recomputeCameraTarget();
    }

    trackStudent(studentId) {
        this.trackedStudentId = studentId == null ? null : String(studentId);
    }

    // 快照到达时调用（data-rebuild path）：重建几何体 + 重算相机目标。
    // RAF 路径的动画推进由 tick() 完成，update() 不再调用 _animateFloors/_animateCamera。
    update(frame) {
        this._lastFrame = frame;
        this._floorCount = frame ? frame.floors.length : 0;
        this._rebuild(frame);
        this._recomputeCameraTarget();
    }

    // RAF 每帧调用（scene3d.animate() 调用）：仅推进插值动画，不重建几何。
    // First-frame safety: 快照到达前 tick 空转，不访问未初始化的 floorGroups。
    tick() {
        if (!this._lastFrame || this._floorGroups.size === 0) return;
        this._animateFloors();
        this._animateCamera();
    }

    // ---- 内部：场景构建 ----

    _clear() {
        // SpriteMaterial.dispose() 不会释放其 .map 纹理（_label 的 CanvasTexture），
        // 而 update()/_rebuild() 每帧重建标签，故须显式 dispose 纹理避免 GPU 泄漏。
        const disposeMat = m => {
            m?.map?.dispose?.();
            m?.dispose?.();
        };
        const dispose = obj => obj.traverse?.(node => {
            node.geometry?.dispose?.();
            if (Array.isArray(node.material)) node.material.forEach(disposeMat);
            else disposeMat(node.material);
        });
        while (this.group.children.length) {
            const child = this.group.children.pop();
            dispose(child);
        }
        this._floorGroups.clear();
    }

    _mat(color, opacity, emissive, emissiveIntensity) {
        return new this.THREE.MeshStandardMaterial({
            color,
            roughness: 0.72,
            metalness: 0.04,
            transparent: opacity != null,
            opacity: opacity == null ? 1 : opacity,
            emissive: emissive != null ? emissive : 0x000000,
            emissiveIntensity: emissiveIntensity != null ? emissiveIntensity : 0,
        });
    }

    _label(text, x, y, z, color, opacity) {
        const canvas = document.createElement('canvas');
        canvas.width = 320;
        canvas.height = 72;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'rgba(7,17,29,0.76)';
        ctx.roundRect?.(4, 4, 312, 64, 10);
        ctx.fill?.();
        ctx.fillStyle = color || PALETTE.label;
        ctx.font = 'bold 26px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, 160, 38);
        const texture = new this.THREE.CanvasTexture(canvas);
        const mat = new this.THREE.SpriteMaterial({ map: texture, transparent: true });
        if (opacity != null) mat.opacity = opacity;
        const sprite = new this.THREE.Sprite(mat);
        sprite.position.set(x, y, z);
        sprite.scale.set(90, 22, 1);
        return sprite;
    }

    _rebuild(frame) {
        const THREE = this.THREE;
        this._clear();
        if (!frame) return;

        // ---- Site plinth（深青大底座，V7 visual identity）----
        const totalSpan = Math.max(1, frame.floors.length) * FLOOR_GAP;
        const plinth = new THREE.Mesh(
            new THREE.BoxGeometry(BASE_W + 28, 6, BASE_D + 24),
            this._mat(0x13243a, undefined, undefined, undefined)
        );
        plinth.position.set(160, -3, BASE_D / 2);
        this.group.add(plinth);

        // 食堂名标签
        this.group.add(this._label(frame.displayName || '食堂', 160, totalSpan + 30, -20,
            PALETTE.labelKpi));

        // ---- Vertical stair core（跨所有楼层的垂直交通核，V7 stairCore）----
        const stairHeight = totalSpan + 10;
        const stairCore = new THREE.Mesh(
            new THREE.BoxGeometry(14, stairHeight, 14),
            this._mat(0x52d6d1, 0.65, 0x52d6d1, 0.18)
        );
        stairCore.position.set(160 - BASE_W / 2 + 18, stairHeight / 2 - 3, BASE_D / 2 - 14);
        stairCore.userData = { kind: 'stairCore' };
        this.group.add(stairCore);

        // 入口标记
        const entrance = new THREE.Mesh(
            new THREE.BoxGeometry(20, 7, 10),
            this._mat(0x52d6d1, undefined, 0x52d6d1, 0.32)
        );
        entrance.position.set(160 - BASE_W / 2 + 28, 4, BASE_D - 6);
        this.group.add(entrance);

        frame.floors.forEach(floor => {
            const fg = new THREE.Group();
            fg.userData = { floorId: floor.floor_id, kind: 'floor' };
            this._floorGroups.set(floor.floor_id, fg);

            // 楼层基准 Y（frame 给的 baseY 已带 index*FLOOR_GAP 偏移）
            const baseY = floor.baseY;
            const fz = BASE_D / 2;  // 使用固定中心 Z，不依赖 frame.z（坐标系一致）

            // ---- 楼板 slab（交替色 + 热力模式）----
            const slabBaseColor = floor.index % 2 ? 0x243f56 : 0x263a50;
            // heatColor 用于热力模式时楼板着色（利用最大队列饱和度）
            const maxSat = floor.windows.length > 0
                ? Math.min(1, Math.max(...floor.windows.map(w => (w.queue_length || 0) / 12)))
                : 0;
            const hc = heatColor(THREE, maxSat);
            const slabColor = this.heatMode ? hc.getHex() : slabBaseColor;
            const slab = new THREE.Mesh(
                new THREE.BoxGeometry(BASE_W, 5, BASE_D),
                this.heatMode
                    ? new THREE.MeshStandardMaterial({
                        color: slabColor, roughness: 0.72,
                        emissive: slabColor, emissiveIntensity: 0.18,
                    })
                    : this._mat(slabColor)
            );
            slab.position.set(160, baseY, fz);
            slab.userData = { floorId: floor.floor_id, kind: 'floor' };
            fg.add(slab);

            // ---- front glass curtain wall（剖切时不建正面，让内部可见）----
            // cutaway 为 true 时省略正面玻璃幕墙，interior 全可见
            if (!this.cutaway) {
                const frontGlass = new THREE.Mesh(
                    new THREE.BoxGeometry(BASE_W, 26, 2),
                    this._mat(0xbdebf2, 0.20)
                );
                frontGlass.name = 'front glass';
                frontGlass.position.set(160, baseY + 14, BASE_D - 1);
                fg.add(frontGlass);
            }

            // 后墙 + 侧墙（半透明）
            const backWall = new THREE.Mesh(
                new THREE.BoxGeometry(BASE_W, 26, 2),
                this._mat(0xbdebf2, 0.15)
            );
            backWall.position.set(160, baseY + 14, 1);
            fg.add(backWall);

            const leftWall = new THREE.Mesh(
                new THREE.BoxGeometry(2, 26, BASE_D),
                this._mat(0xbdebf2, 0.10)
            );
            leftWall.position.set(160 - BASE_W / 2, baseY + 14, fz);
            fg.add(leftWall);

            const rightWall = new THREE.Mesh(
                new THREE.BoxGeometry(2, 26, BASE_D),
                this._mat(0xbdebf2, 0.10)
            );
            rightWall.position.set(160 + BASE_W / 2, baseY + 14, fz);
            fg.add(rightWall);

            // ---- 楼层标签 sprite（非焦点层降透明度）----
            const isFocused = this.mode === 'overview' || this.focusFloorId === floor.floor_id;
            const labelText = `${floor.floor_id} · ${floor.windows.length}窗 · ${floor.seats.length}座`;
            const labelOp = isFocused ? 1.0 : 0.35;
            const lbl = this._label(
                labelText,
                160 - BASE_W / 2 + 50, baseY + 22, -10,
                isFocused ? PALETTE.labelKpi : PALETTE.label,
                labelOp
            );
            fg.add(lbl);

            // 焦点角标
            if (this.mode === 'focus' && this.focusFloorId === floor.floor_id) {
                const fTag = this._label(
                    `${floor.floor_id}F ◀ 焦点`, 160, baseY + 38, -30,
                    PALETTE.labelKpi, 1.0
                );
                fg.add(fTag);
            }

            // ---- 窗口（保持 userData.kind='window' 供 raycaster drill-down）----
            floor.windows.forEach(win => {
                // is_open + is_serving → 红；is_open → teal idle；!is_open → dim
                let winColor = PALETTE.windowIdle;
                if (win.is_open) {
                    winColor = win.is_serving ? PALETTE.windowOpen : 0x2dd4bf;
                } else {
                    winColor = win.closing ? PALETTE.windowClosing : PALETTE.windowClosedEmpty;
                }
                const stall = new THREE.Mesh(
                    new THREE.BoxGeometry(18, 20, 18),
                    this._mat(winColor, win.is_open ? undefined : 0.78)
                );
                stall.position.set(win.position.x, win.position.y, win.position.z);
                stall.userData = { floorId: floor.floor_id, kind: 'window',
                                   windowId: win.id };
                fg.add(stall);

                // 队列热力顶盖（用 heatColor）
                const sat = Math.min(1, (win.queue_length || 0) / 12);
                if (win.is_open && sat > 0) {
                    const hc2 = heatColor(THREE, sat);
                    const cap = new THREE.Mesh(
                        new THREE.BoxGeometry(18, 2.4, 18),
                        new THREE.MeshStandardMaterial({
                            color: hc2,
                            emissive: hc2,
                            emissiveIntensity: 0.45,
                        })
                    );
                    cap.position.set(win.position.x, win.position.y + 11, win.position.z);
                    fg.add(cap);
                }
                if (!win.is_open && win.closing) {
                    fg.add(this._label('关闭中', win.position.x,
                        win.position.y + 18, win.position.z, '#e7bd63'));
                }
            });

            // ---- 座位（保持 userData 兼容）----
            floor.seats.forEach(seat => {
                const seatMesh = new THREE.Mesh(
                    new THREE.BoxGeometry(8, 4, 8),
                    this._mat(seat.status === 'occupied'
                        ? PALETTE.seatOccupied : PALETTE.seatEmpty)
                );
                seatMesh.position.set(seat.position.x, seat.position.y, seat.position.z);
                fg.add(seatMesh);
            });

            // ---- 学生/队列点（userData.kind='student' 供 raycaster）----
            floor.students.forEach(student => {
                const p = student.position3d || student.target;
                const isTracked = this.trackedStudentId != null
                    && String(student.id) === this.trackedStudentId;
                const color = student.position === 'window_queue'
                    || student.position === 'waiting_queue'
                    ? PALETTE.studentQueue : PALETTE.studentMove;
                const dot = new THREE.Mesh(
                    new THREE.SphereGeometry(isTracked ? 5.4 : 3.6, 12, 8),
                    isTracked
                        ? new THREE.MeshStandardMaterial({
                            color: PALETTE.flow, emissive: PALETTE.flow,
                            emissiveIntensity: 0.7 })
                        : this._mat(color)
                );
                dot.position.set(p.x, p.y, p.z);
                dot.userData = { floorId: floor.floor_id, kind: 'student',
                                 studentId: student.id };
                fg.add(dot);
            });

            // ---- 焦点层：发光流线路径（_flowPath 复用，绑定到新材质）----
            if (this.mode === 'focus' && this.focusFloorId === floor.floor_id) {
                fg.add(this._flowPath(floor));
            }

            this.group.add(fg);
        });
    }

    // 发光流线：到达点 → 窗口排 → 座位区 → 离场，冷青发光（spec §4.1 人流分析）。
    _flowPath(floor) {
        const THREE = this.THREE;
        const baseY = floor.baseY;
        const pts = [
            new THREE.Vector3(160, baseY + 13, BASE_D + 20),  // 到达
            new THREE.Vector3(160 - BASE_W / 4, baseY + 14, BASE_D / 4),  // 窗口
            new THREE.Vector3(160, baseY + 9, BASE_D / 2),                // 座位
            new THREE.Vector3(160 + BASE_W / 4, baseY + 13, BASE_D + 20), // 离场
        ];
        const curve = new THREE.CatmullRomCurve3(pts);
        const geo = new THREE.TubeGeometry(curve, 48, 1.4, 8, false);
        const mat = new THREE.MeshStandardMaterial({
            color: PALETTE.flow,
            emissive: PALETTE.flow,
            emissiveIntensity: 0.6,
            transparent: true,
            opacity: 0.75,
        });
        return new THREE.Mesh(geo, mat);
    }

    // ---- 内部：A+C 相机 / 楼层滑开动画 ----

    _recomputeCameraTarget() {
        const THREE = this.THREE;
        if (this.mode === 'focus' && this.focusFloorId != null) {
            const idx = this._floorIndex(this.focusFloorId);
            const y = idx * FLOOR_GAP;
            this._camTarget.pos.set(160, y + 160, y + 340);
            this._camTarget.look.set(160, y + 10, BASE_D / 2);
        } else {
            // A 总览：斜俯环绕整栋堆叠，视野覆盖所有楼层
            const span = Math.max(1, this._floorCount - 1) * FLOOR_GAP;
            const centerY = span / 2;
            this._camTarget.pos.set(300, centerY + 280, span + 420);
            this._camTarget.look.set(160, centerY, BASE_D / 2);
        }
    }

    _floorIndex(floorId) {
        if (!this._lastFrame) return 0;
        const f = this._lastFrame.floors.find(fl => fl.floor_id === floorId);
        return f ? f.index : 0;
    }

    // 非焦点层滑开收起（方案 2，保持 userData.kind 与 slide 语义不变）。
    _animateFloors() {
        this._floorGroups.forEach((fg, floorId) => {
            let targetSlide = 0;
            if (this.mode === 'focus' && this.focusFloorId != null
                && floorId !== this.focusFloorId) {
                const dir = this._floorIndex(floorId)
                    < this._floorIndex(this.focusFloorId) ? -1 : 1;
                targetSlide = dir * FOCUS_SLIDE;
            }
            const prev = this._floorSlide.get(floorId) || 0;
            const next = prev + (targetSlide - prev) * CAM_LERP;
            this._floorSlide.set(floorId, next);
            fg.position.x = next;
        });
    }

    _animateCamera() {
        if (!this.camera) return;
        this.camera.position.lerp(this._camTarget.pos, CAM_LERP);
        if (this.controls) {
            this.controls.target.lerp(this._camTarget.look, CAM_LERP);
        } else {
            this.camera.lookAt(this._camTarget.look);
        }
    }

    dispose() {
        this._clear();
        if (this.group.parent) this.group.parent.remove(this.group);
    }
}

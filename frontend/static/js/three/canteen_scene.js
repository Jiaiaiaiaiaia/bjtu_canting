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

const FLOOR_GAP = 74;
const FLOOR_RISE = 34;
const FOCUS_SLIDE = 520;       // FOCUS 态非焦点层滑开距离
const CAM_LERP = 0.08;         // 相机/层位移插值系数

// 冷青监控调色（与 scene3d / canvas_renderer 图例语义连续）。
const PALETTE = {
    deck: 0x26394d,
    windowOpen: 0xd64a55,
    windowIdle: 0x94a8b5,
    windowClosing: 0x3f5168,    // 关窗暗
    windowClosedEmpty: 0x55636f, // 空关灰
    seatOccupied: 0xe7bd63,
    seatEmpty: 0x77d993,
    studentQueue: 0x9333ea,
    studentMove: 0x52d6d1,
    flow: 0x2dd4bf,             // 发光流线青
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

        // 相机目标（插值逼近，离散切换→平滑飞入）
        this._camTarget = { pos: new THREE.Vector3(260, 260, 520),
                            look: new THREE.Vector3(160, 0, 120) };
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

    // 每帧调用：重建内容（位置已由 state_adapter 插值）+ 推进相机/层动画。
    update(frame) {
        this._lastFrame = frame;
        this._floorCount = frame ? frame.floors.length : 0;
        this._rebuild(frame);
        this._recomputeCameraTarget();
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

    _mat(color, opacity) {
        return new this.THREE.MeshStandardMaterial({
            color,
            roughness: 0.72,
            metalness: 0.04,
            transparent: opacity != null,
            opacity: opacity == null ? 1 : opacity,
        });
    }

    _label(text, x, y, z, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = color || PALETTE.label;
        ctx.font = '24px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(text, 128, 38);
        const texture = new this.THREE.CanvasTexture(canvas);
        const sprite = new this.THREE.Sprite(
            new this.THREE.SpriteMaterial({ map: texture, transparent: true })
        );
        sprite.position.set(x, y, z);
        sprite.scale.set(80, 20, 1);
        return sprite;
    }

    _rebuild(frame) {
        const THREE = this.THREE;
        this._clear();
        if (!frame) return;

        this.group.add(this._label(frame.displayName || '食堂', 160, 70, -40,
            PALETTE.labelKpi));

        frame.floors.forEach(floor => {
            const fg = new THREE.Group();
            fg.userData = { floorId: floor.floor_id, kind: 'floor' };
            this._floorGroups.set(floor.floor_id, fg);

            const deck = new THREE.Mesh(
                new THREE.BoxGeometry(260, 4, 54),
                this._mat(PALETTE.deck)
            );
            deck.position.set(160, floor.baseY, floor.z);
            deck.userData = { floorId: floor.floor_id, kind: 'floor' };
            fg.add(deck);

            // 楼层角标（FOCUS 时叠加焦点标注）
            const tag = this._label(
                `${floor.floor_id}F${this.focusFloorId === floor.floor_id ? ' ◀ 焦点' : ''}`,
                20, floor.baseY + 8, floor.z, PALETTE.labelKpi
            );
            fg.add(tag);

            // 窗口：开放亮 / closing 暗+「关闭中」/ 空关灰；队列饱和度上色顶盖
            floor.windows.forEach(win => {
                let color = PALETTE.windowIdle;
                if (win.is_open) color = win.is_serving ? PALETTE.windowOpen : PALETTE.windowIdle;
                else color = win.closing ? PALETTE.windowClosing : PALETTE.windowClosedEmpty;
                const stall = new THREE.Mesh(
                    new THREE.BoxGeometry(18, 20, 18),
                    this._mat(color, win.is_open ? undefined : 0.78)
                );
                stall.position.set(win.position.x, win.position.y, win.position.z);
                stall.userData = { floorId: floor.floor_id, kind: 'window',
                                   windowId: win.id };
                fg.add(stall);

                const sat = Math.min(1, (win.queue_length || 0) / 12);
                if (win.is_open && sat > 0) {
                    const cap = new THREE.Mesh(
                        new THREE.BoxGeometry(18, 2.4, 18),
                        new THREE.MeshStandardMaterial({
                            color: heatColor(THREE, sat),
                            emissive: heatColor(THREE, sat),
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

            floor.seats.forEach(seat => {
                const seatMesh = new THREE.Mesh(
                    new THREE.BoxGeometry(8, 4, 8),
                    this._mat(seat.status === 'occupied'
                        ? PALETTE.seatOccupied : PALETTE.seatEmpty)
                );
                seatMesh.position.set(seat.position.x, seat.position.y, seat.position.z);
                fg.add(seatMesh);
            });

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

            // 焦点层：到达→窗口→座位→离场 发光路径高亮
            if (this.mode === 'focus' && this.focusFloorId === floor.floor_id) {
                fg.add(this._flowPath(floor));
            }

            this.group.add(fg);
        });
    }

    // 发光流线：到达点 → 窗口排 → 座位区 → 离场，冷青发光（spec §4.1 人流分析）。
    _flowPath(floor) {
        const THREE = this.THREE;
        const pts = [
            new THREE.Vector3(160, floor.baseY + 13, floor.z + 70),  // 到达
            new THREE.Vector3(78, floor.baseY + 14, floor.z - 6),    // 窗口
            new THREE.Vector3(120, floor.baseY + 9, floor.z + 24),   // 座位
            new THREE.Vector3(250, floor.baseY + 13, floor.z + 70),  // 离场
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
            const z = idx * FLOOR_GAP;
            const y = idx * FLOOR_RISE;
            this._camTarget.pos.set(160, y + 120, z + 260);
            this._camTarget.look.set(160, y + 8, z);
        } else {
            // A 总览：斜俯环绕整栋堆叠
            const span = Math.max(1, this._floorCount - 1) * FLOOR_GAP;
            this._camTarget.pos.set(260, 260, span + 520);
            this._camTarget.look.set(160, 0, span / 2 + 60);
        }
    }

    _floorIndex(floorId) {
        if (!this._lastFrame) return 0;
        const f = this._lastFrame.floors.find(fl => fl.floor_id === floorId);
        return f ? f.index : 0;
    }

    // 非焦点层滑开收起（方案 2）。
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

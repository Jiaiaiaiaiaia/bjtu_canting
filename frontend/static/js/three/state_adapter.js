// state_adapter.js — 离散 /api/campus/step snapshot → 稳定连续插值目标
//
// 职责（spec §2 数据流 / §4）：把 coordinator snapshot（单食堂 N=1 明湖学一，
// 携带嵌套 floors[]）转成「按稳定 id 键控」的渲染目标，供帧间插值平滑离散步进。
//
// 不变量：
//  - 后端 snapshot 是唯一真值源。KPI / 计数 / 状态全部原样取自 snapshot/campus_totals，
//    本模块不发明任何统计。
//  - 随机扰动只用于「同格点位互不重叠」，用元素 id 的确定性哈希派生固定偏移，
//    不随帧变化、不改变计数与语义位置（同一 id 每帧落在同一抖动点）。
//
// 输出对单食堂友好：从 snapshot.canteens 取活动食堂（appState.activeCanteenId
// 优先，否则第一个），展开其 floors[]，为每个 window/seat/student 计算稳定布局
// 坐标（与旧 scene3d renderCanteen 的网格摆放一致，避免视觉回归），并对 student
// 做 id->目标 的位置插值缓存。

const FLOOR_GAP = 74;          // 楼层竖向间距（与旧 renderCanteen 一致）
const FLOOR_RISE = 34;         // 楼层抬升步长
const LERP_ALPHA = 0.18;       // 帧间插值系数（离散步进→连续）

// 确定性 [-1,1) 抖动：仅防同格点重叠，与帧无关。
function jitter(seed, salt) {
    const h = Math.sin((seed * 374761393 + salt * 668265263) % 2147483647) * 43758.5453;
    return (h - Math.floor(h)) * 2 - 1;
}

function numericId(id) {
    if (typeof id === 'number') return id;
    const s = String(id ?? '');
    let acc = 0;
    for (let i = 0; i < s.length; i += 1) acc = (acc * 31 + s.charCodeAt(i)) % 2147483647;
    return acc;
}

// 从 snapshot 选出当前单食堂（活动食堂优先），统一退化形状。
export function pickCanteen(snapshot, appState) {
    const canteens = snapshot?.canteens || {};
    const active = appState?.activeCanteenId;
    const canteen = (active && canteens[active]) || Object.values(canteens)[0] || null;
    if (!canteen) return null;
    const floors = Array.isArray(canteen.floors) && canteen.floors.length
        ? canteen.floors
        : [{
            floor_id: 1,
            windows: canteen.windows || [],
            seats: canteen.seats || [],
            students: canteen.students || [],
        }];
    return { canteen, floors };
}

// 单个楼层的稳定布局：窗口排、座位网格、学生网格。坐标沿用旧 scene3d 摆法。
function layoutFloor(floor, floorIndex) {
    const z = floorIndex * FLOOR_GAP;
    const baseY = floorIndex * FLOOR_RISE;
    const windows = (floor.windows || []).map((win, idx) => ({
        id: win.id,
        floor_id: floor.floor_id,
        is_serving: Boolean(win.is_serving),
        // is_open / closing 取自后端派生字段；后端未透出时按 Phase 2 兼容默认开放。
        is_open: win.is_open !== false,
        closing: win.is_open === false && (win.queue_length > 0 || win.is_serving),
        queue_length: win.queue_length || 0,
        total_served: win.total_served || 0,
        position: { x: 52 + idx * 26, y: baseY + 14, z: z - 18 },
    }));
    const seats = (floor.seats || []).slice(0, 90).map((seat, idx) => ({
        id: seat.id,
        floor_id: floor.floor_id,
        status: seat.status,
        position: {
            x: 52 + (idx % 18) * 12,
            y: baseY + 7,
            z: z + 2 + Math.floor(idx / 18) * 10,
        },
    }));
    const students = (floor.students || []).slice(0, 80).map((student, idx) => {
        const sid = numericId(student.id);
        return {
            id: student.id,
            floor_id: floor.floor_id,
            position: student.position,
            target: {
                x: 52 + (idx % 20) * 10 + jitter(sid, 1) * 1.6,
                y: baseY + 13,
                z: z + 48 + Math.floor(idx / 20) * 8 + jitter(sid, 2) * 1.6,
            },
        };
    });
    return {
        floor_id: floor.floor_id,
        index: floorIndex,
        z,
        baseY,
        windows,
        seats,
        students,
    };
}

// StateAdapter 持有 id->当前插值位置 的缓存，跨帧平滑离散 snapshot。
export class StateAdapter {
    constructor() {
        this._studentPos = new Map();   // studentId -> {x,y,z} 当前插值位
    }

    reset() {
        this._studentPos.clear();
    }

    // 把 snapshot 转为渲染目标；students 位置带帧间插值（线性逼近 target）。
    buildFrame(snapshot, appState) {
        const picked = pickCanteen(snapshot, appState);
        if (!picked) return null;
        const { canteen, floors } = picked;
        const seenStudents = new Set();
        const floorFrames = floors.map((floor, idx) => {
            const layout = layoutFloor(floor, idx);
            layout.students.forEach(st => {
                const key = String(st.id);
                seenStudents.add(key);
                const prev = this._studentPos.get(key);
                const next = prev
                    ? {
                        x: prev.x + (st.target.x - prev.x) * LERP_ALPHA,
                        y: prev.y + (st.target.y - prev.y) * LERP_ALPHA,
                        z: prev.z + (st.target.z - prev.z) * LERP_ALPHA,
                    }
                    : { ...st.target };
                this._studentPos.set(key, next);
                st.position3d = next;
            });
            return layout;
        });
        // 清掉已离场学生的插值缓存，避免无界增长。
        for (const key of [...this._studentPos.keys()]) {
            if (!seenStudents.has(key)) this._studentPos.delete(key);
        }
        return {
            canteenId: canteen.id,
            displayName: canteen.display_name || canteen.id,
            floors: floorFrames,
            // KPI 全部来自后端：优先 campus_totals（全局），单食堂顶层字段兜底。
            kpi: deriveKpi(snapshot, canteen),
            perFloorKpi: floorFrames.map(f => derivePerFloorKpi(f)),
            interventions: Array.isArray(snapshot?.interventions)
                ? snapshot.interventions
                : [],
        };
    }
}

// 全局 KPI：只读后端字段，不反推、不发明。
function deriveKpi(snapshot, canteen) {
    const totals = snapshot?.campus_totals || {};
    return {
        total_arrived: pickNum(totals.total_arrived, canteen.total_arrived),
        total_served: pickNum(totals.total_served, canteen.total_served),
        total_in_queue: pickNum(totals.total_in_queue, canteen.total_in_queue),
        total_eating: pickNum(totals.total_eating, canteen.total_eating),
        empty_seats: pickNum(totals.empty_seats, canteen.empty_seats),
        avg_waiting_time: pickNum(totals.avg_waiting_time, canteen.avg_waiting_time),
        current_time: pickNum(snapshot?.current_time, canteen.current_time),
    };
}

// 单层 KPI：由该层 windows/seats/students 直接聚合（仍是后端真值的分区计数）。
function derivePerFloorKpi(floorFrame) {
    const inQueue = floorFrame.windows.reduce((s, w) => s + (w.queue_length || 0), 0);
    const occupied = floorFrame.seats.filter(s => s.status === 'occupied').length;
    return {
        floor_id: floorFrame.floor_id,
        total_in_queue: inQueue,
        total_eating: occupied,
        empty_seats: floorFrame.seats.length - occupied,
        open_windows: floorFrame.windows.filter(w => w.is_open).length,
        window_count: floorFrame.windows.length,
        students: floorFrame.students.length,
    };
}

function pickNum(primary, fallback) {
    if (typeof primary === 'number' && !Number.isNaN(primary)) return primary;
    if (typeof fallback === 'number' && !Number.isNaN(fallback)) return fallback;
    return 0;
}

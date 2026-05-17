// state_adapter.js — 离散 /api/campus/step snapshot → 稳定连续插值目标
//
// 职责（spec §2 数据流 / §4）：把 coordinator snapshot（单食堂 N=1 明湖，
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

// 楼层竖向堆叠：所有楼层共用同一 x/z 占地（一栋楼的同一平面），
// 仅沿 +Y 以 FLOOR_V 间距向上叠成「3 层竖向堆叠剖面」(spec §4.1)。
// canteen_scene 用 frame 给的 baseY 直接建楼板/墙/交通核，不再各自假设步长。
const FLOOR_V = 104;           // 楼层竖向间距（保证总览态三层有清晰空气层）
const LERP_ALPHA = 0.18;       // 帧间插值系数（离散步进→连续）
const FLOOR_CENTER_X = 160;
const FOOTPRINT_GRID = 4;
const FOOTPRINT_MAX_ASPECT_RATIO = 1.85;
const MIN_FLOOR_WIDTH = 260;
const MIN_FLOOR_DEPTH = 156;
const TABLE_CLEARANCE_X = 64;
const TABLE_CLEARANCE_Z = 42;
const WINDOW_CLEARANCE_X = 72;
const WINDOW_CLEARANCE_Z = 46;
const STAIR_CORE_WIDTH = 44;
const SIDE_ENTRANCE_X = -10;   // fallback：实际入口 x 由 footprint.minX - 10 推导
const SIDE_ENTRANCE_ZS = [28, 68]; // fallback：实际入口 z 由 footprint.depth 的 30%/70% 推导
const STUDENT_Y = 7;
// Scale note: scene floor units use roughly 10 units per meter. The 7.2m
// service-to-table buffer combines a high-traffic cafeteria queue bay and main
// aisle, based on dining-hall guidance that primary traffic aisles need about
// 0.9-1.8m and real peak canteen queues need multiple rows before seating.
const SCENE_UNITS_PER_METER = 10;
const SERVICE_TO_TABLE_BUFFER_M = 7.2;
const ENTRANCE_SPAWN_LANE_X = 3.4;
const ENTRANCE_SPAWN_LANE_Z = 4.2;
const WINDOW_QUEUE_LANES = 3;
const WINDOW_QUEUE_LANE_DX = 7.2;
const WINDOW_QUEUE_ROW_DZ = 5.9;
const WINDOW_QUEUE_DEPTH_OFFSET = 13;
const QUEUE_TABLE_BUFFER_Z = 6;
const TABLE_DX = 44;
const TABLE_Z0 = 46;
const TABLE_DZ = 15;
const TABLE_ZONE_AISLE_X = 60;
const TABLE_ROW_AISLE_Z = 12;
const TABLE_WINDOW_GAP_Z = SERVICE_TO_TABLE_BUFFER_M * SCENE_UNITS_PER_METER;
const TABLE_ZONE_SIDE_PADDING = 42;
const TABLE_ZONE_MAX_COLS = 3;
const CHAIR_DX = 12;
const CHAIR_DZ = 7;
const MINGHU_FLOOR_LAYOUTS = {
    1: {
        key: 'basicMealWideAisle',
        windowBays: [
            { id: 'f1-front-service-band-left', side: 'front', weight: 2,
              xStartRatio: 0.22, xEndRatio: 0.34, z: 16,
              bayStaggerZ: [0], minWindowGap: 56 },
            { id: 'f1-front-service-band-center', side: 'front', weight: 2,
              xStartRatio: 0.46, xEndRatio: 0.58, z: 16,
              bayStaggerZ: [0], minWindowGap: 56 },
            { id: 'f1-front-service-band-right', side: 'front', weight: 2,
              xStartRatio: 0.70, xEndRatio: 0.82, z: 16,
              bayStaggerZ: [0], minWindowGap: 56 },
        ],
        windowRows: 1,
        windowZ: [16],
        windowX0: 42,
        windowSpan: 268,
        windowRowOffset: 0,
        minWindowGap: 34,
        continuousFrontAfterCount: 6,
        continuousFrontBand: {
            xStartRatio: 0.20,
            xEndRatio: 0.84,
            z: 16,
            minWindowGap: 44,
        },
        tableShiftX: 0,
        tableZ0: 96,
        tableRowStagger: 0,
        visibleTableCount: 43,
        mainAisleWidth: 72,
        queueBufferDepth: 98,
        tableBlocks: [
            { id: 'f1-left-four-seat-island', type: 'square', tableColor: 0xc79a58, count: 12, cols: 4,
              anchor: 'left', left: 24, z: 0, dx: 38, dz: 26 },
            { id: 'f1-lower-left-fill-tables', type: 'square', tableColor: 0xc79a58, count: 5, cols: 3,
              anchor: 'left', left: 32, z: 112, dx: 38, dz: 30 },
            { id: 'f1-central-dining-island', type: 'square', tableColor: 0xd0a45e, count: 14, cols: 2,
              anchor: 'center', offsetX: 0, z: 8, dx: 80, dz: 24 },
            { id: 'f1-right-long-table-zone', type: 'long', tableColor: 0x9a6b3e, count: 6, cols: 2,
              anchor: 'right', right: 90, z: 18, dx: 48, dz: 36 },
            { id: 'f1-rear-booth-fill', type: 'booth', tableColor: 0xb9804a, count: 6, cols: 3,
              anchor: 'right', right: 24, z: 128, dx: 48, dz: 28 },
        ],
        widthBias: -24,
        depthBias: -20,
        rearNotchDepth: 0,
        cueNames: [
            'f1-snake-queue-guide',
            'f1-pickup-return-lane',
            'f1-main-aisle-cue',
            'f1-condiment-station',
            'f1-tray-return-point',
            // Legacy contract names retained as aliases while the 1F sample is incrementally reshaped.
            'f1-left-square-island',
            'f1-rear-fill-tables',
            'basicMealWideAisle central clear aisle',
            'basicMealWideAisle self service rice line',
        ],
    },
    2: {
        key: 'featureFoodCourt',
        windowBays: [
            { id: 'f2-left-snack-bay', side: 'left', weight: 1,
              xInset: 18, zStart: 40, zEnd: 40,
              bayStaggerX: [0], bayStaggerZ: [0] },
            { id: 'f2-front-coffee-bay', side: 'front', weight: 6,
              xStartRatio: 0.24, xEndRatio: 0.44, z: 16,
              bayStaggerZ: [0], minWindowGap: 28 },
            { id: 'f2-front-hotfood-bay', side: 'front', weight: 6,
              xStartRatio: 0.56, xEndRatio: 0.78, z: 22,
              bayStaggerZ: [0], minWindowGap: 28 },
        ],
        windowRows: 2,
        windowZ: [12, 30],
        windowX0: 42,
        windowSpan: 240,
        windowRowOffset: 18,
        minWindowGap: 34,
        tableShiftX: -5,
        tableZ0: 80,
        tableRowStagger: 10,
        visibleTableCount: 58,
        mainAisleWidth: 68,
        queueBufferDepth: 86,
        tableBlocks: [
            { id: 'f2-left-small-table-bank', type: 'square', tableColor: 0xa0a66a, count: 12, cols: 3,
              anchor: 'left', left: 70, z: 0, dx: 36, dz: 28 },
            { id: 'f2-foodcourt-center-island', type: 'square', tableColor: 0xc58c4f, count: 22, cols: 5,
              anchor: 'center', offsetX: 0, z: 40, dx: 38, dz: 26 },
            { id: 'f2-right-communal-bank', type: 'long', tableColor: 0x7d8d65, count: 12, cols: 3,
              anchor: 'right', right: 70, z: 2, dx: 42, dz: 30 },
            { id: 'f2-rear-flex-fill', type: 'square', tableColor: 0xb9856f, count: 12, cols: 6,
              anchor: 'center', offsetX: -4, z: 184, dx: 36, dz: 26 },
        ],
        widthBias: 12,
        depthBias: 8,
        rearNotchDepth: 32,
        cueNames: [
            'featureFoodCourt coffee island',
            'featureFoodCourt hotpot zone',
        ],
    },
    3: {
        key: 'restaurantDiningRoom',
        windowBays: [
            { id: 'f3-specialty-side-bay', side: 'left', weight: 2,
              xInset: 18, zStart: 28, zEnd: 54,
              bayStaggerX: [0, 3], bayStaggerZ: [0] },
            { id: 'f3-front-hotpot-bay', side: 'front', weight: 4,
              xStartRatio: 0.24, xEndRatio: 0.42, z: 16,
              bayStaggerZ: [0], minWindowGap: 34 },
            { id: 'f3-front-noodle-bay', side: 'front', weight: 4,
              xStartRatio: 0.50, xEndRatio: 0.64, z: 22,
              bayStaggerZ: [0], minWindowGap: 34 },
            { id: 'f3-front-tea-bay', side: 'front', weight: 4,
              xStartRatio: 0.68, xEndRatio: 0.82, z: 16,
              bayStaggerZ: [0], minWindowGap: 34 },
        ],
        windowRows: 2,
        windowZ: [14, 34],
        windowX0: 52,
        windowSpan: 220,
        windowRowOffset: -14,
        minWindowGap: 34,
        sideWindowCount: 2,
        sideWindowX: 18,
        sideWindowZ0: 26,
        sideWindowGap: 30,
        tableShiftX: 8,
        tableZ0: 112,
        tableRowStagger: -8,
        visibleTableCount: 52,
        mainAisleWidth: 72,
        queueBufferDepth: 92,
        tableBlocks: [
            { id: 'f3-wall-booth-run', type: 'booth', tableColor: 0x7a5a40, count: 6, cols: 1,
              anchor: 'left', left: 84, z: 0, dx: 0, dz: 28 },
            { id: 'f3-central-dining-cluster', type: 'square', tableColor: 0x9b7d55, count: 16, cols: 4,
              anchor: 'center', offsetX: 12, z: 28, dx: 34, dz: 28 },
            { id: 'f3-left-mid-square-infill', type: 'square', tableColor: 0x8f7d67, count: 4, cols: 2,
              anchor: 'left', left: 128, z: 98, dx: 34, dz: 28 },
            { id: 'f3-east-mid-square-infill', type: 'square', tableColor: 0x8aa092, count: 6, cols: 3,
              anchor: 'right', right: 112, z: 82, dx: 34, dz: 28 },
            { id: 'f3-rear-hotpot-communal', type: 'long', tableColor: 0x835f42, count: 14, cols: 7,
              anchor: 'center', offsetX: 8, z: 202, dx: 42, dz: 30 },
            { id: 'f3-right-window-booth-run', type: 'booth', tableColor: 0x4e6b70, count: 6, cols: 1,
              anchor: 'right', right: 96, z: 18, dx: 0, dz: 32 },
        ],
        widthBias: 0,
        depthBias: 0,
        rearNotchDepth: 40,
        cueNames: [
            'restaurantDiningRoom booth seating',
            'restaurantDiningRoom service aisle',
        ],
    },
};

function floorLayoutProfile(floorId) {
    return MINGHU_FLOOR_LAYOUTS[floorId] || MINGHU_FLOOR_LAYOUTS[1];
}

function actualTableCount(seats) {
    return Math.ceil((seats || []).length / 4);
}

function visibleTableCountForProfile(seats, profile) {
    const actual = actualTableCount(seats);
    return Math.max(1, Math.min(profile.visibleTableCount || actual, actual));
}

function visualTableIndexForSeat(seatIdx, visibleTableCount) {
    return Math.floor(seatIdx / 4) % visibleTableCount;
}

function tableColumnCount(tableCount) {
    if (tableCount <= 0) return 1;
    return Math.ceil(tableCount / 3);
}

function tableZoneCount(tableCount) {
    if (tableCount >= 15) return 3;
    if (tableCount >= 8) return 2;
    return 1;
}

function tableZoneColumnCount(zoneTableCount) {
    if (zoneTableCount <= 0) return 1;
    return Math.min(TABLE_ZONE_MAX_COLS, Math.max(1, Math.ceil(zoneTableCount / 3)));
}

function tableBlocksForProfile(profile) {
    return Array.isArray(profile.tableBlocks) && profile.tableBlocks.length
        ? profile.tableBlocks
        : [{
            id: `${profile.key || 'default'}-uniform-table-zone`,
            type: 'square',
            count: profile.visibleTableCount || 1,
            cols: tableZoneColumnCount(profile.visibleTableCount || 1),
            anchor: 'center',
            z: 0,
            dx: TABLE_DX,
            dz: TABLE_DZ,
        }];
}

function tableBlockRows(block, count) {
    const cols = Math.max(1, Math.min(block.cols || 1, count || 1));
    return Math.max(1, Math.ceil((count || 1) / cols));
}

function tableBlockForIndex(idx, profile) {
    const blocks = tableBlocksForProfile(profile);
    let cursor = 0;
    for (const block of blocks) {
        const count = Math.max(0, block.count || 0);
        if (idx < cursor + count) {
            return { block, localIdx: idx - cursor };
        }
        cursor += count;
    }
    const fallback = blocks[blocks.length - 1];
    return {
        block: fallback,
        localIdx: Math.max(0, idx - Math.max(0, cursor - (fallback.count || 1))),
    };
}

function tableBlockMetrics(profile, tableCount) {
    const blocks = tableBlocksForProfile(profile);
    let remaining = tableCount;
    let maxOffsetZ = 0;
    let maxBlockWidth = 0;
    blocks.forEach(block => {
        if (remaining <= 0) return;
        const count = Math.min(block.count || 0, remaining);
        remaining -= count;
        const cols = Math.max(1, Math.min(block.cols || 1, count || 1));
        const rows = tableBlockRows(block, count);
        const dx = block.dx ?? TABLE_DX;
        const dz = block.dz ?? TABLE_DZ;
        maxBlockWidth = Math.max(maxBlockWidth, (cols - 1) * dx + TABLE_CLEARANCE_X);
        maxOffsetZ = Math.max(maxOffsetZ, (block.z || 0) + (rows - 1) * dz);
    });
    return { maxBlockWidth, maxOffsetZ };
}

function serviceWindowMaxZ(profile) {
    const bayMaxZ = frontWindowBayMaxZ(profile);
    if (bayMaxZ !== null) return bayMaxZ;
    const frontWindowMaxZ = Math.max(...(profile.windowZ || [14]));
    const sideWindowCount = profile.sideWindowCount || 0;
    const sideWindowMaxZ = sideWindowCount > 0
        ? (profile.sideWindowZ0 || 18) + (sideWindowCount - 1) * (profile.sideWindowGap || 20)
        : frontWindowMaxZ;
    return Math.max(frontWindowMaxZ, sideWindowMaxZ);
}

function tableZoneStartZ(profile) {
    return Math.max(
        profile.tableZ0 || TABLE_Z0,
        serviceWindowMaxZ(profile) + TABLE_WINDOW_GAP_Z + CHAIR_DZ
    );
}

function roundToGrid(value) {
    return Math.ceil(value / FOOTPRINT_GRID) * FOOTPRINT_GRID;
}

function entranceZsForFootprint(footprint) {
    if (!footprint) return SIDE_ENTRANCE_ZS;
    const lower = Math.max(24, Math.round(footprint.depth * 0.30));
    const upper = Math.min(footprint.maxZ - 24, Math.round(footprint.depth * 0.70));
    return [lower, Math.max(lower + 24, upper)];
}

function sideEntranceXForFootprint(footprint) {
    return Math.min(SIDE_ENTRANCE_X, (footprint?.minX ?? 0) + SIDE_ENTRANCE_X);
}

function clamp01(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) return 0;
    return Math.max(0, Math.min(1, value));
}

function profileWindowBays(profile) {
    return Array.isArray(profile.windowBays) && profile.windowBays.length
        ? profile.windowBays
        : null;
}

function bayStaggerZ(bay, localIdx) {
    const pattern = Array.isArray(bay.bayStaggerZ) && bay.bayStaggerZ.length
        ? bay.bayStaggerZ
        : [0];
    return pattern[localIdx % pattern.length] || 0;
}

function bayStaggerX(bay, localIdx) {
    const pattern = Array.isArray(bay.bayStaggerX) && bay.bayStaggerX.length
        ? bay.bayStaggerX
        : [0];
    return pattern[localIdx % pattern.length] || 0;
}

function windowBayMaxZ(profile) {
    const bays = profileWindowBays(profile);
    if (!bays) return null;
    return Math.max(...bays.map(bay => {
        if (bay.side === 'left') {
            return Math.max(bay.zStart || 0, bay.zEnd || 0)
                + Math.max(0, ...((bay.bayStaggerZ || []).map(v => Math.abs(v))));
        }
        return (bay.z || 14) + Math.max(0, ...((bay.bayStaggerZ || []).map(v => Math.abs(v))));
    }));
}

function frontWindowBayMaxZ(profile) {
    const bays = profileWindowBays(profile);
    if (!bays) return null;
    const frontBays = bays.filter(bay => bay.side !== 'left');
    if (!frontBays.length) return null;
    return Math.max(...frontBays.map(bay => (
        (bay.z || 14) + Math.max(0, ...((bay.bayStaggerZ || []).map(v => Math.abs(v))))
    )));
}

function windowBayCounts(total, bays) {
    if (!bays.length || total <= 0) return bays.map(() => 0);
    const weights = bays.map(bay => Math.max(0.1, bay.weight || bay.count || 1));
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
    const raw = weights.map(weight => (total * weight) / totalWeight);
    const counts = raw.map(value => Math.floor(value));
    let assigned = counts.reduce((sum, count) => sum + count, 0);

    raw
        .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
        .sort((a, b) => b.fraction - a.fraction)
        .forEach(({ index }) => {
            if (assigned < total) {
                counts[index] += 1;
                assigned += 1;
            }
        });

    while (assigned < total) {
        const index = counts.indexOf(Math.min(...counts));
        counts[index] += 1;
        assigned += 1;
    }
    while (assigned > total) {
        const index = counts.indexOf(Math.max(...counts));
        counts[index] -= 1;
        assigned -= 1;
    }
    return counts;
}

function continuousFrontWindowBand(profile) {
    return profile && typeof profile.continuousFrontAfterCount === 'number'
        ? (profile.continuousFrontBand || {})
        : null;
}

function dynamicFrontWindowGap(profile, frontWindowCount) {
    const band = continuousFrontWindowBand(profile);
    const baseGap = Math.max(profile.minWindowGap || 0, 28);
    if (!band || frontWindowCount <= profile.continuousFrontAfterCount) {
        return baseGap;
    }
    return Math.max(baseGap, band.minWindowGap || 44);
}

function windowBaySlot(idx, total, profile) {
    const bays = profileWindowBays(profile);
    if (!bays) return null;
    const counts = windowBayCounts(total, bays);
    let cursor = 0;
    for (let i = 0; i < bays.length; i += 1) {
        const count = counts[i];
        if (idx < cursor + count) {
            return {
                bay: bays[i],
                localIdx: idx - cursor,
                bayCount: count,
            };
        }
        cursor += count;
    }
    const lastIdx = bays.length - 1;
    return {
        bay: bays[lastIdx],
        localIdx: Math.max(0, counts[lastIdx] - 1),
        bayCount: Math.max(1, counts[lastIdx]),
    };
}

function furnitureDerivedFootprint(seats, windows, profile) {
    const tableCount = visibleTableCountForProfile(seats, profile);
    const blockMetrics = tableBlockMetrics(profile, tableCount);
    const zoneCount = tableZoneCount(tableCount);
    const tablesPerZone = Math.ceil(tableCount / zoneCount);
    const cols = tableZoneColumnCount(tablesPerZone);
    const rows = Math.max(1, Math.ceil(tablesPerZone / cols));
    const tableWidth = cols > 1
        ? Math.max((cols - 1) * TABLE_DX, blockMetrics.maxBlockWidth)
            + TABLE_CLEARANCE_X
            + (zoneCount - 1) * TABLE_ZONE_AISLE_X
            + zoneCount * TABLE_ZONE_SIDE_PADDING
        : 96;
    const tableDepth = Math.max(
        tableZoneStartZ(profile)
            + (rows - 1) * TABLE_DZ
            + Math.floor((rows - 1) / 2) * TABLE_ROW_AISLE_Z
            + TABLE_CLEARANCE_Z,
        tableZoneStartZ(profile) + blockMetrics.maxOffsetZ + TABLE_CLEARANCE_Z
    );

    const sideWindowCount = Math.min(profile.sideWindowCount || 0, windows.length);
    const frontWindowCount = Math.max(0, windows.length - sideWindowCount);
    const rowCount = Math.max(1, profile.windowRows || 1);
    const perRow = Math.max(1, Math.ceil(frontWindowCount / rowCount));
    const windowWidth = perRow > 1
        ? (perRow - 1) * dynamicFrontWindowGap(profile, frontWindowCount) + WINDOW_CLEARANCE_X
        : 112;
    const bayMaxZ = windowBayMaxZ(profile);
    const windowDepth = (bayMaxZ ?? Math.max(...(profile.windowZ || [14]))) + WINDOW_CLEARANCE_Z;
    const sideWindowDepth = sideWindowCount > 0
        ? (profile.sideWindowZ0 || 18)
            + (sideWindowCount - 1) * (profile.sideWindowGap || 20)
            + WINDOW_CLEARANCE_Z
        : 0;

    let width = roundToGrid(
        Math.max(MIN_FLOOR_WIDTH, tableWidth, windowWidth)
        + STAIR_CORE_WIDTH
        + (profile.widthBias || 0)
    );
    let depth = roundToGrid(
        Math.max(MIN_FLOOR_DEPTH, tableDepth, windowDepth, sideWindowDepth)
        + (profile.depthBias || 0)
    );
    if (width / depth > FOOTPRINT_MAX_ASPECT_RATIO) {
        depth = roundToGrid(width / FOOTPRINT_MAX_ASPECT_RATIO);
    }

    const centerX = FLOOR_CENTER_X;
    const minX = centerX - width / 2;
    const maxX = centerX + width / 2;
    const minZ = 0;
    const maxZ = depth;
    const rawNotch = profile.rearNotchDepth ?? 28;
    const notchDepth = rawNotch === 0 ? 0 : Math.min(
        Math.max(20, rawNotch),
        Math.max(20, Math.round(depth * 0.28))
    );
    const notchWidth = Math.max(STAIR_CORE_WIDTH + 10, Math.round(width * 0.18));
    const outline = notchDepth === 0
        ? [
            { x: minX, z: minZ },
            { x: maxX, z: minZ },
            { x: maxX, z: maxZ },
            { x: minX, z: maxZ },
          ]
        : [
            { x: minX, z: minZ },
            { x: maxX, z: minZ },
            { x: maxX, z: maxZ - notchDepth },
            { x: minX + notchWidth, z: maxZ - notchDepth },
            { x: minX + notchWidth, z: maxZ },
            { x: minX, z: maxZ },
          ];

    return {
        source: 'furnitureDerivedFootprint',
        width,
        depth,
        minX,
        maxX,
        minZ,
        maxZ,
        centerX,
        centerZ: minZ + depth / 2,
        outline,
        entranceZs: entranceZsForFootprint({ depth, maxZ }),
    };
}

function tableSeatPosition(idx, visibleTableCount, baseY, profile, footprint) {
    const tableIdx = visualTableIndexForSeat(idx, visibleTableCount);
    const seatPos = idx % 4;
    const { x: tx, z: tz } = tableZonePosition(tableIdx, visibleTableCount, profile, footprint);
    const ox = seatPos === 0 ? -CHAIR_DX : seatPos === 1 ? CHAIR_DX : 0;
    const oz = seatPos === 2 ? CHAIR_DZ : seatPos === 3 ? -CHAIR_DZ : 0;
    return { x: tx + ox, y: baseY + 5, z: tz + oz };
}

function tableZonePosition(idx, tableCount, profile, footprint) {
    return tableBlockPosition(idx, tableCount, profile, footprint);
}

function tableBlockPosition(idx, tableCount, profile, footprint) {
    const { block, localIdx } = tableBlockForIndex(idx, profile);
    const remainingInBlock = Math.min(block.count || tableCount, tableCount);
    const cols = Math.max(1, Math.min(block.cols || 1, remainingInBlock || 1));
    const col = localIdx % cols;
    const row = Math.floor(localIdx / cols);
    const dx = block.dx ?? TABLE_DX;
    const dz = block.dz ?? TABLE_DZ;
    const clusterWidth = (cols - 1) * dx;
    const z = Math.min(
        footprint.maxZ - 28,
        tableZoneStartZ(profile) + (block.z || 0) + row * dz
    );
    let x;
    if (block.anchor === 'left') {
        x = footprint.minX + (block.left ?? TABLE_ZONE_SIDE_PADDING) + col * dx;
    } else if (block.anchor === 'right') {
        x = footprint.maxX - (block.right ?? TABLE_ZONE_SIDE_PADDING) - (cols - 1 - col) * dx;
    } else {
        x = footprint.centerX + (block.offsetX || 0) - clusterWidth / 2 + col * dx;
    }
    return {
        x: Math.max(footprint.minX + 28, Math.min(footprint.maxX - 28, x)),
        z,
    };
}

function legacyTableZonePosition(idx, tableCount, profile, footprint) {
    const zoneCount = tableZoneCount(tableCount);
    const tablesPerZone = Math.ceil(tableCount / zoneCount);
    const zone = Math.min(zoneCount - 1, Math.floor(idx / tablesPerZone));
    const localIdx = idx - zone * tablesPerZone;
    const zoneTableCount = Math.min(tablesPerZone, tableCount - zone * tablesPerZone);
    const cols = tableZoneColumnCount(zoneTableCount);
    const col = localIdx % cols;
    const row = Math.floor(localIdx / cols);
    const usableWidth = Math.max(96, footprint.width - TABLE_ZONE_SIDE_PADDING * 2);
    const zoneGap = zoneCount > 1
        ? Math.min(TABLE_ZONE_AISLE_X, Math.max(38, usableWidth * 0.24))
        : 0;
    const zoneWidth = zoneCount > 1
        ? Math.max(42, (usableWidth - (zoneCount - 1) * zoneGap) / zoneCount)
        : usableWidth;
    const localDx = cols > 1 ? Math.min(TABLE_DX, zoneWidth / (cols - 1)) : 0;
    const clusterWidth = (cols - 1) * localDx;
    const zoneStart = footprint.centerX - usableWidth / 2 + zone * (zoneWidth + zoneGap);
    return {
        x: zoneStart + zoneWidth / 2 - clusterWidth / 2 + col * localDx
            + (row % 2) * (profile.tableRowStagger || 0) * 0.45,
        z: Math.min(
            footprint.maxZ - 28,
            tableZoneStartZ(profile)
                + row * TABLE_DZ
                + Math.floor(row / 2) * TABLE_ROW_AISLE_Z
        ),
    };
}

function continuousFrontWindowPosition(idx, total, baseY, profile, footprint) {
    const band = continuousFrontWindowBand(profile);
    if (!band) return null;

    const sideWindowCount = Math.min(profile.sideWindowCount || 0, total);
    if (idx < sideWindowCount) return null;

    const frontTotal = Math.max(1, total - sideWindowCount);
    if (frontTotal <= profile.continuousFrontAfterCount) return null;

    const frontIdx = idx - sideWindowCount;
    const startX = footprint.minX + footprint.width * (band.xStartRatio ?? 0.20);
    const endX = footprint.minX + footprint.width * (band.xEndRatio ?? 0.84);
    const span = Math.max(0, endX - startX);
    const minGap = dynamicFrontWindowGap(profile, frontTotal);
    const step = frontTotal > 1
        ? Math.max(minGap, span / (frontTotal - 1))
        : 0;
    const centeredStart = (startX + endX) / 2 - (step * (frontTotal - 1)) / 2;
    return {
        x: Math.max(
            footprint.minX + 32,
            Math.min(footprint.maxX - 32, centeredStart + frontIdx * step)
        ),
        y: baseY + 13,
        z: Math.max(
            footprint.minZ + 8,
            Math.min(footprint.maxZ - 12, band.z ?? (profile.windowZ || [14])[0] ?? 14)
        ),
        side: 'front',
        bayId: band.id || 'continuous-front-service-band',
        queueMaxZ: tableZoneStartZ(profile) - CHAIR_DZ - QUEUE_TABLE_BUFFER_Z,
    };
}

function windowPositionForProfile(idx, total, baseY, profile, footprint) {
    const continuousPosition = continuousFrontWindowPosition(idx, total, baseY, profile, footprint);
    if (continuousPosition) return continuousPosition;

    const bayPosition = windowBayPosition(idx, total, baseY, profile, footprint);
    if (bayPosition) return bayPosition;

    const sideWindowCount = Math.min(profile.sideWindowCount || 0, total);
    if (idx < sideWindowCount) {
        const sideWindowInsetX = profile.sideWindowX ?? 18;
        return {
            // sideWindowX is an inset from the derived left wall, not a global x.
            x: Math.min(
                footprint.minX + 24,
                Math.max(footprint.minX + 8, footprint.minX + sideWindowInsetX)
            ),
            y: baseY + 13,
            z: (profile.sideWindowZ0 || 18) + idx * (profile.sideWindowGap || 20),
            side: 'left',
        };
    }
    const frontIdx = idx - sideWindowCount;
    const frontTotal = Math.max(1, total - sideWindowCount);
    const rowCount = Math.max(1, profile.windowRows || 1);
    const row = rowCount === 1 ? 0 : frontIdx % rowCount;
    const col = rowCount === 1 ? frontIdx : Math.floor(frontIdx / rowCount);
    const perRow = Math.max(1, Math.ceil(frontTotal / rowCount));
    const span = Math.min(profile.windowSpan || 250, footprint.width - 104);
    const wStep = perRow > 1
        ? Math.max(profile.minWindowGap || 0, span / (perRow - 1))
        : 0;
    const rowOffset = row === 0 ? 0 : (profile.windowRowOffset || 0);
    return {
        x: Math.min(
            footprint.maxX - 36,
            footprint.minX + (profile.windowX0 || 35) + col * wStep + rowOffset
        ),
        y: baseY + 13,
        z: (profile.windowZ || [14])[row] ?? 14,
        side: 'front',
        queueMaxZ: tableZoneStartZ(profile) - CHAIR_DZ - QUEUE_TABLE_BUFFER_Z,
    };
}

function windowBayPosition(idx, total, baseY, profile, footprint) {
    const slot = windowBaySlot(idx, total, profile);
    if (!slot) return null;

    const { bay, localIdx, bayCount } = slot;
    if (bay.side === 'left') {
        const t = bayCount <= 1 ? 0.5 : localIdx / (bayCount - 1);
        const z = (bay.zStart || 18)
            + ((bay.zEnd || bay.zStart || 18) - (bay.zStart || 18)) * t
            + bayStaggerZ(bay, localIdx);
        return {
            x: Math.max(
                footprint.minX + 8,
                Math.min(footprint.minX + 32, footprint.minX + (bay.xInset || 18) + bayStaggerX(bay, localIdx))
            ),
            y: baseY + 13,
            z: Math.max(footprint.minZ + 8, Math.min(footprint.maxZ - 12, z)),
            side: 'left',
            bayId: bay.id,
        };
    }

    const startX = footprint.minX + footprint.width * (bay.xStartRatio ?? 0.18);
    const endX = footprint.minX + footprint.width * (bay.xEndRatio ?? 0.82);
    const availableSpan = Math.max(0, endX - startX);
    const step = bayCount > 1
        ? Math.max(bay.minWindowGap || 0, availableSpan / (bayCount - 1))
        : 0;
    const centeredStart = (startX + endX) / 2 - (step * (bayCount - 1)) / 2;
    return {
        x: Math.max(
            footprint.minX + 32,
            Math.min(footprint.maxX - 32, centeredStart + localIdx * step)
        ),
        y: baseY + 13,
        z: Math.max(
            footprint.minZ + 8,
            Math.min(footprint.maxZ - 12, (bay.z || 14) + bayStaggerZ(bay, localIdx))
        ),
        side: 'front',
        bayId: bay.id,
        queueMaxZ: tableZoneStartZ(profile) - CHAIR_DZ - QUEUE_TABLE_BUFFER_Z,
    };
}

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

// 单个楼层的稳定布局：窗口排、座位网格、学生网格。
// 每层内容只在本层 footprint 内布局，footprint 由桌椅、窗口、通道和楼梯核清距推导。
// CanteenScene 消费 frame 中每个 floor.footprint / footprint.outline，
// 不在渲染层重新猜楼层占地。
function layoutFloor(floor, floorIndex) {
    const baseY = floorIndex * FLOOR_V;            // 纯竖向堆叠
    const wins = floor.windows || [];
    const rawSeats = floor.seats || [];
    const profile = floorLayoutProfile(floor.floor_id);
    const footprint = furnitureDerivedFootprint(rawSeats, wins, profile);
    const windows = wins.map((win, idx) => ({
        id: win.id,
        floor_id: floor.floor_id,
        is_serving: Boolean(win.is_serving),
        // is_open / closing 取自后端派生字段；后端未透出时按 Phase 2 兼容默认开放。
        is_open: win.is_open !== false,
        closing: win.is_open === false && (win.queue_length > 0 || win.is_serving),
        queue_length: win.queue_length || 0,
        total_served: win.total_served || 0,
        position: windowPositionForProfile(idx, wins.length, baseY, profile, footprint),
    }));
    const visibleTableCount = visibleTableCountForProfile(rawSeats, profile);
    const seats = rawSeats.map((seat, idx) => ({
        id: seat.id,
        floor_id: floor.floor_id,
        status: seat.status,
        // 统计保留全量后端 seat；3D 坐标映射到有限可视桌组，避免几百个座位挤爆楼面。
        position: tableSeatPosition(idx, visibleTableCount, baseY, profile, footprint),
    }));
    const windowById = new Map(windows.map(win => [String(win.id), win]));
    const seatById = new Map(seats.map(seat => [String(seat.id), seat]));
    const students = (floor.students || []).map((student, idx) => {
        const sid = numericId(student.id);
        return {
            id: student.id,
            floor_id: floor.floor_id,
            position: student.position,
            position_detail: student.position_detail,
            queue_index: student.queue_index,
            from_floor_id: student.from_floor_id,
            target_floor_id: student.target_floor_id,
            floor_switch_progress: student.floor_switch_progress,
            target: placeStudentTarget(
                student, idx, baseY, footprint, windows, seats, windowById, seatById, sid
            ),
        };
    });
    return {
        floor_id: floor.floor_id,
        index: floorIndex,
        z: footprint.centerZ,
        baseY,
        footprint,
        windows,
        seats,
        students,
    };
}

function placeStudentTarget(student, idx, baseY, footprint, windows, seats, windowById, seatById, sid) {
    const position = student.position;
    if (position === 'floor_switching') {
        return stairSwitchTarget(student, baseY, footprint, sid);
    }
    if (position === 'window_queue') {
        const win = windowById.get(String(student.position_detail)) || windows[idx % Math.max(1, windows.length)];
        if (win) {
            const qIndex = Number.isFinite(student.queue_index) ? student.queue_index : idx;
            const lane = qIndex % WINDOW_QUEUE_LANES;
            const row = Math.floor(qIndex / WINDOW_QUEUE_LANES);
            const lateral = (lane - (WINDOW_QUEUE_LANES - 1) / 2) * WINDOW_QUEUE_LANE_DX;
            const depth = WINDOW_QUEUE_DEPTH_OFFSET + row * WINDOW_QUEUE_ROW_DZ;
            if (win.position.side === 'left') {
                return {
                    x: win.position.x + depth + jitter(sid, 1) * 0.9,
                    y: baseY + STUDENT_Y,
                    z: win.position.z + lateral + jitter(sid, 2) * 0.8,
                };
            }
            return {
                x: win.position.x + lateral + jitter(sid, 1) * 0.9,
                y: baseY + STUDENT_Y,
                z: Math.min(
                    win.position.queueMaxZ ?? 60,
                    win.position.z + depth + jitter(sid, 2) * 0.8
                ),
            };
        }
    }
    if (position === 'being_served') {
        const win = windowById.get(String(student.position_detail)) || windows[idx % Math.max(1, windows.length)];
        if (win) {
            return {
                x: win.position.x + jitter(sid, 1) * 0.7,
                y: baseY + STUDENT_Y,
                z: win.position.z + 6 + jitter(sid, 2) * 0.6,
            };
        }
    }
    if (position === 'seated') {
        const seat = seatById.get(String(student.position_detail)) || seats[idx % Math.max(1, seats.length)];
        if (seat) {
            return {
                x: seat.position.x + jitter(sid, 1) * 0.8,
                y: baseY + STUDENT_Y,
                z: seat.position.z + jitter(sid, 2) * 0.8,
            };
        }
    }
    if (position === 'waiting_queue') {
        const qIndex = Number.isFinite(student.position_detail) ? student.position_detail : idx;
        return {
            x: 60 + (qIndex % 10) * 24 + jitter(sid, 1) * 0.9,
            y: baseY + STUDENT_Y,
            z: 70 + Math.floor(qIndex / 10) * 4 + jitter(sid, 2) * 0.8,
        };
    }
    return {
        x: 50 + (idx % 18) * 12 + jitter(sid, 1) * 1.6,
        y: baseY + STUDENT_Y,
        z: 38 + Math.floor(idx / 18) * 4 + jitter(sid, 2) * 1.4,
    };
}

function stairSwitchTarget(student, baseY, footprint, sid) {
    const fromFloor = Number.isFinite(student.from_floor_id)
        ? student.from_floor_id
        : student.floor_id;
    const targetFloor = Number.isFinite(student.target_floor_id)
        ? student.target_floor_id
        : fromFloor;
    const progress = clamp01(student.floor_switch_progress);
    const step = Number.isFinite(student.stair_step)
        ? Math.max(0, Math.min(7, student.stair_step))
        : Math.min(7, Math.floor(progress * 8));
    const t = step / 7;
    const direction = targetFloor >= fromFloor ? 1 : -1;
    const entranceZs = entranceZsForFootprint(footprint);
    const startZ = direction > 0 ? entranceZs[0] : entranceZs[1];
    const endZ   = direction > 0 ? entranceZs[1] : entranceZs[0];
    return {
        x: sideEntranceXForFootprint(footprint) + 9 + jitter(sid, 11) * 0.45,
        y: baseY + STUDENT_Y + t * FLOOR_V * (targetFloor - fromFloor),
        z: startZ + t * (endZ - startZ) + jitter(sid, 12) * 0.5,
    };
}

function studentEntranceTarget(baseY, target, footprint, student) {
    if (student?.position === 'floor_switching') return target;
    const targetZ = target?.z ?? 40;
    const entranceZs = entranceZsForFootprint(footprint);
    const z = entranceZs.reduce((best, candidate) => (
        Math.abs(candidate - targetZ) < Math.abs(best - targetZ) ? candidate : best
    ), entranceZs[0]);
    const sid = numericId(student?.id);
    const qIndex = Number.isFinite(student?.queue_index)
        ? student.queue_index
        : sid % 15;
    const xLane = (qIndex % 3) - 1;
    const zLane = (Math.floor(qIndex / 3) % 5) - 2;
    const entryX = sideEntranceXForFootprint(footprint)
            + xLane * ENTRANCE_SPAWN_LANE_X
            + jitter(sid, 5) * 0.7;
    return {
        x: Math.min(-1, entryX),
        y: baseY + STUDENT_Y,
        z: z + zLane * ENTRANCE_SPAWN_LANE_Z + jitter(sid, 6) * 0.9,
    };
}

function studentKey(student) {
    return String(student.id);
}

function attachUnassignedStudents(canteen, floors) {
    const normalized = floors.map(floor => ({
        ...floor,
        windows: floor.windows || [],
        seats: floor.seats || [],
        students: [...(floor.students || [])],
    }));
    if (!normalized.length) return normalized;

    const assigned = new Set();
    normalized.forEach(floor => {
        floor.students.forEach(student => assigned.add(studentKey(student)));
    });
    const floorIds = new Set(normalized.map(floor => floor.floor_id));
    (canteen.students || []).forEach(student => {
        const hasFloor = floorIds.has(student.floor_id);
        const key = studentKey(student);
        if (!hasFloor && !assigned.has(key)) {
            normalized[0].students.push(student);
            assigned.add(key);
        }
    });
    return normalized;
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
        const visibleFloors = attachUnassignedStudents(canteen, floors);
        const floorFrames = visibleFloors.map((floor, idx) => {
            const layout = layoutFloor(floor, idx);
            layout.students.forEach(st => {
                const key = String(st.id);
                seenStudents.add(key);
                const prev = this._studentPos.get(key);
                const entry = studentEntranceTarget(layout.baseY, st.target, layout.footprint, st);
                const next = prev
                    ? {
                        x: prev.x + (st.target.x - prev.x) * LERP_ALPHA,
                        y: prev.y + (st.target.y - prev.y) * LERP_ALPHA,
                        z: prev.z + (st.target.z - prev.z) * LERP_ALPHA,
                    }
                    : entry;
                this._studentPos.set(key, next);
                st.position3d = next;
                st.entry3d = entry;
                st.is_entering = !prev || (
                    st.position !== 'seated'
                    && Math.abs(next.z - st.target.z) > 2
                    && next.z >= Math.min(entry.z, st.target.z)
                );
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
            sim_time: pickNum(snapshot?.current_time, canteen.current_time),
            students_in_canteen: floorFrames.reduce(
                (sum, floor) => sum + floor.students.length, 0
            ),
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

// canteen_layouts.js — 无 THREE 依赖的布局常量、几何数据、纯计算函数

export const WINDOW_LABEL_MAX_CHARS = 6;
export const WINDOW_LABEL_LINE_MAX_CHARS = 4;
export const WINDOW_LABEL_WORLD_WIDTH = 48;
export const WINDOW_LABEL_WORLD_HEIGHT = 16;
export const WINDOW_LABEL_RENDER_ORDER = 80;
export const WINDOW_LABEL_DENSITY_STEP = 2;
export const LABEL_TEXTURE_SCALE = 3;
export const LABEL_CANVAS_WIDTH = 320;
export const LABEL_CANVAS_HEIGHT_SINGLE = 72;
export const LABEL_CANVAS_HEIGHT_MULTI = 96;
export const WINDOW_INTERVENTION_EFFECT_MS = 1800;
export const WINDOW_INTERVENTION_PULSE_COLOR = 0x2dd4bf;
export const FRONT_WINDOW_COUNTER_SIZE = [24, 4.2, 6.2];
export const FRONT_WINDOW_GLASS_GUARD_SIZE = [24, 2.2, 0.8];
export const FRONT_WINDOW_STATUS_RAIL_SIZE = [12, 1.1, 0.8];
export const FRONT_WINDOW_STATUS_RAIL_IDLE_COLOR = 0x6f8790;
export const FRONT_WINDOW_STATUS_RAIL_SERVING_COLOR = 0x5eead4;
export const FRONT_WINDOW_SERVING_LIGHT_COLOR = 0x5eead4;
export const FRONT_WINDOW_SERVING_LIGHT_SIZE = [9, 1.4, 1.0];
export const FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE = [18, 0.9, 1.1];
export const FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY = 0.50;
export const FRONT_WINDOW_QUEUE_HEAT_CLEAR_COLOR = 0x2dd4bf;
export const FRONT_WINDOW_QUEUE_HEAT_BUSY_COLOR = 0x9ed7c5;
export const FRONT_WINDOW_MENU_BOARD_WIDTH = 42;
export const FRONT_WINDOW_MENU_BOARD_HEIGHT = 8.8;
export const FRONT_WINDOW_LABEL_X_OFFSET = 0;
export const FRONT_WINDOW_LABEL_Y_OFFSET = 20.4;
export const FRONT_WINDOW_LABEL_Z_OFFSET = -13.2;
// Style B: 实体建筑·写实风格 — 暖象牙楼板 + 水泥墙体
export const FLOOR_SLAB_COLORS = [0xf0f4ee, 0xe3ece8];
export const FLOOR_TILE_COLOR = 0xf4f7f1;
export const FLOOR_SLAB_OPACITY = 0.055;
export const OVERVIEW_FLOOR_SLAB_OPACITY = 0.07;
export const FOCUS_FLOOR_SLAB_OPACITY = 1.0;
export const FLOOR_SLAB_RENDER_ORDER = -4;
// 透明层显式绘制阶梯：同 renderOrder 的透明物体按包围球距离逐帧重排，
// 大块近共面板在环绕相机时排序翻转 → 闪烁；显式阶梯让混合顺序确定。
export const WALL_RENDER_ORDER = -3;
export const FLOOR_SKIRT_RENDER_ORDER = -3;
export const FLOOR_EDGE_BAND_RENDER_ORDER = -2;
export const WINDOW_GLASS_RENDER_ORDER = -1;
export const FLOOR_DECAL_RENDER_ORDER = 1;
export const QUEUE_HEAT_RENDER_ORDER = 3;
export const STAIR_CORE_RENDER_ORDER = 5;
export const DEFAULT_LABEL_RENDER_ORDER = 30;
export const FLOOR_OUTLINE_OPACITY = 0.72;
export const FLOOR_TILE_OUTLINE_OPACITY = 0.42;
export const FLOOR_EDGE_BAND_HEIGHT = 4.8;
export const FLOOR_EDGE_BAND_THICKNESS = 2.4;
export const FLOOR_EDGE_BAND_OPACITY = 0.95;
// drop band tops slightly below the slab plane: both surfaces are transparent
// with depthWrite off, so an exactly coplanar pair blends in unstable order.
export const FLOOR_EDGE_BAND_Y_EPSILON = 0.08;
export const FLOOR_BACK_WALL_OPACITY = 0.075;
export const FLOOR_SIDE_WALL_OPACITY = 0.035;
export const OVERVIEW_FLOOR_GRADIENT_Z_OFFSETS = [48, 12, -24];
export const OVERVIEW_FLOOR_GRADIENT_OPACITY = [1.0, 0.64, 0.38];
// Style B 墙体 / 边框色（暖水泥灰）
export const FLOOR_WALL_COLOR = 0x8a7a6a;
export const FLOOR_EDGE_COLOR = 0x3a2e28;
export const OPEN_BUILDING_FRAME_OPACITY = 0.76;
export const OPEN_BUILDING_DEPTH_PAD = 8;
export const INTERFLOOR_SHADOW_OPACITY = 0.34;
export const INTERFLOOR_SHADOW_HEIGHT = 2.6;

// 食堂建筑尺寸从 state_adapter 的 frame.floors[].footprint 读取；正常路径使用
// 每个 floor.footprint / footprint.outline 渲染真实楼层轮廓。默认值只用于
// 首帧/兼容兜底，正常路径不再把每层强制塞进统一长矩形。
export const DEFAULT_FOOTPRINT_WIDTH = 320;
export const DEFAULT_FOOTPRINT_DEPTH = 180;
export const DEFAULT_CENTER_X = 160;

export const TABLE_DX = 44;
export const TABLE_Z0 = 46;
export const TABLE_DZ = 15;
export const TABLE_ZONE_AISLE_X = 60;
export const TABLE_ROW_AISLE_Z = 12;
// Keep scene geometry aligned with state_adapter.js: roughly 10 scene units per
// meter, with a 7.2m window-to-table buffer for peak queueing plus main aisle.
export const SCENE_UNITS_PER_METER = 10;
export const SERVICE_TO_TABLE_BUFFER_M = 7.2;
export const TABLE_WINDOW_GAP_Z = SERVICE_TO_TABLE_BUFFER_M * SCENE_UNITS_PER_METER;
export const TABLE_ZONE_SIDE_PADDING = 42;
export const TABLE_ZONE_MAX_COLS = 3;
export const CHAIR_DX = 12;
export const CHAIR_DZ = 7;
export const SIDE_ENTRANCE_X = -10;
export const SITE_PLINTH_CENTER_Y = -7;
export const SIDE_ENTRANCE_MARKERS = [
    { name: 'canteenEntranceLowerStair', z: 28, stairName: 'stairCoreEntranceLower' },
    { name: 'canteenEntranceUpperStair', z: 68, stairName: 'stairCoreEntranceUpper' },
];
export const ENTRANCE_MARKER_DEPTH = 44;
export const ENTRANCE_DOOR_HEIGHT = 14.5;
export const ENTRANCE_DOOR_DEPTH = 46;
export const ENTRANCE_GLASS_HEIGHT = 10.8;
export const ENTRANCE_GLASS_DEPTH = 32;
export const ENTRANCE_CANOPY_DEPTH = 54;

export function actualTableCount(seats) {
    return Math.ceil((seats || []).length / 4);
}

export function visibleTableCountForProfile(seats, profile) {
    const actual = actualTableCount(seats);
    return Math.max(1, Math.min(profile.visibleTableCount || actual, actual));
}

export function visualTableIndexForSeat(seatIdx, visibleTableCount) {
    return Math.floor(seatIdx / 4) % visibleTableCount;
}

export function tableColumnCount(tableCount) {
    if (tableCount <= 0) return 1;
    return Math.ceil(tableCount / 3);
}

export function tableZoneCount(tableCount) {
    if (tableCount >= 15) return 3;
    if (tableCount >= 8) return 2;
    return 1;
}

export function tableZoneColumnCount(zoneTableCount) {
    if (zoneTableCount <= 0) return 1;
    return Math.min(TABLE_ZONE_MAX_COLS, Math.max(1, Math.ceil(zoneTableCount / 3)));
}

export function tableBlocksForProfile(profile) {
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

export function tableBlockForIndex(idx, profile) {
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

export function serviceWindowMaxZ(profile) {
    const frontWindowMaxZ = Math.max(...(profile.windowZ || [14]));
    const sideWindowCount = profile.sideWindowCount || 0;
    const sideWindowMaxZ = sideWindowCount > 0
        ? (profile.sideWindowZ0 || 18) + (sideWindowCount - 1) * (profile.sideWindowGap || 20)
        : frontWindowMaxZ;
    return Math.max(frontWindowMaxZ, sideWindowMaxZ);
}

export function tableZoneStartZ(profile) {
    return Math.max(
        profile.tableZ0 || TABLE_Z0,
        serviceWindowMaxZ(profile) + TABLE_WINDOW_GAP_Z + CHAIR_DZ
    );
}

export function tableZonePosition(idx, tableCount, profile, footprint) {
    return tableBlockPosition(idx, tableCount, profile, footprint);
}

export function tableBlockPosition(idx, tableCount, profile, footprint) {
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

export function legacyTableZonePosition(idx, tableCount, profile, footprint) {
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

export function defaultFootprint() {
    const minX = DEFAULT_CENTER_X - DEFAULT_FOOTPRINT_WIDTH / 2;
    const maxX = DEFAULT_CENTER_X + DEFAULT_FOOTPRINT_WIDTH / 2;
    const maxZ = DEFAULT_FOOTPRINT_DEPTH;
    return {
        source: 'defaultFootprint',
        width: DEFAULT_FOOTPRINT_WIDTH,
        depth: DEFAULT_FOOTPRINT_DEPTH,
        minX,
        maxX,
        minZ: 0,
        maxZ,
        centerX: DEFAULT_CENTER_X,
        centerZ: maxZ / 2,
        outline: [
            { x: minX, z: 0 },
            { x: maxX, z: 0 },
            { x: maxX, z: maxZ - 28 },
            { x: minX + 64, z: maxZ - 28 },
            { x: minX + 64, z: maxZ },
            { x: minX, z: maxZ },
        ],
    };
}

export function normalizedFootprint(fp) {
    if (!fp || !Array.isArray(fp.outline) || fp.outline.length < 3) {
        return defaultFootprint();
    }
    return {
        ...fp,
        centerX: fp.centerX ?? (fp.minX + fp.maxX) / 2,
        centerZ: fp.centerZ ?? (fp.minZ + fp.maxZ) / 2,
    };
}

// 冷青监控调色（与 scene3d / canvas_renderer 图例语义连续）。
export const PALETTE = {
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
export const PHOTO_WALL_SIGN_COLOR = 0x18384a;

export const STUDENT_CLOTHING_PALETTE = [
    0x2563eb, 0x059669, 0xf59e0b, 0xdc2626,
    0x7c3aed, 0x0f766e, 0xbe123c, 0x475569,
];
export const STUDENT_SERVING_STATUS_COLOR = 0x5eead4;

export function stableStudentClothingColor(student) {
    const key = String(student?.id ?? 'student');
    let hash = 0;
    for (let i = 0; i < key.length; i += 1) {
        hash = ((hash * 31) + key.charCodeAt(i)) >>> 0;
    }
    return STUDENT_CLOTHING_PALETTE[hash % STUDENT_CLOTHING_PALETTE.length];
}

export function studentStatusColor(student) {
    if (student.position === 'window_queue') return PALETTE.studentQueue;
    if (student.position === 'waiting_queue') return 0x8b5cf6;
    if (student.position === 'being_served') return STUDENT_SERVING_STATUS_COLOR;
    if (student.position === 'seated') return PALETTE.seatOccupied;
    return PALETTE.studentMove;
}

// Real Minghu / Xueyi photo cues from Dianping/Ctrip search:
// black-framed window wall, glossy pale floor, wood four-seat tables,
// mixed green/pink/gray chairs, white ceiling pipes, muted menu boards.
export const photoWindowWall = {
    frame: 0x17202b,
    glass: 0xcfe9ee,
    tile: 0xd7e0dc,
    wall: 0xe7ece7,
    menu: PHOTO_WALL_SIGN_COLOR,
};
export const mixedChairPalette = [0x1f7568, 0xd9869c, 0x65737f, 0x9b8f6a];
export const FLOOR_TABLE_COLOR_FALLBACKS = {
    square: 0xc79a58,
    long: 0x9a6b3e,
    booth: 0xb9804a,
};
// Spec §A per-floor stall theme: material/color-temperature only, emissive ≈ 0.
export const STALL_THEME = {
    1: { sign: 0x8a9aa6, counter: 0x9aa7ad, rail: 0x7d8a90, glass: 0xbcd6db, roughness: 0.40 }, // brushed steel, cool
    2: { sign: 0xc79a58, counter: 0xb88c4f, rail: 0x8a6537, glass: 0xe8d2a8, roughness: 0.46 }, // warm wood + brass
    3: { sign: 0x7a5a40, counter: 0x6e553e, rail: 0x4e3b2a, glass: 0x9b7d55, roughness: 0.52 }, // dark wood, warm
};
export function stallTheme(floorId) {
    return STALL_THEME[floorId] || STALL_THEME[1];
}
export const MINGHU_FLOOR_LAYOUTS = {
    1: {
        key: 'basicMealWideAisle',
        windowBays: [
            { id: 'f1-front-service-band-left', side: 'front' },
            { id: 'f1-front-service-band-center', side: 'front' },
            { id: 'f1-front-service-band-right', side: 'front' },
        ],
        tableShiftX: 0,
        tableZ0: 96,
        tableRowStagger: 0,
        windowZ: [16],
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
        tableVariants: ['square', 'square', 'long', 'square'],
        cueColor: 0x2dd4bf,
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
            { id: 'f2-left-snack-bay', side: 'left' },
            { id: 'f2-front-coffee-bay', side: 'front' },
            { id: 'f2-front-hotfood-bay', side: 'front' },
        ],
        tableShiftX: -5,
        tableZ0: 80,
        tableRowStagger: 10,
        windowZ: [12, 30],
        sideWindowCount: 1,
        sideWindowZ0: 40,
        sideWindowGap: 44,
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
            { id: 'f2-mid-right-flex-fill', type: 'square', tableColor: 0xb9856f, count: 6, cols: 3,
              anchor: 'right', right: 70, z: 148, dx: 38, dz: 30 },
            { id: 'f2-rear-flex-fill', type: 'square', tableColor: 0xb9856f, count: 6, cols: 3,
              anchor: 'center', offsetX: -80, z: 167, dx: 40, dz: 33 },
        ],
        tableVariants: ['long', 'square', 'square', 'long', 'square'],
        cueColor: 0xe7bd63,
    },
    3: {
        key: 'restaurantDiningRoom',
        windowBays: [
            { id: 'f3-specialty-side-bay', side: 'left' },
            { id: 'f3-front-hotpot-bay', side: 'front' },
            { id: 'f3-front-noodle-bay', side: 'front' },
            { id: 'f3-front-tea-bay', side: 'front' },
        ],
        tableShiftX: 8,
        tableZ0: 112,
        tableRowStagger: -8,
        windowZ: [14, 34],
        sideWindowCount: 2,
        sideWindowZ0: 28,
        sideWindowGap: 26,
        visibleTableCount: 52,
        mainAisleWidth: 72,
        queueBufferDepth: 92,
        tableBlocks: [
            { id: 'f3-wall-booth-run', type: 'booth', tableColor: 0x7a5a40, count: 6, cols: 1,
              anchor: 'left', left: 58, z: 0, dx: 0, dz: 28 },
            { id: 'f3-central-dining-cluster', type: 'square', tableColor: 0x9b7d55, count: 18, cols: 3,
              anchor: 'center', offsetX: -10, z: 20, dx: 44, dz: 26 },
            { id: 'f3-left-mid-square-infill', type: 'square', tableColor: 0x8f7d67, count: 6, cols: 2,
              anchor: 'left', left: 126, z: 100, dx: 40, dz: 30 },
            { id: 'f3-east-mid-square-infill', type: 'square', tableColor: 0x8aa092, count: 8, cols: 2,
              anchor: 'right', right: 136, z: 64, dx: 42, dz: 32 },
            { id: 'f3-rear-hotpot-communal', type: 'long', tableColor: 0x835f42, count: 8, cols: 4,
              anchor: 'center', offsetX: 44, z: 176, dx: 46, dz: 28 },
            { id: 'f3-right-window-booth-run', type: 'booth', tableColor: 0x4e6b70, count: 6, cols: 1,
              anchor: 'right', right: 68, z: 0, dx: 0, dz: 32 },
        ],
        tableVariants: ['booth', 'square', 'booth', 'long', 'square'],
        cueColor: 0x8b5cf6,
    },
};
export const MINGHU_WINDOW_LABELS = {
    1: ['小份菜', '麻辣香锅', '美味拌饭', '面食', '自选菜', '自选菜'],
    2: ['库迪咖啡', '西北刀削面', '炒鸡米饭', '分米鸡', '热卤拌饭', '云南菌菇炒饭',
        '土豆泥拌饭', '烤鸭', '炙烤五花肉', '煲仔饭', '麻辣香锅', '广东美食', '自选快餐'],
    3: ['旋转小火锅', '东北麻辣烫', '黄焖鸡', '猪排饭', '手工水饺', '海南鸡饭',
        '热卤拌饭', '重庆面庄', '小锅焖面', '广式烧腊', '鲍汁捞饭', '茶瀑布',
        '牛肉粉丝汤', '特色窗口'],
};

export function compactWindowLabel(text) {
    const label = String(text || '').trim();
    if (label.length <= WINDOW_LABEL_MAX_CHARS) return label;
    return label.slice(0, WINDOW_LABEL_MAX_CHARS);
}

export function windowLabelLines(text) {
    const label = compactWindowLabel(text);
    if (label.length <= WINDOW_LABEL_LINE_MAX_CHARS) return [label];
    const splitAt = Math.ceil(label.length / 2);
    return [label.slice(0, splitAt), label.slice(splitAt)].filter(Boolean);
}

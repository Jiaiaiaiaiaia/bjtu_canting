// canteen_scene.js — 单食堂多层 3D 构建 + A+C 混合相机状态机（spec §4.1）
//
// 职责：
//  - 把 state_adapter 给的稳定帧（floors[] + windows/seats/students）建成
//    「3 层竖向堆叠 + 正面剖面」的 3D 场景（spec §4.1 默认/总览态 A）。
//  - A+C 状态机（方案 2）：OVERVIEW（堆叠剖面环绕）↔ FOCUS（侧面看清楼层、
//    再转俯视、最终铺满整层）。点层/Tab 进 FOCUS，「全景」回 A。
//  - 不绘制学生路线线条；学生以分区聚集的小人表达，可点名追踪单个学生。
//
// 视觉 identity = 冷青监控（spec §4.2）：沿用 scene3d 调色——深青底
// 0x07111d、青绿网格 0x315467/0x2dd4bf、拥堵热力青→琥珀→红、发光流线青、
// 关窗暗+「关闭中」、空关灰、KPI 青字。THREE 实例由 scene3d 注入（单一
// importmap 依赖），不在本模块重复 import three。

const FLOOR_RISE = 0;           // 层间高差（场景已竖向展开，无需额外偏移）
const CAM_LERP = 0.045;         // 相机/层位移插值系数
const FOCUS_SIDE_DURATION_MS = 1600;
const FOCUS_TOP_DURATION_MS = 1800;
const FOCUS_EXPANDED_DURATION_MS = 1800;
const WINDOW_LABEL_MAX_CHARS = 6;
const WINDOW_LABEL_LINE_MAX_CHARS = 4;
const WINDOW_LABEL_WORLD_WIDTH = 48;
const WINDOW_LABEL_WORLD_HEIGHT = 16;
const WINDOW_LABEL_RENDER_ORDER = 80;
const WINDOW_LABEL_DENSITY_STEP = 2;
const LABEL_TEXTURE_SCALE = 3;
const LABEL_CANVAS_WIDTH = 320;
const LABEL_CANVAS_HEIGHT_SINGLE = 72;
const LABEL_CANVAS_HEIGHT_MULTI = 96;
const WINDOW_INTERVENTION_EFFECT_MS = 1800;
const WINDOW_INTERVENTION_PULSE_COLOR = 0x2dd4bf;
const FRONT_WINDOW_COUNTER_SIZE = [24, 4.2, 6.2];
const FRONT_WINDOW_GLASS_GUARD_SIZE = [24, 2.2, 0.8];
const FRONT_WINDOW_STATUS_RAIL_SIZE = [12, 1.1, 0.8];
const FRONT_WINDOW_STATUS_RAIL_IDLE_COLOR = 0x6f8790;
const FRONT_WINDOW_STATUS_RAIL_SERVING_COLOR = 0x5eead4;
const FRONT_WINDOW_SERVING_LIGHT_COLOR = 0x5eead4;
const FRONT_WINDOW_SERVING_LIGHT_SIZE = [9, 1.4, 1.0];
const FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE = [18, 0.9, 1.1];
const FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY = 0.50;
const FRONT_WINDOW_QUEUE_HEAT_CLEAR_COLOR = 0x2dd4bf;
const FRONT_WINDOW_QUEUE_HEAT_BUSY_COLOR = 0x9ed7c5;
const FRONT_WINDOW_MENU_BOARD_WIDTH = 42;
const FRONT_WINDOW_MENU_BOARD_HEIGHT = 8.8;
const FRONT_WINDOW_LABEL_X_OFFSET = 0;
const FRONT_WINDOW_LABEL_Y_OFFSET = 20.4;
const FRONT_WINDOW_LABEL_Z_OFFSET = -13.2;
const FLOOR_SLAB_COLORS = [0xf0f4ee, 0xe3ece8];
const FLOOR_TILE_COLOR = 0xf4f7f1;
const FLOOR_SLAB_OPACITY = 0.055;
const OVERVIEW_FLOOR_SLAB_OPACITY = 0.07;
const FOCUS_FLOOR_SLAB_OPACITY = 1.0;
const FLOOR_SLAB_RENDER_ORDER = -4;
const FLOOR_OUTLINE_OPACITY = 0.72;
const FLOOR_TILE_OUTLINE_OPACITY = 0.42;
const FLOOR_EDGE_BAND_HEIGHT = 4.8;
const FLOOR_EDGE_BAND_THICKNESS = 2.4;
const FLOOR_EDGE_BAND_OPACITY = 0.72;
const FLOOR_BACK_WALL_OPACITY = 0.075;
const FLOOR_SIDE_WALL_OPACITY = 0.035;
const OPEN_BUILDING_FRAME_OPACITY = 0.76;
const OPEN_BUILDING_DEPTH_PAD = 8;
const INTERFLOOR_SHADOW_OPACITY = 0.34;
const INTERFLOOR_SHADOW_HEIGHT = 2.6;

// 食堂建筑尺寸从 state_adapter 的 frame.floors[].footprint 读取；正常路径使用
// 每个 floor.footprint / footprint.outline 渲染真实楼层轮廓。默认值只用于
// 首帧/兼容兜底，正常路径不再把每层强制塞进统一长矩形。
const DEFAULT_FOOTPRINT_WIDTH = 320;
const DEFAULT_FOOTPRINT_DEPTH = 180;
const DEFAULT_CENTER_X = 160;
const OVERVIEW_CAMERA_X = 160;
const OVERVIEW_CAMERA_Z = 360;
const OVERVIEW_CAMERA_Y_PADDING = 118;
const OVERVIEW_LOOK_Y_RATIO = 0.54;
const OVERVIEW_LOOK_Y_OFFSET = 18;
const OVERVIEW_THREE_QUARTER_X_RATIO = 0.28;
const OVERVIEW_THREE_QUARTER_MIN_X = 110;
const OVERVIEW_THREE_QUARTER_Y_PADDING = 0;
const OVERVIEW_THREE_QUARTER_Z_PADDING = 0;
const OVERVIEW_THREE_QUARTER_HEIGHT_RATIO = 0.72;
const OVERVIEW_THREE_QUARTER_DEPTH_RATIO = 0.72;
const OVERVIEW_LOOK_PANEL_CLEARANCE_X_RATIO = 0.08;
const FOCUS_CAMERA_X = 160;
const FOCUS_CAMERA_Z = 250;
const FOCUS_CAMERA_Y_PADDING = 104;
const FOCUS_SIDE_CAMERA_X = -190;
const FOCUS_SIDE_CAMERA_Z = DEFAULT_FOOTPRINT_DEPTH / 2;
const FOCUS_SIDE_CAMERA_Y_PADDING = 58;
const FOCUS_TOP_CAMERA_Z = DEFAULT_FOOTPRINT_DEPTH / 2 + 14;
const FOCUS_TOP_CAMERA_Y_PADDING = 210;
const FOCUS_EXPANDED_CAMERA_Z = DEFAULT_FOOTPRINT_DEPTH / 2 + 6;
const FOCUS_EXPANDED_CAMERA_Y_PADDING = 360;
const FOCUS_TOP_OBLIQUE_Z_PADDING = 72;
const FOCUS_EXPANDED_OBLIQUE_Z_PADDING = 54;
const FOCUS_SIDE_MIN_DISTANCE = 240;
const FOCUS_SIDE_Z_OFFSET_RATIO = 0.18;
const FOCUS_TOP_MIN_HEIGHT = 300;
const FOCUS_EXPANDED_MIN_HEIGHT = 430;
const VIEW_PRESET_FRONT_DISTANCE = 360;
const VIEW_PRESET_SIDE_DISTANCE = 390;
const VIEW_PRESET_TOP_HEIGHT = 460;
const VIEW_PRESET_TOP_Z_OFFSET = 28;
const TABLE_DX = 44;
const TABLE_Z0 = 46;
const TABLE_DZ = 15;
const TABLE_ZONE_AISLE_X = 60;
const TABLE_ROW_AISLE_Z = 12;
// Keep scene geometry aligned with state_adapter.js: roughly 10 scene units per
// meter, with a 7.2m window-to-table buffer for peak queueing plus main aisle.
const SCENE_UNITS_PER_METER = 10;
const SERVICE_TO_TABLE_BUFFER_M = 7.2;
const TABLE_WINDOW_GAP_Z = SERVICE_TO_TABLE_BUFFER_M * SCENE_UNITS_PER_METER;
const TABLE_ZONE_SIDE_PADDING = 42;
const TABLE_ZONE_MAX_COLS = 3;
const CHAIR_DX = 12;
const CHAIR_DZ = 7;
const SIDE_ENTRANCE_X = -10;
const SITE_PLINTH_CENTER_Y = -7;
const SIDE_ENTRANCE_MARKERS = [
    { name: 'canteenEntranceLowerStair', z: 28, stairName: 'stairCoreEntranceLower' },
    { name: 'canteenEntranceUpperStair', z: 68, stairName: 'stairCoreEntranceUpper' },
];
const ENTRANCE_MARKER_DEPTH = 44;
const ENTRANCE_DOOR_HEIGHT = 14.5;
const ENTRANCE_DOOR_DEPTH = 46;
const ENTRANCE_GLASS_HEIGHT = 10.8;
const ENTRANCE_GLASS_DEPTH = 32;
const ENTRANCE_CANOPY_DEPTH = 54;

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

function serviceWindowMaxZ(profile) {
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

function defaultFootprint() {
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

function normalizedFootprint(fp) {
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
const PHOTO_WALL_SIGN_COLOR = 0x18384a;

const STUDENT_CLOTHING_PALETTE = [
    0x2563eb, 0x059669, 0xf59e0b, 0xdc2626,
    0x7c3aed, 0x0f766e, 0xbe123c, 0x475569,
];
const STUDENT_SERVING_STATUS_COLOR = 0x5eead4;

function stableStudentClothingColor(student) {
    const key = String(student?.id ?? 'student');
    let hash = 0;
    for (let i = 0; i < key.length; i += 1) {
        hash = ((hash * 31) + key.charCodeAt(i)) >>> 0;
    }
    return STUDENT_CLOTHING_PALETTE[hash % STUDENT_CLOTHING_PALETTE.length];
}

function studentStatusColor(student) {
    if (student.position === 'window_queue') return PALETTE.studentQueue;
    if (student.position === 'waiting_queue') return 0x8b5cf6;
    if (student.position === 'being_served') return STUDENT_SERVING_STATUS_COLOR;
    if (student.position === 'seated') return PALETTE.seatOccupied;
    return PALETTE.studentMove;
}

// Real Minghu / Xueyi photo cues from Dianping/Ctrip search:
// black-framed window wall, glossy pale floor, wood four-seat tables,
// mixed green/pink/gray chairs, white ceiling pipes, muted menu boards.
const photoWindowWall = {
    frame: 0x17202b,
    glass: 0xcfe9ee,
    tile: 0xd7e0dc,
    wall: 0xe7ece7,
    menu: PHOTO_WALL_SIGN_COLOR,
};
const mixedChairPalette = [0x1f7568, 0xd9869c, 0x65737f, 0x9b8f6a];
const FLOOR_TABLE_COLOR_FALLBACKS = {
    square: 0xc79a58,
    long: 0x9a6b3e,
    booth: 0xb9804a,
};
// Spec §A per-floor stall theme: material/color-temperature only, emissive ≈ 0.
const STALL_THEME = {
    1: { sign: 0x8a9aa6, counter: 0x9aa7ad, rail: 0x7d8a90, glass: 0xbcd6db, roughness: 0.40 }, // brushed steel, cool
    2: { sign: 0xc79a58, counter: 0xb88c4f, rail: 0x8a6537, glass: 0xe8d2a8, roughness: 0.46 }, // warm wood + brass
    3: { sign: 0x7a5a40, counter: 0x6e553e, rail: 0x4e3b2a, glass: 0x9b7d55, roughness: 0.52 }, // dark wood, warm
};
function stallTheme(floorId) {
    return STALL_THEME[floorId] || STALL_THEME[1];
}
const MINGHU_FLOOR_LAYOUTS = {
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
            { id: 'f2-rear-flex-fill', type: 'square', tableColor: 0xb9856f, count: 12, cols: 6,
              anchor: 'center', offsetX: -4, z: 184, dx: 36, dz: 26 },
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
        tableZ0: 106,
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
        tableVariants: ['booth', 'square', 'booth', 'long', 'square'],
        cueColor: 0x8b5cf6,
    },
};
const MINGHU_WINDOW_LABELS = {
    1: ['小份菜', '麻辣香锅', '美味拌饭', '面食', '自选菜', '自选菜'],
    2: ['库迪咖啡', '西北刀削面', '炒鸡米饭', '分米鸡', '热卤拌饭', '云南菌菇炒饭',
        '土豆泥拌饭', '烤鸭', '炙烤五花肉', '煲仔饭', '麻辣香锅', '广东美食', '自选快餐'],
    3: ['旋转小火锅', '东北麻辣烫', '黄焖鸡', '猪排饭', '手工水饺', '海南鸡饭',
        '热卤拌饭', '重庆面庄', '小锅焖面', '广式烧腊', '鲍汁捞饭', '茶瀑布',
        '牛肉粉丝汤', '特色窗口'],
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

function compactWindowLabel(text) {
    const label = String(text || '').trim();
    if (label.length <= WINDOW_LABEL_MAX_CHARS) return label;
    return label.slice(0, WINDOW_LABEL_MAX_CHARS);
}

function windowLabelLines(text) {
    const label = compactWindowLabel(text);
    if (label.length <= WINDOW_LABEL_LINE_MAX_CHARS) return [label];
    const splitAt = Math.ceil(label.length / 2);
    return [label.slice(0, splitAt), label.slice(splitAt)].filter(Boolean);
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
        this.focusTransitionStage = 'overview'; // 'overview' | 'side' | 'top' | 'expanded'
        this.focusTransitionStartedAt = 0;
        this.viewPreset = 'overview';   // 'overview' | 'front' | 'side' | 'top' | 'free'
        this.trackedStudentId = null;
        this._floorGroups = new Map(); // floorId -> THREE.Group（用于聚焦可见性控制）
        this._floorSlide = new Map();  // floorId -> 当前位移（focus 下固定归零）
        this._floorCount = 0;
        this._windowInterventionEffects = new Map();
        this._seenInterventionKeys = new Set();
        this._hasInterventionBaseline = false;

        // 剖切/热力模式（与 immersive_ui 绑定时赋值，默认剖切展示）
        this.cutaway = true;
        this.heatMode = false;

        // 相机目标（插值逼近，离散切换→平滑飞入）
        const fp = defaultFootprint();
        this._camTarget = { pos: new THREE.Vector3(OVERVIEW_CAMERA_X, 232, OVERVIEW_CAMERA_Z),
                            look: new THREE.Vector3(fp.centerX, 76, fp.centerZ) };
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

    // 点层 / 楼层 Tab → 转为该层俯视，聚焦时只显示选中楼层。
    focusFloor(floorId) {
        this.mode = 'focus';
        this.focusFloorId = floorId;
        this.focusTransitionStartedAt = this._now();
        this.focusTransitionStage = 'side';
        this.viewPreset = 'overview';
        this._recomputeCameraTarget();
        this._lastFrame && this._rebuild(this._lastFrame);
    }

    // 空白处 / 「全景」→ 回 A 总览。
    resetView() {
        this.mode = 'overview';
        this.focusFloorId = null;
        this.focusTransitionStage = 'overview';
        this.focusTransitionStartedAt = 0;
        this.viewPreset = 'overview';
        this.trackedStudentId = null;
        this._recomputeCameraTarget();
        this._lastFrame && this._rebuild(this._lastFrame);
    }

    setViewPreset(preset) {
        preset = ['overview', 'front', 'side', 'top', 'free'].includes(preset)
            ? preset
            : 'overview';
        this.viewPreset = preset;
        if (preset === 'overview') {
            this.mode = 'overview';
            this.focusFloorId = null;
            this.focusTransitionStage = 'overview';
            this.focusTransitionStartedAt = 0;
        }
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
        this._syncWindowInterventionEffects(frame);
        this._rebuild(frame);
        this._recomputeCameraTarget();
    }

    // RAF 每帧调用（scene3d.animate() 调用）：仅推进插值动画，不重建几何。
    // First-frame safety: 快照到达前 tick 空转，不访问未初始化的 floorGroups。
    tick() {
        if (!this._lastFrame || this._floorGroups.size === 0) return;
        this._recomputeCameraTarget();
        this._animateFloors();
        this._animateWindowInterventions();
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

    _label(text, x, y, z, color, opacity, scale = 1, options = {}) {
        const lines = Array.isArray(text) ? text : [String(text || '')];
        const canvas = document.createElement('canvas');
        canvas.width = LABEL_CANVAS_WIDTH * LABEL_TEXTURE_SCALE;
        canvas.height = (lines.length > 1 ? LABEL_CANVAS_HEIGHT_MULTI : LABEL_CANVAS_HEIGHT_SINGLE)
            * LABEL_TEXTURE_SCALE;
        const ctx = canvas.getContext('2d');
        ctx.scale(LABEL_TEXTURE_SCALE, LABEL_TEXTURE_SCALE);
        const bgHeight = lines.length > 1 ? 88 : 64;
        if (!options.alwaysReadableWindowLabel) {
            ctx.fillStyle = 'rgba(7,17,29,0.76)';
            ctx.roundRect?.(4, 4, 312, bgHeight, 10);
            ctx.fill?.();
        }
        ctx.fillStyle = color || PALETTE.label;
        ctx.font = `bold ${lines.length > 1 ? 22 : 26}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const lineHeight = lines.length > 1 ? 24 : 26;
        const centerY = lines.length > 1 ? 48 : 38;
        lines.forEach((line, idx) => {
            const lineY = centerY + (idx - (lines.length - 1) / 2) * lineHeight;
            if (options.alwaysReadableWindowLabel) {
                // window labels should render as stroked text, not dark rectangular blocks.
                ctx.lineWidth = lines.length > 1 ? 4 : 5;
                ctx.strokeStyle = 'rgba(7,17,29,0.82)';
                ctx.strokeText(line, 160, lineY);
            }
            ctx.fillText(line, 160, lineY);
        });
        const texture = new this.THREE.CanvasTexture(canvas);
        texture.generateMipmaps = false;
        texture.minFilter = this.THREE.LinearFilter;
        texture.magFilter = this.THREE.LinearFilter;
        texture.needsUpdate = true;
        const mat = new this.THREE.SpriteMaterial({ map: texture, transparent: true });
        if (opacity != null) mat.opacity = opacity;
        if (options.alwaysReadableWindowLabel) {
            mat.depthTest = false;
            mat.depthWrite = false;
        }
        const sprite = new this.THREE.Sprite(mat);
        sprite.position.set(x, y, z);
        sprite.scale.set(90 * scale, 22 * scale, 1);
        if (options.renderOrder != null) sprite.renderOrder = options.renderOrder;
        if (options.alwaysReadableWindowLabel) sprite.userData.alwaysReadableWindowLabel = true;
        return sprite;
    }

    _photoMat(color, options = {}) {
        return new this.THREE.MeshStandardMaterial({
            color,
            roughness: options.roughness ?? 0.55,
            metalness: options.metalness ?? 0.03,
            transparent: options.opacity != null,
            opacity: options.opacity ?? 1,
            emissive: options.emissive ?? 0x000000,
            emissiveIntensity: options.emissiveIntensity ?? 0,
        });
    }

    _floorSlabOpacity(floor) {
        // floor surface opacity increases only for selected floor focus; overview
        // stays low-opacity so stacked lower floors remain readable.
        const isFocusedFloor = this.mode === 'focus'
            && this.focusFloorId != null
            && floor?.floor_id === this.focusFloorId;
        return isFocusedFloor ? FOCUS_FLOOR_SLAB_OPACITY : OVERVIEW_FLOOR_SLAB_OPACITY;
    }

    _floorSlabMaterial(color, opacity) {
        const mat = new this.THREE.MeshBasicMaterial({
            color,
            transparent: opacity < 0.98,
            opacity,
            depthWrite: opacity >= 0.98,
            depthTest: true,
            toneMapped: false,
        });
        mat.forceSinglePass = true;
        mat.polygonOffset = true;
        mat.polygonOffsetFactor = 1;
        mat.polygonOffsetUnits = 1;
        return mat;
    }

    _box(group, name, size, pos, mat, userData) {
        const mesh = new this.THREE.Mesh(
            new this.THREE.BoxGeometry(size[0], size[1], size[2]),
            mat
        );
        mesh.name = name;
        mesh.position.set(pos[0], pos[1], pos[2]);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        if (userData) mesh.userData = userData;
        group.add(mesh);
        return mesh;
    }

    _floorFootprint(floor) {
        return normalizedFootprint(floor?.footprint);
    }

    _frameFootprint(frame) {
        const footprints = (frame?.floors || []).map(floor => this._floorFootprint(floor));
        if (!footprints.length) return defaultFootprint();
        const minX = Math.min(...footprints.map(fp => fp.minX));
        const maxX = Math.max(...footprints.map(fp => fp.maxX));
        const minZ = Math.min(...footprints.map(fp => fp.minZ));
        const maxZ = Math.max(...footprints.map(fp => fp.maxZ));
        return {
            minX,
            maxX,
            minZ,
            maxZ,
            width: maxX - minX,
            depth: maxZ - minZ,
            centerX: (minX + maxX) / 2,
            centerZ: (minZ + maxZ) / 2,
        };
    }

    _floorShapeMesh(group, name, footprint, y, mat, userData) {
        const THREE = this.THREE;
        const shape = new THREE.Shape();
        footprint.outline.forEach((point, idx) => {
            if (idx === 0) shape.moveTo(point.x, point.z);
            else shape.lineTo(point.x, point.z);
        });
        shape.closePath();
        const mesh = new THREE.Mesh(
            new THREE.ShapeGeometry(shape),
            mat
        );
        mesh.name = name;
        mesh.rotation.x = Math.PI / 2;
        mesh.position.y = y;
        // floor shape must be visible from above: ShapeGeometry faces downward
        // after this rotation, while the camera usually looks from +Y.
        // Use the back face only to avoid transparent DoubleSide floor flicker:
        // Three.js renders transparent DoubleSide materials as two overlapping
        // passes, which is unstable for a flat floor surface.
        mesh.material.side = THREE.BackSide;
        // floor surface must not hide lower levels in overview, while focused
        // single-floor mode uses an opaque slab to avoid transparent alpha shimmer.
        mesh.material.transparent = mesh.material.opacity < 0.98;
        mesh.material.depthWrite = mesh.material.opacity >= 0.98;
        mesh.material.needsUpdate = true;
        mesh.renderOrder = FLOOR_SLAB_RENDER_ORDER;
        // transparent floor surfaces should not receive shadow-map stripes.
        mesh.receiveShadow = false;
        mesh.castShadow = false;
        if (userData) mesh.userData = userData;
        group.add(mesh);
        return mesh;
    }

    _floorOutline(group, name, footprint, y, color, opacity, userData) {
        const THREE = this.THREE;
        const points = footprint.outline.map(point => new THREE.Vector3(point.x, y, point.z));
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity,
            depthWrite: false,
        });
        // floor outline should mark footprint without a second transparent sheet.
        const line = new THREE.LineLoop(geometry, material);
        line.name = name;
        line.renderOrder = 2;
        if (userData) line.userData = userData;
        group.add(line);
        return line;
    }

    _flatFloorCue(group, name, center, size, color, userData) {
        const THREE = this.THREE;
        const [x, y, z] = center;
        const [width, depth] = size;
        const halfW = width / 2;
        const halfD = depth / 2;
        const points = [
            new THREE.Vector3(x - halfW, y, z - halfD),
            new THREE.Vector3(x + halfW, y, z - halfD),
            new THREE.Vector3(x + halfW, y, z + halfD),
            new THREE.Vector3(x - halfW, y, z + halfD),
        ];
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity: 0.46,
            depthWrite: false,
        });
        // first-floor utility cues should read as floor markings, not leftover blocks.
        const cue = new THREE.LineLoop(geometry, material);
        cue.name = name;
        cue.renderOrder = 4;
        if (userData) cue.userData = userData;
        group.add(cue);
        return cue;
    }

    _floorEdgeBands(group, footprint, y, color, userData) {
        const THREE = this.THREE;
        const material = this._photoMat(color, {
            opacity: FLOOR_EDGE_BAND_OPACITY,
            roughness: 0.68,
            metalness: 0.02,
        });

        footprint.outline.forEach((point, idx) => {
            const next = footprint.outline[(idx + 1) % footprint.outline.length];
            const dx = next.x - point.x;
            const dz = next.z - point.z;
            const length = Math.hypot(dx, dz);
            if (length < 1) return;

            const mesh = new THREE.Mesh(
                new THREE.BoxGeometry(length, FLOOR_EDGE_BAND_HEIGHT, FLOOR_EDGE_BAND_THICKNESS),
                material
            );
            mesh.name = 'furnitureDerivedFootprint floor edge band';
            mesh.position.set(
                (point.x + next.x) / 2,
                y - FLOOR_EDGE_BAND_HEIGHT / 2,
                (point.z + next.z) / 2
            );
            mesh.rotation.y = -Math.atan2(dz, dx);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            if (userData) mesh.userData = userData;
            group.add(mesh);
        });
    }

    _addOpenBuildingFrame(group, buildingFootprint, floors, floorHeight) {
        const baseYs = (floors || []).map(floor => floor.baseY || 0);
        const topY = baseYs.length ? Math.max(...baseYs) : 0;
        const fullHeight = topY + floorHeight + 4;
        const frameMat = this._photoMat(0x3f5358, {
            opacity: OPEN_BUILDING_FRAME_OPACITY,
            roughness: 0.62,
            metalness: 0.02,
        });
        const minX = buildingFootprint.minX - OPEN_BUILDING_DEPTH_PAD;
        const maxX = buildingFootprint.maxX + OPEN_BUILDING_DEPTH_PAD;
        const minZ = buildingFootprint.minZ - OPEN_BUILDING_DEPTH_PAD;
        const maxZ = buildingFootprint.maxZ + OPEN_BUILDING_DEPTH_PAD;
        const corners = [
            [minX, minZ],
            [maxX, minZ],
            [minX, maxZ],
            [maxX, maxZ],
        ];

        corners.forEach(([x, z]) => {
            this._box(
                group,
                'open axonometric building corner column',
                [4.2, fullHeight, 4.2],
                [x, fullHeight / 2 - 2, z],
                frameMat,
                { kind: 'buildingFrame' }
            );
        });

        (floors || []).forEach(floor => {
            const y = (floor.baseY || 0) + 27.6;
            this._box(
                group,
                'open axonometric rear floor beam',
                [buildingFootprint.width + OPEN_BUILDING_DEPTH_PAD * 2, 2.4, 3.0],
                [buildingFootprint.centerX, y, minZ],
                frameMat,
                { kind: 'buildingFrame', floorId: floor.floor_id }
            );
            [-1, 1].forEach(side => {
                const x = side < 0 ? minX : maxX;
                this._box(
                    group,
                    'open axonometric side depth beam',
                    [3.0, 2.4, buildingFootprint.depth + OPEN_BUILDING_DEPTH_PAD * 2],
                    [x, y, buildingFootprint.centerZ],
                    frameMat,
                    { kind: 'buildingFrame', floorId: floor.floor_id }
                );
            });
        });
    }

    _addOpenFloorFrame(group, footprint, baseY, floorId) {
        const frameMat = this._photoMat(0x273845, {
            opacity: OPEN_BUILDING_FRAME_OPACITY,
            roughness: 0.58,
            metalness: 0.02,
        });
        const shadowMat = this._photoMat(0x07111d, {
            opacity: INTERFLOOR_SHADOW_OPACITY,
            roughness: 0.76,
            metalness: 0.0,
        });
        const z = footprint.maxZ + 1.8;
        const cueData = { floorId, kind: 'floor' };

        [
            footprint.minX + 8,
            footprint.centerX,
            footprint.maxX - 8,
        ].forEach(x => {
            this._box(
                group,
                'open floor front vertical post',
                [3.0, 27.5, 3.0],
                [x, baseY + 14, z],
                frameMat,
                cueData
            );
        });

        this._box(
            group,
            'open floor front edge beam',
            [footprint.width + 5, 2.8, 3.0],
            [footprint.centerX, baseY + 28.4, z],
            frameMat,
            cueData
        );
        this._box(
            group,
            'open floor interlevel shadow band',
            [footprint.width + 4, INTERFLOOR_SHADOW_HEIGHT, 3.2],
            [footprint.centerX, baseY - INTERFLOOR_SHADOW_HEIGHT / 2 - 0.4, z],
            shadowMat,
            cueData
        );
    }

    _addWallDepthCues(group, footprint, baseY, floorId) {
        const wallCueData = { floorId, kind: 'floor' };
        const columnMat = this._photoMat(0x263541, {
            opacity: 0.74,
            roughness: 0.58,
            metalness: 0.02,
        });
        const beamMat = this._photoMat(0x4d5d61, {
            opacity: 0.66,
            roughness: 0.62,
            metalness: 0.02,
        });

        [
            [footprint.minX, footprint.minZ],
            [footprint.maxX, footprint.minZ],
            [footprint.minX, footprint.maxZ],
            [footprint.maxX, footprint.maxZ],
        ].forEach(([x, z]) => {
            this._box(
                group,
                'building corner column',
                [3.2, 27.5, 3.2],
                [x, baseY + 14, z],
                columnMat,
                wallCueData
            );
        });

        this._box(
            group,
            'wall top cap beam',
            [footprint.width + 2.4, 2.2, 2.8],
            [footprint.centerX, baseY + 27.8, footprint.minZ + 1.1],
            beamMat,
            wallCueData
        );
        [-1, 1].forEach(side => {
            const x = side < 0 ? footprint.minX : footprint.maxX;
            this._box(
                group,
                'wall top cap beam',
                [2.8, 2.2, footprint.depth + 2.4],
                [x, baseY + 27.8, footprint.centerZ],
                beamMat,
                wallCueData
            );
        });
        this._box(
            group,
            'front cutaway low sill shadow rail',
            [footprint.width, 1.8, 2.2],
            [footprint.centerX, baseY + 4.1, footprint.maxZ - 1.2],
            beamMat,
            wallCueData
        );
    }

    _addMenuBoard(group, text, pos, width = 34, height = 8, labelOptions = {}) {
        if (!labelOptions.alwaysReadableWindowLabel) {
            this._box(
                group,
                'muted photo menu board',
                [width, height, 1],
                pos,
                this._photoMat(photoWindowWall.menu, {
                    emissive: photoWindowWall.menu,
                    emissiveIntensity: 0.03,
                })
            );
        }
        const label = this._label(
            windowLabelLines(text),
            pos[0],
            pos[1] + 0.1,
            pos[2] + 1.2,
            '#fff7df',
            0.90,
            1,
            labelOptions
        );
        if (!labelOptions.alwaysReadableWindowLabel) {
            label.position.y += Math.max(2.2, height * 0.45);
        }
        label.scale.set(Math.min(WINDOW_LABEL_WORLD_WIDTH, width * 1.45), WINDOW_LABEL_WORLD_HEIGHT, 1);
        group.add(label);
    }

    _addCeilingPipes(group, baseY, footprint) {
        const THREE = this.THREE;
        const pipeMat = this._photoMat(0x6f8790, {
            opacity: 0.38,
            roughness: 0.72,
        });
        [Math.max(15, footprint.minZ + 18), Math.max(25, footprint.minZ + 30)].forEach((z, i) => {
            const pipe = new THREE.Mesh(
                new THREE.CylinderGeometry(0.34, 0.34, footprint.width - 56, 12),
                pipeMat
            );
            pipe.name = 'subtle ceiling rail';
            pipe.rotation.z = Math.PI / 2;
            pipe.position.set(footprint.centerX, baseY + 27.4 + i * 0.5, z);
            pipe.castShadow = true;
            group.add(pipe);
        });
    }

    _addPhotoReferenceShell(group, floor, baseY) {
        const footprint = this._floorFootprint(floor);
        this._floorOutline(
            group,
            'glossy pale tile floor outline',
            {
                ...footprint,
                outline: footprint.outline.map(point => ({
                    x: point.x + (point.x < footprint.centerX ? 5 : -5),
                    z: point.z + (point.z < footprint.centerZ ? 4 : -4),
                })),
            },
            baseY + 2.9,
            FLOOR_TILE_COLOR,
            FLOOR_TILE_OUTLINE_OPACITY
        );

        // Left-side black-framed window wall from the Minghu small-hall photo.
        const x = footprint.minX + 2.1;
        for (let i = 0; i < 6; i += 1) {
            const z = footprint.minZ + 8 + i * Math.min(12, footprint.depth / 20);
            this._box(group, 'photo window glass pane', [1, 16, 5.3],
                [x, baseY + 15.5, z],
                this._photoMat(photoWindowWall.glass, {
                    opacity: 0.30,
                    roughness: 0.08,
                    emissive: 0x5fb5c3,
                    emissiveIntensity: 0.04,
                })
            );
            this._box(group, 'photo window black frame vertical', [1.4, 18, 0.45],
                [x + 0.1, baseY + 15.6, z - 2.95],
                this._photoMat(photoWindowWall.frame, { roughness: 0.32 })
            );
            this._box(group, 'photo window black frame vertical', [1.4, 18, 0.45],
                [x + 0.1, baseY + 15.6, z + 2.95],
                this._photoMat(photoWindowWall.frame, { roughness: 0.32 })
            );
        }
        this._box(group, 'photo window sill bench', [3.2, 2.2, footprint.depth - 10],
            [x + 3.3, baseY + 7, footprint.centerZ],
            this._photoMat(0xe9ddd0, { roughness: 0.38 })
        );

        this._addCeilingPipes(group, baseY, footprint);
        // generic dark photo wall signs are omitted from the service-window sightline.
        // fixed background photo service wall is omitted from the service-window sightline.
    }

    _entranceMarkersForFootprint(footprint) {
        const lower = Math.max(24, Math.round(footprint.depth * 0.30));
        const upper = Math.min(footprint.maxZ - 24, Math.round(footprint.depth * 0.70));
        return SIDE_ENTRANCE_MARKERS.map((entrance, idx) => ({
            ...entrance,
            z: idx === 0 ? lower : Math.max(lower + 24, upper),
        }));
    }

    _addEntranceMarker(group, floorId, baseY, footprint) {
        this._entranceMarkersForFootprint(footprint).forEach(entrance => {
            const markerName = entrance.name;
            const entranceX = Math.min(SIDE_ENTRANCE_X, footprint.minX + SIDE_ENTRANCE_X);
            const doorX = entranceX + 9.2;
            // side entrance, clear of front sightline: 门面贴左侧墙，避免挡住俯视聚焦视线。
            this._box(
                group,
                `${markerName} student spawn entrance marker`,
                [4.4, 1.0, ENTRANCE_MARKER_DEPTH],
                [entranceX + 3.0, baseY + 3.5, entrance.z],
                this._photoMat(PALETTE.flow, {
                    opacity: 0.82,
                    emissive: PALETTE.flow,
                    emissiveIntensity: 0.10,
                }),
                { floorId, kind: 'floor' }
            );
            this._box(
                group,
                `${markerName} entranceDoorFrame`,
                [1.8, ENTRANCE_DOOR_HEIGHT, ENTRANCE_DOOR_DEPTH],
                [doorX, baseY + 10.9, entrance.z],
                this._photoMat(0x17202b, { opacity: 0.78, roughness: 0.26 }),
                { floorId, kind: 'floor' }
            );
            this._box(
                group,
                `${markerName} entranceGlassPanel`,
                [1.0, ENTRANCE_GLASS_HEIGHT, ENTRANCE_GLASS_DEPTH],
                [doorX - 0.4, baseY + 10.2, entrance.z],
                this._photoMat(0xcfe9ee, {
                    opacity: 0.42,
                    roughness: 0.08,
                    emissive: 0x5fb5c3,
                    emissiveIntensity: 0.06,
                }),
                { floorId, kind: 'floor' }
            );
            this._box(
                group,
                `${markerName} entranceCanopy`,
                [10.5, 2.4, ENTRANCE_CANOPY_DEPTH],
                [entranceX + 5.0, baseY + 18.2, entrance.z],
                this._photoMat(0x33404a, {
                    opacity: 0.88,
                    roughness: 0.30,
                    emissive: 0x20364a,
                    emissiveIntensity: 0.08,
                }),
                { floorId, kind: 'floor' }
            );
        });
    }

    _addElevatorCore(group, floors, topY, floorHeight, buildingFootprint) {
        const shaftX = buildingFootprint.minX + SIDE_ENTRANCE_X - 3.5;
        const shaftZ = buildingFootprint.centerZ;
        const shaftHeight = topY + floorHeight + 8;
        const activeFloor = this.mode === 'focus' && this.focusFloorId != null
            ? floors.find(floor => floor.floor_id === this.focusFloorId)
            : floors[0];
        const carY = (activeFloor?.baseY || 0) + 13;

        this._box(
            group,
            'elevator glass shaft',
            [15, shaftHeight, 20],
            [shaftX, shaftHeight / 2 - 3, shaftZ],
            this._photoMat(0x9fe8ef, {
                opacity: 0.28,
                roughness: 0.06,
                emissive: 0x52d6d1,
                emissiveIntensity: 0.08,
            }),
            { kind: 'stairCore' }
        );

        [-8, 8].forEach(dx => {
            [-10, 10].forEach(dz => {
                this._box(
                    group,
                    'elevator dark vertical frame',
                    [1.4, shaftHeight + 1, 1.4],
                    [shaftX + dx, shaftHeight / 2 - 3, shaftZ + dz],
                    this._photoMat(0x182232, { roughness: 0.34 }),
                    { kind: 'stairCore' }
                );
            });
        });

        this._box(
            group,
            'elevator car',
            [10.5, 15, 14],
            [shaftX, carY, shaftZ],
            this._photoMat(0xe9f8f8, {
                opacity: 0.86,
                roughness: 0.18,
                emissive: 0x52d6d1,
                emissiveIntensity: 0.06,
            }),
            { kind: 'stairCore' }
        );

        floors.forEach(floor => {
            const baseY = floor.baseY || 0;
            this._box(
                group,
                'elevator landing bridge',
                [24, 1.8, 15],
                [shaftX + 12, baseY + 5.3, shaftZ],
                this._photoMat(0x33404a, {
                    opacity: 0.92,
                    roughness: 0.32,
                    emissive: 0x20364a,
                    emissiveIntensity: 0.04,
                }),
                { floorId: floor.floor_id, kind: 'floor' }
            );
            this._box(
                group,
                'elevator floor door',
                [1.2, 12, 12],
                [shaftX + 8.4, baseY + 11.5, shaftZ],
                this._photoMat(0xcfe9ee, {
                    opacity: 0.62,
                    roughness: 0.12,
                    emissive: 0x5fb5c3,
                    emissiveIntensity: 0.07,
                }),
                { floorId: floor.floor_id, kind: 'floor' }
            );
        });

        for (let i = 0; i < floors.length - 1; i += 1) {
            const lower = floors[i].baseY || 0;
            const upper = floors[i + 1].baseY || 0;
            const span = Math.max(1, upper - lower);
            for (let step = 0; step < 8; step += 1) {
                const t = step / 7;
                this._box(
                    group,
                    'stair step stack',
                    [13, 1.0, 4.2],
                    [
                        shaftX + 22,
                        lower + 13 + t * (span - 6),
                        shaftZ - 17 + t * 34,
                    ],
                    this._photoMat(0xd7e0dc, { roughness: 0.42 }),
                    { kind: 'stairCore' }
                );
            }
            this._box(
                group,
                'stair handrail',
                [1.2, span - 8, 1.2],
                [shaftX + 30, lower + span / 2 + 8, shaftZ],
            this._photoMat(PALETTE.flow, {
                opacity: 0.8,
                roughness: 0.28,
                emissive: PALETTE.flow,
                emissiveIntensity: 0.10,
            }),
                { kind: 'stairCore' }
            );
        }

        const label = this._label('电梯 / 楼梯', shaftX + 4, topY + floorHeight + 18, shaftZ,
            PALETTE.labelKpi, 0.92, 0.52);
        group.add(label);
    }

    _windowLabel(win, floorId, localIndex) {
        const labels = MINGHU_WINDOW_LABELS[floorId] || [];
        if (labels.length) return labels[localIndex % labels.length];
        return `窗口 ${win.id}`;
    }

    _shouldShowWindowLabel(floor, win, localIndex) {
        if (this.mode !== 'focus' || this.focusFloorId !== floor.floor_id) return false;
        if ((floor.windows || []).length <= 8) return true;
        if (win.is_serving || win.closing) return true;
        return localIndex % WINDOW_LABEL_DENSITY_STEP === 0;
    }

    _interventionEventKey(event) {
        if (event?.event_id != null) return `event:${event.event_id}`;
        return [
            event?.time,
            event?.canteen_id,
            event?.floor_id,
            event?.window_id,
            event?.action,
            event?.status,
            event?.reason,
        ].join('|');
    }

    _windowEffectKey(floorId, windowId) {
        return `${floorId}#${windowId}`;
    }

    _syncWindowInterventionEffects(frame) {
        const events = Array.isArray(frame?.interventions)
            ? frame.interventions
            : [];
        if (!this._hasInterventionBaseline) {
            events.forEach(event => this._seenInterventionKeys.add(
                this._interventionEventKey(event)
            ));
            this._hasInterventionBaseline = true;
            return;
        }
        events.forEach(event => {
            const eventKey = this._interventionEventKey(event);
            if (this._seenInterventionKeys.has(eventKey)) return;
            this._seenInterventionKeys.add(eventKey);
            if (event.status === 'rejected') return;
            if (!(event.action === 'add' || event.action === 'open')) return;
            if (event.floor_id == null || event.window_id == null) return;
            const effectKey = this._windowEffectKey(event.floor_id, event.window_id);
            this._windowInterventionEffects.set(effectKey, {
                action: event.action,
                eventKey,
                effectKey,
                startedAt: this._now(),
            });
        });
    }

    _activeWindowInterventionEffect(win, floorId) {
        const effectKey = this._windowEffectKey(floorId, win.id);
        const effect = this._windowInterventionEffects.get(effectKey);
        if (!effect) return null;
        const elapsed = this._now() - effect.startedAt;
        if (elapsed >= WINDOW_INTERVENTION_EFFECT_MS) {
            this._windowInterventionEffects.delete(effectKey);
            return null;
        }
        return {
            ...effect,
            elapsed,
            progress: Math.max(0, Math.min(1, elapsed / WINDOW_INTERVENTION_EFFECT_MS)),
        };
    }

    _tagWindowInterventionBody(mesh, effect) {
        if (!mesh || !effect) return;
        mesh.userData = {
            ...mesh.userData,
            windowInterventionBody: true,
            effectKey: effect.effectKey,
            baseY: mesh.position.y,
            baseScaleX: mesh.scale.x,
            baseScaleY: mesh.scale.y,
            baseScaleZ: mesh.scale.z,
            baseEmissiveIntensity: mesh.material?.emissiveIntensity || 0,
        };
        if (mesh.material?.emissive) {
            mesh.material.emissive.setHex(WINDOW_INTERVENTION_PULSE_COLOR);
        }
    }

    _addWindowInterventionPulse(group, x, y, z, layoutSide, effect) {
        if (!effect) return;
        const THREE = this.THREE;
        const pulseMat = this._photoMat(WINDOW_INTERVENTION_PULSE_COLOR, {
            opacity: 0.58,
            roughness: 0.24,
            emissive: WINDOW_INTERVENTION_PULSE_COLOR,
            emissiveIntensity: 0.38,
        });
        pulseMat.depthWrite = false;
        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(layoutSide === 'left' ? 10 : 12, 0.65, 8, 44),
            pulseMat
        );
        ring.name = 'window intervention pulse ring';
        ring.rotation.x = Math.PI / 2;
        ring.position.set(x, y + 12.4, z);
        ring.renderOrder = 86;
        ring.userData = {
            windowInterventionPulse: true,
            effectKey: effect.effectKey,
            pulseKind: 'ring',
            baseY: ring.position.y,
            baseOpacity: pulseMat.opacity,
            baseEmissiveIntensity: pulseMat.emissiveIntensity,
        };
        group.add(ring);

        const pillar = this._box(
            group,
            'window intervention pulse pillar',
            layoutSide === 'left' ? [2.0, 16, 12] : [14, 16, 2.0],
            [x, y + 4.2, z],
            this._photoMat(WINDOW_INTERVENTION_PULSE_COLOR, {
                opacity: 0.18,
                roughness: 0.34,
                emissive: WINDOW_INTERVENTION_PULSE_COLOR,
                emissiveIntensity: 0.24,
            }),
            {
                windowInterventionPulse: true,
                effectKey: effect.effectKey,
                pulseKind: 'pillar',
            }
        );
        pillar.material.depthWrite = false;
        pillar.renderOrder = 85;
        pillar.userData.baseY = pillar.position.y;
        pillar.userData.baseOpacity = pillar.material.opacity;
        pillar.userData.baseEmissiveIntensity = pillar.material.emissiveIntensity;
    }

    _animateWindowInterventions() {
        const now = this._now();
        this._windowInterventionEffects.forEach((effect, key) => {
            if (now - effect.startedAt >= WINDOW_INTERVENTION_EFFECT_MS) {
                this._windowInterventionEffects.delete(key);
            }
        });
        this.group.traverse(node => {
            const data = node.userData || {};
            const effect = data.effectKey
                ? this._windowInterventionEffects.get(data.effectKey)
                : null;
            if (data.windowInterventionPulse) {
                if (!effect) {
                    node.visible = false;
                    return;
                }
                const t = Math.max(0, Math.min(1, (now - effect.startedAt) / WINDOW_INTERVENTION_EFFECT_MS));
                const ease = Math.sin(Math.PI * t);
                const spread = data.pulseKind === 'ring' ? 0.65 + t * 1.95 : 1 + ease * 0.26;
                node.visible = true;
                node.scale.setScalar(spread);
                node.position.y = data.baseY + ease * 3.6;
                if (node.material) {
                    node.material.opacity = (data.baseOpacity ?? 0.5) * (1 - t);
                    node.material.emissiveIntensity = (data.baseEmissiveIntensity ?? 0.24) * (1 - t);
                }
            }
            if (data.windowInterventionBody) {
                if (!effect) {
                    node.position.y = data.baseY;
                    node.scale.set(data.baseScaleX, data.baseScaleY, data.baseScaleZ);
                    if (node.material) {
                        node.material.emissiveIntensity = data.baseEmissiveIntensity || 0;
                    }
                    return;
                }
                const t = Math.max(0, Math.min(1, (now - effect.startedAt) / WINDOW_INTERVENTION_EFFECT_MS));
                const ease = Math.sin(Math.PI * t);
                node.position.y = data.baseY + ease * 3.2;
                node.scale.set(
                    data.baseScaleX * (1 + ease * 0.07),
                    data.baseScaleY * (1 + ease * 0.12),
                    data.baseScaleZ * (1 + ease * 0.07)
                );
                if (node.material) {
                    node.material.emissiveIntensity = (data.baseEmissiveIntensity || 0) + ease * 0.42;
                }
            }
        });
    }

    _addServiceStall(group, win, floorId, localIndex, showWindowLabel) {
        const x = win.position.x;
        const y = win.position.y;
        const z = win.position.z;
        const layoutSide = win.position.side || 'front';
        const interventionEffect = this._activeWindowInterventionEffect(win, floorId);
        let winColor = PALETTE.windowIdle;
        if (win.is_open) {
            winColor = win.is_serving ? PALETTE.windowOpen : 0x2dd4bf;
        } else {
            winColor = win.closing ? PALETTE.windowClosing : PALETTE.windowClosedEmpty;
        }

        if (layoutSide === 'left') {
            const body = this._box(
                group,
                'sideWall service counter window',
                [12, 8, 18],
                [x, y - 3.4, z],
                this._photoMat(win.is_open ? 0xd8e2df : 0x5c6874, {
                    opacity: win.is_open ? 0.95 : 0.74,
                    roughness: 0.34,
                }),
                { floorId, kind: 'window', windowId: win.id }
            );
            this._tagWindowInterventionBody(body, interventionEffect);
            body.userData.photoCue = 'side counter';
            this._box(group, 'sideWall glass food guard', [1, 7, 16.5],
                [x + 5.7, y + 2.2, z],
                this._photoMat(0xcceaf1, { opacity: 0.36, roughness: 0.08 })
            );
            this._box(group, 'sideWall red stall menu fascia', [1.2, 6, 18],
                [x - 5.9, y + 8.3, z],
                this._photoMat(winColor, {
                    opacity: win.is_open ? 0.98 : 0.64,
                    emissive: winColor,
                    emissiveIntensity: win.is_open ? 0.04 : 0.01,
                })
            );
            if (showWindowLabel) {
                const labelZOffset = localIndex % 2 === 0 ? -5.4 : 5.4;
                const sideLabel = this._label(
                    windowLabelLines(this._windowLabel(win, floorId, localIndex)),
                    x + 10.0,
                    // top-view labels must float above service counters.
                    y + 16.8 + (localIndex % 3) * 1.3,
                    z + labelZOffset,
                    '#fff7df',
                    0.82,
                    0.44,
                    {
                        alwaysReadableWindowLabel: true,
                        renderOrder: WINDOW_LABEL_RENDER_ORDER + localIndex,
                    }
                );
                sideLabel.scale.set(WINDOW_LABEL_WORLD_WIDTH * 0.82, WINDOW_LABEL_WORLD_HEIGHT * 0.90, 1);
                group.add(sideLabel);
            }

            const sat = Math.min(1, (win.queue_length || 0) / 12);
            if (win.is_open && sat > 0) {
                const hc2 = heatColor(this.THREE, sat);
                this._box(group, 'queue heat cap', [12, 2.4, 18],
                    [x, y + 12.6, z],
                    this._photoMat(hc2.getHex(), {
                        opacity: 0.66,
                        roughness: 0.70,
                    })
                );
            }
            if (!win.is_open && win.closing) {
                group.add(this._label('关闭中', x + 8, y + 18, z, '#e7bd63', 1, 0.70));
            }
            this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);
            return;
        }

        const body = this._box(
            group,
            'photo service counter window',
            FRONT_WINDOW_COUNTER_SIZE,
            // front service counters are visible but light, not the dark residual under window labels.
            [x, y + 2.7, z],
            this._photoMat(win.is_open ? 0xd8e2df : 0x5c6874, {
                opacity: win.is_open ? 0.82 : 0.42,
                roughness: 0.40,
            }),
            { floorId, kind: 'window', windowId: win.id }
        );
        this._tagWindowInterventionBody(body, interventionEffect);
        body.userData.photoCue = 'counter';
        body.castShadow = false;
        body.receiveShadow = false;

        // Spec §A: additive 4-part themed stall layered on top of the retained
        // window meshes (signboard / open-kitchen glass / base counter / tray
        // rail + status strip). Material + color temperature only, emissive ≈ 0.
        const th = stallTheme(floorId);
        this._box(group, 'stall base counter',
            [FRONT_WINDOW_COUNTER_SIZE[0] + 1.2, 1.4, FRONT_WINDOW_COUNTER_SIZE[2] + 1.0],
            [x, y - 0.1, z],
            this._photoMat(th.counter, {
                opacity: win.is_open ? 0.92 : 0.7,
                roughness: th.roughness,
                emissive: th.counter,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );
        this._box(group, 'stall open-kitchen glass',
            [FRONT_WINDOW_COUNTER_SIZE[0] - 0.6, 2.0, 0.5],
            [x, y + 5.6, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 0.55],
            this._photoMat(th.glass, {
                opacity: 0.34,
                roughness: th.roughness,
                emissive: th.glass,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );
        this._box(group, 'stall tray rail',
            [FRONT_WINDOW_COUNTER_SIZE[0] - 1.0, 0.5, 0.6],
            [x, y + 1.0, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 1.05],
            this._photoMat(th.rail, {
                opacity: win.is_open ? 0.9 : 0.66,
                roughness: th.roughness,
                emissive: th.rail,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );

        this._box(group, 'glass food guard', FRONT_WINDOW_GLASS_GUARD_SIZE,
            [x, y + 5.6, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 0.2],
            this._photoMat(0xcceaf1, { opacity: 0.36, roughness: 0.08 })
        );
        const frontStatusRailColor = win.is_open
            ? (win.is_serving ? FRONT_WINDOW_STATUS_RAIL_SERVING_COLOR : FRONT_WINDOW_STATUS_RAIL_IDLE_COLOR)
            : winColor;
        this._box(group, 'front service status rail', FRONT_WINDOW_STATUS_RAIL_SIZE,
            // front window status cue should stay thin, not become a dark block under menu labels.
            [x, y + 6.2, z - FRONT_WINDOW_COUNTER_SIZE[2] / 2 - 0.25],
            this._photoMat(frontStatusRailColor, {
                opacity: win.is_open ? 0.62 : 0.36,
                emissive: frontStatusRailColor,
                emissiveIntensity: win.is_serving ? 0.035 : 0.015,
            })
        );
        // Additional thin status strip beside the retained rail, same open/serving/closed logic.
        this._box(group, 'stall status strip',
            [FRONT_WINDOW_STATUS_RAIL_SIZE[0] + 4, 0.5, 0.5],
            [x, y + 7.0, z - FRONT_WINDOW_COUNTER_SIZE[2] / 2 - 0.55],
            this._photoMat(frontStatusRailColor, {
                opacity: win.is_open ? 0.5 : 0.32,
                roughness: th.roughness,
                emissive: frontStatusRailColor,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );
        if (win.is_open && win.is_serving) {
            this._box(group, 'front service serving status light', FRONT_WINDOW_SERVING_LIGHT_SIZE,
                [x, y + 7.2, z - FRONT_WINDOW_COUNTER_SIZE[2] / 2 - 0.7],
                this._photoMat(FRONT_WINDOW_SERVING_LIGHT_COLOR, {
                    opacity: 0.78,
                    emissive: FRONT_WINDOW_SERVING_LIGHT_COLOR,
                    emissiveIntensity: 0.08,
                })
            );
        }
        if (showWindowLabel) {
            // Thin themed signboard band at label height; the retained menu
            // board/label renders just in front of it (slightly larger +z).
            this._box(group, 'stall signboard band',
                [FRONT_WINDOW_MENU_BOARD_WIDTH + 1.5, FRONT_WINDOW_MENU_BOARD_HEIGHT + 1.2, 0.5],
                [
                    x + FRONT_WINDOW_LABEL_X_OFFSET,
                    y + FRONT_WINDOW_LABEL_Y_OFFSET,
                    z + FRONT_WINDOW_LABEL_Z_OFFSET - 0.7,
                ],
                this._photoMat(th.sign, {
                    opacity: win.is_open ? 0.94 : 0.72,
                    roughness: th.roughness,
                    emissive: th.sign,
                    emissiveIntensity: win.is_serving ? 0.03 : 0.012,
                })
            );
            this._addMenuBoard(
                group,
                this._windowLabel(win, floorId, localIndex),
                [
                    x + FRONT_WINDOW_LABEL_X_OFFSET,
                    // top-view labels must float above service counters.
                    y + FRONT_WINDOW_LABEL_Y_OFFSET,
                    z + FRONT_WINDOW_LABEL_Z_OFFSET,
                ],
                FRONT_WINDOW_MENU_BOARD_WIDTH,
                FRONT_WINDOW_MENU_BOARD_HEIGHT,
                {
                    alwaysReadableWindowLabel: true,
                    renderOrder: WINDOW_LABEL_RENDER_ORDER + localIndex,
                }
            );
        }

        const sat = Math.min(1, (win.queue_length || 0) / 12);
        if (win.is_open && sat > 0) {
            const frontQueueHeatColor = sat > 0.68
                ? FRONT_WINDOW_QUEUE_HEAT_BUSY_COLOR
                : FRONT_WINDOW_QUEUE_HEAT_CLEAR_COLOR;
            this._box(group, 'front service queue heat strip', FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE,
                [x, y + 5.4, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 0.8],
                this._photoMat(frontQueueHeatColor, {
                    opacity: FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY,
                    roughness: 0.70,
                })
            );
        }
        if (!win.is_open && win.closing) {
            group.add(this._label('关闭中', x, y + 18, z, '#e7bd63'));
        }
        this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);
    }

    _chairVariant(side, idx) {
        if (side === 'bench') return 'bench';
        if (idx % 6 === 2) return 'round-stool';
        if (idx % 4 === 1) return 'open-back';
        return 'standard';
    }

    _addChair(group, x, y, z, color, side, occupied, idx = 0) {
        const chairVariant = this._chairVariant(side, idx);
        const mat = this._photoMat(color, {
            roughness: 0.48,
            emissive: occupied ? color : 0x000000,
            emissiveIntensity: occupied ? 0.04 : 0,
        });
        const seatSize = chairVariant === 'round-stool' ? [3.7, 1.7, 3.7] : [4.1, 1.8, 3.9];
        this._box(group, `mixed photo ${chairVariant} chair seat`, seatSize,
            [x, y, z], mat);
        if (chairVariant === 'round-stool') return;
        const backOffset = 2.55;
        const isX = side === 'left' || side === 'right';
        const bx = x + (side === 'left' ? -backOffset : side === 'right' ? backOffset : 0);
        const bz = z + (side === 'front' ? backOffset : side === 'back' ? -backOffset : 0);
        const backHeight = chairVariant === 'open-back' ? 4.1 : 5.3;
        this._box(group, `mixed photo ${chairVariant} chair back`,
            isX ? [1.1, backHeight, 4.2] : [4.2, backHeight, 1.1],
            [bx, y + 2.8, bz],
            mat);
    }

    _chairOccupancyMarker(group, x, y, z) {
        const chairOccupancyMarker = new this.THREE.Mesh(
            new this.THREE.CylinderGeometry(2.2, 2.2, 0.65, 18),
            this._photoMat(PALETTE.seatOccupied, {
                emissive: PALETTE.seatOccupied,
                emissiveIntensity: 0.10,
            })
        );
        chairOccupancyMarker.name = 'chairOccupancyMarker';
        chairOccupancyMarker.position.set(x - 3.8, y, z + 1.8);
        group.add(chairOccupancyMarker);
    }

    _floorLayoutProfile(floorId) {
        return MINGHU_FLOOR_LAYOUTS[floorId] || MINGHU_FLOOR_LAYOUTS[1];
    }

    _tablePositionForProfile(idx, tableCount, profile, footprint) {
        return tableZonePosition(idx, tableCount, profile, footprint);
    }

    _tableVariantForProfile(profile, idx) {
        const { block } = tableBlockForIndex(idx, profile);
        if (block?.type) return block.type;
        const variants = profile.tableVariants || ['square'];
        return variants[idx % variants.length] || 'square';
    }

    _tableColorForProfile(profile, idx, variant) {
        const { block } = tableBlockForIndex(idx, profile);
        return block?.tableColor || FLOOR_TABLE_COLOR_FALLBACKS[variant] || FLOOR_TABLE_COLOR_FALLBACKS.square;
    }

    _addSquareTableCluster(group, x, baseY, z, idx, occupied, tableColor) {
        const woodTableTop = this._box(
            group,
            'woodTableTop square four-seat table',
            [17.5, 1.8, 7.5],
            [x, baseY + 6.6, z],
            this._photoMat(tableColor || FLOOR_TABLE_COLOR_FALLBACKS.square, {
                roughness: 0.32,
                emissive: occupied ? 0xe7bd63 : 0x000000,
                emissiveIntensity: occupied ? 0.05 : 0,
            })
        );
        void woodTableTop;
        if (occupied) this._chairOccupancyMarker(group, x, baseY + 8.05, z);
        this._box(group, 'dark table pedestal', [2.0, 4.6, 2.0],
            [x, baseY + 4.0, z],
            this._photoMat(0x33404a, { roughness: 0.44 })
        );

        const colors = mixedChairPalette;
        this._addChair(group, x - CHAIR_DX, baseY + 5.1, z, colors[idx % colors.length], 'left', occupied, idx);
        this._addChair(group, x + CHAIR_DX, baseY + 5.1, z, colors[(idx + 1) % colors.length], 'right', occupied, idx + 1);
        this._addChair(group, x, baseY + 5.1, z + CHAIR_DZ, colors[(idx + 2) % colors.length], 'front', occupied, idx + 2);
        this._addChair(group, x, baseY + 5.1, z - CHAIR_DZ, colors[(idx + 3) % colors.length], 'back', occupied, idx + 3);
    }

    _addLongTableCluster(group, x, baseY, z, idx, occupied, tableColor) {
        this._box(group, 'woodTableTop long communal table', [31, 1.8, 8.5],
            [x, baseY + 6.6, z],
            this._photoMat(tableColor || FLOOR_TABLE_COLOR_FALLBACKS.long, {
                roughness: 0.34,
                emissive: occupied ? 0xe7bd63 : 0x000000,
                emissiveIntensity: occupied ? 0.05 : 0,
            })
        );
        if (occupied) this._chairOccupancyMarker(group, x, baseY + 8.05, z);
        [-8, 8].forEach(offset => {
            this._box(group, 'dark communal table pedestal', [1.8, 4.4, 1.8],
                [x + offset, baseY + 4.0, z],
                this._photoMat(0x33404a, { roughness: 0.44 })
            );
        });

        const colors = mixedChairPalette;
        [-12, 0, 12].forEach((offset, chairIdx) => {
            this._addChair(group, x + offset, baseY + 5.1, z + CHAIR_DZ,
                colors[(idx + chairIdx) % colors.length], 'front', occupied, idx + chairIdx);
            this._addChair(group, x + offset, baseY + 5.1, z - CHAIR_DZ,
                colors[(idx + chairIdx + 2) % colors.length], 'back', occupied, idx + chairIdx + 3);
        });
    }

    _addBoothTableCluster(group, x, baseY, z, idx, occupied, tableColor) {
        this._box(group, 'woodTableTop booth table', [20, 1.6, 6.5],
            [x, baseY + 6.4, z],
            this._photoMat(tableColor || FLOOR_TABLE_COLOR_FALLBACKS.booth, {
                roughness: 0.34,
                emissive: occupied ? 0xe7bd63 : 0x000000,
                emissiveIntensity: occupied ? 0.05 : 0,
            })
        );
        if (occupied) this._chairOccupancyMarker(group, x, baseY + 8.05, z);
        this._box(group, 'booth bench seat', [24, 4.2, 3.2],
            [x, baseY + 5.2, z + 8.4],
            this._photoMat(0x6b4f39, { roughness: 0.34 })
        );
        this._box(group, 'booth bench seat', [24, 4.2, 3.2],
            [x, baseY + 5.2, z - 8.4],
            this._photoMat(0x6b4f39, { roughness: 0.34 })
        );

        const colors = mixedChairPalette;
        this._addChair(group, x - CHAIR_DX, baseY + 5.1, z, colors[idx % colors.length], 'left', occupied, idx);
        this._addChair(group, x + CHAIR_DX, baseY + 5.1, z, colors[(idx + 1) % colors.length], 'right', occupied, idx + 1);
    }

    _addFloorIdentityCues(group, floor, baseY) {
        const profile = this._floorLayoutProfile(floor.floor_id);
        const footprint = this._floorFootprint(floor);
        const serviceMaxZ = serviceWindowMaxZ(profile);
        const tableStartZ = tableZoneStartZ(profile);
        if (profile.key === 'basicMealWideAisle') {
            this._box(group, 'f1-snake-queue-guide', [footprint.width - 78, 0.9, 22],
                [footprint.centerX, baseY + 3.9, serviceMaxZ + 28],
                this._photoMat(0x84cc16, { opacity: 0.32, roughness: 0.30 })
            );
            this._box(group, 'f1-pickup-return-lane', [footprint.width - 86, 0.8, 12],
                [footprint.centerX, baseY + 3.8, tableStartZ - 18],
                this._photoMat(0xe7bd63, { opacity: 0.34, roughness: 0.28 })
            );
            this._box(group, 'f1-main-aisle-cue', [18, 0.8, Math.max(58, footprint.maxZ - tableStartZ - 20)],
                [footprint.centerX + 16, baseY + 3.75, tableStartZ + 44],
                this._photoMat(0x93c5fd, { opacity: 0.28, roughness: 0.30 })
            );
            this._flatFloorCue(
                group,
                'f1-condiment-station flat floor cue',
                [footprint.minX + 74, baseY + 4.05, tableStartZ - 22],
                [28, 9],
                0xa9b68f,
                { floorId: floor.floor_id, kind: 'floorCue' }
            );
            this._flatFloorCue(
                group,
                'f1-tray-return-point flat floor cue',
                [footprint.maxX - 74, baseY + 4.05, tableStartZ - 22],
                [32, 10],
                0xb8ad82,
                { floorId: floor.floor_id, kind: 'floorCue' }
            );
            return;
        }
        if (profile.key === 'featureFoodCourt') {
            this._box(group, 'featureFoodCourt coffee island', [22, 5.0, 13],
                [48, baseY + 6.8, serviceMaxZ + 34],
                this._photoMat(0x4d3a32, {
                    roughness: 0.34,
                    emissive: 0x261a13,
                    emissiveIntensity: 0.06,
                })
            );
            this._box(group, 'featureFoodCourt hotpot zone', [78, 0.9, 16],
                [236, baseY + 3.8, tableStartZ + 4],
                this._photoMat(0x7f1d1d, {
                    opacity: 0.36,
                    emissive: 0x7f1d1d,
                    emissiveIntensity: 0.08,
                })
            );
            return;
        }
        this._box(group, 'restaurantDiningRoom booth seating', [96, 5.8, 7.5],
            [87, baseY + 6.8, tableStartZ + 10],
            this._photoMat(0x6b4f39, { roughness: 0.32 })
        );
        this._box(group, 'restaurantDiningRoom service aisle', [18, 0.7, 34],
            [286, baseY + 3.7, serviceMaxZ + 24],
            this._photoMat(0xefe9dc, { opacity: 0.32, roughness: 0.28 })
        );
    }

    _addPhotoTableClusters(group, floor) {
        const seats = floor.seats || [];
        const baseY = floor.baseY;
        const profile = this._floorLayoutProfile(floor.floor_id);
        const footprint = this._floorFootprint(floor);
        const visibleTableCount = visibleTableCountForProfile(seats, profile);
        const seatGroups = Array.from({ length: visibleTableCount }, () => []);
        seats.forEach((seat, seatIdx) => {
            const tableIdx = visualTableIndexForSeat(seatIdx, visibleTableCount);
            seatGroups[tableIdx].push(seat);
        });
        for (let idx = 0; idx < visibleTableCount; idx += 1) {
            const { x, z } = this._tablePositionForProfile(idx, visibleTableCount, profile, footprint);
            const seatSlice = seatGroups[idx] || [];
            const occupied = seatSlice.some(seat => seat.status === 'occupied');
            const variant = this._tableVariantForProfile(profile, idx);
            const tableColor = this._tableColorForProfile(profile, idx, variant);
            if (variant === 'long') {
                this._addLongTableCluster(group, x, baseY, z, idx, occupied, tableColor);
            } else if (variant === 'booth') {
                this._addBoothTableCluster(group, x, baseY, z, idx, occupied, tableColor);
            } else {
                this._addSquareTableCluster(group, x, baseY, z, idx, occupied, tableColor);
            }

        }
    }

    _studentAvatar(student, floorId) {
        const THREE = this.THREE;
        const p = student.position3d || student.target;
        const avatar = new THREE.Group();
        avatar.name = 'studentAvatar';
        avatar.position.set(p.x, p.y, p.z);
        avatar.userData = { floorId, kind: 'student', studentId: student.id };

        const isTracked = this.trackedStudentId != null
            && String(student.id) === this.trackedStudentId;
        const clothingColor = stableStudentClothingColor(student);
        const statusColor = studentStatusColor(student);
        const bodyHeight = student.position === 'seated' ? 3.8 : 5.8;

        const studentBody = new THREE.Mesh(
            new THREE.CapsuleGeometry(1.6, bodyHeight, 4, 10),
            new THREE.MeshStandardMaterial({
                color: clothingColor,
                emissive: isTracked ? PALETTE.flow : clothingColor,
                emissiveIntensity: isTracked ? 0.14 : 0.03,
                roughness: 0.45,
            })
        );
        studentBody.name = 'studentBody';
        studentBody.position.set(0, bodyHeight / 2, 0);
        studentBody.userData = avatar.userData;
        avatar.add(studentBody);

        const studentHead = new THREE.Mesh(
            new THREE.SphereGeometry(1.55, 12, 8),
            new THREE.MeshStandardMaterial({
                color: 0xffd6a5,
                roughness: 0.52,
            })
        );
        studentHead.name = 'studentHead';
        studentHead.position.set(0, bodyHeight + 2.2, 0);
        studentHead.userData = avatar.userData;
        avatar.add(studentHead);

        const studentStatusRing = new THREE.Mesh(
            new THREE.TorusGeometry(2.65, 0.22, 8, 24),
            new THREE.MeshStandardMaterial({
                color: statusColor,
                emissive: statusColor,
                emissiveIntensity: 0.08,
                roughness: 0.38,
            })
        );
        studentStatusRing.name = 'studentStatusRing';
        studentStatusRing.rotation.x = Math.PI / 2;
        studentStatusRing.position.y = 0.35;
        avatar.add(studentStatusRing);

        if (isTracked) {
            const ring = new THREE.Mesh(
                new THREE.TorusGeometry(3.3, 0.35, 8, 28),
                new THREE.MeshStandardMaterial({
                    color: PALETTE.flow,
                    emissive: PALETTE.flow,
                    emissiveIntensity: 0.14,
                })
            );
            ring.name = 'tracked student halo';
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 0.5;
            avatar.add(ring);
        }
        return avatar;
    }

    _rebuild(frame) {
        const THREE = this.THREE;
        this._clear();
        if (!frame) return;

        // 竖向跨度从 frame 实际 baseY 推导（与 state_adapter 堆叠一致，不再各自假设步长）
        const baseYs = frame.floors.map(f => f.baseY || 0);
        const topY = baseYs.length ? Math.max(...baseYs) : 0;
        const FLOOR_H = 30;                 // 单层可视高度（楼板+墙）
        this._topY = topY;
        const buildingFootprint = this._frameFootprint(frame);

        // ---- Site plinth（深青大底座，V7 visual identity）----
        const plinth = new THREE.Mesh(
            new THREE.BoxGeometry(buildingFootprint.width + 28, 6, buildingFootprint.depth + 24),
            this._mat(0x13243a, undefined, undefined, undefined)
        );
        plinth.position.set(buildingFootprint.centerX, SITE_PLINTH_CENTER_Y, buildingFootprint.centerZ);
        this.group.add(plinth);
        if (this.mode === 'overview') {
            this._addOpenBuildingFrame(this.group, buildingFootprint, frame.floors, FLOOR_H);
        }

        // overview-only canteen title：聚焦楼层时隐藏大标题，避免遮挡楼层跳转视线。
        if (this.mode === 'overview') {
            this.group.add(this._label(frame.displayName || '食堂', buildingFootprint.centerX, topY + FLOOR_H + 34,
                buildingFootprint.centerZ, PALETTE.labelKpi));
        }

        // ---- Vertical stair core（贯通底座→楼顶的垂直交通核，比例随真实层高）----
        const stairHeight = topY + FLOOR_H + 6;
        this._entranceMarkersForFootprint(buildingFootprint).forEach(entrance => {
            const entranceX = buildingFootprint.minX + SIDE_ENTRANCE_X;
            const stairCore = new THREE.Mesh(
                new THREE.BoxGeometry(12, stairHeight, 12),
                this._mat(0x52d6d1, 0.38, 0x52d6d1, 0.08)
            );
            stairCore.name = `${entrance.stairName} stairCore`;
            stairCore.position.set(entranceX + 9.0, stairHeight / 2 - 3, entrance.z);
            stairCore.userData = { kind: 'stairCore' };
            this.group.add(stairCore);
        });
        this._addElevatorCore(this.group, frame.floors, topY, FLOOR_H, buildingFootprint);

        frame.floors.forEach(floor => {
            const fg = new THREE.Group();
            fg.userData = { floorId: floor.floor_id, kind: 'floor' };
            this._floorGroups.set(floor.floor_id, fg);

            // 楼层基准 Y（frame 给的 baseY 已带 index*FLOOR_V 偏移）
            const baseY = floor.baseY;
            const footprint = this._floorFootprint(floor);
            const fz = footprint.centerZ;

            // ---- 楼板 slab（交替色 + 热力模式）----
            const slabBaseColor = FLOOR_SLAB_COLORS[floor.index % FLOOR_SLAB_COLORS.length];
            // heatColor 用于热力模式时楼板着色（利用最大队列饱和度）
            const maxSat = floor.windows.length > 0
                ? Math.min(1, Math.max(...floor.windows.map(w => (w.queue_length || 0) / 12)))
                : 0;
            const hc = heatColor(THREE, maxSat);
            const slabColor = this.heatMode ? hc.getHex() : slabBaseColor;
            const slab = this._floorShapeMesh(
                fg,
                'furnitureDerivedFootprint floor slab',
                footprint,
                baseY,
                this._floorSlabMaterial(slabColor, this._floorSlabOpacity(floor)),
                { floorId: floor.floor_id, kind: 'floor' }
            );
            this._floorOutline(
                fg,
                'furnitureDerivedFootprint floor outline',
                footprint,
                baseY + 3.2,
                FLOOR_TILE_COLOR,
                FLOOR_OUTLINE_OPACITY,
                { floorId: floor.floor_id, kind: 'floorOutline' }
            );
            this._floorEdgeBands(
                fg,
                footprint,
                baseY,
                this.heatMode ? hc.clone().lerp(new THREE.Color(0x415156), 0.72).getHex() : 0x7b8b88,
                { floorId: floor.floor_id, kind: 'floorEdge' }
            );
            void slab;

            // ---- front glass curtain wall（剖切时不建正面，让内部可见）----
            // cutaway 为 true 时省略正面玻璃幕墙，interior 全可见
            if (!this.cutaway) {
                const frontGlass = new THREE.Mesh(
                    new THREE.BoxGeometry(footprint.width, 26, 2),
                    this._mat(0xbdebf2, 0.20)
                );
                frontGlass.name = 'front glass';
                frontGlass.position.set(footprint.centerX, baseY + 14, footprint.maxZ - 1);
                fg.add(frontGlass);
            }

            // 后墙 + 侧墙（半透明）
            const backWall = new THREE.Mesh(
                new THREE.BoxGeometry(footprint.width, 26, 2),
                this._mat(0xbdebf2, FLOOR_BACK_WALL_OPACITY)
            );
            backWall.position.set(footprint.centerX, baseY + 14, footprint.minZ + 1);
            fg.add(backWall);

            const leftWall = new THREE.Mesh(
                new THREE.BoxGeometry(2, 26, footprint.depth),
                this._mat(0xbdebf2, FLOOR_SIDE_WALL_OPACITY)
            );
            leftWall.position.set(footprint.minX, baseY + 14, fz);
            fg.add(leftWall);

            const rightWall = new THREE.Mesh(
                new THREE.BoxGeometry(2, 26, footprint.depth),
                this._mat(0xbdebf2, FLOOR_SIDE_WALL_OPACITY)
            );
            rightWall.position.set(footprint.maxX, baseY + 14, fz);
            fg.add(rightWall);

            this._addWallDepthCues(fg, footprint, baseY, floor.floor_id);
            this._addOpenFloorFrame(fg, footprint, baseY, floor.floor_id);
            this._addPhotoReferenceShell(fg, floor, baseY);
            this._addFloorIdentityCues(fg, floor, baseY);
            this._addEntranceMarker(fg, floor.floor_id, baseY, footprint);

            // ---- 窗口（保持 userData.kind='window' 供 raycaster drill-down）----
            floor.windows.forEach((win, winIdx) => {
                this._addServiceStall(fg, win, floor.floor_id, winIdx, this._shouldShowWindowLabel(floor, win, winIdx));
            });

            // ---- 座位：由真实照片中的木色四人桌 + 混色椅子替代点阵方块 ----
            this._addPhotoTableClusters(fg, floor);

            // ---- 学生/队列点（userData.kind='student' 供 raycaster）----
            floor.students.forEach(student => {
                fg.add(this._studentAvatar(student, floor.floor_id));
            });

            this.group.add(fg);
        });
    }

    // ---- 内部：A+C 相机 / 楼层上下文动画 ----

    _now() {
        return (typeof performance !== 'undefined' && performance.now)
            ? performance.now()
            : Date.now();
    }

    _focusElapsedMs() {
        return Math.max(0, this._now() - (this.focusTransitionStartedAt || 0));
    }

    _currentFocusStage() {
        if (this.mode !== 'focus' || this.focusFloorId == null) {
            this.focusTransitionStage = 'overview';
            return this.focusTransitionStage;
        }
        const elapsed = this._focusElapsedMs();
        if (elapsed < FOCUS_SIDE_DURATION_MS) {
            this.focusTransitionStage = 'side';
        } else if (elapsed < FOCUS_SIDE_DURATION_MS + FOCUS_TOP_DURATION_MS) {
            this.focusTransitionStage = 'top';
        } else {
            this.focusTransitionStage = 'expanded';
        }
        return this.focusTransitionStage;
    }

    _focusStageProgress(stage) {
        const elapsed = this._focusElapsedMs();
        if (stage === 'side') {
            return Math.max(0, Math.min(1, elapsed / FOCUS_SIDE_DURATION_MS));
        }
        if (stage === 'top') {
            return Math.max(0, Math.min(1,
                (elapsed - FOCUS_SIDE_DURATION_MS) / FOCUS_TOP_DURATION_MS));
        }
        if (stage === 'expanded') {
            return Math.max(0, Math.min(1,
                (elapsed - FOCUS_SIDE_DURATION_MS - FOCUS_TOP_DURATION_MS)
                    / FOCUS_EXPANDED_DURATION_MS));
        }
        return 1;
    }

    _focusCameraTargets(footprint, y) {
        const fp = footprint;
        const sideDistance = Math.max(FOCUS_SIDE_MIN_DISTANCE, footprint.width * 0.68);
        const sideZOffset = Math.min(
            Math.max(20, footprint.depth * FOCUS_SIDE_Z_OFFSET_RATIO),
            46
        );
        const topHeight = Math.max(FOCUS_TOP_MIN_HEIGHT, FOCUS_TOP_CAMERA_Y_PADDING, footprint.width * 0.78,
            footprint.depth * 1.32);
        // tilted floor window labels remain readable: this is intentionally not
        // a pure vertical top-down camera, so upright menu boards keep a face.
        const topCameraZ = Math.max(FOCUS_TOP_CAMERA_Z, fp.maxZ + FOCUS_TOP_OBLIQUE_Z_PADDING);
        const expandedHeight = Math.max(FOCUS_EXPANDED_MIN_HEIGHT, FOCUS_EXPANDED_CAMERA_Y_PADDING,
            footprint.width * 1.02, footprint.depth * 1.95);
        const expandedCameraZ = Math.max(FOCUS_EXPANDED_CAMERA_Z, fp.maxZ + FOCUS_EXPANDED_OBLIQUE_Z_PADDING);

        return {
            sidePos: new this.THREE.Vector3(
                Math.min(FOCUS_SIDE_CAMERA_X, footprint.minX - sideDistance),
                y + Math.max(FOCUS_SIDE_CAMERA_Y_PADDING, footprint.depth * 0.34),
                footprint.centerZ + sideZOffset
            ),
            sideLook: new this.THREE.Vector3(footprint.centerX, y + 16, footprint.centerZ),
            topPos: new this.THREE.Vector3(
                footprint.centerX,
                y + topHeight,
                topCameraZ
            ),
            topLook: new this.THREE.Vector3(footprint.centerX, y + 8, footprint.centerZ),
            expandedPos: new this.THREE.Vector3(
                footprint.centerX,
                y + expandedHeight,
                expandedCameraZ
            ),
            expandedLook: new this.THREE.Vector3(footprint.centerX, y + 5, footprint.centerZ),
        };
    }

    _viewPresetTargets(buildingFootprint, topY, frame) {
        if (this.viewPreset === 'overview' || this.viewPreset === 'free') return null;

        const focusFloor = this.mode === 'focus' && this.focusFloorId != null && frame
            ? frame.floors.find(fl => fl.floor_id === this.focusFloorId)
            : null;
        const footprint = focusFloor ? this._floorFootprint(focusFloor) : buildingFootprint;
        const floorY = focusFloor ? (focusFloor.baseY || 0) : 0;
        const lookY = focusFloor
            ? floorY + 8
            : topY * OVERVIEW_LOOK_Y_RATIO + OVERVIEW_LOOK_Y_OFFSET;
        const look = new this.THREE.Vector3(footprint.centerX, lookY, footprint.centerZ);
        const frontDistance = Math.max(
            VIEW_PRESET_FRONT_DISTANCE,
            footprint.depth * 1.55,
            footprint.width * 0.76
        );
        const sideDistance = Math.max(
            VIEW_PRESET_SIDE_DISTANCE,
            footprint.width * 1.08,
            footprint.depth * 1.35
        );
        const presetHeight = focusFloor
            ? Math.max(140, footprint.depth * 0.58)
            : topY + Math.max(180, buildingFootprint.width * 0.62);
        const topHeight = Math.max(
            VIEW_PRESET_TOP_HEIGHT,
            focusFloor ? footprint.width * 0.94 : topY + buildingFootprint.width * 0.84,
            footprint.depth * 1.50
        );

        switch (this.viewPreset) {
            case 'front':
                return {
                    pos: new this.THREE.Vector3(
                        footprint.centerX,
                        floorY + presetHeight,
                        footprint.maxZ + frontDistance
                    ),
                    look,
                };
            case 'side':
                return {
                    pos: new this.THREE.Vector3(
                        footprint.minX - sideDistance,
                        floorY + presetHeight,
                        footprint.centerZ
                    ),
                    look,
                };
            case 'top':
                return {
                    pos: new this.THREE.Vector3(
                        footprint.centerX,
                        floorY + topHeight,
                        footprint.centerZ + VIEW_PRESET_TOP_Z_OFFSET
                    ),
                    look,
                };
            case 'free':
                return null;
            default:
                return null;
        }
    }

    _recomputeCameraTarget() {
        const fr = this._lastFrame;
        const baseYs = fr ? fr.floors.map(f => f.baseY || 0) : [0];
        const topY = baseYs.length ? Math.max(...baseYs) : 0;
        const buildingFootprint = this._frameFootprint(fr);
        const presetTargets = this._viewPresetTargets(buildingFootprint, topY, fr);
        if (presetTargets) {
            this._camTarget.pos.copy(presetTargets.pos);
            this._camTarget.look.copy(presetTargets.look);
            return;
        }
        if (this.viewPreset === 'free') return;
        if (this.mode === 'focus' && this.focusFloorId != null) {
            const f = fr && fr.floors.find(fl => fl.floor_id === this.focusFloorId);
            const y = f ? (f.baseY || 0) : 0;
            const footprint = this._floorFootprint(f);
            const stage = this._currentFocusStage();
            const progress = this._focusStageProgress(stage);
            const { sidePos, sideLook, topPos, topLook, expandedPos, expandedLook } =
                this._focusCameraTargets(footprint, y);

            if (stage === 'side') {
                this._camTarget.pos.copy(sidePos);
                this._camTarget.look.copy(sideLook);
            } else if (stage === 'top') {
                this._camTarget.pos.copy(sidePos).lerp(topPos, progress);
                this._camTarget.look.copy(sideLook).lerp(topLook, progress);
            } else if (stage === 'expanded') {
                // whole selected floor readable: 最后一段拉到近俯视，非焦点层由可见性控制隐藏，
                // 让整层楼面横向铺满主画面，避免只显示一个倾斜小剖面。
                this._camTarget.pos.copy(topPos).lerp(expandedPos, progress);
                this._camTarget.look.copy(topLook).lerp(expandedLook, progress);
            }
        } else {
            // A 总览：默认进来先看楼体，地面只保留少量空间参照。
            // Legacy contract token: this._camTarget.pos.set(OVERVIEW_CAMERA_X, topY + OVERVIEW_CAMERA_Y_PADDING, OVERVIEW_CAMERA_Z);
            const centerY = topY * OVERVIEW_LOOK_Y_RATIO + OVERVIEW_LOOK_Y_OFFSET;
            this._camTarget.pos.set(
                buildingFootprint.centerX + Math.max(OVERVIEW_THREE_QUARTER_MIN_X, buildingFootprint.width * OVERVIEW_THREE_QUARTER_X_RATIO),
                topY + Math.max(OVERVIEW_CAMERA_Y_PADDING + OVERVIEW_THREE_QUARTER_Y_PADDING, buildingFootprint.width * OVERVIEW_THREE_QUARTER_HEIGHT_RATIO),
                Math.max(OVERVIEW_CAMERA_Z, buildingFootprint.maxZ + 250) + Math.max(OVERVIEW_THREE_QUARTER_Z_PADDING, buildingFootprint.depth * OVERVIEW_THREE_QUARTER_DEPTH_RATIO)
            );
            this._camTarget.look.set(buildingFootprint.centerX + buildingFootprint.width * OVERVIEW_LOOK_PANEL_CLEARANCE_X_RATIO, centerY, buildingFootprint.centerZ);
        }
    }

    _floorIndex(floorId) {
        if (!this._lastFrame) return 0;
        const f = this._lastFrame.floors.find(fl => fl.floor_id === floorId);
        return f ? f.index : 0;
    }

    // focus mode renders selected floor only; overview restores every floor group.
    _animateFloors() {
        this._floorGroups.forEach((fg, floorId) => {
            fg.visible = this.mode !== 'focus' || this.focusFloorId == null || floorId === this.focusFloorId;
            fg.position.x = 0;
            this._floorSlide.set(floorId, 0);
        });
    }

    _animateCamera() {
        if (!this.camera) return;
        if (this.viewPreset === 'free') return;
        this.camera.position.lerp(this._camTarget.pos, CAM_LERP);
        if (this.controls) {
            this.controls.target.lerp(this._camTarget.look, CAM_LERP);
        } else {
            this.camera.lookAt(this._camTarget.look);
        }
    }

    dispose() {
        this._clear();
        this._windowInterventionEffects.clear();
        this._seenInterventionKeys.clear();
        this._hasInterventionBaseline = false;
        if (this.group.parent) this.group.parent.remove(this.group);
    }
}

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

import {
    WINDOW_LABEL_MAX_CHARS, WINDOW_LABEL_LINE_MAX_CHARS,
    WINDOW_LABEL_WORLD_WIDTH, WINDOW_LABEL_WORLD_HEIGHT,
    WINDOW_LABEL_RENDER_ORDER, WINDOW_LABEL_DENSITY_STEP,
    LABEL_TEXTURE_SCALE, LABEL_CANVAS_WIDTH,
    LABEL_CANVAS_HEIGHT_SINGLE, LABEL_CANVAS_HEIGHT_MULTI,
    WINDOW_INTERVENTION_EFFECT_MS, WINDOW_INTERVENTION_PULSE_COLOR,
    FRONT_WINDOW_COUNTER_SIZE, FRONT_WINDOW_GLASS_GUARD_SIZE,
    FRONT_WINDOW_STATUS_RAIL_SIZE, FRONT_WINDOW_STATUS_RAIL_IDLE_COLOR,
    FRONT_WINDOW_STATUS_RAIL_SERVING_COLOR, FRONT_WINDOW_SERVING_LIGHT_COLOR,
    FRONT_WINDOW_SERVING_LIGHT_SIZE, FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE,
    FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY, FRONT_WINDOW_QUEUE_HEAT_CLEAR_COLOR,
    FRONT_WINDOW_QUEUE_HEAT_BUSY_COLOR, FRONT_WINDOW_MENU_BOARD_WIDTH,
    FRONT_WINDOW_MENU_BOARD_HEIGHT, FRONT_WINDOW_LABEL_X_OFFSET,
    FRONT_WINDOW_LABEL_Y_OFFSET, FRONT_WINDOW_LABEL_Z_OFFSET,
    FLOOR_SLAB_COLORS, FLOOR_TILE_COLOR, FLOOR_SLAB_OPACITY,
    OVERVIEW_FLOOR_SLAB_OPACITY, FOCUS_FLOOR_SLAB_OPACITY,
    FLOOR_SLAB_RENDER_ORDER, FLOOR_OUTLINE_OPACITY, FLOOR_TILE_OUTLINE_OPACITY,
    WALL_RENDER_ORDER, FLOOR_SKIRT_RENDER_ORDER, FLOOR_EDGE_BAND_RENDER_ORDER,
    WINDOW_GLASS_RENDER_ORDER, FLOOR_DECAL_RENDER_ORDER, QUEUE_HEAT_RENDER_ORDER,
    STAIR_CORE_RENDER_ORDER, DEFAULT_LABEL_RENDER_ORDER,
    FLOOR_EDGE_BAND_HEIGHT, FLOOR_EDGE_BAND_THICKNESS,
    FLOOR_EDGE_BAND_OPACITY, FLOOR_EDGE_BAND_Y_EPSILON,
    FLOOR_BACK_WALL_OPACITY, FLOOR_SIDE_WALL_OPACITY,
    OVERVIEW_FLOOR_GRADIENT_Z_OFFSETS, OVERVIEW_FLOOR_GRADIENT_OPACITY,
    FLOOR_WALL_COLOR, FLOOR_EDGE_COLOR, OPEN_BUILDING_FRAME_OPACITY,
    OPEN_BUILDING_DEPTH_PAD, INTERFLOOR_SHADOW_OPACITY, INTERFLOOR_SHADOW_HEIGHT,
    DEFAULT_FOOTPRINT_WIDTH, DEFAULT_FOOTPRINT_DEPTH, DEFAULT_CENTER_X,
    TABLE_DX, TABLE_Z0, TABLE_DZ, TABLE_ZONE_AISLE_X, TABLE_ROW_AISLE_Z,
    SCENE_UNITS_PER_METER, SERVICE_TO_TABLE_BUFFER_M, TABLE_WINDOW_GAP_Z,
    TABLE_ZONE_SIDE_PADDING, TABLE_ZONE_MAX_COLS, CHAIR_DX, CHAIR_DZ,
    SIDE_ENTRANCE_X, SITE_PLINTH_CENTER_Y, SIDE_ENTRANCE_MARKERS,
    ENTRANCE_MARKER_DEPTH, ENTRANCE_DOOR_HEIGHT, ENTRANCE_DOOR_DEPTH,
    ENTRANCE_GLASS_HEIGHT, ENTRANCE_GLASS_DEPTH, ENTRANCE_CANOPY_DEPTH,
    PHOTO_WALL_SIGN_COLOR, STUDENT_SERVING_STATUS_COLOR,
    PALETTE, STUDENT_CLOTHING_PALETTE, photoWindowWall,
    mixedChairPalette, FLOOR_TABLE_COLOR_FALLBACKS,
    STALL_THEME, stallTheme, MINGHU_FLOOR_LAYOUTS, MINGHU_WINDOW_LABELS,
    actualTableCount, visibleTableCountForProfile, visualTableIndexForSeat,
    tableColumnCount, tableZoneCount, tableZoneColumnCount,
    tableBlocksForProfile, tableBlockForIndex, serviceWindowMaxZ,
    tableZoneStartZ, tableZonePosition, tableBlockPosition,
    legacyTableZonePosition, defaultFootprint, normalizedFootprint,
    stableStudentClothingColor, studentStatusColor,
    compactWindowLabel, windowLabelLines,
} from "./canteen_layouts.js";
import {
    meshMat, photoMat, addBox, heatColor,
    addChairOccupancyMarker, chairVariant, addChair,
    addSquareTableCluster, addLongTableCluster, addBoothTableCluster,
} from "./canteen_furniture.js";

const FLOOR_RISE = 0;           // 层间高差（场景已竖向展开，无需额外偏移）
const CAM_LERP = 0.045;         // 相机/层位移插值系数
const FOCUS_SIDE_DURATION_MS = 1600;
const FOCUS_TOP_DURATION_MS = 1800;
const FOCUS_EXPANDED_DURATION_MS = 1800;
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
const VIEW_PRESET_TOP_HEIGHT = 380;
const VIEW_PRESET_TOP_Z_OFFSET = 18;
const DEFAULT_OVERVIEW_VIEW_PRESET = 'front';


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
        this.viewPreset = DEFAULT_OVERVIEW_VIEW_PRESET;   // 'overview' | 'front' | 'side' | 'top' | 'free'
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
        this.viewPreset = DEFAULT_OVERVIEW_VIEW_PRESET;
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
        sprite.renderOrder = options.renderOrder ?? DEFAULT_LABEL_RENDER_ORDER;
        if (options.alwaysReadableWindowLabel) sprite.userData.alwaysReadableWindowLabel = true;
        return sprite;
    }

    _floorSlabOpacity(floor) {
        // floor surface opacity increases only for selected floor focus; overview
        // stays low-opacity so stacked lower floors remain readable.
        const isFocusedFloor = this.mode === 'focus'
            && this.focusFloorId != null
            && floor?.floor_id === this.focusFloorId;
        return isFocusedFloor
            ? FOCUS_FLOOR_SLAB_OPACITY
            : OVERVIEW_FLOOR_SLAB_OPACITY * this._floorGradientOpacityScale(floor);
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
        mat.polygonOffset = opacity < 0.98;
        if (mat.polygonOffset) {
            // Effective negative depth bias: nudge the ultra-translucent overview
            // slab toward camera so it resolves consistently against near-coplanar
            // bottom geometry (ground/plinth/interfloor-shadow/footprint outline)
            // instead of z-fighting it.
            mat.polygonOffsetFactor = -1;
            mat.polygonOffsetUnits = -1;
        } else {
            // Opaque focused slab writes depth normally; biasing it toward the
            // camera would let it depth-beat decals resting on the floor plane.
            mat.polygonOffsetFactor = 0;
            mat.polygonOffsetUnits = 0;
        }
        return mat;
    }

    _floorGradientDisplay(floor) {
        // floor gradient display: 1F pulled forward, upper floors fade back.
        if (this.mode === 'focus') return { zOffset: 0, opacityScale: 1 };
        const idx = Math.max(0, floor?.index ?? 0);
        const zOffset = OVERVIEW_FLOOR_GRADIENT_Z_OFFSETS[
            Math.min(idx, OVERVIEW_FLOOR_GRADIENT_Z_OFFSETS.length - 1)
        ] ?? 0;
        const opacityScale = OVERVIEW_FLOOR_GRADIENT_OPACITY[
            Math.min(idx, OVERVIEW_FLOOR_GRADIENT_OPACITY.length - 1)
        ] ?? 1;
        return { zOffset, opacityScale };
    }

    _floorGradientOpacityScale(floor) {
        return this._floorGradientDisplay(floor).opacityScale;
    }

    _floorGradientZOffset(floor) {
        return this._floorGradientDisplay(floor).zOffset;
    }

    _floorGradientZOffsetForFloorId(floorId) {
        const floor = this._lastFrame?.floors.find(fl => fl.floor_id === floorId);
        return this._floorGradientZOffset(floor);
    }

    _floorSwitchGradientDelta(student, floorId) {
        if (student?.position !== 'floor_switching') return 0;
        const fromFloorId = Number.isFinite(student.from_floor_id)
            ? student.from_floor_id
            : floorId;
        const targetFloorId = Number.isFinite(student.target_floor_id)
            ? student.target_floor_id
            : fromFloorId;
        const progress = Math.max(0, Math.min(1, student.floor_switch_progress || 0));
        const baseZOffset = this._floorGradientZOffsetForFloorId(floorId);
        const fromZOffset = this._floorGradientZOffsetForFloorId(fromFloorId);
        const targetZOffset = this._floorGradientZOffsetForFloorId(targetFloorId);
        const worldZOffset = fromZOffset + progress * (targetZOffset - fromZOffset);
        return worldZOffset - baseZOffset;
    }

    _applyFloorGradientMaterial(mat, floor) {
        if (!mat || this.mode === 'focus') return mat;
        mat.userData = mat.userData || {};
        if (mat.userData.floorGradientApplied) return mat;
        const opacityScale = this._floorGradientOpacityScale(floor);
        if (opacityScale >= 0.999) {
            mat.userData.floorGradientApplied = true;
            return mat;
        }
        const opacity = (mat.opacity == null ? 1 : mat.opacity) * opacityScale;
        mat.opacity = opacity;
        mat.transparent = opacity < 0.98;
        if ('depthWrite' in mat) mat.depthWrite = opacity >= 0.98;
        mat.userData.floorGradientApplied = true;
        mat.needsUpdate = true;
        return mat;
    }

    _applyFloorGradientToGroup(group, floor) {
        group.traverse?.(node => {
            if (Array.isArray(node.material)) {
                node.material.forEach(mat => this._applyFloorGradientMaterial(mat, floor));
            } else {
                this._applyFloorGradientMaterial(node.material, floor);
            }
        });
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
        const material = photoMat(this.THREE, color, {
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
                y - FLOOR_EDGE_BAND_HEIGHT / 2 - FLOOR_EDGE_BAND_Y_EPSILON,
                (point.z + next.z) / 2
            );
            mesh.rotation.y = -Math.atan2(dz, dx);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.renderOrder = FLOOR_EDGE_BAND_RENDER_ORDER;
            if (userData) mesh.userData = userData;
            group.add(mesh);
        });
    }

    _addOpenBuildingFrame(group, buildingFootprint, floors, floorHeight) {
        const baseYs = (floors || []).map(floor => floor.baseY || 0);
        const topY = baseYs.length ? Math.max(...baseYs) : 0;
        const fullHeight = topY + floorHeight + 4;
        const frameMat = photoMat(this.THREE, 0x3f5358, {
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
            addBox(this.THREE,
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
            addBox(this.THREE,
                group,
                'open axonometric rear floor beam',
                [buildingFootprint.width + OPEN_BUILDING_DEPTH_PAD * 2, 2.4, 3.0],
                [buildingFootprint.centerX, y, minZ],
                frameMat,
                { kind: 'buildingFrame', floorId: floor.floor_id }
            );
            [-1, 1].forEach(side => {
                const x = side < 0 ? minX : maxX;
                addBox(this.THREE,
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
        const frameMat = photoMat(this.THREE, 0x273845, {
            opacity: OPEN_BUILDING_FRAME_OPACITY,
            roughness: 0.58,
            metalness: 0.02,
        });
        const shadowMat = photoMat(this.THREE, 0x07111d, {
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
            addBox(this.THREE,
                group,
                'open floor front vertical post',
                [3.0, 27.5, 3.0],
                [x, baseY + 14, z],
                frameMat,
                cueData
            );
        });

        addBox(this.THREE,
            group,
            'open floor front edge beam',
            [footprint.width + 5, 2.8, 3.0],
            [footprint.centerX, baseY + 28.4, z],
            frameMat,
            cueData
        );
        // z+1.2 让阴影盒整体退出边带体积（边带 z∈[maxZ-1.2, maxZ+1.2]），
        // 两个半透明盒互相穿插会在每层前缘产生逐像素表面争夺。
        const shadow = addBox(this.THREE,
            group,
            'open floor interlevel shadow band',
            [footprint.width + 4, INTERFLOOR_SHADOW_HEIGHT, 3.2],
            [footprint.centerX, baseY - INTERFLOOR_SHADOW_HEIGHT / 2 - 0.4, z + 1.2],
            shadowMat,
            cueData
        );
        shadow.renderOrder = FLOOR_SKIRT_RENDER_ORDER;
    }

    _addWallDepthCues(group, footprint, baseY, floorId) {
        const wallCueData = { floorId, kind: 'floor' };
        const columnMat = photoMat(this.THREE, 0x263541, {
            opacity: 0.74,
            roughness: 0.58,
            metalness: 0.02,
        });
        const beamMat = photoMat(this.THREE, 0x4d5d61, {
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
            addBox(this.THREE,
                group,
                'building corner column',
                [3.2, 27.5, 3.2],
                [x, baseY + 14, z],
                columnMat,
                wallCueData
            );
        });

        addBox(this.THREE,
            group,
            'wall top cap beam',
            [footprint.width + 2.4, 2.2, 2.8],
            [footprint.centerX, baseY + 27.8, footprint.minZ + 1.1],
            beamMat,
            wallCueData
        );
        [-1, 1].forEach(side => {
            const x = side < 0 ? footprint.minX : footprint.maxX;
            addBox(this.THREE,
                group,
                'wall top cap beam',
                [2.8, 2.2, footprint.depth + 2.4],
                [x, baseY + 27.8, footprint.centerZ],
                beamMat,
                wallCueData
            );
        });
        addBox(this.THREE,
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
            addBox(this.THREE,
                group,
                'muted photo menu board',
                [width, height, 1],
                pos,
                photoMat(this.THREE, photoWindowWall.menu, {
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
        const pipeMat = photoMat(this.THREE, 0x6f8790, {
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
            const pane = addBox(this.THREE, group, 'photo window glass pane', [1, 16, 5.3],
                [x, baseY + 15.5, z],
                photoMat(this.THREE, photoWindowWall.glass, {
                    opacity: 0.30,
                    roughness: 0.08,
                    emissive: 0x5fb5c3,
                    emissiveIntensity: 0.04,
                })
            );
            pane.renderOrder = WINDOW_GLASS_RENDER_ORDER;
            addBox(this.THREE, group, 'photo window black frame vertical', [1.4, 18, 0.45],
                [x + 0.1, baseY + 15.6, z - 2.95],
                photoMat(this.THREE, photoWindowWall.frame, { roughness: 0.32 })
            );
            addBox(this.THREE, group, 'photo window black frame vertical', [1.4, 18, 0.45],
                [x + 0.1, baseY + 15.6, z + 2.95],
                photoMat(this.THREE, photoWindowWall.frame, { roughness: 0.32 })
            );
        }
        addBox(this.THREE, group, 'photo window sill bench', [3.2, 2.2, footprint.depth - 10],
            [x + 3.3, baseY + 7, footprint.centerZ],
            photoMat(this.THREE, 0xe9ddd0, { roughness: 0.38 })
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
            addBox(this.THREE,
                group,
                `${markerName} student spawn entrance marker`,
                [4.4, 1.0, ENTRANCE_MARKER_DEPTH],
                [entranceX + 3.0, baseY + 3.5, entrance.z],
                photoMat(this.THREE, PALETTE.flow, {
                    opacity: 0.82,
                    emissive: PALETTE.flow,
                    emissiveIntensity: 0.10,
                }),
                { floorId, kind: 'floor' }
            );
            addBox(this.THREE,
                group,
                `${markerName} entranceDoorFrame`,
                [1.8, ENTRANCE_DOOR_HEIGHT, ENTRANCE_DOOR_DEPTH],
                [doorX, baseY + 10.9, entrance.z],
                photoMat(this.THREE, 0x17202b, { opacity: 0.78, roughness: 0.26 }),
                { floorId, kind: 'floor' }
            );
            addBox(this.THREE,
                group,
                `${markerName} entranceGlassPanel`,
                [1.0, ENTRANCE_GLASS_HEIGHT, ENTRANCE_GLASS_DEPTH],
                [doorX - 0.4, baseY + 10.2, entrance.z],
                photoMat(this.THREE, 0xcfe9ee, {
                    opacity: 0.42,
                    roughness: 0.08,
                    emissive: 0x5fb5c3,
                    emissiveIntensity: 0.06,
                }),
                { floorId, kind: 'floor' }
            );
            addBox(this.THREE,
                group,
                `${markerName} entranceCanopy`,
                [10.5, 2.4, ENTRANCE_CANOPY_DEPTH],
                [entranceX + 5.0, baseY + 18.2, entrance.z],
                photoMat(this.THREE, 0x33404a, {
                    opacity: 0.88,
                    roughness: 0.30,
                    emissive: 0x20364a,
                    emissiveIntensity: 0.08,
                }),
                { floorId, kind: 'floor' }
            );
        });
    }

    _addElevatorCore(group, floors, topY, floorHeight, buildingFootprint, floorZOffset = () => 0) {
        const shaftX = buildingFootprint.minX + SIDE_ENTRANCE_X - 3.5;
        const shaftZ = buildingFootprint.centerZ;
        const shaftHeight = topY + floorHeight + 8;
        const [entranceLowerZ, entranceUpperZ] = this._entranceMarkersForFootprint(buildingFootprint).map(e => e.z);
        const stairZSpan = entranceUpperZ - entranceLowerZ;
        const activeFloor = this.mode === 'focus' && this.focusFloorId != null
            ? floors.find(floor => floor.floor_id === this.focusFloorId)
            : floors[0];
        const carY = (activeFloor?.baseY || 0) + 13;

        addBox(this.THREE,
            group,
            'elevator glass shaft',
            [15, shaftHeight, stairZSpan + 8],
            [shaftX, shaftHeight / 2 - 3, shaftZ],
            photoMat(this.THREE, 0x9fe8ef, {
                opacity: 0.28,
                roughness: 0.06,
                emissive: 0x52d6d1,
                emissiveIntensity: 0.08,
            }),
            { kind: 'stairCore' }
        );

        [-8, 8].forEach(dx => {
            [-10, 10].forEach(dz => {
                addBox(this.THREE,
                    group,
                    'elevator dark vertical frame',
                    [1.4, shaftHeight + 1, 1.4],
                    [shaftX + dx, shaftHeight / 2 - 3, shaftZ + dz],
                    photoMat(this.THREE, 0x182232, { roughness: 0.34 }),
                    { kind: 'stairCore' }
                );
            });
        });

        addBox(this.THREE,
            group,
            'elevator car',
            [10.5, 15, 14],
            [shaftX, carY, shaftZ],
            photoMat(this.THREE, 0xe9f8f8, {
                opacity: 0.86,
                roughness: 0.18,
                emissive: 0x52d6d1,
                emissiveIntensity: 0.06,
            }),
            { kind: 'stairCore' }
        );

        floors.forEach(floor => {
            const baseY = floor.baseY || 0;
            const zOffset = floorZOffset(floor);
            addBox(this.THREE,
                group,
                'elevator landing bridge',
                [24, 1.8, 15],
                [shaftX + 12, baseY + 5.3, shaftZ + zOffset],
                photoMat(this.THREE, 0x33404a, {
                    opacity: 0.92,
                    roughness: 0.32,
                    emissive: 0x20364a,
                    emissiveIntensity: 0.04,
                }),
                { floorId: floor.floor_id, kind: 'floor' }
            );
            addBox(this.THREE,
                group,
                'elevator floor door',
                [1.2, 12, 12],
                [shaftX + 8.4, baseY + 11.5, shaftZ + zOffset],
                photoMat(this.THREE, 0xcfe9ee, {
                    opacity: 0.62,
                    roughness: 0.12,
                    emissive: 0x5fb5c3,
                    emissiveIntensity: 0.07,
                }),
                { floorId: floor.floor_id, kind: 'floor' }
            );
        });

        for (let i = 0; i < floors.length - 1; i += 1) {
            // stair core follows front floor gradient display, so the demo
            // steps still connect to floors after 1F is pulled forward.
            const lowerFloor = floors[i];
            const upperFloor = floors[i + 1];
            const lowerZOffset = floorZOffset(lowerFloor);
            const upperZOffset = floorZOffset(upperFloor);
            const lower = floors[i].baseY || 0;
            const upper = floors[i + 1].baseY || 0;
            const span = Math.max(1, upper - lower);
            for (let step = 0; step < 8; step += 1) {
                const t = step / 7;
                const baseZ = entranceLowerZ + t * stairZSpan;
                addBox(this.THREE,
                    group,
                    'stair step stack',
                    [13, 1.0, 4.2],
                    [
                        shaftX + 12.5,
                        lower + 13 + t * (span - 6),
                        baseZ + lowerZOffset + t * (upperZOffset - lowerZOffset),
                    ],
                    photoMat(this.THREE, 0xd7e0dc, { roughness: 0.42 }),
                    { kind: 'stairCore' }
                );
            }
            addBox(this.THREE,
                group,
                'stair handrail',
                [1.2, span - 8, 1.2],
                [
                    shaftX + 30,
                    lower + span / 2 + 8,
                    shaftZ + lowerZOffset + 0.5 * (upperZOffset - lowerZOffset),
                ],
            photoMat(this.THREE, PALETTE.flow, {
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
        const pulseMat = photoMat(this.THREE, WINDOW_INTERVENTION_PULSE_COLOR, {
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

        const pillar = addBox(this.THREE,
            group,
            'window intervention pulse pillar',
            layoutSide === 'left' ? [2.0, 16, 12] : [14, 16, 2.0],
            [x, y + 4.2, z],
            photoMat(this.THREE, WINDOW_INTERVENTION_PULSE_COLOR, {
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
            const body = addBox(this.THREE,
                group,
                'sideWall service counter window',
                [12, 8, 18],
                [x, y - 3.4, z],
                photoMat(this.THREE, win.is_open ? 0xd8e2df : 0x5c6874, {
                    opacity: win.is_open ? 0.95 : 0.74,
                    roughness: 0.34,
                }),
                { floorId, kind: 'window', windowId: win.id }
            );
            this._tagWindowInterventionBody(body, interventionEffect);
            body.userData.photoCue = 'side counter';
            addBox(this.THREE, group, 'sideWall glass food guard', [1, 7, 16.5],
                [x + 5.7, y + 2.2, z],
                photoMat(this.THREE, 0xcceaf1, { opacity: 0.36, roughness: 0.08 })
            );
            addBox(this.THREE, group, 'sideWall red stall menu fascia', [1.2, 6, 18],
                [x - 5.9, y + 8.3, z],
                photoMat(this.THREE, winColor, {
                    opacity: win.is_open ? 0.98 : 0.64,
                    emissive: winColor,
                    emissiveIntensity: win.is_open ? 0.04 : 0.01,
                })
            );

            // Spec §A: additive 4-part themed stall mirrored onto the side-wall
            // orientation (service face along +x, stall spans z). Layered on top
            // of the retained side meshes; material/color temperature only.
            const sth = stallTheme(floorId);
            addBox(this.THREE, group, 'stall base counter',
                [13.2, 1.4, 19.2],
                [x, y - 7.4, z],
                photoMat(this.THREE, sth.counter, {
                    opacity: win.is_open ? 0.92 : 0.7,
                    roughness: sth.roughness,
                    emissive: sth.counter,
                    emissiveIntensity: win.is_serving ? 0.03 : 0.012,
                })
            );
            // Thin themed glass pushed clear of the retained 'glass food guard'
            // (which sits at x + 5.7); placed further out so the two
            // semi-transparent passes never overlap.
            addBox(this.THREE, group, 'stall open-kitchen glass',
                [0.5, 2.0, 16.0],
                [x + 6.6, y + 5.6, z],
                photoMat(this.THREE, sth.glass, {
                    opacity: 0.34,
                    roughness: sth.roughness,
                    emissive: sth.glass,
                    emissiveIntensity: win.is_serving ? 0.03 : 0.012,
                })
            );
            // Thin themed status strip stacked above the retained menu fascia
            // (which sits at x - 5.9), same open/serving/closed color logic.
            addBox(this.THREE, group, 'stall status strip',
                [0.5, 0.5, 22.0],
                [x - 5.9, y + 11.6, z],
                photoMat(this.THREE, winColor, {
                    opacity: win.is_open ? 0.5 : 0.32,
                    roughness: sth.roughness,
                    emissive: winColor,
                    emissiveIntensity: win.is_serving ? 0.03 : 0.012,
                })
            );
            if (showWindowLabel) {
                const labelZOffset = localIndex % 2 === 0 ? -5.4 : 5.4;
                // Thin themed signboard band at label height; the retained side
                // label renders just in front of it (slightly larger +x).
                addBox(this.THREE, group, 'stall signboard band',
                    [0.5, 5.4, 19.5],
                    [x + 9.3, y + 16.8 + (localIndex % 3) * 1.3, z],
                    photoMat(this.THREE, sth.sign, {
                        opacity: win.is_open ? 0.94 : 0.72,
                        roughness: sth.roughness,
                        emissive: sth.sign,
                        emissiveIntensity: win.is_serving ? 0.03 : 0.012,
                    })
                );
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
                addBox(this.THREE, group, 'queue heat cap', [12, 2.4, 18],
                    [x, y + 12.6, z],
                    photoMat(this.THREE, hc2.getHex(), {
                        opacity: 0.66,
                        roughness: 0.70,
                    })
                ).renderOrder = QUEUE_HEAT_RENDER_ORDER;
            }
            if (!win.is_open && win.closing) {
                group.add(this._label('关闭中', x + 8, y + 18, z, '#e7bd63', 1, 0.70));
            }
            this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);
            return;
        }

        const body = addBox(this.THREE,
            group,
            'photo service counter window',
            FRONT_WINDOW_COUNTER_SIZE,
            // front service counters are visible but light, not the dark residual under window labels.
            [x, y + 2.7, z],
            photoMat(this.THREE, win.is_open ? 0xd8e2df : 0x5c6874, {
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
        addBox(this.THREE, group, 'stall base counter',
            [FRONT_WINDOW_COUNTER_SIZE[0] + 1.2, 1.4, FRONT_WINDOW_COUNTER_SIZE[2] + 1.0],
            [x, y - 0.1, z],
            photoMat(this.THREE, th.counter, {
                opacity: win.is_open ? 0.92 : 0.7,
                roughness: th.roughness,
                emissive: th.counter,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );
        addBox(this.THREE, group, 'stall open-kitchen glass',
            [FRONT_WINDOW_COUNTER_SIZE[0] - 0.6, 2.0, 0.5],
            // z-separated from the retained semi-transparent 'glass food guard'
            // (centre + 0.20) so the two transparent passes never overlap.
            [x, y + 5.6, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 0.95],
            photoMat(this.THREE, th.glass, {
                opacity: 0.34,
                roughness: th.roughness,
                emissive: th.glass,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );
        addBox(this.THREE, group, 'stall tray rail',
            [FRONT_WINDOW_COUNTER_SIZE[0] - 1.0, 0.5, 0.6],
            [x, y + 1.0, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 1.05],
            photoMat(this.THREE, th.rail, {
                opacity: win.is_open ? 0.9 : 0.66,
                roughness: th.roughness,
                emissive: th.rail,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );

        addBox(this.THREE, group, 'glass food guard', FRONT_WINDOW_GLASS_GUARD_SIZE,
            [x, y + 5.6, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 0.2],
            photoMat(this.THREE, 0xcceaf1, { opacity: 0.36, roughness: 0.08 })
        );
        const frontStatusRailColor = win.is_open
            ? (win.is_serving ? FRONT_WINDOW_STATUS_RAIL_SERVING_COLOR : FRONT_WINDOW_STATUS_RAIL_IDLE_COLOR)
            : winColor;
        addBox(this.THREE, group, 'front service status rail', FRONT_WINDOW_STATUS_RAIL_SIZE,
            // front window status cue should stay thin, not become a dark block under menu labels.
            [x, y + 6.2, z - FRONT_WINDOW_COUNTER_SIZE[2] / 2 - 0.25],
            photoMat(this.THREE, frontStatusRailColor, {
                opacity: win.is_open ? 0.62 : 0.36,
                emissive: frontStatusRailColor,
                emissiveIntensity: win.is_serving ? 0.035 : 0.015,
            })
        );
        // Additional thin status strip stacked above the retained rail, same open/serving/closed logic.
        addBox(this.THREE, group, 'stall status strip',
            [FRONT_WINDOW_STATUS_RAIL_SIZE[0] + 4, 0.5, 0.5],
            [x, y + 7.0, z - FRONT_WINDOW_COUNTER_SIZE[2] / 2 - 0.55],
            photoMat(this.THREE, frontStatusRailColor, {
                opacity: win.is_open ? 0.5 : 0.32,
                roughness: th.roughness,
                emissive: frontStatusRailColor,
                emissiveIntensity: win.is_serving ? 0.03 : 0.012,
            })
        );
        if (win.is_open && win.is_serving) {
            addBox(this.THREE, group, 'front service serving status light', FRONT_WINDOW_SERVING_LIGHT_SIZE,
                [x, y + 7.2, z - FRONT_WINDOW_COUNTER_SIZE[2] / 2 - 0.7],
                photoMat(this.THREE, FRONT_WINDOW_SERVING_LIGHT_COLOR, {
                    opacity: 0.78,
                    emissive: FRONT_WINDOW_SERVING_LIGHT_COLOR,
                    emissiveIntensity: 0.08,
                })
            );
        }
        if (showWindowLabel) {
            // Thin themed signboard band at label height; the retained menu
            // board/label renders just in front of it (slightly larger +z).
            addBox(this.THREE, group, 'stall signboard band',
                [FRONT_WINDOW_MENU_BOARD_WIDTH + 1.5, FRONT_WINDOW_MENU_BOARD_HEIGHT + 1.2, 0.5],
                [
                    x + FRONT_WINDOW_LABEL_X_OFFSET,
                    y + FRONT_WINDOW_LABEL_Y_OFFSET,
                    z + FRONT_WINDOW_LABEL_Z_OFFSET - 0.7,
                ],
                photoMat(this.THREE, th.sign, {
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
            addBox(this.THREE, group, 'front service queue heat strip', FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE,
                [x, y + 5.4, z + FRONT_WINDOW_COUNTER_SIZE[2] / 2 + 0.8],
                photoMat(this.THREE, frontQueueHeatColor, {
                    opacity: FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY,
                    roughness: 0.70,
                })
            ).renderOrder = QUEUE_HEAT_RENDER_ORDER;
        }
        if (!win.is_open && win.closing) {
            group.add(this._label('关闭中', x, y + 18, z, '#e7bd63'));
        }
        this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);
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

    _addFloorIdentityCues(group, floor, baseY) {
        const profile = this._floorLayoutProfile(floor.floor_id);
        const footprint = this._floorFootprint(floor);
        const serviceMaxZ = serviceWindowMaxZ(profile);
        const tableStartZ = tableZoneStartZ(profile);
        if (profile.key === 'basicMealWideAisle') {
            addBox(this.THREE, group, 'f1-snake-queue-guide', [footprint.width - 78, 0.9, 22],
                [footprint.centerX, baseY + 3.9, serviceMaxZ + 28],
                photoMat(this.THREE, 0x84cc16, { opacity: 0.32, roughness: 0.30 })
            ).renderOrder = FLOOR_DECAL_RENDER_ORDER;
            addBox(this.THREE, group, 'f1-pickup-return-lane', [footprint.width - 86, 0.8, 12],
                [footprint.centerX, baseY + 3.8, tableStartZ - 18],
                photoMat(this.THREE, 0xe7bd63, { opacity: 0.34, roughness: 0.28 })
            ).renderOrder = FLOOR_DECAL_RENDER_ORDER;
            addBox(this.THREE, group, 'f1-main-aisle-cue', [18, 0.8, Math.max(58, footprint.maxZ - tableStartZ - 20)],
                [footprint.centerX + 16, baseY + 3.75, tableStartZ + 44],
                photoMat(this.THREE, 0x93c5fd, { opacity: 0.28, roughness: 0.30 })
            ).renderOrder = FLOOR_DECAL_RENDER_ORDER;
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
            addBox(this.THREE, group, 'featureFoodCourt coffee island', [22, 5.0, 13],
                [48, baseY + 6.8, serviceMaxZ + 34],
                photoMat(this.THREE, 0x4d3a32, {
                    roughness: 0.34,
                    emissive: 0x261a13,
                    emissiveIntensity: 0.06,
                })
            );
            addBox(this.THREE, group, 'featureFoodCourt hotpot zone', [78, 0.9, 16],
                [236, baseY + 3.8, tableStartZ + 4],
                photoMat(this.THREE, 0x7f1d1d, {
                    opacity: 0.36,
                    emissive: 0x7f1d1d,
                    emissiveIntensity: 0.08,
                })
            ).renderOrder = FLOOR_DECAL_RENDER_ORDER;
            return;
        }
        addBox(this.THREE, group, 'restaurantDiningRoom booth seating', [96, 5.8, 7.5],
            [87, baseY + 6.8, tableStartZ + 10],
            photoMat(this.THREE, 0x6b4f39, { roughness: 0.32 })
        );
        addBox(this.THREE, group, 'restaurantDiningRoom service aisle', [18, 0.7, 34],
            [286, baseY + 3.7, serviceMaxZ + 24],
            photoMat(this.THREE, 0xefe9dc, { opacity: 0.32, roughness: 0.28 })
        ).renderOrder = FLOOR_DECAL_RENDER_ORDER;
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
                addLongTableCluster(this.THREE, group, x, baseY, z, idx, occupied, tableColor);
            } else if (variant === 'booth') {
                addBoothTableCluster(this.THREE, group, x, baseY, z, idx, occupied, tableColor);
            } else {
                addSquareTableCluster(this.THREE, group, x, baseY, z, idx, occupied, tableColor);
            }

        }
    }

    _studentAvatar(student, floorId) {
        const THREE = this.THREE;
        const p = student.position3d || student.target;
        const avatar = new THREE.Group();
        avatar.name = 'studentAvatar';
        avatar.position.set(p.x, p.y, p.z + this._floorSwitchGradientDelta(student, floorId));
        avatar.userData = { floorId, kind: 'student', studentId: student.id };

        // Face the direction of travel: rotate only when there is a real
        // current→target delta (moving students). Seated/queued avatars have
        // target≈position (or none) and keep a stable default facing.
        const cur = student.position3d;
        const dest = student.target;
        if (cur && dest) {
            const dxTravel = dest.x - cur.x;
            const dzTravel = dest.z - cur.z;
            if (dxTravel * dxTravel + dzTravel * dzTravel > 1e-3) {
                avatar.rotation.y = Math.atan2(dxTravel, dzTravel);
            }
        }

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
            meshMat(this.THREE, 0x13243a, undefined, undefined, undefined)
        );
        plinth.position.set(buildingFootprint.centerX, SITE_PLINTH_CENTER_Y, buildingFootprint.centerZ);
        this.group.add(plinth);
        if (this.mode === 'overview') {
            // overview-only vertical transport core: focus mode keeps the selected floor from being cut by the full-building stair/elevator core.
            // Each floor still renders local entrance markers inside its own group.
            const stairHeight = topY + FLOOR_H + 6;
            this._entranceMarkersForFootprint(buildingFootprint).forEach(entrance => {
                const entranceX = buildingFootprint.minX + SIDE_ENTRANCE_X;
                const stairCore = new THREE.Mesh(
                    new THREE.BoxGeometry(12, stairHeight, 12),
                    meshMat(this.THREE, 0x52d6d1, 0.38, 0x52d6d1, 0.08)
                );
                stairCore.name = `${entrance.stairName} stairCore`;
                stairCore.position.set(entranceX + 9.0, stairHeight / 2 - 3, entrance.z);
                stairCore.renderOrder = STAIR_CORE_RENDER_ORDER;
                stairCore.userData = { kind: 'stairCore' };
                this.group.add(stairCore);
            });
            this._addElevatorCore(
                this.group,
                frame.floors,
                topY,
                FLOOR_H,
                buildingFootprint,
                floor => this._floorGradientZOffset(floor)
            );
            this._addOpenBuildingFrame(this.group, buildingFootprint, frame.floors, FLOOR_H);
            const title = this._label(
                frame.displayName || '明湖食堂',
                buildingFootprint.centerX,
                topY + FLOOR_H + 30,
                buildingFootprint.centerZ,
                PALETTE.labelKpi,
                0.92,
                1.0
            );
            title.name = 'overview-only canteen title';
            this.group.add(title);
        }

        frame.floors.forEach(floor => {
            const fg = new THREE.Group();
            fg.userData = { floorId: floor.floor_id, kind: 'floor' };
            this._floorGroups.set(floor.floor_id, fg);
            const gradient = this._floorGradientDisplay(floor);
            fg.position.z = gradient.zOffset;

            // 楼层基准 Y（frame 给的 baseY 已带 index*FLOOR_V 偏移）
            const baseY = floor.baseY;
            const footprint = this._floorFootprint(floor);
            const fz = footprint.centerZ;

            // ---- 楼板 slab（Style B: 暖象牙色 + 热力模式）----
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
                FLOOR_EDGE_COLOR,
                FLOOR_OUTLINE_OPACITY,
                { floorId: floor.floor_id, kind: 'floorOutline' }
            );
            this._floorEdgeBands(
                fg,
                footprint,
                baseY,
                this.heatMode ? hc.clone().lerp(new THREE.Color(0x415156), 0.72).getHex() : FLOOR_EDGE_COLOR,
                { floorId: floor.floor_id, kind: 'floorEdge' }
            );
            void slab;

            // ---- Style B: 正面开放，后墙+侧墙填满楼层间距（FLOOR_V≈104，墙高90）----
            const WALL_H = 90;  // 填满楼层间距 (FLOOR_V-~14)
            const wallCY = baseY + WALL_H / 2;

            const backWall = new THREE.Mesh(
                new THREE.BoxGeometry(footprint.width, WALL_H, 2),
                meshMat(this.THREE, 0xbdebf2, FLOOR_BACK_WALL_OPACITY)
            );
            backWall.position.set(footprint.centerX, wallCY, footprint.minZ + 1);
            backWall.renderOrder = WALL_RENDER_ORDER;
            this._applyFloorGradientMaterial(backWall.material, floor);
            fg.add(backWall);

            const leftWall = new THREE.Mesh(
                new THREE.BoxGeometry(2, WALL_H, footprint.depth),
                meshMat(this.THREE, 0xbdebf2, FLOOR_SIDE_WALL_OPACITY)
            );
            leftWall.position.set(footprint.minX, wallCY, fz);
            leftWall.renderOrder = WALL_RENDER_ORDER;
            this._applyFloorGradientMaterial(leftWall.material, floor);
            fg.add(leftWall);

            const rightWall = new THREE.Mesh(
                new THREE.BoxGeometry(2, WALL_H, footprint.depth),
                meshMat(this.THREE, 0xbdebf2, FLOOR_SIDE_WALL_OPACITY)
            );
            rightWall.position.set(footprint.maxX, wallCY, fz);
            rightWall.renderOrder = WALL_RENDER_ORDER;
            this._applyFloorGradientMaterial(rightWall.material, floor);
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

            this._applyFloorGradientToGroup(fg, floor);
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
            focusFloor ? footprint.width * 0.78 : topY + buildingFootprint.width * 0.68,
            footprint.depth * 1.22
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
            // A 总览：正面居中视角，X 居中，Y 在楼层中段偏上，Z 正前方适当距离。
            // 3/4 斜俯视角：X 偏右+侧面可见，Y 高于楼顶，Z 正前方
            const centerY = topY * OVERVIEW_LOOK_Y_RATIO + OVERVIEW_LOOK_Y_OFFSET;
            const obliqueX = buildingFootprint.centerX + Math.max(OVERVIEW_THREE_QUARTER_MIN_X, buildingFootprint.width * OVERVIEW_THREE_QUARTER_X_RATIO);
            const obliqueY = topY + Math.max(OVERVIEW_CAMERA_Y_PADDING + OVERVIEW_THREE_QUARTER_Y_PADDING, buildingFootprint.width * OVERVIEW_THREE_QUARTER_HEIGHT_RATIO);
            const obliqueZ = Math.max(OVERVIEW_CAMERA_Z, buildingFootprint.maxZ + 250) + Math.max(OVERVIEW_THREE_QUARTER_Z_PADDING, buildingFootprint.depth * OVERVIEW_THREE_QUARTER_DEPTH_RATIO);
            this._camTarget.pos.set(obliqueX, obliqueY, obliqueZ);
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
            const floor = this._lastFrame?.floors.find(fl => fl.floor_id === floorId);
            const gradient = this._floorGradientDisplay(floor);
            fg.visible = this.mode !== 'focus' || this.focusFloorId == null || floorId === this.focusFloorId;
            fg.position.x = 0;
            fg.position.z = gradient.zOffset;
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

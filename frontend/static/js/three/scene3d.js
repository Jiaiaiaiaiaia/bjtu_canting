// scene3d.js — 3D 核心 + 对外 facade（spec §2/§4）
//
// 本文件是 3D 的 CORE：renderer / scene / camera / 动画循环 / 场景切换，
// 并对外**仅**暴露 `window.CanteenApp3D = { init, render, dispose }`。
// 拆分后的职责委派：
//   - 单食堂多层场景构建 + A+C 相机状态机 → canteen_scene.js (CanteenScene)
//   - 离散 snapshot → 连续插值目标             → state_adapter.js (StateAdapter)
//   - 右侧三段运维台 + 窗口干预 API 出口        → intervention_ui.js (InterventionUI)
//
// 不变量（契约测试断言，勿删 token）：
//   - `import * as THREE from 'three'` / OrbitControls import 保留。
//   - `window.CanteenApp3D = {` + `init(container)` + `render(snapshot, appState)`
//     + `dispose()` 保留；campus 路径的 `visibleCanteens` / `pendingCanteens`
//     处理保留。
//   - 无 WebGL 兜底：`let webglAvailable = true;` / `webglAvailable = false;` /
//     `if (!webglAvailable || !renderer || !contentGroup) {` /
//     `showFallback(document.getElementById('three-stage'));` / `return;` 保留。

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { SceneFX } from './scene_fx.js';
import { ImmersiveUI } from './immersive_ui.js';
import { StateAdapter } from './state_adapter.js';
import { CanteenScene } from './canteen_scene.js';
import { InterventionUI } from './intervention_ui.js';

let containerEl = null;
let renderer = null;
let sceneFX = null;
let immersiveUI = null;
let sceneApi = null;
let scene = null;
let camera = null;
let controls = null;
let contentGroup = null;
let webglAvailable = true;

// 拆分后的协作单元（单食堂 3D 主体验）
let stateAdapter = null;
let canteenScene = null;
let interventionUI = null;
let raycaster = null;
const pointer = new THREE.Vector2();
let lastAppState = null;

function init(container) {
    if (!container) return;
    if (!webglAvailable) {
        showFallback(container);
        return;
    }
    if (containerEl === container && renderer) {
        resize();
        return;
    }
    dispose();
    containerEl = container;
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07111d);

    camera = new THREE.PerspectiveCamera(48, 16 / 9, 0.1, 4000);
    camera.position.set(260, 260, 520);

    try {
        renderer = new THREE.WebGLRenderer({
            antialias: true,
            preserveDrawingBuffer: true,
        });
    } catch (err) {
        webglAvailable = false;
        showFallback(container);
        scene = null;
        camera = null;
        controls = null;
        contentGroup = null;
        return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    scene.fog = new THREE.Fog(0x07111d, 520, 2200);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(160, 0, 120);

    const hemi = new THREE.HemisphereLight(0xeef6f4, 0x1c2b3c, 2.1);
    scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xffffff, 2.4);
    sun.position.set(160, 420, 260);
    sun.castShadow = true;
    scene.add(sun);
    const teal = new THREE.PointLight(0x52d6d1, 1.2, 800);
    teal.position.set(160, 180, 120);
    scene.add(teal);

    const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(640, 460),
        new THREE.MeshStandardMaterial({ color: 0x123044, roughness: 0.92 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(160, -2, 120);
    scene.add(floor);

    const grid = new THREE.GridHelper(640, 32, 0x2dd4bf, 0x315467);
    grid.position.set(160, 0, 120);
    scene.add(grid);

    contentGroup = new THREE.Group();
    scene.add(contentGroup);

    // 委派单元装配（facade 内部，对外不可见）
    stateAdapter = new StateAdapter();
    canteenScene = new CanteenScene(THREE, scene, camera, controls);
    interventionUI = new InterventionUI();
    interventionUI.mount(container);
    // 干预 API 回包 → 立即用返回 snapshot 刷新一帧（不等下一 step）。
    interventionUI.onSnapshot = snapshot => {
        if (snapshot && lastAppState) render(snapshot, lastAppState);
    };

    raycaster = new THREE.Raycaster();
    renderer.domElement.addEventListener('pointerdown', onPointerDown);

    sceneFX = new SceneFX();
    sceneFX.mount(renderer, scene, camera);

    immersiveUI = new ImmersiveUI();
    immersiveUI.mount(container);
    sceneApi = {
        focusFloor(id) { canteenScene?.focusFloor?.(id); },
        resetView()    { canteenScene?.resetView?.(); },
        resetCamera()  { canteenScene?.resetView?.(); },
        setCutaway(b)  {
            if (!canteenScene) return;
            canteenScene.cutaway = !!b;
            if (canteenScene.lastFrame) canteenScene.update(canteenScene.lastFrame);
        },
        setHeat(b)     {
            if (!canteenScene) return;
            canteenScene.heatMode = !!b;
            if (canteenScene.lastFrame) canteenScene.update(canteenScene.lastFrame);
        },
    };

    resize();
    animate();
}

// 点选：命中楼层/学生 → 进 FOCUS / 点名追踪；空白 → 回 A 总览。
function onPointerDown(event) {
    if (!canteenScene || !renderer || !camera) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(canteenScene.group.children, true);
    const hit = hits.find(h => h.object?.userData?.kind);
    if (!hit) {
        canteenScene.resetView();
        return;
    }
    const data = hit.object.userData;
    if (data.kind === 'student') {
        canteenScene.trackStudent(data.studentId);
        canteenScene.focusFloor(data.floorId);
    } else if (data.floorId != null) {
        canteenScene.focusFloor(data.floorId);
    }
}

function resize() {
    if (!containerEl || !renderer || !camera) return;
    const width = Math.max(1, containerEl.clientWidth || 960);
    const height = Math.max(1, containerEl.clientHeight || 560);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (sceneFX) sceneFX.setSize(width, height);
}

function showFallback(container) {
    if (!container) return;
    container.innerHTML = '<div class="three-fallback">当前环境无法创建 WebGL 上下文，已保留 2D 视图。</div>';
}

function animate() {
    if (!renderer || !scene || !camera) return;
    requestAnimationFrame(animate);
    // 单食堂 FOCUS/总览相机与楼层滑开动画由 CanteenScene 推进（位置已由
    // StateAdapter 插值，这里只推进相机/层位移逼近）。
    if (canteenScene && lastAppState?.view === 'canteen') {
        canteenScene.tick();
    }
    if (controls) controls.update();
    sceneFX ? sceneFX.render() : renderer.render(scene, camera);
}

function clearContent() {
    if (!contentGroup) return;
    while (contentGroup.children.length) {
        const child = contentGroup.children.pop();
        child.traverse?.(node => {
            node.geometry?.dispose?.();
            if (Array.isArray(node.material)) {
                node.material.forEach(m => m.dispose?.());
            } else {
                node.material?.dispose?.();
            }
        });
    }
}

function material(color, options = {}) {
    return new THREE.MeshStandardMaterial({
        color,
        roughness: 0.72,
        metalness: 0.04,
        transparent: Boolean(options.opacity),
        opacity: options.opacity ?? 1,
    });
}

// campus 多食堂总览路径保留（含 visibleCanteens / pendingCanteens 处理），
// 旧校园联合演示/手动入口仍可用；单食堂 3D 主体验走 renderCanteen 委派。
function markerEntries(snapshot, appState) {
    const runtime = snapshot?.canteens || {};
    const visibleCanteens = Array.isArray(appState?.visibleCanteens)
        ? appState.visibleCanteens
        : [];
    const pendingCanteens = new Set(appState?.pendingCanteens || []);
    const entries = [];
    const seen = new Set();

    visibleCanteens.forEach(item => {
        if (!item || !item.id) return;
        const live = runtime[item.id];
        entries.push([item.id, {
            ...item,
            ...(live || {}),
            pending: !live && (
                item.runtime_included === false ||
                item.data_status === 'missing' ||
                pendingCanteens.has(item.id)
            ),
        }]);
        seen.add(item.id);
    });

    Object.entries(runtime).forEach(([id, canteen]) => {
        if (!seen.has(id)) entries.push([id, { ...canteen, pending: false }]);
    });
    return entries;
}

function addLabel(text, x, y, z, color = '#eef6f4') {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = color;
    ctx.font = '24px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(text, 128, 38);
    const texture = new THREE.CanvasTexture(canvas);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true }));
    sprite.position.set(x, y, z);
    sprite.scale.set(80, 20, 1);
    contentGroup.add(sprite);
}

function renderCampus(snapshot, appState) {
    markerEntries(snapshot, appState).forEach(([id, canteen]) => {
        const pos = canteen.campus_position;
        if (!pos) return;
        const pending = Boolean(canteen.pending);
        const height = pending ? 18 : 32 + Math.min(34, queueLength(canteen));
        const mesh = new THREE.Mesh(
            new THREE.BoxGeometry(54, height, 42),
            material(pending ? 0xb7bdc7 : 0xd64a55, pending ? { opacity: 0.42 } : {})
        );
        mesh.position.set(pos.x, height / 2, pos.y);
        mesh.castShadow = true;
        mesh.userData = { id, pending };
        contentGroup.add(mesh);
        addLabel(
            `${canteen.display_name || id}${pending ? ' 待补' : ''}`,
            pos.x,
            height + 18,
            pos.y,
            pending ? '#e7bd63' : '#eef6f4'
        );
    });

    (snapshot.in_transit || []).forEach(item => {
        const from = item.from_canteen_id
            ? snapshot.canteens?.[item.from_canteen_id]?.campus_position
            : { x: 0, y: 0 };
        const to = snapshot.canteens?.[item.to_canteen_id]?.campus_position;
        if (!from || !to) return;
        const progress = Math.max(0, Math.min(1, item.progress || 0));
        const dot = new THREE.Mesh(
            new THREE.SphereGeometry(5, 16, 12),
            material(0x52d6d1)
        );
        dot.position.set(
            from.x + (to.x - from.x) * progress,
            9,
            from.y + (to.y - from.y) * progress
        );
        contentGroup.add(dot);
    });
}

function queueLength(canteen) {
    const windowQueue = (canteen.windows || [])
        .reduce((sum, win) => sum + (win.queue_length || 0), 0);
    return windowQueue + (canteen.waiting_queue_length || 0);
}

// 单食堂 3D 主体验：委派给 StateAdapter（插值）+ CanteenScene（多层/相机）
// + InterventionUI（三段运维台 + 窗口干预 API）。
function renderCanteen(snapshot, appState) {
    if (!stateAdapter || !canteenScene) return;
    const frame = stateAdapter.buildFrame(snapshot, appState || {});
    if (!frame) return;
    canteenScene.update(frame);
    if (immersiveUI) immersiveUI.update(frame, sceneApi);
    if (interventionUI) {
        interventionUI.render(frame, canteenScene.mode, canteenScene.focusFloorId);
    }
}

function render(snapshot, appState) {
    if (!renderer) init(document.getElementById('three-stage'));
    if (!webglAvailable || !renderer || !contentGroup) {
        showFallback(document.getElementById('three-stage'));
        return;
    }
    lastAppState = appState || {};
    if (appState?.view === 'canteen') {
        // 单食堂场景由 CanteenScene 自管其 group；core 的 contentGroup 清空，
        // 避免 campus 残留叠加。
        clearContent();
        renderCanteen(snapshot, appState || {});
    } else {
        clearContent();
        if (canteenScene) canteenScene.clearScene();
        renderCampus(snapshot, appState || {});
        immersiveUI?.update?.(null, sceneApi);
    }
    resize();
}

function dispose() {
    immersiveUI?.dispose?.(); immersiveUI = null;
    if (interventionUI) interventionUI.dispose();
    if (canteenScene) canteenScene.dispose();
    if (renderer) {
        renderer.domElement?.removeEventListener?.('pointerdown', onPointerDown);
        renderer.dispose();
        renderer.domElement?.remove();
    }
    renderer = null;
    scene = null;
    camera = null;
    controls = null;
    contentGroup = null;
    stateAdapter = null;
    canteenScene = null;
    interventionUI = null;
    raycaster = null;
    lastAppState = null;
    sceneApi = null;
    if (sceneFX) { sceneFX.dispose(); sceneFX = null; }
}

window.addEventListener('resize', resize);

window.CanteenApp3D = {
    init(container) {
        init(container);
    },
    render(snapshot, appState) {
        render(snapshot, appState);
    },
    dispose() {
        dispose();
    },
};

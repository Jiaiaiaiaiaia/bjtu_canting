import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let containerEl = null;
let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let contentGroup = null;

function init(container) {
    if (!container) return;
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
        showFallback(container);
        scene = null;
        camera = null;
        controls = null;
        contentGroup = null;
        return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(160, 0, 120);

    const hemi = new THREE.HemisphereLight(0xeef6f4, 0x1c2b3c, 2.1);
    scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xffffff, 2.4);
    sun.position.set(160, 420, 260);
    sun.castShadow = true;
    scene.add(sun);

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
    resize();
    animate();
}

function resize() {
    if (!containerEl || !renderer || !camera) return;
    const width = Math.max(1, containerEl.clientWidth || 960);
    const height = Math.max(1, containerEl.clientHeight || 560);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
}

function showFallback(container) {
    container.innerHTML = '<div class="three-fallback">当前环境无法创建 WebGL 上下文，已保留 2D 视图。</div>';
}

function animate() {
    if (!renderer || !scene || !camera) return;
    requestAnimationFrame(animate);
    if (controls) controls.update();
    renderer.render(scene, camera);
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

function renderCanteen(snapshot, appState) {
    const canteen = snapshot?.canteens?.[appState?.activeCanteenId]
        || Object.values(snapshot?.canteens || {})[0];
    if (!canteen) return;
    addLabel(canteen.display_name || appState.activeCanteenId || '食堂', 160, 70, -40);

    const floors = canteen.floors || [{ floor_id: 1, windows: canteen.windows, seats: canteen.seats }];
    floors.forEach((floor, floorIndex) => {
        const z = floorIndex * 74;
        const deck = new THREE.Mesh(
            new THREE.BoxGeometry(260, 4, 54),
            material(0x26394d)
        );
        deck.position.set(160, floorIndex * 34, z);
        contentGroup.add(deck);

        (floor.windows || []).forEach((win, idx) => {
            const stall = new THREE.Mesh(
                new THREE.BoxGeometry(18, 20, 18),
                material(win.is_serving ? 0xd64a55 : 0x94a8b5)
            );
            stall.position.set(52 + idx * 26, floorIndex * 34 + 14, z - 18);
            contentGroup.add(stall);
        });

        (floor.seats || []).slice(0, 90).forEach((seat, idx) => {
            const seatMesh = new THREE.Mesh(
                new THREE.BoxGeometry(8, 4, 8),
                material(seat.status === 'occupied' ? 0xe7bd63 : 0x77d993)
            );
            seatMesh.position.set(
                52 + (idx % 18) * 12,
                floorIndex * 34 + 7,
                z + 2 + Math.floor(idx / 18) * 10
            );
            contentGroup.add(seatMesh);
        });

        (floor.students || []).slice(0, 80).forEach((student, idx) => {
            const dot = new THREE.Mesh(
                new THREE.SphereGeometry(3.6, 12, 8),
                material(student.position === 'waiting_queue' ? 0x9333ea : 0x52d6d1)
            );
            dot.position.set(
                52 + (idx % 20) * 10,
                floorIndex * 34 + 13,
                z + 48 + Math.floor(idx / 20) * 8
            );
            contentGroup.add(dot);
        });
    });
}

function render(snapshot, appState) {
    if (!renderer) init(document.getElementById('three-stage'));
    clearContent();
    if (appState?.view === 'canteen') {
        renderCanteen(snapshot, appState || {});
    } else {
        renderCampus(snapshot, appState || {});
    }
    resize();
}

function dispose() {
    if (renderer) {
        renderer.dispose();
        renderer.domElement?.remove();
    }
    renderer = null;
    scene = null;
    camera = null;
    controls = null;
    contentGroup = null;
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

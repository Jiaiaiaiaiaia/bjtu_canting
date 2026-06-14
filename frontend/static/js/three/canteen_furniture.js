// canteen_furniture.js — THREE-injected material and furniture builders.

import {
    PALETTE, mixedChairPalette, CHAIR_DX, CHAIR_DZ, FLOOR_TABLE_COLOR_FALLBACKS,
} from "./canteen_layouts.js";

export function chairVariant(side, idx) {
    if (side === 'bench') return 'bench';
    if (idx % 6 === 2) return 'round-stool';
    if (idx % 4 === 1) return 'open-back';
    return 'standard';
}

export function meshMat(THREE, color, opacity, emissive, emissiveIntensity) {
    return new THREE.MeshStandardMaterial({
        color,
        roughness: 0.72,
        metalness: 0.04,
        transparent: opacity != null,
        opacity: opacity == null ? 1 : opacity,
        // translucent surfaces must not write depth: a depth-writing translucent
        // box culls whole objects behind it whenever the per-frame distance sort
        // flips, which reads as orbit-dependent popping/flicker.
        depthWrite: opacity == null || opacity >= 0.98,
        emissive: emissive != null ? emissive : 0x000000,
        emissiveIntensity: emissiveIntensity != null ? emissiveIntensity : 0,
    });
}

export function photoMat(THREE, color, options = {}) {
    return new THREE.MeshStandardMaterial({
        color,
        roughness: options.roughness ?? 0.55,
        metalness: options.metalness ?? 0.03,
        transparent: options.opacity != null,
        opacity: options.opacity ?? 1,
        depthWrite: options.opacity == null || options.opacity >= 0.98,
        emissive: options.emissive ?? 0x000000,
        emissiveIntensity: options.emissiveIntensity ?? 0,
    });
}

export function addBox(THREE, group, name, size, pos, mat, userData) {
    const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(size[0], size[1], size[2]),
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

// 拥堵热力青→琥珀→红（按队列饱和度 0..1）。
export function heatColor(THREE, t) {
    const x = Math.max(0, Math.min(1, t));
    const teal = new THREE.Color(0x2dd4bf);
    const amber = new THREE.Color(0xe7bd63);
    const red = new THREE.Color(0xd64a55);
    return x < 0.5
        ? teal.clone().lerp(amber, x / 0.5)
        : amber.clone().lerp(red, (x - 0.5) / 0.5);
}

export function addChairOccupancyMarker(THREE, group, x, y, z) {
    const chairOccupancyMarker = new THREE.Mesh(
        new THREE.CylinderGeometry(5.5, 5.5, 0.4, 14),
        photoMat(THREE, PALETTE.seatOccupied, {
            emissive: PALETTE.seatOccupied,
            emissiveIntensity: 0.12,
            opacity: 0.65,
        })
    );
    chairOccupancyMarker.name = 'chairOccupancyMarker';
    chairOccupancyMarker.position.set(x, y, z);
    group.add(chairOccupancyMarker);
}

export function addChair(THREE, group, x, y, z, color, side, occupied, idx = 0) {
    const variant = chairVariant(side, idx);
    const mat = photoMat(THREE, color, {
        roughness: 0.48,
        emissive: occupied ? color : 0x000000,
        emissiveIntensity: occupied ? 0.04 : 0,
    });
    const seatSize = variant === 'round-stool' ? [3.4, 1.7, 3.4] : [3.6, 1.8, 3.2];
    addBox(THREE, group, `mixed photo ${variant} chair seat`, seatSize,
        [x, y, z], mat);
    if (variant === 'round-stool') return;
    const backOffset = 2.4;
    const isX = side === 'left' || side === 'right';
    const bx = x + (side === 'left' ? -backOffset : side === 'right' ? backOffset : 0);
    const bz = z + (side === 'front' ? backOffset : side === 'back' ? -backOffset : 0);
    const backHeight = variant === 'open-back' ? 3.8 : 5.0;
    addBox(THREE, group, `mixed photo ${variant} chair back`,
        isX ? [0.7, backHeight, 3.4] : [3.4, backHeight, 0.7],
        [bx, y + 3.4, bz],
        mat);
}

export function addSquareTableCluster(THREE, group, x, baseY, z, idx, occupied, tableColor) {
    const woodTableTop = addBox(THREE,
        group,
        'woodTableTop square four-seat table',
        [17.5, 1.8, 7.5],
        [x, baseY + 6.6, z],
        photoMat(THREE, tableColor || FLOOR_TABLE_COLOR_FALLBACKS.square, {
            roughness: 0.32,
            emissive: occupied ? 0xe7bd63 : 0x000000,
            emissiveIntensity: occupied ? 0.05 : 0,
        })
    );
    void woodTableTop;
    addBox(THREE, group, 'dark table pedestal', [2.0, 4.6, 2.0],
        [x, baseY + 4.0, z],
        photoMat(THREE, 0x33404a, { roughness: 0.44 })
    );

    const colors = mixedChairPalette;
    addChair(THREE, group, x - CHAIR_DX, baseY + 5.1, z, colors[idx % colors.length], 'left', occupied, idx);
    addChair(THREE, group, x + CHAIR_DX, baseY + 5.1, z, colors[(idx + 1) % colors.length], 'right', occupied, idx + 1);
    addChair(THREE, group, x, baseY + 5.1, z + CHAIR_DZ, colors[(idx + 2) % colors.length], 'front', occupied, idx + 2);
    addChair(THREE, group, x, baseY + 5.1, z - CHAIR_DZ, colors[(idx + 3) % colors.length], 'back', occupied, idx + 3);
}

export function addLongTableCluster(THREE, group, x, baseY, z, idx, occupied, tableColor) {
    addBox(THREE, group, 'woodTableTop long communal table', [31, 1.8, 8.5],
        [x, baseY + 6.6, z],
        photoMat(THREE, tableColor || FLOOR_TABLE_COLOR_FALLBACKS.long, {
            roughness: 0.34,
            emissive: occupied ? 0xe7bd63 : 0x000000,
            emissiveIntensity: occupied ? 0.05 : 0,
        })
    );
    [-8, 8].forEach(offset => {
        addBox(THREE, group, 'dark communal table pedestal', [1.8, 4.4, 1.8],
            [x + offset, baseY + 4.0, z],
            photoMat(THREE, 0x33404a, { roughness: 0.44 })
        );
    });

    const colors = mixedChairPalette;
    [-12, 0, 12].forEach((offset, chairIdx) => {
        addChair(THREE, group, x + offset, baseY + 5.1, z + CHAIR_DZ,
            colors[(idx + chairIdx) % colors.length], 'front', occupied, idx + chairIdx);
        addChair(THREE, group, x + offset, baseY + 5.1, z - CHAIR_DZ,
            colors[(idx + chairIdx + 2) % colors.length], 'back', occupied, idx + chairIdx + 3);
    });
}

export function addBoothTableCluster(THREE, group, x, baseY, z, idx, occupied, tableColor) {
    addBox(THREE, group, 'woodTableTop booth table', [20, 1.6, 6.5],
        [x, baseY + 6.4, z],
        photoMat(THREE, tableColor || FLOOR_TABLE_COLOR_FALLBACKS.booth, {
            roughness: 0.34,
            emissive: occupied ? 0xe7bd63 : 0x000000,
            emissiveIntensity: occupied ? 0.05 : 0,
        })
    );
    addBox(THREE, group, 'booth bench seat', [24, 4.2, 3.2],
        [x, baseY + 5.2, z + 8.4],
        photoMat(THREE, 0x6b4f39, { roughness: 0.34 })
    );
    addBox(THREE, group, 'booth bench seat', [24, 4.2, 3.2],
        [x, baseY + 5.2, z - 8.4],
        photoMat(THREE, 0x6b4f39, { roughness: 0.34 })
    );

    const colors = mixedChairPalette;
    addChair(THREE, group, x - CHAIR_DX, baseY + 5.1, z, colors[idx % colors.length], 'left', occupied, idx);
    addChair(THREE, group, x + CHAIR_DX, baseY + 5.1, z, colors[(idx + 1) % colors.length], 'right', occupied, idx + 1);
}

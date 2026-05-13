// ================================== Campus SVG 总览地图
(function() {
    const App = window.CanteenApp = window.CanteenApp || {};
    const SVG_NS = 'http://www.w3.org/2000/svg';
    let svgInited = false;
    let lastMarkerSignature = null;

    function createSvgEl(tag, attrs) {
        const el = document.createElementNS(SVG_NS, tag);
        Object.entries(attrs || {}).forEach(([key, value]) => {
            el.setAttribute(key, value);
        });
        return el;
    }

    function ensureSvg() {
        return document.getElementById('campus-map-svg');
    }

    function ensureLayer(id) {
        const svg = ensureSvg();
        if (!svg) return null;
        let layer = document.getElementById(id);
        if (!layer) {
            layer = createSvgEl('g', { id });
            svg.appendChild(layer);
        }
        return layer;
    }

    function markerEntries(snapshot) {
        const runtime = snapshot?.canteens || {};
        const visible = Array.isArray(App.state?.visibleCanteens)
            ? App.state.visibleCanteens
            : [];
        const pending = new Set(App.state?.pendingCanteens || []);
        const entries = [];
        const seen = new Set();

        visible.forEach(item => {
            if (!item || !item.id) return;
            const live = runtime[item.id];
            const marker = { ...item, ...(live || {}) };
            marker.runtime_included = Boolean(live) || item.runtime_included !== false;
            marker.pending_marker = !live && (
                item.runtime_included === false ||
                item.data_status === 'missing' ||
                pending.has(item.id)
            );
            entries.push([item.id, marker]);
            seen.add(item.id);
        });

        Object.entries(runtime).forEach(([cid, canteen]) => {
            if (seen.has(cid)) return;
            entries.push([cid, {
                ...canteen,
                runtime_included: true,
                pending_marker: false,
            }]);
        });

        return entries;
    }

    function markerSignature(entries) {
        return (entries || [])
            .map(([cid, canteen]) => {
                const pos = canteen.campus_position || {};
                return [
                    cid,
                    canteen.display_name || '',
                    pos.x ?? '',
                    pos.y ?? '',
                    canteen.pending_marker ? 'pending' : 'runtime',
                ].join(':');
            })
            .sort()
            .join('|');
    }

    function clearMarkerNodes(svg) {
        if (!svg) return;
        if (typeof svg.querySelectorAll === 'function') {
            svg.querySelectorAll('.canteen-marker').forEach(node => node.remove());
            return;
        }
        if (Array.isArray(svg.children)) {
            svg.children = svg.children.filter(
                child => child?.attrs?.class !== 'canteen-marker'
            );
        }
    }

    function initSvg(entries) {
        const svg = ensureSvg();
        if (!svg) return;
        svg.setAttribute('viewBox', '-50 -50 500 400');

        for (const [cid, c] of entries || []) {
            if (!c.campus_position) continue;
            const isPending = Boolean(c.pending_marker);
            const g = createSvgEl('g', {
                class: 'canteen-marker',
                'data-cid': cid,
                'data-pending': isPending ? 'true' : 'false',
                'data-runtime-included': c.runtime_included ? 'true' : 'false',
            });
            const rect = createSvgEl('rect', {
                x: c.campus_position.x - 25,
                y: c.campus_position.y - 25,
                width: 50,
                height: 50,
                rx: 6,
                fill: isPending ? '#e5e7eb' : '#f8fafc',
                stroke: isPending ? '#f59e0b' : '#64748b',
                'stroke-width': 1.5,
                opacity: isPending ? 0.45 : 1,
            });
            if (isPending) {
                rect.setAttribute('stroke-dasharray', '4 3');
            }
            const label = createSvgEl('text', {
                x: c.campus_position.x,
                y: c.campus_position.y + 5,
                'text-anchor': 'middle',
                'font-size': 12,
                fill: '#0f172a',
            });
            label.textContent = isPending
                ? `${c.display_name || cid} 待补`
                : (c.display_name || cid);
            g.appendChild(rect);
            g.appendChild(label);
            if (!isPending) {
                g.addEventListener('click', () => {
                    App.state.view = 'canteen';
                    App.state.activeCanteenId = cid;
                    App.state.activeFloorId = null;
                    if (App.applyViewState) App.applyViewState();
                    if (App.state.lastData && App.refreshCampusView) {
                        App.refreshCampusView(App.state.lastData);
                    }
                });
            }
            svg.appendChild(g);
        }
        lastMarkerSignature = markerSignature(entries);
        svgInited = true;
    }

    function queueLength(canteen) {
        const windowQueue = (canteen.windows || [])
            .reduce((sum, w) => sum + (w.queue_length || 0), 0);
        return windowQueue + (canteen.waiting_queue_length || 0);
    }

    function renderCampusMap(snapshot) {
        const svg = ensureSvg();
        if (!svg || !snapshot) return;
        const entries = markerEntries(snapshot);
        const signature = markerSignature(entries);
        if (signature !== lastMarkerSignature) {
            clearMarkerNodes(svg);
            svgInited = false;
        }
        if (!svgInited) initSvg(entries);

        for (const cid in snapshot.canteens || {}) {
            const c = snapshot.canteens[cid];
            const intensity = Math.min(1, queueLength(c) / 50);
            const color = `rgb(239, ${Math.floor(120 - 60 * intensity)}, 68)`;
            const rect = document.querySelector(
                `.canteen-marker[data-cid="${cid}"] rect`
            );
            if (rect) rect.setAttribute('fill', color);
        }
        renderInTransitDots(snapshot);
    }

    function renderInTransitDots(snapshot) {
        const layer = ensureLayer('transit-layer');
        if (!layer) return;
        layer.innerHTML = '';
        for (const t of snapshot.in_transit || []) {
            const from = t.from_canteen_id
                ? snapshot.canteens[t.from_canteen_id]?.campus_position
                : { x: 0, y: 0 };
            const to = snapshot.canteens[t.to_canteen_id]?.campus_position;
            if (!from || !to) continue;
            const progress = Math.max(0, Math.min(1, t.progress || 0));
            const x = from.x + (to.x - from.x) * progress;
            const y = from.y + (to.y - from.y) * progress;
            const dot = createSvgEl('circle', {
                cx: x,
                cy: y,
                r: 3,
                fill: '#9333ea',
            });
            layer.appendChild(dot);
        }
    }

    App.createSvgEl = createSvgEl;
    App.markerEntries = markerEntries;
    App.renderCampusMap = renderCampusMap;
    App.renderInTransitDots = renderInTransitDots;
})();

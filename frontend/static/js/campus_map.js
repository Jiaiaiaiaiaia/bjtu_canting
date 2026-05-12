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

    function markerSignature(canteens) {
        return Object.entries(canteens || {})
            .map(([cid, canteen]) => {
                const pos = canteen.campus_position || {};
                return [
                    cid,
                    canteen.display_name || '',
                    pos.x ?? '',
                    pos.y ?? '',
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

    function initSvg(canteens) {
        const svg = ensureSvg();
        if (!svg) return;
        svg.setAttribute('viewBox', '-50 -50 500 400');

        for (const cid in canteens || {}) {
            const c = canteens[cid];
            if (!c.campus_position) continue;
            const g = createSvgEl('g', {
                class: 'canteen-marker',
                'data-cid': cid,
            });
            const rect = createSvgEl('rect', {
                x: c.campus_position.x - 25,
                y: c.campus_position.y - 25,
                width: 50,
                height: 50,
                rx: 6,
                fill: '#f8fafc',
                stroke: '#64748b',
                'stroke-width': 1.5,
            });
            const label = createSvgEl('text', {
                x: c.campus_position.x,
                y: c.campus_position.y + 5,
                'text-anchor': 'middle',
                'font-size': 12,
                fill: '#0f172a',
            });
            label.textContent = c.display_name || cid;
            g.appendChild(rect);
            g.appendChild(label);
            g.addEventListener('click', () => {
                App.state.view = 'canteen';
                App.state.activeCanteenId = cid;
                App.state.activeFloorId = null;
                if (App.applyViewState) App.applyViewState();
                if (App.state.lastData && App.refreshCampusView) {
                    App.refreshCampusView(App.state.lastData);
                }
            });
            svg.appendChild(g);
        }
        lastMarkerSignature = markerSignature(canteens);
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
        const signature = markerSignature(snapshot.canteens || {});
        if (signature !== lastMarkerSignature) {
            clearMarkerNodes(svg);
            svgInited = false;
        }
        if (!svgInited) initSvg(snapshot.canteens || {});

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
    App.renderCampusMap = renderCampusMap;
    App.renderInTransitDots = renderInTransitDots;
})();

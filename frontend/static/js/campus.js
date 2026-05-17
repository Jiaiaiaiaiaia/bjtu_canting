// ================================== Campus 食堂下钻层
(function() {
    const App = window.CanteenApp = window.CanteenApp || {};
    let lastCanteenOrderKey = null;
    let canteenSelectBound = false;

    function state() {
        return App.state || {};
    }

    function byId(id) {
        return document.getElementById(id);
    }

    function bindCanteenSelect(sel) {
        if (!sel || canteenSelectBound) return;
        sel.addEventListener('change', e => {
            state().activeCanteenId = e.target.value;
            state().activeFloorId = null;
            if (state().lastData) refreshCampusView(state().lastData);
        });
        canteenSelectBound = true;
    }

    function canteenOrderOf(canteenOrder, canteens) {
        if (Array.isArray(canteenOrder) && canteenOrder.length) return canteenOrder;
        return Object.keys(canteens || {});
    }

    function fillCanteenSelect(canteenOrder, canteens) {
        const order = canteenOrderOf(canteenOrder, canteens);
        if (!state().activeCanteenId && order.length > 0) {
            state().activeCanteenId = order[0];
        }

        const sel = byId('active-canteen-select');
        if (!sel) return;
        bindCanteenSelect(sel);

        const orderKey = order.join(',');
        if (orderKey === lastCanteenOrderKey) {
            if (state().activeCanteenId) sel.value = state().activeCanteenId;
            return;
        }
        lastCanteenOrderKey = orderKey;

        const prevSelected = sel.value || state().activeCanteenId;
        sel.innerHTML = '';
        for (const cid of order) {
            const opt = document.createElement('option');
            opt.value = cid;
            opt.textContent = canteens?.[cid]?.display_name || cid;
            sel.appendChild(opt);
        }

        if (order.includes(prevSelected)) {
            sel.value = prevSelected;
        } else if (order.length > 0) {
            sel.value = order[0];
        }
        state().activeCanteenId = sel.value || state().activeCanteenId || null;
    }

    function pickCanteenView(snapshot) {
        if (!snapshot || !snapshot.canteens) return null;
        const order = canteenOrderOf(snapshot.canteen_order, snapshot.canteens);
        if (!state().activeCanteenId && order.length > 0) {
            state().activeCanteenId = order[0];
        }
        return state().activeCanteenId
            ? snapshot.canteens[state().activeCanteenId]
            : null;
    }

    function refreshCampusView(snapshot) {
        if (!snapshot) return;

        const order = canteenOrderOf(snapshot.canteen_order, snapshot.canteens);
        state().canteenOrder = order;

        if (state().view === 'canteen') {
            fillCanteenSelect(order, snapshot.canteens || {});
            const canteenView = pickCanteenView(snapshot);
            if (!canteenView) {
                console.warn('activeCanteenId not in snapshot:', state().activeCanteenId);
                updateCampusOverview(snapshot);
                return;
            }

            if (App.renderFloorTabs) App.renderFloorTabs(canteenView);
            const filteredView = filterByFloor(canteenView, state().activeFloorId);
            if (App.drawCanteen) App.drawCanteen(filteredView);
            if (App.updateInfoPanel) App.updateInfoPanel(filteredView);
        }

        updateCampusOverview(snapshot);
    }

    function filterByFloor(canteenView, activeFloorId) {
        if (activeFloorId == null) return canteenView;
        const floorBlock = (canteenView.floors || [])
            .find(f => String(f.floor_id) === String(activeFloorId));
        if (!floorBlock) return canteenView;

        return {
            ...canteenView,
            windows: floorBlock.windows,
            seats: floorBlock.seats,
            students: floorBlock.students,
        };
    }

    function setText(id, value) {
        const node = byId(id);
        if (node) node.textContent = String(value);
    }

    function updateCampusOverview(snapshot) {
        const t = snapshot?.campus_totals || {};
        setText('campus-total-arrived', t.total_arrived ?? 0);
        setText('campus-total-served', t.total_served ?? 0);
        setText('campus-in-transit', t.total_in_transit ?? 0);
        setText('campus-total-switches', t.total_switches ?? 0);
        const avgWaiting = Number(t.avg_waiting_time || 0);
        setText('campus-avg-waiting', `${avgWaiting.toFixed(1)} s`);
    }

    bindCanteenSelect(byId('active-canteen-select'));

    App.refreshCampusView = refreshCampusView;
    App.fillCanteenSelect = fillCanteenSelect;
    App.pickCanteenView = pickCanteenView;
    App.filterByFloor = filterByFloor;
    App.updateCampusOverview = updateCampusOverview;
})();

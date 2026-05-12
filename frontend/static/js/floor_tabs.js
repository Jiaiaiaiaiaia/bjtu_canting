// ================================== Campus 楼层 Tab
(function() {
    const App = window.CanteenApp = window.CanteenApp || {};
    const lastFloorKeyByCanteen = {};

    function renderFloorTabs(canteenView) {
        const container = document.getElementById('floor-tabs');
        if (!container || !canteenView) return;

        const floors = canteenView.floors || [];
        if (floors.length <= 1) {
            container.innerHTML = '';
            App.state.activeFloorId = null;
            return;
        }

        const floorKey = floors.map(f => f.floor_id).join(',');
        if (lastFloorKeyByCanteen[canteenView.id] === floorKey) {
            syncActiveTab(container);
            return;
        }
        lastFloorKeyByCanteen[canteenView.id] = floorKey;

        container.innerHTML = '';
        container.appendChild(makeTab(null, '全楼层'));
        for (const f of floors) {
            container.appendChild(makeTab(f.floor_id, `${f.floor_id}F`));
        }
        syncActiveTab(container);
    }

    function makeTab(floorId, label) {
        const btn = document.createElement('button');
        btn.dataset.floor = floorId == null ? 'all' : String(floorId);
        btn.textContent = label;
        btn.addEventListener('click', () => {
            App.state.activeFloorId = floorId;
            document.querySelectorAll('#floor-tabs button')
                .forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (App.state.lastData && App.refreshCampusView) {
                App.refreshCampusView(App.state.lastData);
            }
        });
        return btn;
    }

    function syncActiveTab(container) {
        const activeFloor = App.state.activeFloorId == null
            ? 'all'
            : String(App.state.activeFloorId);
        const buttons = Array.from(container.children || []);
        if (!buttons.some(btn => btn.dataset.floor === activeFloor)) {
            App.state.activeFloorId = null;
        }
        const nextActive = App.state.activeFloorId == null
            ? 'all'
            : String(App.state.activeFloorId);
        buttons.forEach(btn => {
            if (btn.dataset.floor === nextActive) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    App.renderFloorTabs = renderFloorTabs;
    App.makeFloorTab = makeTab;
})();

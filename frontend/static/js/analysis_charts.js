// ================================== 数据分析图表模块
(function() {
    const App = window.CanteenApp = window.CanteenApp || {};

    function renderStatCards(s, deps) {
        const doc = deps.document;
        doc.getElementById('stat-total-arrived').textContent = s.total_arrived;
        doc.getElementById('stat-total-served').textContent = s.total_served;
        doc.getElementById('stat-avg-waiting').textContent = `${s.avg_waiting_time.toFixed(1)} s`;
        doc.getElementById('stat-avg-eating').textContent = `${(s.avg_eating_time / 60).toFixed(1)} min`;
        doc.getElementById('stat-peak').textContent = s.peak_queue_length;
        doc.getElementById('stat-seat-utilization').textContent = `${s.seat_utilization.toFixed(1)}%`;
    }

    function normalizeWindowServed(windowServed) {
        if (Array.isArray(windowServed)) {
            return windowServed.map((value, i) => ({ name: `窗口 ${i + 1}`, value }));
        }
        if (!windowServed || typeof windowServed !== 'object') return [];
        return Object.entries(windowServed).flatMap(([canteenId, values]) =>
            (values || []).map((value, i) => ({ name: `${canteenId} 窗口 ${i + 1}`, value }))
        );
    }

    function renderCharts(stats, deps) {
        const { document: doc, echarts, state } = deps;
        disposeCharts(deps);
        const windowSeries = normalizeWindowServed(stats.window_served);

        state.charts.window = echarts.init(doc.getElementById('window-chart'));
        state.charts.window.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 40, right: 20, top: 20, bottom: 30 },
            xAxis: { type: 'category', data: windowSeries.map(item => item.name) },
            yAxis: { type: 'value' },
            series: [{ type: 'bar', data: windowSeries.map(item => item.value), itemStyle: { color: '#b91c1c' } }],
        });

        state.charts.pie = echarts.init(doc.getElementById('pie-chart'));
        state.charts.pie.setOption({
            tooltip: { trigger: 'item' },
            legend: { bottom: 0 },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                data: windowSeries.map(item => ({ value: item.value, name: item.name })),
            }],
        });

        const qt = stats.queue_timeline || { x: [], y: [] };
        state.charts.queue = echarts.init(doc.getElementById('queue-chart'));
        state.charts.queue.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 40, right: 20, top: 20, bottom: 30 },
            xAxis: { type: 'category', data: qt.x.map(x => `${x}分`) },
            yAxis: { type: 'value' },
            series: [{
                type: 'line', smooth: true, data: qt.y,
                areaStyle: { color: 'rgba(255, 152, 0, 0.2)' },
                itemStyle: { color: '#ff9800' },
            }],
        });

        const st = stats.seat_util_timeline || { x: [], y: [] };
        state.charts.seat = echarts.init(doc.getElementById('seat-chart'));
        state.charts.seat.setOption({
            tooltip: { trigger: 'axis', formatter: '{b}：{c}%' },
            grid: { left: 40, right: 20, top: 20, bottom: 30 },
            xAxis: { type: 'category', data: st.x.map(x => `${x}分`) },
            yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
            series: [{
                type: 'line', smooth: true, data: st.y,
                areaStyle: { color: 'rgba(76, 175, 80, 0.25)' },
                itemStyle: { color: '#4CAF50' },
            }],
        });
    }

    function disposeCharts(deps) {
        const { state } = deps;
        Object.values(state.charts).forEach(c => c && c.dispose());
        state.charts = {};
    }

    function resizeCharts(deps) {
        const { state } = deps;
        Object.values(state.charts).forEach(c => c && c.resize());
        if (state.historyChart) state.historyChart.resize();
    }

    App.AnalysisCharts = {
        renderStatCards,
        renderCharts,
        disposeCharts,
        resizeCharts,
        normalizeWindowServed,
    };
})();

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

    function toNumber(value, fallback = 0) {
        const number = Number(value);
        return Number.isFinite(number) ? number : fallback;
    }

    function formatSeconds(seconds) {
        const value = toNumber(seconds);
        if (value >= 60) return `${(value / 60).toFixed(1)} min`;
        return `${value.toFixed(1)} s`;
    }

    function formatPercent(value) {
        return `${toNumber(value).toFixed(1)}%`;
    }

    function findPeakPoint(timeline) {
        const x = timeline && Array.isArray(timeline.x) ? timeline.x : [];
        const y = timeline && Array.isArray(timeline.y) ? timeline.y : [];
        if (!y.length) return { value: 0, timeText: '暂无数据' };

        let peakIndex = 0;
        let peakValue = toNumber(y[0]);
        y.forEach((value, index) => {
            const numeric = toNumber(value);
            if (numeric > peakValue) {
                peakValue = numeric;
                peakIndex = index;
            }
        });

        const minute = toNumber(x[peakIndex]);
        const minuteText = Number.isInteger(minute) ? String(minute) : minute.toFixed(1);
        return { value: peakValue, timeText: `${minuteText} 分` };
    }

    function buildDiagnosis(stats) {
        stats = stats || {};
        const totalArrived = toNumber(stats.total_arrived);
        const totalServed = toNumber(stats.total_served);
        const peakQueue = toNumber(stats.peak_queue_length);
        const avgWait = toNumber(stats.avg_waiting_time);
        const seatUtilization = toNumber(stats.seat_utilization);
        const peakPoint = findPeakPoint(stats.queue_timeline);

        if (totalArrived <= 0) {
            return {
                level: '待仿真',
                levelClass: 'idle',
                bottleneck: '暂无样本',
                peakTime: '暂无数据',
                action: '先完成一次仿真',
                summary: '完成仿真后生成诊断。',
            };
        }

        const waitingPressure = avgWait >= 120 || peakQueue >= 30 ? 2 : (avgWait >= 45 || peakQueue >= 10 ? 1 : 0);
        const seatPressure = seatUtilization >= 85 ? 2 : (seatUtilization >= 70 ? 1 : 0);
        const maxPressure = Math.max(waitingPressure, seatPressure);
        const unfinished = Math.max(totalArrived - totalServed, 0);

        let level = '低拥堵';
        let levelClass = 'low';
        let bottleneck = '暂无明显瓶颈';
        let action = '保持当前窗口与座位配置';

        if (maxPressure >= 2) {
            level = '高拥堵';
            levelClass = 'high';
        } else if (maxPressure === 1) {
            level = '中等拥堵';
            levelClass = 'medium';
        }

        if (waitingPressure > 0 && seatPressure > 0) {
            bottleneck = waitingPressure >= seatPressure ? '窗口排队与座位周转' : '座位周转与窗口排队';
            action = waitingPressure >= seatPressure ? '优先增开窗口，再评估座位' : '优先增加座位，再评估窗口';
        } else if (waitingPressure > 0) {
            bottleneck = '窗口排队压力';
            action = '增开窗口或缩短平均打饭时间';
        } else if (seatPressure > 0) {
            bottleneck = '座位周转压力';
            action = '增加座位或缩短平均就餐时间';
        }

        let summary = `峰值排队 ${Math.max(peakQueue, peakPoint.value)} 人，平均等待 ${formatSeconds(avgWait)}，座位利用率 ${formatPercent(seatUtilization)}。`;
        if (unfinished > 0) {
            summary += ` 仍有 ${unfinished} 人未完成服务，方案对比时建议先结束仿真。`;
        }
        if (stats.switch_rate !== undefined) {
            summary += ` 跨食堂改派率 ${formatPercent(toNumber(stats.switch_rate) * 100)}。`;
        }

        return {
            level,
            levelClass,
            bottleneck,
            peakTime: peakPoint.timeText,
            action,
            summary,
        };
    }

    function withoutPriority(item) {
        const { priority, ...publicItem } = item;
        return publicItem;
    }

    function buildInterventions(stats) {
        stats = stats || {};
        const totalArrived = toNumber(stats.total_arrived);
        const peakQueue = toNumber(stats.peak_queue_length);
        const avgWait = toNumber(stats.avg_waiting_time);
        const seatUtilization = toNumber(stats.seat_utilization);
        const switchRate = toNumber(stats.switch_rate, -1);

        if (totalArrived <= 0) {
            return [{
                title: '先完成一次仿真',
                tag: '待数据',
                impact: '完成仿真后展示可比较的调参方向。',
                tone: 'neutral',
            }];
        }

        const waitingPressure = avgWait >= 120 || peakQueue >= 30 ? 2 : (avgWait >= 45 || peakQueue >= 10 ? 1 : 0);
        const seatPressure = seatUtilization >= 85 ? 2 : (seatUtilization >= 70 ? 1 : 0);
        const interventions = [];

        if (waitingPressure > 0) {
            interventions.push({
                title: '增开服务窗口',
                tag: waitingPressure >= 2 ? '优先干预' : '备选干预',
                impact: `平均等待 ${formatSeconds(avgWait)}，峰值排队 ${peakQueue} 人；优先通过增开窗口或缩短打饭时间降低排队压力。`,
                tone: waitingPressure >= 2 ? 'high' : 'medium',
                priority: waitingPressure * 10 + (waitingPressure >= seatPressure ? 2 : 0),
            });
        }

        if (seatPressure > 0) {
            interventions.push({
                title: '增加座位供给',
                tag: seatPressure >= 2 ? '优先干预' : '备选干预',
                impact: `座位利用率 ${formatPercent(seatUtilization)}；优先通过增加座位或压缩平均就餐时间缓解周转压力。`,
                tone: seatPressure >= 2 ? 'high' : 'medium',
                priority: seatPressure * 10 + (seatPressure > waitingPressure ? 2 : 0),
            });
        }

        if (switchRate >= 0.2) {
            interventions.push({
                title: '优化跨食堂分流',
                tag: '校园路由',
                impact: `改派率 ${formatPercent(switchRate * 100)}；可调低高峰入口权重或强化实时队长信息，减少无效迁移。`,
                tone: 'medium',
                priority: 8,
            });
        }

        if (!interventions.length) {
            interventions.push({
                title: '保持当前配置',
                tag: '低拥堵',
                impact: `平均等待 ${formatSeconds(avgWait)}，峰值排队 ${peakQueue} 人，座位利用率 ${formatPercent(seatUtilization)}；当前配置可作为对照组。`,
                tone: 'low',
                priority: 1,
            });
        }

        return interventions
            .sort((a, b) => b.priority - a.priority)
            .slice(0, 3)
            .map(withoutPriority);
    }

    function setText(doc, id, value) {
        const element = doc.getElementById(id);
        if (element) element.textContent = value;
        return element;
    }

    function renderDiagnosis(stats, deps) {
        const doc = deps.document;
        const diagnosis = buildDiagnosis(stats || {});
        const level = setText(doc, 'diagnosis-level', diagnosis.level);
        if (level) {
            level.className = `diagnosis-level ${diagnosis.levelClass}`;
        }
        setText(doc, 'diagnosis-bottleneck', diagnosis.bottleneck);
        setText(doc, 'diagnosis-peak-time', diagnosis.peakTime);
        setText(doc, 'diagnosis-action', diagnosis.action);
        setText(doc, 'diagnosis-summary', diagnosis.summary);
    }

    function addInterventionCard(doc, list, item) {
        const card = doc.createElement('article');
        card.className = `intervention-card ${item.tone || 'neutral'}`;

        const tag = doc.createElement('span');
        tag.className = 'intervention-tag';
        tag.textContent = item.tag;

        const title = doc.createElement('strong');
        title.textContent = item.title;

        const impact = doc.createElement('p');
        impact.className = 'intervention-impact';
        impact.textContent = item.impact;

        card.append(tag, title, impact);
        list.appendChild(card);
    }

    function renderInterventions(stats, deps) {
        const doc = deps.document;
        const list = doc.getElementById('intervention-list');
        if (!list) return;

        const interventions = buildInterventions(stats || {});
        list.innerHTML = '';
        interventions.forEach(item => addInterventionCard(doc, list, item));

        const primary = interventions[0];
        setText(doc, 'intervention-summary', primary ? `建议优先：${primary.title}` : '暂无建议');
    }

    function renderCharts(stats, deps) {
        const { document: doc, echarts, state } = deps;
        disposeCharts(deps);
        renderDiagnosis(stats, deps);
        renderInterventions(stats, deps);
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
        buildDiagnosis,
        renderDiagnosis,
        buildInterventions,
        renderInterventions,
    };
})();

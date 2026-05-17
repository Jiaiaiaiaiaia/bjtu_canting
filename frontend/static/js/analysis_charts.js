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
        let offset = 0;
        return Object.values(windowServed).flatMap(values => {
            const items = (values || []).map((value, i) => ({ name: `窗口 ${offset + i + 1}`, value }));
            offset += items.length;
            return items;
        });
    }

    function buildWindowServiceShare(windowSeries, limit = 6) {
        const items = (windowSeries || [])
            .map(item => ({ name: item.name, rawValue: toNumber(item.value) }))
            .filter(item => item.rawValue > 0);
        const total = items.reduce((sum, item) => sum + item.rawValue, 0);
        if (total <= 0) return [];

        const visibleLimit = Math.max(1, Math.floor(toNumber(limit, 12)));
        const sorted = [...items].sort((a, b) => b.rawValue - a.rawValue);
        const visible = sorted.slice(0, visibleLimit);
        const hidden = sorted.slice(visibleLimit);
        const shareItems = visible.map(item => ({
            ...item,
            value: +((item.rawValue / total) * 100).toFixed(1),
        }));

        if (hidden.length) {
            const otherValue = hidden.reduce((sum, item) => sum + item.rawValue, 0);
            shareItems.push({
                name: '其余窗口',
                rawValue: otherValue,
                value: +((otherValue / total) * 100).toFixed(1),
            });
        }

        return shareItems;
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

    function formatMinutes(seconds) {
        const value = toNumber(seconds);
        return `${(value / 60).toFixed(1)} 分`;
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

    function buildTimelineInsight(stats) {
        stats = stats || {};
        const totalArrived = toNumber(stats.total_arrived);
        if (totalArrived <= 0) {
            return {
                badge: '等待数据',
                summary: '完成仿真后显示高峰排队、平均等待和座位峰值。',
            };
        }

        const queuePeak = findPeakPoint(stats.queue_timeline);
        const seatPeak = findPeakPoint(stats.seat_util_timeline);
        const peakQueue = Math.max(toNumber(stats.peak_queue_length), queuePeak.value);
        const seatPeakValue = Math.max(toNumber(stats.seat_utilization), seatPeak.value);
        const peakTime = queuePeak.timeText === '暂无数据' ? '结束时' : queuePeak.timeText;

        return {
            badge: peakQueue > 0 ? `高峰 ${peakTime}` : '低排队',
            summary: `峰值排队 ${Math.round(peakQueue)} 人，平均等待 ${formatSeconds(stats.avg_waiting_time)}，座位最高 ${formatPercent(seatPeakValue)}。`,
        };
    }

    function buildWindowLoadInsight(windowSeries) {
        const items = (windowSeries || [])
            .map(item => ({ name: item.name, value: toNumber(item.value) }));
        if (!items.length) {
            return {
                badge: '等待数据',
                summary: '完成仿真后显示最忙和最空窗口。',
                top: [],
                bottom: [],
            };
        }

        const total = items.reduce((sum, item) => sum + item.value, 0);
        const average = total / Math.max(items.length, 1);
        const top = [...items].sort((a, b) => b.value - a.value).slice(0, Math.min(5, items.length));
        const bottom = [...items].sort((a, b) => a.value - b.value).slice(0, Math.min(3, items.length));
        const busiest = top[0] || { name: '暂无', value: 0 };
        const emptiest = bottom[0] || { name: '暂无', value: 0 };
        const imbalance = busiest.value > average * 1.5 || (emptiest.value === 0 && busiest.value > 0);

        return {
            badge: imbalance ? '负载不均' : '负载均衡',
            summary: `最忙 ${busiest.name} 服务 ${Math.round(busiest.value)} 人，最空 ${emptiest.name} 服务 ${Math.round(emptiest.value)} 人。`,
            top,
            bottom,
        };
    }

    function buildSeatTrendInsight(stats) {
        stats = stats || {};
        const seatPeak = findPeakPoint(stats.seat_util_timeline);
        const peakValue = Math.max(toNumber(stats.seat_utilization), seatPeak.value);
        const peakTime = seatPeak.timeText === '暂无数据' ? '结束时' : seatPeak.timeText;

        if (toNumber(stats.total_arrived) <= 0 && peakValue <= 0) {
            return {
                badge: '等待数据',
                summary: '完成仿真后显示座位使用峰值。',
            };
        }

        return {
            badge: peakValue >= 85 ? '座位紧张' : (peakValue >= 70 ? '接近上限' : '座位充足'),
            summary: `最高 ${formatPercent(peakValue)}，峰值出现在 ${peakTime}。`,
        };
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

    function actionLabel(action) {
        if (action === 'add') return '添加窗口';
        if (action === 'open') return '增开窗口';
        if (action === 'close') return '关窗';
        return '窗口调整';
    }

    function queueDeltaText(delta) {
        const value = toNumber(delta);
        if (Math.abs(value) < 0.5) return '平均排队基本持平';
        if (value < 0) return `平均排队下降 ${Math.abs(value).toFixed(1)} 人`;
        return `平均排队上升 ${value.toFixed(1)} 人`;
    }

    function buildInterventionEffects(stats) {
        stats = stats || {};
        const analysis = stats.intervention_analysis || {};
        const events = Array.isArray(analysis.events) ? analysis.events : [];
        if (!events.length) {
            return {
                summary: analysis.summary || '暂无已记录干预事件',
                items: [{
                    title: '暂无干预事件',
                    tag: '待数据',
                    impact: '运行中开关窗口后显示队列和服务变化。',
                    tone: 'neutral',
                }],
            };
        }

        return {
            summary: analysis.summary || `已记录 ${events.length} 次窗口干预。`,
            items: events.slice(-4).map(event => {
                const floor = event.floor_id !== undefined && event.floor_id !== null
                    ? `${event.floor_id}F `
                    : '';
                const windowText = event.window_id !== undefined && event.window_id !== null
                    ? `窗${event.window_id}`
                    : '窗口';
                const status = event.status === 'rejected' ? '已拒绝' : '已执行';
                const deltaText = queueDeltaText(event.avg_queue_delta);
                const windowDelta = toNumber(event.open_window_delta);
                const windowDeltaText = windowDelta
                    ? `开放窗口 ${windowDelta > 0 ? '+' : ''}${windowDelta}`
                    : '开放窗口不变';
                return {
                    title: `${floor}${windowText} ${actionLabel(event.action)}`.trim(),
                    tag: `${status} · ${formatMinutes(event.time)}`,
                    impact: event.summary || `${windowDeltaText}，${deltaText}。`,
                    tone: event.verdict || (event.status === 'rejected' ? 'rejected' : 'neutral'),
                };
            }),
        };
    }

    function cloneSingleConfig(config) {
        return {
            window_count: toNumber(config.window_count),
            seat_count: toNumber(config.seat_count),
            avg_serve_time: toNumber(config.avg_serve_time),
            avg_eat_time: toNumber(config.avg_eat_time),
            arrival_rate: toNumber(config.arrival_rate),
            total_time: toNumber(config.total_time),
        };
    }

    function buildSuggestedSingleConfig(config, stats) {
        if (!config) {
            return { config: null, summary: '缺少基线配置，无法生成建议方案。', primaryAction: null };
        }

        const base = cloneSingleConfig(config);
        const next = { ...base };
        const primary = buildInterventions(stats || {})[0] || {};
        const changes = [];

        if (primary.title === '增开服务窗口') {
            const windowStep = Math.max(1, Math.ceil(base.window_count * 0.25));
            const nextWindowCount = Math.min(20, base.window_count + windowStep);
            if (nextWindowCount > base.window_count) {
                next.window_count = nextWindowCount;
                changes.push(`窗口 ${base.window_count} -> ${nextWindowCount}`);
            } else {
                const nextServeTime = Math.max(5, +(base.avg_serve_time * 0.9).toFixed(1));
                if (nextServeTime < base.avg_serve_time) {
                    next.avg_serve_time = nextServeTime;
                    changes.push(`打饭 ${base.avg_serve_time}s -> ${nextServeTime}s`);
                }
            }
        } else if (primary.title === '增加座位供给') {
            const seatStep = Math.max(10, Math.ceil(base.seat_count * 0.2));
            const nextSeatCount = Math.min(1000, base.seat_count + seatStep);
            if (nextSeatCount > base.seat_count) {
                next.seat_count = nextSeatCount;
                changes.push(`座位 ${base.seat_count} -> ${nextSeatCount}`);
            } else {
                const nextEatTime = Math.max(1, +(base.avg_eat_time * 0.9).toFixed(1));
                if (nextEatTime < base.avg_eat_time) {
                    next.avg_eat_time = nextEatTime;
                    changes.push(`就餐 ${base.avg_eat_time}min -> ${nextEatTime}min`);
                }
            }
        }

        if (!changes.length) {
            return {
                config: null,
                summary: '当前配置暂无需要自动重跑的干预，可作为对照组。',
                primaryAction: primary.title || null,
            };
        }

        return {
            config: next,
            summary: `建议方案：${changes.join('，')}`,
            primaryAction: primary.title,
        };
    }

    function formatSignedSeconds(value) {
        const prefix = value > 0 ? '+' : '';
        return `${prefix}${formatSeconds(value)}`;
    }

    function formatSignedInteger(value) {
        const rounded = Math.round(toNumber(value));
        const prefix = rounded > 0 ? '+' : '';
        return `${prefix}${rounded}`;
    }

    function formatSignedPercent(value) {
        const number = toNumber(value);
        const prefix = number > 0 ? '+' : '';
        return `${prefix}${number.toFixed(1)}%`;
    }

    function comparisonTone(delta, lowerIsBetter = true) {
        if (Math.abs(delta) < 0.01) return 'flat';
        const improved = lowerIsBetter ? delta < 0 : delta > 0;
        return improved ? 'improved' : 'worse';
    }

    function buildScenarioComparison(baselineStats, adjustedStats) {
        const baselineWait = toNumber(baselineStats && baselineStats.avg_waiting_time);
        const adjustedWait = toNumber(adjustedStats && adjustedStats.avg_waiting_time);
        const baselinePeak = toNumber(baselineStats && baselineStats.peak_queue_length);
        const adjustedPeak = toNumber(adjustedStats && adjustedStats.peak_queue_length);
        const baselineSeat = toNumber(baselineStats && baselineStats.seat_utilization);
        const adjustedSeat = toNumber(adjustedStats && adjustedStats.seat_utilization);

        return [
            {
                key: 'wait',
                label: '平均等待',
                baseline: formatSeconds(baselineWait),
                adjusted: formatSeconds(adjustedWait),
                delta: formatSignedSeconds(adjustedWait - baselineWait),
                tone: comparisonTone(adjustedWait - baselineWait),
            },
            {
                key: 'peak',
                label: '峰值排队',
                baseline: `${Math.round(baselinePeak)} 人`,
                adjusted: `${Math.round(adjustedPeak)} 人`,
                delta: formatSignedInteger(adjustedPeak - baselinePeak),
                tone: comparisonTone(adjustedPeak - baselinePeak),
            },
            {
                key: 'seat',
                label: '座位利用率',
                baseline: formatPercent(baselineSeat),
                adjusted: formatPercent(adjustedSeat),
                delta: formatSignedPercent(adjustedSeat - baselineSeat),
                tone: comparisonTone(adjustedSeat - baselineSeat),
            },
        ];
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

    function addInterventionEffectCard(doc, list, item) {
        const card = doc.createElement('article');
        card.className = `intervention-effect-card ${item.tone || 'neutral'}`;

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

    function renderInterventionEffects(stats, deps) {
        const doc = deps.document;
        const list = doc.getElementById('intervention-effect-list');
        if (!list) return;

        const effects = buildInterventionEffects(stats || {});
        list.innerHTML = '';
        effects.items.forEach(item => addInterventionEffectCard(doc, list, item));
        setText(doc, 'intervention-effect-summary', effects.summary);
    }

    function renderScenarioComparison(baselineStats, adjustedStats, summary, deps) {
        const doc = deps.document;
        const box = doc.getElementById('scenario-comparison');
        if (box) box.hidden = false;
        setText(doc, 'scenario-adjustment', summary || '建议方案已完成。');

        const metricDom = {
            wait: {
                baseline: 'scenario-baseline-wait',
                adjusted: 'scenario-adjusted-wait',
                delta: 'scenario-delta-wait',
            },
            peak: {
                baseline: 'scenario-baseline-peak',
                adjusted: 'scenario-adjusted-peak',
                delta: 'scenario-delta-peak',
            },
            seat: {
                baseline: 'scenario-baseline-seat',
                adjusted: 'scenario-adjusted-seat',
                delta: 'scenario-delta-seat',
            },
        };

        buildScenarioComparison(baselineStats || {}, adjustedStats || {}).forEach(item => {
            const ids = metricDom[item.key];
            if (!ids) return;
            setText(doc, ids.baseline, item.baseline);
            setText(doc, ids.adjusted, item.adjusted);
            const delta = setText(doc, ids.delta, item.delta);
            if (delta) delta.className = `scenario-delta ${item.tone}`;
        });
    }

    function renderAnalysisNarrative(stats, windowSeries, deps) {
        const doc = deps.document;
        const timeline = buildTimelineInsight(stats || {});
        const windowLoad = buildWindowLoadInsight(windowSeries || []);
        const seatTrend = buildSeatTrendInsight(stats || {});
        const share = buildWindowServiceShare(windowSeries || []);
        const totalServed = share.reduce((sum, item) => sum + toNumber(item.rawValue), 0);
        const leadingShare = share
            .filter(item => item.name !== '其余窗口')
            .slice(0, 3)
            .reduce((sum, item) => sum + toNumber(item.value), 0);

        setText(doc, 'timeline-insight', timeline.summary);
        setText(doc, 'timeline-badge', timeline.badge);
        setText(doc, 'window-balance-summary', windowLoad.summary);
        setText(doc, 'window-balance-badge', windowLoad.badge);
        setText(doc, 'seat-trend-summary', seatTrend.summary);
        setText(
            doc,
            'service-concentration-summary',
            totalServed > 0
                ? `前三个窗口承担 ${leadingShare.toFixed(1)}% 服务量，总服务 ${Math.round(totalServed)} 人。`
                : '完成仿真后显示窗口服务是否集中。'
        );
    }

    function renderCharts(stats, deps) {
        const { document: doc, echarts, state } = deps;
        stats = stats || {};
        disposeCharts(deps);
        renderDiagnosis(stats, deps);
        renderInterventions(stats, deps);
        renderInterventionEffects(stats, deps);
        const windowSeries = normalizeWindowServed(stats.window_served);
        renderAnalysisNarrative(stats, windowSeries, deps);

        state.charts.window = echarts.init(doc.getElementById('window-chart'));
        const rankedWindows = [...windowSeries]
            .map(item => ({ name: item.name, value: toNumber(item.value) }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 8)
            .reverse();
        state.charts.window.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 64, right: 38, top: 8, bottom: 18 },
            xAxis: {
                type: 'value',
                axisLabel: { formatter: '{value} 人' },
                splitLine: { lineStyle: { color: '#eef2f7' } },
            },
            yAxis: {
                type: 'category',
                data: rankedWindows.map(item => item.name),
                axisLabel: { color: '#4b5563' },
            },
            series: [{
                type: 'bar',
                data: rankedWindows.map(item => item.value),
                label: { show: true, position: 'right', formatter: '{c} 人' },
                itemStyle: { color: '#dc2626', borderRadius: [0, 4, 4, 0] },
            }],
        });

        const windowShare = buildWindowServiceShare(windowSeries);
        state.charts.windowShare = echarts.init(doc.getElementById('pie-chart'));
        const shareData = [...windowShare].reverse();
        state.charts.windowShare.setOption({
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter(params) {
                    const item = params && params[0];
                    if (!item) return '';
                    const rawValue = item.data && item.data.rawValue !== undefined ? item.data.rawValue : 0;
                    return `${item.name}<br/>占总服务：${item.value}%<br/>服务人数：${rawValue} 人`;
                },
            },
            grid: { left: 64, right: 44, top: 8, bottom: 18 },
            xAxis: {
                type: 'value',
                max: 100,
                axisLabel: { formatter: '{value}%' },
                splitLine: { lineStyle: { color: '#eef2f7' } },
            },
            yAxis: {
                type: 'category',
                data: shareData.map(item => item.name),
                axisLabel: { color: '#4b5563' },
            },
            series: [{
                type: 'bar',
                data: shareData.map(item => ({ value: item.value, rawValue: item.rawValue })),
                label: { show: true, position: 'right', formatter: '{c}%' },
                itemStyle: { color: '#2563eb', borderRadius: [0, 4, 4, 0] },
            }],
        });

        const qt = stats.queue_timeline || { x: [], y: [] };
        const st = stats.seat_util_timeline || { x: [], y: [] };
        const timelineX = (qt.x && qt.x.length ? qt.x : st.x) || [];
        state.charts.queue = echarts.init(doc.getElementById('queue-chart'));
        state.charts.queue.setOption({
            tooltip: { trigger: 'axis' },
            legend: { top: 0, right: 0 },
            grid: { left: 46, right: 50, top: 36, bottom: 34 },
            xAxis: { type: 'category', data: timelineX.map(x => `${x}分`) },
            yAxis: [
                { type: 'value', name: '排队', min: 0 },
                { type: 'value', name: '座位', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
            ],
            series: [
                {
                    name: '排队人数',
                    type: 'line',
                    smooth: true,
                    data: qt.y || [],
                    areaStyle: { color: 'rgba(220, 38, 38, 0.14)' },
                    itemStyle: { color: '#dc2626' },
                    lineStyle: { width: 2 },
                },
                {
                    name: '座位利用率',
                    type: 'line',
                    smooth: true,
                    yAxisIndex: 1,
                    data: st.y || [],
                    itemStyle: { color: '#2563eb' },
                    lineStyle: { width: 2 },
                },
            ],
        });

        state.charts.seat = echarts.init(doc.getElementById('seat-chart'));
        state.charts.seat.setOption({
            tooltip: { trigger: 'axis', formatter: '{b}：{c}%' },
            grid: { left: 42, right: 18, top: 8, bottom: 24 },
            xAxis: { type: 'category', data: st.x.map(x => `${x}分`) },
            yAxis: {
                type: 'value',
                max: 100,
                axisLabel: { formatter: '{value}%' },
                splitLine: { lineStyle: { color: '#eef2f7' } },
            },
            series: [{
                type: 'line', smooth: true, data: st.y,
                areaStyle: { color: 'rgba(22, 163, 74, 0.16)' },
                itemStyle: { color: '#16a34a' },
                markLine: {
                    symbol: 'none',
                    data: [{ yAxis: 85, name: '紧张线' }],
                    lineStyle: { color: '#f59e0b', type: 'dashed' },
                    label: { formatter: '85%' },
                },
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
        buildWindowServiceShare,
        buildDiagnosis,
        renderDiagnosis,
        buildInterventions,
        renderInterventions,
        buildInterventionEffects,
        renderInterventionEffects,
        buildSuggestedSingleConfig,
        buildScenarioComparison,
        renderScenarioComparison,
        buildTimelineInsight,
        buildWindowLoadInsight,
        buildSeatTrendInsight,
        renderAnalysisNarrative,
    };
})();

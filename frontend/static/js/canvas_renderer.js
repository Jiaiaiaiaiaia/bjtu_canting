// ================================== Canvas 食堂布局渲染模块
(function() {
    const App = window.CanteenApp = window.CanteenApp || {};

    function drawCanteen(data, deps) {
        const { canvas, ctx } = deps;
        if (!canvas || !ctx || !data) return;
        const W = canvas.width;
        const H = canvas.height;
        ctx.clearRect(0, 0, W, H);

        drawBackground(W, H, deps);
        const windowBoxes = drawWindows(data.windows, W, deps);
        drawSeats(data.seats, W, H, deps);
        drawWaitingQueueLabel(data.waiting_queue_length, W, H, deps);
        drawStudentDots(data, windowBoxes, W, H, deps);
    }

    function drawBackground(W, H, deps) {
        const { ctx } = deps;
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 2;
        ctx.strokeRect(12, 12, W - 24, H - 24);
        ctx.font = '12px "PingFang SC", sans-serif';
        ctx.fillStyle = '#64748b';
        ctx.textAlign = 'left';
    }

    function drawWindows(windows, W, deps) {
        const { ctx } = deps;
        if (!windows || !windows.length) return [];
        const count = windows.length;
        const winW = 80, winH = 50;
        const gap = Math.max(10, (W - 60 - count * winW) / (count + 1));
        const baseX = (W - (count * winW + (count - 1) * gap)) / 2;
        const y = 50;
        const boxes = [];

        windows.forEach((w, i) => {
            const x = baseX + i * (winW + gap);
            const color = w.is_serving ? '#b91c1c' : '#94a3b8';
            ctx.fillStyle = color;
            ctx.fillRect(x, y, winW, winH);
            ctx.strokeStyle = '#991b1b';
            ctx.strokeRect(x, y, winW, winH);
            ctx.fillStyle = '#fff';
            ctx.font = '13px "PingFang SC", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`窗口 ${w.id + 1}`, x + winW / 2, y + 22);
            ctx.font = '11px "PingFang SC", sans-serif';
            ctx.fillText(`已服务 ${w.total_served}`, x + winW / 2, y + 40);

            const queueX = x + winW / 2;
            const queueY = y + winH + 12;
            if (w.queue_length > 12) {
                ctx.fillStyle = '#64748b';
                ctx.font = '11px sans-serif';
                ctx.fillText(`+${w.queue_length - 12}`, queueX, queueY + 14 + 12 * 14 + 4);
            }

            boxes.push({ id: w.id, x, y, w: winW, h: winH, queueX, queueY });
        });

        return boxes;
    }

    function drawSeats(seats, W, H, deps) {
        const { ctx } = deps;
        if (!seats || !seats.length) return [];
        const total = seats.length;
        const cols = Math.min(20, Math.ceil(Math.sqrt(total * 1.8)));
        const rows = Math.ceil(total / cols);
        const size = 18;
        const gap = 5;
        const areaW = cols * (size + gap) - gap;
        const startX = (W - areaW) / 2;
        const startY = 260;

        seats.forEach((s, i) => {
            const r = Math.floor(i / cols);
            const c = i % cols;
            const x = startX + c * (size + gap);
            const y = startY + r * (size + gap);
            if (s.status === 'occupied') {
                const intensity = Math.min(1, s.remaining_time / (30 * 60));
                const g = Math.floor(120 - 60 * intensity);
                ctx.fillStyle = `rgb(239, ${g}, 68)`;
            } else {
                ctx.fillStyle = '#d1fae5';
            }
            ctx.fillRect(x, y, size, size);
            ctx.strokeStyle = '#94a3b8';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x, y, size, size);
        });

        return { startX, startY, cols, size, gap };
    }

    function drawWaitingQueueLabel(count, W, H, deps) {
        const { ctx } = deps;
        if (!count) return;
        ctx.fillStyle = '#64748b';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(`等位队列：${count} 人`, W - 30, H - 40);
        if (count > 10) {
            ctx.fillText(`+${count - 10}`, W - 30, H - 4);
        }
    }

    function computeStudentTargets(students, windowBoxes, W, H) {
        if (!students) return {};
        const boxByWid = {};
        windowBoxes.forEach(b => { boxByWid[b.id] = b; });

        const targets = {};
        const queueIdxByWindow = {};
        for (const s of students) {
            if (s.position === 'window_queue') {
                const wid = s.position_detail;
                const idx = (queueIdxByWindow[wid] = (queueIdxByWindow[wid] || 0));
                queueIdxByWindow[wid] = idx + 1;
                const box = boxByWid[wid];
                if (!box || idx >= 12) continue;
                targets[s.id] = {
                    x: box.queueX,
                    y: box.queueY + 14 + idx * 14,
                    color: '#ff9800',
                };
            } else if (s.position === 'being_served') {
                const box = boxByWid[s.position_detail];
                if (!box) continue;
                targets[s.id] = {
                    x: box.x + box.w / 2,
                    y: box.y + box.h - 8,
                    color: '#fbbf24',
                };
            } else if (s.position === 'waiting_queue') {
                const idx = typeof s.position_detail === 'number' ? s.position_detail : 0;
                if (idx >= 10) continue;
                targets[s.id] = {
                    x: W - 40 + (idx % 5) * 12,
                    y: H - 28 + Math.floor(idx / 5) * 12,
                    color: '#9333ea',
                };
            }
        }
        return targets;
    }

    function drawStudentDots(data, windowBoxes, W, H, deps) {
        const { ctx, state } = deps;
        if (!state.studentPrev) state.studentPrev = {};
        const targets = computeStudentTargets(data.students, windowBoxes, W, H);
        const prev = state.studentPrev;
        const next = {};
        const lerp = 0.4;
        for (const id in targets) {
            const t = targets[id];
            const p = prev[id];
            const x = p ? p.x + (t.x - p.x) * lerp : t.x;
            const y = p ? p.y + (t.y - p.y) * lerp : t.y;
            ctx.fillStyle = t.color;
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = 'rgba(15, 23, 42, 0.25)';
            ctx.lineWidth = 0.6;
            ctx.stroke();
            next[id] = { x, y };
        }
        state.studentPrev = next;
    }

    function renderLegendBar(legendBar) {
        if (!legendBar) return;
        const items = [
            { color: '#b91c1c', text: '占用窗口' },
            { color: '#94a3b8', text: '空闲窗口' },
            { color: '#ff9800', text: '排队' },
            { color: '#fbbf24', text: '打饭' },
            { color: '#9333ea', text: '等位' },
            { color: '#ef4444', text: '就餐中' },
            { color: '#d1fae5', text: '空座' },
            { color: 'linear-gradient(90deg,#ef4444,#fde68a)', text: '热力(剩余时间)' },
        ];
        legendBar.innerHTML = items.map(it =>
            `<span style="display:inline-flex;align-items:center;gap:4px;">` +
            `<span style="width:10px;height:10px;background:${it.color};border-radius:2px;"></span>${it.text}</span>`
        ).join('');
    }

    App.CanvasRenderer = {
        drawCanteen,
        drawWindows,
        drawSeats,
        drawStudentDots,
        renderLegendBar,
    };
})();

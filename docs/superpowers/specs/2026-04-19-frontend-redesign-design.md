# Frontend Redesign: A 学术简约 + 规格补齐

**日期**: 2026-04-19
**状态**: 已确认
**改动范围**: 前端视觉 + 少量后端字段

---

## 1. 目标

将就餐仿真系统前端从当前"能用"状态升级到"答辩级"视觉品质，同时补齐设计规格说明书中要求但尚未实现的功能点。

### 1.1 不在范围内

- 后端仿真算法（engine.py 核心逻辑）
- API 接口签名与数据库 schema
- Canvas 绘制算法（drawStudentDots / drawSeats 热力色算法）
- ECharts 图表数据流
- 现有 38 条 pytest 用例的逻辑

---

## 2. 视觉系统

### 2.1 配色

| Token | 色值 | 用途 |
|-------|------|------|
| 主色 | `#b91c1c` | BJTU 红，按钮/激活 tab/强调数字 |
| 主色浅 | `#fef2f2` | hover 背景/饼图底色 |
| 主色深 | `#991b1b` | 按钮按下态 |
| 文字主 | `#111827` | 标题/主要数据 |
| 文字次 | `#4b5563` | 正文/nav 未激活 |
| 文字提示 | `#6b7280` | label/副标题 |
| 文字禁用 | `#9ca3af` | 禁用状态 |
| 边框 | `#e5e7eb` | 卡片/输入框/分割线 |
| 边框深 | `#d1d5db` | 表单输入框 |
| 页面底 | `#f9fafb` | body 背景 |
| 卡片底 | `#ffffff` | 所有卡片/面板 |
| 成功绿 | `#059669` | 正向指标（完成就餐等） |
| 警示黄 | `#f59e0b` | 峰值/警戒值 |

Canvas 保留色：`#ff9800` 排队（window_queue）、`#fbbf24` 打饭（being_served）、`#9333ea` 等位（waiting_queue，当前代码已用紫色）、红→黄热力梯度（seated 占用时长）。

### 2.2 字体

```css
font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
```

| 级别 | 字号 | 字重 |
|------|------|------|
| H1（系统标题） | 20px | 600 |
| H2（页面标题） | 18px | 600 |
| H3（卡片/图表标题） | 14px | 600 |
| 统计卡数字 | 26px | 700 |
| 信息面板数字 | 20px | 600 |
| 正文 | 13px | 400 |
| Label | 11px | 400 |

### 2.3 间距

4 的倍数：4 / 8 / 12 / 16 / 20 / 24 / 32 px。

### 2.4 圆角

- 小 6px：按钮、输入框
- 中 8px：统计卡、info 卡
- 大 10-12px：大容器、图表卡片

### 2.5 阴影策略

不使用 box-shadow。所有卡片用 `border: 1px solid #e5e7eb` 替代，保持克制。

---

## 3. 页面改动

### 3.1 顶部导航（全局）

- Logo 色块：28×28px 圆角 6px `#b91c1c` 方块
- 系统名：14px `#111827` font-weight:600
- Nav links：13px，未激活 `#4b5563`，激活 `#b91c1c` + font-weight:600 + 底部 2px 红色边
- 底边线：`1px solid #e5e7eb`

### 3.2 参数配置页

- 表单收在 560px 居中卡片（`border: 1px solid #e5e7eb; border-radius: 12px`）
- 6 个参数双列 grid（`grid-template-columns: 1fr 1fr; gap: 16px 20px`）
- 标题下加提示行："配置完后点击开始仿真，自动跳转到仿真运行页"
- "恢复默认值"：白底 + `border: 1px solid #d1d5db`
- "开始仿真"：`#b91c1c` 实底白字
- 按钮组右对齐

### 3.3 仿真运行页

**信息面板：**
- 从 6 项增至 7 项（新增"平均等待"）
- 当前布局是左侧 220px 竖向 sidebar（`.simulation-container` 用 `grid-template-columns: 220px 1fr`）。改为：移除 sidebar 结构，info 面板挪到画布上方，`grid-template-columns: repeat(7, 1fr)` 水平一行展示
- 响应式：`@media (max-width: 900px)` 改为 `repeat(3, 1fr)` 三列折行；`@media (max-width: 640px)` 改为单列
- 每项为独立卡片：白底 + 细边框 + 8px 圆角
- 新增第 7 项"平均等待"用红色边框 `#fecaca` 区分
- `resetSimulationState()`（main.js:131 附近）需同步重置第 7 项 DOM 为 `0.0 s`

**食堂画布区：**
- Canvas 外加卡片容器（白底 + 细边框 + 10px 圆角）
- 卡片顶部一行：左"食堂平面布局"标题 + 右颜色图例（排队/打饭/等位/热力梯度）。注意：后端学生位置状态为 `window_queue`/`being_served`/`waiting_queue`/`seated`/`left`，无"找座"可持续状态；图例中对应 `waiting_queue` 显示为"等位"
- "等位队列：N 人"保留在 Canvas 右下

**控制栏：**
- 整体放入卡片容器
- 速度控制：`<select id="speed">` 替换为 `<input type="range" id="speed-range" min="0" max="3" step="1" value="1">`（默认 value=1 即 ×2）
- JS 端：`const SPEED_MAP = [1, 2, 5, 10];` 将 index 转换为实际倍速值。变量从 `speedSelect` 改名为 `speedRange`，事件从 `change` 改为 `input`（拖动实时响应）
- 旁边新增 `<span id="speed-label">×2</span>` 显示当前倍速文字，`input` 事件回调更新 `state.speed = SPEED_MAP[speedRange.value]` + `speedLabel.textContent`
- "暂停/开始"按钮：红底白字
- "结束仿真"按钮：白底红边

### 3.4 数据分析页

**统计卡：**
- 从当前 `repeat(auto-fit, minmax(180px, 1fr))`（渲染为 3×2）改为显式 `repeat(6, 1fr)` 单行
- 响应式：`@media (max-width: 900px)` 改为 `repeat(3, 1fr)` 两行；`@media (max-width: 640px)` 改为 `repeat(2, 1fr)`
- 每张卡增加副标题行（灰色小字，如"60 min 窗口期"）

**图表区：**
- 2×2 grid 不变
- 每个图表加卡片容器（白底 + 细边框 + 10px 圆角 + 内 padding 16px）
- 图表标题 14px 粗体

**重新仿真按钮：**
- 从当前位置搬到页面右下角
- 红底白字样式

### 3.5 历史记录页

- 表格奇数行背景 `#f9fafb`（zebra stripes）
- 行 hover 背景 `#fef2f2`
- 详情面板放进卡片容器

### 3.6 仿真结束自动跳转（已有，保留）

两条路径均已实现自动跳转，逻辑不同但效果一致：
- `endBtn` handler（main.js:98-123）：调 `POST /api/simulation/finish` 拿到 stats → 直接调 `renderStatCards(stats)` + `renderCharts(stats)` 渲染
- 自然结束分支（main.js:165-168）：调 `showPage('analysis')` → 再调 `loadStatistics()` 间接通过 `GET /api/statistics` 获取 stats 渲染

此次改动只做样式适配，不改逻辑。

---

## 4. 后端改动

**唯一改动：`engine.py` 的 `_build_state()` 方法**

在返回的 state dict 中增加 `avg_waiting_time` 字段。

**口径说明：** 实时面板统计"已开始服务的学生"（`start_service_time is not None`）的等待均值，与最终统计 `get_statistics()` 的口径不同——后者统计"已完成就餐"（`end_eat_time is not None`）的学生。实时口径涵盖更多学生，因此仿真中途两者数值会有差异；仿真结束（所有学生完成就餐）后二者收敛一致。

```python
served = [s for s in self.students if s.start_service_time is not None]
waiting_times = [s.start_service_time - s.arrival_time for s in served]
avg_waiting = sum(waiting_times) / len(waiting_times) if waiting_times else 0.0
```

然后将 `avg_waiting` 加入返回字典。不引入新的累加器属性。

---

## 5. 文件清单

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `frontend/static/css/style.css` | 重写 | ~500 行（从 326 行扩展） |
| `frontend/templates/index.html` | 小改 | ~20 行差异 |
| `frontend/static/js/main.js` | 小改 | ~40 行差异 |
| `backend/simulation/engine.py` | 微改 | ~5 行 |
| `backend/tests/test_engine.py` | 加 1 条 | ~8 行 |

---

## 6. 验证计划

### 6.1 视觉验证（手动）

启动 `python app.py`，走完全流程：参数配置 → 开始仿真 → 运行中观察 → 结束 → 自动跳分析 → 重新仿真 → 历史记录。对照 mockup 截图。

### 6.2 功能验证

- 第 7 项"平均等待"每步更新、非负、与选定口径（已开始服务的学生）一致。平均值不保证单调递增——新进入服务的短等待学生会拉低均值
- 速度滑块四档切换正常
- 结束仿真后自动跳分析页，统计卡数值与 `/api/statistics` 一致
- 历史表格点击行可展开详情图表

### 6.3 回归验证

```bash
cd backend && python -m pytest tests/ -v
```

预期：39 passed（38 + 1 新增）。Canvas 动画帧率无可感知下降。

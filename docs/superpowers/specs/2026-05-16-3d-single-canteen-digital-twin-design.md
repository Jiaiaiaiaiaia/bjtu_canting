# 3D 单食堂数字孪生升级设计

**项目**：北京交通大学就餐仿真系统（Canteen）
**日期**：2026-05-16
**分支**：codex/canteen-demo-polish
**状态**：设计已确认（brainstorming 五节逐节锁定），待 spec 评审 → 实施计划拆分
**目标**：把仿真页升级为「单食堂多层 3D 数字孪生」主体验，支持运行中开/关窗口真改后端排队，并加入时变到达高峰，面向**比赛/作品展示**（技术含量 + 视觉冲击，兼顾可分析）。
**审查依据**：`reviews/2026-05-16_code-review.md`

---

## 0. Supersedes（取代的旧设计方向 · 仅标记不删除）

本 spec 取代以下旧 3D / 多食堂设计方向。它们均为「校园/多食堂」中心，与本次「单食堂唯一主线」冲突，**保留以维持可追溯性**；是否归档或删除留作本 spec 评审通过后的**单独 cleanup commit**（届时列文件清单、说明过时原因、归档 vs 删除单独审）：

- `docs/superpowers/specs/2026-05-14-3d-digital-twin-canteen-design.md`
- `docs/superpowers/plans/2026-05-14-3d-digital-twin-canteen-plan.md`
- `docs/superpowers/specs/2026-04-28-3d-immersive-multi-canteen-design.md`
- `docs/superpowers/plans/2026-04-28-3d-immersive-multi-canteen-plan.md`
- `docs/superpowers/plans/2026-05-12-threejs-canteen-v7-plan.md`

salvage（保留并重定范围）：深色数字孪生视觉、真楼层堆叠、运行中窗口干预、后端为唯一真值源。drop（弃用）：校园沙盘、跨食堂 `StudentRouter`、`in_transit`、学活待补点位、多食堂产品形态。

---

## 1. 范围与不变量

**单食堂为唯一主线**。砍掉校园「产品形态」（多食堂沙盘、跨食堂路由、in_transit、学活）；**保留 `/api/campus/*` + `CampusCoordinator` 作技术底座**，以 **N=1 单食堂（明湖学一 3 层）** 承载多层 3D。

不变量（任一破坏即视为设计违例）：

- Phase 2 `/api/config` + `/api/simulation/*` + `SimulationEngine._build_state()` 的 flat 形状**一字不改**（兼容基线，`backend/api/routes.py:30-33,114-163`；`backend/simulation/engine.py:217-272`）。
- 后端测试 `184 passed` 保持绿。`test_multi_floor.py:29`（`active_window_count==33`）不破。`/api/campus/presets/default` 及 `test_campus_preset_loader.py` / `test_campus_api.py` 契约不破。
- 后端 snapshot 是唯一真值源；KPI 取后端 totals，不从 Three.js 反推；随机扰动只防点位重叠，不改统计。
- 术语：**演示/叙事层不使用「路由」一词**（「路由」专指已删除的跨食堂 `StudentRouter`）；窗口选择统一称「窗口候选集 / 学生窗口分配」（`Canteen.shortest_window()`）。**后端仍保留 `router` 配置字段（如 `max_switches_per_student`）作为 `CampusCoordinator` 兼容结构**，这不与上句矛盾。
- 等价性表述统一为**仿真语义层完全一致**（trace、事件序列、开放窗数、队列分布、KPI timeline、最终 totals），**排除 DB 自增 id 与时间戳等非仿真字段**；不使用 API/DB 字节级相等。
- **单食堂强制 `router.max_switches_per_student=0`**（Phase 2 门面已在 `engine.py:121` 设置；新增 `load_single_canteen_preset()` 同样固定为 0）。据此 `student.py:66-114` 的 `router.try_switch`/`in_transit`/步行切换分支在单食堂模式下**可证为死代码**——这是 §3.3「原窗自然 drain」成立的前提，不得隐式依赖。

---

## 2. 架构与模块边界 + 数据流

**后端 — 单一汇流构造**
- 新增 `backend/simulation/canteen_config.py: build_single_canteen_config(spec) -> dict`，产出 `CampusCoordinator` 可消费的 `{canteens:[多层], campus:{}, router:{}}`。
- 旧 Phase 2 六参数被当成「退化单层预设」经同一 builder；`engine._to_single_canteen_config`（`engine.py:77-124`）瘦成「六参数→单层预设→builder」。Phase 2 旧路径独立保留、行为不变。
- `Canteen`/`Canteen.snapshot()` 已原生支持多层（`canteen.py:109-135,241-253`），同时吐 flat（Phase 2 兼容）+ 嵌套 `floors[]`（3D 用），不发明新形状。

**前端 — 模块拆分，3D 主体验**
- `scene3d.js` 拆为 `scene3d.js`(core: renderer/相机/循环/`render(snapshot,state)`)、`canteen_scene.js`(多层堆叠/楼层聚焦/剖面/编码)、`intervention_ui.js`(窗口开关→干预 API→事件提示)、`state_adapter.js`(离散 snapshot→连续插值)。**不做 campus_scene**。
- 对外**仍只暴露 `window.CanteenApp3D.init/render/dispose`**（拆分藏 facade 后，保 `test_frontend_three_js_contract.py` 绿，含 `visibleCanteens/pendingCanteens` token）。
- 「3D 默认主屏」为待实现目标（现状 `main.js:13 renderMode:'2d'`）；实现时改默认为 3D 并保 2D（`canvas_renderer`/SVG）兜底/调试。

**数据流（唯一真值源）**
```
SimPy → /api/campus/step (coordinator.snapshot, 含 floors[]) → state_adapter → Three.js 连续插值
                                            ↘ 窗口干预 API → 改后端状态 → 下一帧 snapshot
```
注：`/api/simulation/step` 不透出 `floors[]`（`_build_state` 只回 flat），故 3D 数据源必须是 `/api/campus/step`。

---

## 3. 后端改动细节

### 3.1 单食堂预设入口
- 新增 `presets/loader.py: load_single_canteen_preset()` → N=1 config（`canteens=[明湖学一(minghu_xueyi.json 3 层原值)]`、`campus={演示尺度 + entrance + 单食堂平凡步行}`、`router={…}`）。
- 新增 `GET /api/campus/presets/single-canteen`，**返回与 `/presets/default` 同 envelope**：`{mode, config, visible_canteens=[minghu_xueyi 注解], pending_canteens=[], source_scale, demo_runtime}`，前端 `applyCampusPresetMetadata()` 零分叉。`/presets/default`（`campus_routes.py:318-328`）及其测试不动。
- **前端主入口绑定**：3D 主体验的 preset-first 路径（`main.js` 的 `syncModeForms` / `loadDefaultCampusPreset` / `getCampusConfigForSubmit`，约 `main.js:147-154/175-187/203-214`）改调 `/api/campus/presets/single-canteen`；`/presets/default` 仅保留为旧校园联合演示/手动入口兼容，**不作为本次默认入口**——否则会把明湖/学四/学活待补带回，违反「单食堂唯一主线」（§1）。
- `/api/campus/config`（已校验 `campus/canteens/router`，`campus_routes.py:31-56`）原样消费。

### 3.2 窗口开放状态机
- `Window` 加 `is_open: bool=True`。
- `Canteen.__init__` 把建窗循环由 `range(active_count)` 改为 **`range(physical_count)`**（`canteen.py:123`）；每层前 `active_count` 个 `is_open=True`，其余 `False`。
- 新增 `Canteen.open_window_count = sum(w.is_open for w in windows)`；新增 `Canteen.open_window_capacity_score = sum(1/w.canteen_avg_serve_time for w in windows if w.is_open)`。`active_window_count` 含义/值不变（保 `test_multi_floor.py:29`）。
- `Canteen.shortest_window()` 在 `is_open` 窗口中取 min（`canteen.py:167-168`）；候选空即拒绝。`router.py:57` capacity 改用 `open_window_capacity_score`；构造守卫（`canteen.py:161`）= 初始至少 1 个开放窗；KPI 显示 `open_window_count`。
- 不变量：构造守卫 + §3.4「拒关最后一个开放窗」⇒ **`is_open` 窗口集恒非空**，`shortest_window()` 候选永不为空，无需定义「全部窗口关闭」的 fallback 路径。

### 3.3 关窗 drain 语义（钉死）
- `is_open=False` 后**立即移出 `shortest_window()` 候选集**；既有 `waiting_students` 与已 pending 的 `resource.request()`（`student.py:66`）**不迁移、不取消**，原窗自然 drain（`student.py:66-114` 对已入队者照常 grant/serve）。**不触碰 SimPy request**。
- drain 正确性前提：§1 不变量「单食堂 `max_switches_per_student=0`」⇒ `student.py:66-114` 不会因耐心超时走切换/步行分支，已入队学生只会停在原窗等到被服务，drain 闭合。
- 开窗 = 将某 `is_open=False` 的 physical 窗置 True，下次 `shortest_window()` 纳入（真增服务能力）。
- snapshot 派生 `closing = (not is_open) and (queue_length>0 or is_serving)`。3D：开放=亮、closing=暗+「关闭中」、空且关闭=灰。

### 3.4 单食堂窗口干预 API + 持久化全链
- `POST /api/campus/canteens/<cid>/windows/<wid>/toggle {open: bool}`（N=1 下 `cid` 固定，保留以对齐 snapshot 键）。
- 返回：更新后 coordinator snapshot（含 `floors[]`）+ `campus_totals` + 本次 `intervention` 事件 + 拒绝原因。
- 规则：重复开/关 **idempotent 返回**；**拒关最后一个开放窗** → `status:rejected`。
- 事件 `{time, canteen_id, floor_id, window_id, action:open|close, status:applied|rejected, reason?}`。
- **持久化全链（仅限 campus 路径，Phase 2 不动）**（否则现场可看、历史不可验）：`CampusCoordinator` 持 `interventions[]`、`snapshot()` 透出；`db_migrate` 仿现有幂等 `_column_exists`+`ALTER`（`db_migrate.py:26-34`）给 **`campus_snapshot`** 表加 `interventions_json`；改动只触及 **`campus_routes.py` 的 campus 版**方法——`_snapshot()`/`_compact_snapshot()`（`campus_routes.py:106`，**非** `engine.py` 的 Phase 2 `_compact_snapshot`）带 `interventions`、`_flush_campus_snapshots()` INSERT、`_load_campus_history_rows()` SELECT+`json.loads`、`get_campus_history`/`list_campus_history_configs` 自动传播。**Phase 2 `engine._compact_snapshot` 与 `simulation_snapshot` 表一字不改**。
- **干预即时可查（钉死）**：`_load_campus_history_rows()`（`campus_routes.py:150-172`）只读 DB、不读未 flush 的 `snapshot_buffer`；故干预 API 成功**或拒绝**后，必须**立即**追加一条 `event_type='intervention'` 的 compact snapshot 并**当场调用 `_flush_campus_snapshots()`**（不等 `STEP_FLUSH_THRESHOLD`），保证演示中干预后立刻 `GET /api/campus/history` 即可见该 intervention。

### 3.5 ArrivalSchedule λ(t) + per-student trace（同源·保 A/B）
- 新增 `ArrivalSchedule`：形状 `s(t)=baseline + 午高峰爬升 + 离散下课脉冲`；积分归一 `k=(N·α·coverage)/∫₀ᵀ s(t)dt`，`λ(t)=k·s(t)` ⇒ `∫λ=total_students·lunch_alpha·coverage` 不变（仅时间再分布，不改总量；保 demo scale 与历史统计含义，对齐 `arrival_generator.py:50-61` 现义）。
- 非齐次泊松用 thinning（Lewis–Shedler），`λ_max` 出候选间隔、`λ(t)/λ_max` 接受；**`build_single_canteen_traces`（`student_trace.py:20`）与实时 `ArrivalGenerator._run`（`arrival_generator.py:84`）共用同一 `ArrivalSchedule`+同一 thinning+同一 `streams.arrival` 流**。
- **常量旁路**：`ArrivalSchedule.is_constant`（无 ramp/pulse）→ 走旧 `expovariate` 路径，不抽 acceptance、不进 thinning ⇒ 与今日恒定行为在**仿真语义层完全一致**（到达序列与随机消费序列一致；排除 DB/API 偶发字段）。Phase 2 与既有测试不受影响。
- **per-student trace（4.3 定稿）**：campus N=1 支持 `rng_seed`，由 `build_random_streams()` 生成 arrival/routing/service/eat 四流；`ArrivalSchedule` 生成带 `service_z/eat_z` 的 per-student trace（`StudentTrace(arrival_at, patience_z, service_z, eat_z)`，`student_trace.py:5`；`student.py:106-110/137-141` 已支持 z_score 路径），`ArrivalGenerator` replay trace。baseline 与 intervention 两次运行**共享同一 trace**，只改变窗口状态/干预时刻。
- 联动修复：`/api/campus/config`（`campus_routes.py:362`）改用 `build_random_streams(rng_seed)` 传 `CampusCoordinator`，修掉 `coordinator.py:38-41` 对 N=1 的 service/eat 回退全局 `random`（审查 §7-#2）。

### 3.6 Phase 2 不变量
`/api/config`+`/api/simulation/*`+`_build_state` flat 形状不改；未配 λ(t) 时单食堂行为与今日仿真语义一致。

---

## 4. 3D 场景与交互

### 4.1 舞台 = A+C 混合相机状态机
- **默认/总览态 = A**：明湖学一 3 层竖向堆叠 + 正面剖面切开，斜俯可环绕；右侧三段运维台；全局 KPI。开场视图。
- **下钻/分析态 = C**：点某层或楼层 Tab → 相机飞入该层；**非焦点层滑开收起**（方案 2，给焦点层最大屏幕与最清晰细节）；本层 KPI + 该层窗口网格同屏。
- **人流分析**：焦点层支持「到达→窗口→座位→离场」发光路径高亮，可**点名追踪单个学生**全程；角落常驻堆叠缩略并标当前焦点层；空白处/「全景」→ 回 A。

### 4.2 视觉 identity = 冷青监控
- 沿用现有 `scene3d.js` 深青底（`0x07111d`）/青绿网格（`0x315467`/`0x2dd4bf`），拥堵热力青→琥珀→红渐变；发光流线青；关窗暗 + 「关闭中」标记，空关灰；KPI 青字。与现有 2D 图例语义连续（`canvas_renderer.js` renderLegendBar）。

### 4.3 右侧面板 = 三段竖排运维台
- 顶 = KPI 大数字（总览态显全局；下钻态显本层）。
- 中 = 按楼层分组的窗口开关网格（▣开/▢关可点，关窗即「关闭中」）。
- 底 = 干预事件流滚动日志（时间·层·窗·动作·结果），即 §3.4 `interventions` 的 UI 出口。

### 4.4 派生默认（按现有图例 + scene3d 调色推导，不另行决策）
窗口/座位/学生/关窗的具体配色与相机/剖面手感取现有 `canvas_renderer.js` 图例与 `scene3d.js` 调色为默认，实施时细化；不偏离冷青监控 identity。

---

## 5. 演示叙事与验收

### 5.1 主叙事（一条贯穿线，2–3 分钟）
1. 开场 = A 总览：3 层堆叠剖面、冷青、全局 KPI 平稳。
2. λ(t) 午高峰爬升 + 下课脉冲 → 人流涌入，三层窗口排队/热力青烧到红，全局 KPI（等待↑/排队↑）蹿升。
3. 拥堵爆发后**主动开窗**（开启 physical 窗 → 服务能力↑）；干预事件流即时落条，`shortest_window()` 即时改变窗口候选集与学生分配。
4. 下钻 2F（相机飞入、非焦点层滑开）→ 路径高亮 + 点名追踪某学生，本层 KPI + 该层窗口网格同屏。
5. 推进数分钟 → 排队回落、KPI 下降，**归因于开窗**；干预事件流 + KPI 前后差 = 当场因果证据。
6. 收尾回 A 总览，展示全过程曲线。
- **关窗单列**为负向/异常干预（展示「减服务能力 → 等待恶化」，同为真后端因果），**不与 KPI 改善绑定**。

### 5.2 验收（证明非假动效）
- 后端 snapshot 唯一真值源；干预入 `interventions_json`，history 可事后调出（§3.4 全链）。
- 同一运行内：干预前 snapshot → 干预 API 响应 → 干预后 snapshot → history intervention 记录 → 开放窗数变化 → 队列分布变化 → 等待趋势变化，缺一不可。
- 浏览器 E2E：默认 3D 主屏、console 0 error、canvas 非空像素、WebGL 不可用回退可用、窄屏控件不重叠；证据落 `docs/phase3/`。

---

## 6. 测试策略

### 6.1 回归底线（不可破）
`184 passed` 绿；Phase 2 三接口 + `_build_state` flat 形状不变；未配 λ(t) 时单食堂仿真语义一致；`test_multi_floor.py:29` 不破；`/api/campus/presets/default` + `test_campus_preset_loader/test_campus_api` 不破。

### 6.2 新增后端测试
- 窗口状态机：全 `physical_count` 实例化、初始 `is_open` 子集正确；`shortest_window` 仅取 `is_open`；`open_window_count`/`open_window_capacity_score` 正确。
- 干预：开窗后被后续 `shortest_window` 纳入；关窗停接新、不取消 pending request、原窗 drain；重复开/关 idempotent；拒关最后开放窗 `status:rejected`；事件入 `interventions_json`+history 全链可回读；**干预后立即 `GET /api/campus/history` 即可见该 intervention（无需等 flush 阈值）**。
- ArrivalSchedule：常量 ≡ 旧 `expovariate` 在**仿真语义层完全一致**（同 seed；比较到达序列/随机消费序列，排除 DB id/timestamp）；非常量 `∫λ=N·α·coverage` 归一；trace 带 `service_z/eat_z`。
  - 第一个要写的硬验收测试（具体锚点）：`test_arrival_schedule_constant_matches_legacy` —— 固定 `rng_seed`，断言 `ArrivalSchedule(is_constant=True)` 经新路径生成的到达时刻序列与现 `build_single_canteen_traces()`（`student_trace.py:20`）逐项一致；置于 `backend/tests/`，与 `test_random_streams.py`/`test_student_trace.py` 同风格。
- **硬验收（4.3 非假动效）**：同 `rng_seed` → 同四流 → 同 per-student trace；**无干预两次运行仿真语义结果完全一致**（比较 trace、事件序列、开放窗数、队列分布、KPI timeline、最终 totals；**排除 DB 自增 id 与时间戳**），证明无随机噪声；baseline vs intervention 仅差干预时，开放窗数/队列分布/等待趋势差异**确由干预产生**。

### 6.3 前端契约
`window.CanteenApp3D.init/render/dispose` + `visibleCanteens/pendingCanteens` token 不破；3D 为默认主屏（renderMode 默认改 3D，契约测试相应更新）、2D 兜底仍可用；A+C 状态机/三段面板/干预控件调 campus 干预 API 的契约；`node --check` 覆盖 scene3d/canteen_scene/intervention_ui/state_adapter。

### 6.4 浏览器 E2E 证据
默认 3D 主屏、console 0 error、canvas 非空像素、开/关窗前后 snapshot+KPI+interventions、同 seed A/B 对照、WebGL 回退、窄屏不重叠；落 `docs/phase3/screenshots` + `browser_e2e_check.md` + `three-result.json`。

---

## 7. 风险与边界
- 不把单食堂 3D 退化回「可选彩蛋」；2D 仅兜底/调试，非主演示。
- 不伪造统计：所有指标变化来自后端 snapshot；前端只插值/呈现。
- 关窗不与 KPI 改善绑定（语义为减服务能力）；正向叙事用开窗。
- 不破 Phase 2 兼容面；不复活校园多食堂产品形态。
- 旧 3D 文档清理为本 spec 评审通过后的单独 commit，需列清单单独审。
- 实施前以本 spec 经 spec-document-reviewer 评审 + 用户确认；再由 writing-plans 拆实施计划。

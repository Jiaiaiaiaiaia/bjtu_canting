# 北京交通大学就餐仿真系统 — 系统性代码审查报告

| 项目 | 内容 |
|---|---|
| 仓库 | Canteen（就餐/餐厅就餐仿真系统） |
| 分支 | `codex/canteen-demo-polish` |
| 审查日期 | 2026-05-16 |
| 范围 | 主仓库 `backend/` + `frontend/`（`.worktrees/3d-canteen-digital-twin` 为另一分支副本，不计入） |
| 技术栈 | Python · Flask · SimPy · SQLite · 原生 JS · ECharts · Three.js |
| 测试状态 | `184 passed in 4.69s`（`PYTHONPATH=backend pytest backend/tests -q`） |
| 审查方式 | 全量阅读后端 simulation/api 模块、前端全部 JS/HTML/CSS、presets、测试，结论均给出 文件:行 |

---

## 1. 代码结构与工程质量

**做得好的地方（具体）**

- 分层清晰：`backend/simulation/`（engine/coordinator/canteen/student/router/campus/stats/arrival_generator）、`backend/api/`（routes/campus_routes/db_migrate）、前端 IIFE 模块（CanvasRenderer / AnalysisCharts / campus / floor_tabs）+ ES module `scene3d.js`。
- `SimulationEngine` 作为兼容门面套在 `CampusCoordinator` 上（`engine.py:17-47`），单食堂/校园共用一条 SimPy 代码路径，避免两套引擎。
- `random_streams.py:14-22` 用 1 主种子派生 4 条独立流（arrival/routing/service/eat）+ `student_trace.py` 预生成轨迹，`main.js:566-575` 受控同种子重跑——真正的实验设计水平，超出课程平均。
- `db_migrate.py` 幂等可重入，迁移防御到位。

**问题（具体）**

| 位置 | 问题 |
|---|---|
| `queue_sim.py:5-22`、`dining_sim.py:5-22` | `Window`/`pick_shortest_window`/`Seat`/`pick_nearest_seat` 是 Phase 2 死代码；全仓库仅 `sample_serve_time`/`sample_eat_time` 被引用（`student.py:7-8`）。`canteen.py:11-71` 又定义了一套 `Window`/`Seat` dataclass → 两套 Window/Seat 模型并存，易看错。 |
| `dining_sim.py:15` | `pick_nearest_seat`（按窗口就近选座）是死代码；真实选座是 `student.py:132` `seat_pool.get()` 抢任意座 → 选座逻辑实际上完全无几何。 |
| `api/routes.py:21`、`campus_routes.py:9,28` | 模块级全局 `_session` dict；`campus_routes` `import api.routes as single_routes` 直接改其私有全局 → 全局可变状态，非线程安全，所有用户共用一个仿真；`app.py:23 CORS(app)` 全开放。 |
| `routes.py:171,242,248` | API 直接读引擎私有字段 `engine._is_started/_is_ended`，封装被穿透。 |
| `analysis_charts.js:80-81` 与 `149-150` | 拥堵阈值 `120/45/30/85/70/10` 逐字重复两遍（buildDiagnosis 与 buildInterventions），改一处忘另一处必出 bug。 |
| 魔法数字遍布 | `canvas_renderer.js:55,126`(队列截断 12)、`108,142`(等位截断 10)、`85`(座位热力 `30*60`)、`158`(lerp 0.4)；`scene3d.js:243,256` `slice(0,90)/(0,80)`；`queue_sim.py:27`/`dining_sim.py:28` `std=0.2*mean` 写死；`index.html:50-70` 默认值与 `main.js:52-59 DEFAULTS` 重复，会漂移。 |
| 配置不集中 | 单→校园映射硬编码在 `engine.py:77-124`；前端阈值散在 JS；无统一常量/schema 模块。 |
| 扩展性 | 预设 JSON 增食堂/楼层/窗口支持良好（`canteen.py:109-135`），但 `minghu_xueyi.json:23` 的 `by_type`（rice/noodle/specialty）只解析不使用，无法按窗口类型建模；路由是单一硬编码类，无策略插件点。 |

## 2. 模拟逻辑真实性

**先纠正一个判断**：后端不是「看起来在动但没决策」。它是真正的离散事件仿真——SimPy `Resource`/`Store`/process、`expovariate` 到达、`normalvariate` 服务，且有真实决策：软概率选食堂（`router.py:47-60`）、耐心超时切换（`student.py:66-94`）、最短队列（`canteen.py:167-168`）。

**但理想化非常严重：**

1. **到达过程过于理想** — `arrival_generator.py:50-61,110-123` 是恒定速率齐次泊松 `λ = N·α·coverage/T`。无午餐尖峰爬升曲线，无批量到达（下课铃 → 成群涌入）。`peak_beta` 字段定义了却明确不用（`arrival_generator.py:54-56` 注释、`_campus.json:5`）。单食堂同样恒定（`student_trace.py:20-40`）。
2. **单食堂模式退化** — `engine.py:119,121` 写死 `typical_wait_seconds=0`、`max_switches_per_student=0` → 耐心超时 `try_switch` 必返回 None（`router.py:67-68`）→ `student.py:96 yield req` 无限硬等 → 单食堂无 balking、无 reneging、无 jockeying、无走路。本质是 FIFO 多窗口 + 共享座位池的教科书排队。
3. **无空间模型** — 学生位置是逻辑状态（`canteen.py:210-235`），不是坐标。`canvas_renderer.js:158-173` lerp 0.4 只是在固定槽位间插值，看着像流动，实则无寻路、无通道宽度、无碰撞、无拥堵扩散；就餐中学生不画成点（只染座位色）。
4. **选座无几何** — 座位是 `simpy.Store` FIFO（`canteen.py:147-149` + `student.py:132`），3 楼学生可瞬间拿到 1 楼座位，无走到座位过程，`floor_id` 选座时被忽略。
5. **服务/就餐分布失真** — `queue_sim.py:25-33`/`dining_sim.py:25-34` 用对称正态截断。真实打饭/就餐右偏（应 lognormal/gamma）；`by_type` 不影响速度。

**结论**：后端排队动力学是真的，但属「理想 M/G/c」级别；校园模式补了路由/走路/切换，但跑在占位数据上（`_campus.json:20`、`minghu_xueyi.json:11` 全是 `_TODO_field_research_pending`）。

## 3. 展示效果与交互体验

**强项**：四页结构（`index.html`）、实时信息面板、图例栏（`canvas_renderer.js:176-192`）、播放/暂停/速度×1/2/5/10/结束/重置、校园 2D SVG 地图 + Three.js 3D + 2D 回退、楼层 Tab、食堂切换。分析页的拥堵诊断（`analysis_charts.js:60-125` 规则可解释）、干预建议（`132-197` 带优先级）、受控同种子方案对比（`main.js:598-641`）三块，把它从「动画」提升到「有分析价值」。

**展示短板**

- 运行页无实时拥堵热力图/排队随时间曲线；队列时间线只在仿真结束后的分析页出现（`analysis_charts.js:434-446`）。
- 实时画布每窗口最多画 12 排队 + 10 等位点（`canvas_renderer.js:55-58,107-109,126,142`），人数一大就饱和，视觉误导。
- 就餐人群不可见（只数字 + 座位染色）。
- `canteen.py:270` 单食堂 `avg_waiting_time` 占位 0.0，只有 campus_totals 修正。
- 运行中不能改参数，必须重置；单食堂模式 0 切换 0 走路，「校园分流」故事在单食堂讲不出。
- 面向非专业观众的屏上解释/单位说明偏少。

## 4. 实际应用价值

**已具备**：预设 JSON 摄入（`presets/*.json` + `loader.py`）、SQLite 历史持久化（`routes.py:36-66`）、可解释诊断+干预+受控 A/B、4 条可复现随机流。

**离真实应用还差**

- **无数据输入接口**：无 CSV/刷卡流水/历史客流导入；预设全是手写 JSON 且 `_TODO_field_research_pending`。
- **可复现性缺陷（实锤）**：校园模式 `campus_routes.py:362` 只传一个 rng，`coordinator.py:40-41` 令 `service_rng=eat_rng=None`，于是 `queue_sim.py:29`/`dining_sim.py:31` 回退全局 `random` → 校园模式即使设 rng_seed 也不可复现，且跨次运行污染全局 RNG。单食堂模式正确（`engine.py:26`）。
- **无校准/验证**：`minghu_xueyi.json:10 observed_peak_queue:25` 从未与仿真对比；无 RMSE/CI/预热期/重复，单次运行无误差棒。
- **无结果导出**（CSV/JSON），只能 DB→图表。
- **多方案对比**：单食堂有自动 A/B，校园模式被禁用（`main.js:579-583`）；无批量参数扫描。
- 输入校验浅（`routes.py:69-88` 仅 >0；`campus_routes.py:31-56` 不深校 router/canteen 子字段）。

## 5. 算法与性能

- `engine._advance_until_visible_change`（`engine.py:159-185`）逐微事件 `env.step()`，每步重算 `_semantic_metrics()`→`canteen.snapshot()` O(W+S+N) 并比对全体学生元组（`engine.py:194-199`），随后 `_build_state` 再 snapshot 一次 → 每可见 step ≈ O(微事件·N)。
- `engine.history` 每可见 step 追加且内存不裁剪（`engine.py:154`），`_aggregate_timeline` 全量扫描（`324-346`）。
- finish 同步在请求里最多 200 万步建快照（`routes.py:246-258`/`campus_routes.py:443-460`）。真实规模 `_campus.json` ≈ 28000·0.65·0.65/90 ≈ 131/分钟 × 5400s ≈ 1.18 万学生，O(E·N) 会拖垮/超时 Flask 请求；演示预设故意缩到 180 人/300s（`loader.py:11-15`）掩盖。
- 无 O(n²) 碰撞（因无空间模型——这也是它无法做空间真实性的原因）。仿真层/可视层确实分离，架构正确。
- `database/simulation.db` 本地已 144MB，`simulation_snapshot` 每可见 step 一行从不清理，`/history` `SELECT *` 无分页（`routes.py:308-313`）。
- **结论**：≤约 1–2k 学生演示流畅；10k+ 真实规模同步跑不动。

## 6. 数据与参数设计

- 可配置：单食堂 6 参数有 min/max（`index.html:47-72`）+ 后端 >0 校验；校园走 JSON 预设（楼层/窗口/座位齐全）。`avg_serve`/`avg_eat` 的 std=0.2·mean 不可配（写死）。
- 随机性：有（expovariate + normalvariate）。种子：单食堂 4 独立流 + trace，受控对比复用同种子——优秀；校园模式部分失效（见 §4）。
- 默认值/边界：HTML 有 min/max，后端有 >0；但无上界、无预热期、无重复次数；`peak_beta` 闲置；无结果导出；预设数据全是占位。

## 7. 主要问题总结

| # | 问题 | 严重度 | 对展示影响 | 对应用影响 | 推荐修改方向 |
|---|---|---|---|---|---|
| 1 | 到达为恒定泊松，无尖峰/批量；`peak_beta` 闲置 | 高 | 看不到「下课涌入」高潮，演示平淡 | 高峰预测失真，结论不可信 | `arrival_generator` 改时变强度 λ(t) + 批量到达；启用 `peak_beta` |
| 2 | 校园模式 service/eat RNG 回退全局 random，不可复现 | 高 | 无 | 实验不可重复，结论无法验证 | `campus_routes.py:362` 改用 `build_random_streams`，传入 coordinator |
| 3 | 无空间/寻路模型，选座无几何，就餐者不可见 | 高 | 像示意图非仿真，拥堵位置看不出 | 不能做动线/选址分析 | 引入网格坐标 + A* 寻路 + 按楼层/距离选座 |
| 4 | 单食堂退化：无 balking/reneging/jockeying | 中 | 单食堂分流故事讲不出 | 排队模型不真实 | 单模式也开 patience/换队，参数可配 |
| 5 | 全局 `_session`、穿透私有、CORS 全开 | 中 | 多人演示互相覆盖 | 不可多用户/不可上线 | 会话化（session id）+ 引擎公有 API |
| 6 | 死代码/双 Window-Seat 模型、阈值重复两遍 | 中 | 无 | 维护易引 bug | 删 `queue_sim`/`dining_sim` 类，阈值抽常量 |
| 7 | 无数据导入/校准/导出，预设全占位 | 中 | 无 | 无法对接真实数据做决策 | 加 CSV 导入 + 校准对比 + 结果导出 |
| 8 | finish 同步 2M 步 + history 不裁剪 + 144MB DB | 中 | 大规模卡死/超时 | 无法跑真实规模 | 异步任务 + 快照下采样 + DB 清理/分页 |
| 9 | 实时无热力图，画布点数截断误导 | 中 | 拥堵程度无法量化感知 | 无可解释拥堵定位 | 实时拥堵热力 + 数值标注替代截断 |
| 10 | 服务/就餐用对称正态，by_type 不生效 | 低 | 无 | 服务时间分布失真 | 改 lognormal/gamma，按窗口类型差异化 |

## 8. 改进方案（三档）

### A. 快速展示版（1–2 天，最高性价比 6 条）

1. `arrival_generator` 加分段强度：午餐前 10 分钟线性爬升到峰值再衰减（用已有 `peak_beta`），演示立刻有「高潮」。
2. 实时拥堵热力：复用 `campus_map.js:171` intensity 思路，给运行页画布窗口/区域按 `queue_load` 染色 + 数值标注，替代 `canvas_renderer.js:55,107` 的点截断。
3. 修 §7-#2：`campus_routes.py:362` 用 `build_random_streams` 传 coordinator，让校园模式可复现。
4. 单食堂打开切换演示：`engine.py:119,121` 放开 `typical_wait_seconds`/`max_switches`。
5. 运行页加排队随时间迷你折线（数据已在 `engine.history`，无需后端改）。
6. 抽常量：把 `analysis_charts.js:80-81/149-150` 阈值与 `canvas_renderer.js` 魔法数提到 `constants.js`。

### B. 课程/比赛作品版（架构+算法+指标升级）

- **空间化**：食堂平面引入网格坐标，学生=Agent，入口→窗口→座位→出口用 A* 寻路，通道设宽度容量 → 真正 ABM；可视层据坐标渲染。
- **到达建模**：非齐次泊松 + 课程表驱动批量到达；服务时间改 lognormal/gamma，按 `by_type` 差异化。
- **指标体系**：加预热期、N 次重复、均值±95%CI、窗口利用率/Little's law 校验、瓶颈定位。
- **性能**：finish 改后台任务 + 进度轮询；快照按分钟下采样写库；`/history` 分页；启动清理旧 DB。
- **工程**：`_session` 改 per-session；引擎暴露公有状态；删双 Window/Seat 死代码统一为 `canteen.py` 模型。

### C. 实际应用原型版（管理决策价值）

- **数据接入**：CSV/Excel 导入刷卡流水→反推到达强度曲线；窗口出餐速度、座位数、平面图坐标导入。
- **校准与验证**：用 `observed_peak_queue` 等实测做参数标定（最小化仿真-实测 RMSE），输出拟合优度；warm-up + replication + CI。
- **决策输出**：方案对比矩阵（增窗口/改动线/调座位/错峰）→ 对照表 + 导出 CSV/PDF。
- **可解释性**：把 `buildDiagnosis`/`buildInterventions` 升级为带数据支撑的瓶颈归因。
- **多用户/部署**：会话隔离、鉴权、收紧 CORS、异步仿真服务。

## 9. 整体评价（满分 10）

| 维度 | 评分 | 依据 |
|---|---|---|
| 代码工程质量 | 7.0 | 分层清晰、184 测试 4.7s 全过、门面模式优秀；扣分：全局 session、死/重复代码、阈值重复、无中央配置 |
| 模拟真实性 | 5.0 | 真 DES + 真路由决策；但到达恒定无尖峰、单食堂退化无 balking、无空间/选座几何、对称正态、数据占位 |
| 展示效果 | 7.0 | UI 干净、2D/3D、诊断/干预/受控对比有分析价值；扣分：无实时热力、点数截断误导、就餐者不可见 |
| 可交互性 | 7.0 | 暂停/变速/结束/重置/模式/楼层/3D/受控 A/B 齐全；扣分：不能运行中调参、校园无 A/B |
| 可扩展性 | 6.0 | 预设驱动加食堂/楼层好；扣分：策略硬编码、`by_type` 不生效、全局状态、无插件点 |
| 实际应用价值 | 4.0 | 可解释诊断+受控对比是雏形；扣分：无数据导入/校准/导出，校园不可复现，单次无 CI |
| **综合评分** | **5.7** | 课程实训中上水平：工程与测试规范扎实、实验设计意识超出平均；核心差距在「仿真真实性」与「可应用性」——目前是一个做得很认真的理想化排队仿真演示，距离「分析/决策系统」还有 §8-B/C 的距离 |

**一句话总结**：后端是货真价实的 SimPy 离散事件仿真且有决策逻辑（不是假动画），工程规范与测试纪律在课程项目里属上乘；但模型停在「理想 M/G/c + 占位数据」，缺空间、缺尖峰、缺校验、缺数据接入——优先级最高的三件事是 §7 表中的 #1（时变到达）、#2（校园可复现性实锤 bug）、#3（空间/选座几何）。

---

## 附：后续方向决策（2026-05-16，审查之后）

- 经确认，校园联合（多食堂）模式**不是必交/评分交付物，可自由取舍**。
- 决策方向：以**单食堂为唯一主线**深做。技术事实——单食堂门面跑在 `CampusCoordinator` 之上（`engine.py:31`），故「换成单食堂」= 收掉前端/API 的校园面（`index.html:41-44` 模式选项、`campus_routes.py` 蓝图、`presets/` 占位数据停止维护），**保留 coordinator 内核**（单食堂依赖它，184 测试靠它绿），后端核心几乎不动。
- 省下时间按杠杆投到单食堂：§8-A 的时变/批量到达、实时拥堵热力、右偏服务分布、放开 balking/reneging，再补预热期+重复+CI（§8-B）。
- 待办：以上为方向共识，具体范围（删/藏清单、本迭代纳入的 §8 项、截止时间）将经 brainstorming 锁定后再动代码。

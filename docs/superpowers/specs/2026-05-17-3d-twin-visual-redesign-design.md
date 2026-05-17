# 3D 单食堂数字孪生 · 视觉重做设计（V7 全屏沉浸）

状态：Approved（spec-review 通过；用户复核已提 5 处小修 + 2 条计划注意点，应用后进 writing-plans）
日期：2026-05-17
分支：`3d-single-canteen-twin`
关联：`docs/superpowers/specs/2026-05-16-3d-single-canteen-digital-twin-design.md`（功能基线，本稿不改其数据语义）、`docs/superpowers/plans/2026-05-17-3d-single-canteen-digital-twin.md`（Phase A–H 已完成，Task I1 待闭合）

---

## 0. 背景与问题

Phase A–H 已落地「单食堂多层 3D 数字孪生」的**数据与交互内核**（后端唯一真值、运行中窗口干预真改排队、λ(t) 高峰、A+C 相机状态机、`CanteenApp3D` 契约、212 后端测试全绿、干预因果硬验收通过）。

但实测渲染**视觉不达标**：当前 `canteen_scene.js` 是平面网格地板上散落的方块（窗口）+ 碎方块（座位）+ 小球（学生），三层未可读堆叠、无建筑感、无玻璃/雾/阴影/辉光；且整个 3D 被嵌在白色应用外壳的小框里。用户判定「虽是 3D 但没有 3D 的样子，很丑」。

用户已自行迭代出参照原型（**全屏沉浸玻璃数字孪生**：玻璃幕墙建筑、楼层堆叠、垂直交通核、雾、PCF 软阴影、冷青辉光、悬浮玻璃面板、剖切/热力）。该原型即本次视觉目标。

> **参照原型绝对路径（重要）**：`/Users/sissi/PycharmProjects/Canteen/.superpowers/brainstorm/96186-1778598663/canteen-three-real-model-v7.html`。`.superpowers/` 被 gitignore，**不随 worktree 检出**；从 worktree `cwd` 用相对路径会找不到，实现/计划阶段须用上述**主仓库绝对路径**读取该原型作视觉参照（不复制其静态 `CANTEENS` 数据）。

**用户决策（已确认）**
- 布局：**全屏沉浸（V7 风格）** —— 仿真运行视图内 3D 占满视口，玻璃面板悬浮，去掉白色应用外壳；其余 2D 页（参数/分析/历史）不变。
- 精细度：**对齐 V7 + 后处理增强** —— 达到 V7 场景/质感水准，再加轻量 Bloom 辉光与更好材质。
- 解除原 Task I1「只改 docs/phase3」文件范围限制。

## 1. 目标

把已验证的实时数字孪生内核，用 V7 级视觉重新表达，且**不回退任何已验证能力**：

1. 仿真运行 3D 态为全屏沉浸 V7 观感（玻璃建筑 + 雾 + 软阴影 + 冷青辉光 + 悬浮玻璃面板 + 可读三层堆叠 + 剖切/热力 + 平滑相机）。
2. 仍由后端实时快照驱动（`StateAdapter` 帧），运行中窗口干预仍真改后端排队并即时入历史。
3. `window.CanteenApp3D` 契约、Phase 2 接口形状、212 后端测试、无 WebGL 2D 兜底全部不破。
4. 顺带修复 390×780 窄屏「运维台 / 拥堵图例」重叠且溢出视口的真实缺陷。
5. 收尾按新视觉重出 spec §6.4 浏览器 E2E 证据并闭合 Task I1。

**非目标（Out of scope）**
- 不改后端任何代码 / 数据语义 / API 形状。
- 不恢复校园沙盘、跨食堂路由、`in_transit`、学活待补点位（2026-05-16 spec §0 已 drop，维持）。
- 不引入前端框架 / 构建步骤 / 运行时 CDN；不做与本目标无关的重构。
- 不把 V7 原型的**静态 `CANTEENS` 数据**带入（违背「后端唯一真值」）。

## 2. 设计原则与硬约束

- **后端唯一真值，零后端改动**：渲染只读 `StateAdapter` 帧；212 后端测试因不碰后端而自然全绿（仍作回归门）。
- **契约逐字保留**（契约测试 `backend/tests/test_frontend_three_js_contract.py`）：`scene3d.js` 内
  `window.CanteenApp3D = {`、`init(container)`、`render(snapshot, appState)`、`dispose()`、`visibleCanteens`、`pendingCanteens` 字面不删；`state_adapter.js`/`canteen_scene.js`/`intervention_ui.js` 三文件继续存在。
- **无 WebGL 兜底逐字保留**（`scene3d.js` 头注释列明的不变量）：`let webglAvailable = true;`、`webglAvailable = false;`、`if (!webglAvailable || !renderer || !contentGroup) {`、`showFallback(document.getElementById('three-stage'));`、`return;` 保留。
- **兜底边界（消歧）**：`.three-fallback` **仅当 WebGL 不可用**时出现；**Bloom/composer 初始化或运行失败不触发兜底**，只关闭后处理并继续 `renderer.render(scene, camera)`（仍是 3D，仅无辉光）。两条路径互斥，不得混用。
- **main.js 契约逐字保留**（`backend/tests/test_frontend_main_js_contract.py`）：`async function loadSingleCanteenPreset()`、`/api/campus/presets/single-canteen`、`async function loadDefaultCampusPreset()`、`/campus/presets/default`、`renderMode: '3d'`、`state.renderMode = '3d'`，且不得出现 `renderMode: '2d'` / `state.renderMode = '2d'`，`canvas_renderer` 兜底分支保留。
- **本地资源**：three@0.164.1 已本地 vendored；后处理须 vendor **three 0.164.1 的 addon 依赖闭包**（至少 `EffectComposer`/`RenderPass`/`ShaderPass`/`UnrealBloomPass`/`Pass.js`/`CopyShader`/`LuminosityHighPassShader`，若用 composer 正确输出色链还需 `OutputPass.js`；**确切闭包由实现计划逐一解析 import 后确定**），并**保留 `examples/jsm/postprocessing` 与 `examples/jsm/shaders` 相对目录结构**（否则模块间相对 `import` 断链）；全部入本地 importmap，运行时不连网。
- **冷青 identity 不偏离**（2026-05-16 spec §4.2）：背景 `#07111d`、网格青 `#2dd4bf`/`#315467`、热力青→琥珀→红、流线青、关窗暗灰、KPI 青字；V7 调色与之一致（青 `#52d6d1`、绿 `#77d993`、红 `#d64a55`、金 `#e7bd63`）。
- **小步、隔离、可独立理解**：新增视觉单元为独立小模块，facade 不变；不破既有 `applyViewState()` 分支语义（沉浸态用独立 class，不改原 hidden 逻辑判断）。

## 3. 架构与模块边界

仍是 `scene3d.js`（CORE + 唯一对外 facade）委派三协作单元，本稿**新增两个小模块**并就地强化两个：

| 模块 | 角色 | 本稿改动 |
|---|---|---|
| `scene3d.js` | CORE：renderer/scene/camera/动画循环/facade；契约 token | 加灯光/雾/tone-mapping/`scene_fx` 装配；`render/init/dispose` 接 composer；契约与兜底 token 不动 |
| `state_adapter.js` | 离散 snapshot → 插值帧 | 不变（数据语义稳定）；如需补几何所需字段，仅在帧对象上**追加**只读字段，不改既有字段 |
| `canteen_scene.js` | 单食堂多层场景 + A+C 相机 | **重做几何/材质**：站台基座、每层 slab、玻璃幕墙前壁（剖切切换）、半透背/侧墙、垂直交通核、楼层标牌、窗口/桌组/座位点/队列/学生、焦点发光流线；加大层距使三层可读堆叠；相机取景居中 |
| `intervention_ui.js` | 三段运维台 + 窗口干预 API 出口 | 改 V7 玻璃面板观感（KPI metric-grid / 楼层列表 / 干预日志 / 图例）；**DOM 结构关键钩子与 toggle API 端点不变**（`#three-ops-console`、`.ops-grid .ops-win button`、`.ops-log`、`POST /api/campus/canteens/<cid>/windows/<wid>/toggle`） |
| `scene_fx.js`（新增） | 后处理：EffectComposer + RenderPass + UnrealBloomPass + ACESFilmic tone-mapping | 仅作用高 emissive（窗口/流线/交通核）；构造/运行失败→降级为 `renderer.render(scene,camera)`（**不触发 `.three-fallback`**，仍 3D） |
| `immersive_ui.js`（新增） | V7 玻璃顶栏（品牌 + 视图段「校园/食堂」+ 工具条「剖/热/播放/复位」）、楼层条、状态行、tooltip | 纯 DOM overlay，挂 `#three-stage`；含**返回 2D / 应用导航入口**保证可达性 |

> 单元判据：每个新模块「做什么/怎么用/依赖谁」可独立说清；`scene_fx`/`immersive_ui` 对 `scene3d` 仅暴露 `mount/update/dispose` 之类窄接口，不触私有。

## 4. 视觉与布局规格

### 4.1 全屏沉浸布局
- 触发条件：**仿真运行页处于激活态** **且** `state.mode==='campus'` **且** `state.renderMode==='3d'`，则 `document.body` 加 `.twin-immersive`，否则移除。注意「当前页」不在 `state` 里，须读 DOM（`#simulation-page.active`），不新增持久状态源。
- 该 class 下：隐藏白色应用导航/页面内边距/2D 专用容器；`#three-stage` `position:fixed; inset:0`（占满视口）；V7 玻璃 overlay 悬浮其上。
- 退出（切 2D / 切其它视图 / 切其它页 / 仿真结束跳分析）→ 移除 class，原 2D 外壳与参数/分析/历史**完全复原**。
- 玻璃顶栏内提供「返回/2D」「参数·分析·历史」入口（不丢可达性）；2D 兜底分支保留。
- 实现方式：`main.js` 新增 `syncImmersiveShell()` —— 计算 `isImmersive = document.getElementById('simulation-page')?.classList.contains('active') && state.mode==='campus' && state.renderMode==='3d'`，`document.body.classList.toggle('twin-immersive', isImmersive)`。**由 `showPage()` 与 `applyViewState()` 两处都调用**（因 `showPage()` 现不调用 `applyViewState()`，仅靠后者会在切到分析/历史页时残留 `body.twin-immersive`）。不改 `applyViewState()` 既有 hidden 判断，不引入新持久状态。
- **契约硬约束**：沉浸切换与「返回/2D」入口只用 `.twin-immersive` 类与现有 `render-switcher`（`state.renderMode` 经既有路径切回），**严禁**在 `main.js` 出现 `renderMode: '2d'` 或 `state.renderMode = '2d';` 字面 —— `test_frontend_main_js_contract.py::test_preset_first_uses_single_canteen_and_3d_default` 对这两个字面做了否定断言（`not in s`），新增代码触发即回归失败。

### 4.2 场景构图（canteen_scene.js，由实时帧驱动）
- 站台基座（深青 slab）+ 每层：slab（隔层微差或热力色）、**玻璃幕墙前壁**（`剖` 开则隐前壁露内部）、半透背/侧墙、楼层标牌 sprite（`{id} · {windows}窗 · {seats}座`，焦点高亮/非焦点淡出）。
- 窗口：开放=青、服务中=红高亮、关闭=暗灰 + 「关闭中」标记（沿用既有 `is_open/closing/is_serving` 帧字段）。
- 桌组 + 座位点：占用=金/红、空=绿（沿用帧 `seat.status`）。
- 队列/学生 agent：沿用帧 `students`；焦点层叠加「到达→窗口→座位→离场」发光流线（已存在 `_flowPath`，保留并接新材质）。
- 垂直交通核（半透发光）贯通各层 + 入口标记。
- 层距加大 + 墙体/交通核使**三层明确堆叠可读**；A+C 相机状态机（OVERVIEW 堆叠剖面 ⇄ FOCUS 飞入单层、非焦点层滑开）保留，仅调相机取景使建筑居中可辨（同时根治此前下钻命中难、画面扁平）。
- **RAF/重建解耦（实现约束，必须写进计划）**：现状 `scene3d.js:animate()` 每 RAF 调 `canteenScene.update(lastFrame)`，而 `canteen_scene.js:update()` 内含 `_rebuild()`（全量 `_clear()`+重建）。V7 级几何 + Bloom 后**每帧重建**会致性能与 E2E 稳定性风险。计划须把职责拆为：① **snapshot 到来时**（`render()` 路径）重建/更新数据与几何；② **RAF 每帧仅**推进相机插值、楼层滑开、`composer.render()`，不再 `_rebuild()`。facade/契约不变。

### 4.3 质感（冷青，spec §4.2 不偏离）
- 背景 `#07111d` + 径向青/琥珀辉光渐变（CSS shell）；`scene.fog`；renderer：PCFSoftShadowMap、ACESFilmic、`setPixelRatio(min(dpr,2))`。
- 灯光：HemisphereLight + 主 DirectionalLight（投影）+ 冷青 PointLight。
- 玻璃幕墙/墙体半透低粗糙；Bloom 仅提亮窗口/流线/交通核等高 emissive，强度保守可关。

### 4.4 玻璃面板（CSS 移植 V7 → style.css，作用域化）
- 顶栏/工具条/楼层条/状态行/tooltip/三段运维台统一 V7 玻璃观感（`backdrop-filter: blur`、圆角、细边、阴影），全部 scope 在 `.twin-immersive` 下，**不影响**非沉浸态既有样式。
- 移植 V7 的 `@media (max-width:960px)` 响应式（面板重排/收起）——**此举顺带修复** 390×780「`#three-ops-console` 与 `#twin-congestion-legend` 重叠且溢出」真实缺陷（验收见 §6）。

## 5. 数据流（不退回静态）

`dispatchStep → GET /api/campus/step → window.CanteenApp3D.render(snapshot, state)`
→ `StateAdapter.buildFrame(snapshot, appState)` 插值帧
→ `CanteenScene.update(frame)` 重建（新几何/材质）
→ `InterventionUI.render(frame, mode, focusFloorId)`（新玻璃观感）
→ `scene_fx` composer 出图（失败→`renderer.render`）。

窗口干预：运维台按钮 → `POST /api/campus/canteens/<cid>/windows/<wid>/toggle {open}` → 后端即时 flush → `GET /api/campus/history` 即时含该 intervention（Phase E/F 已硬验收，本稿不动）。

## 6. 测试与验收

**回归门（必须全绿）**
- `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` → 212+（不碰后端，期望逐字不变）。
- `node --check <file>`（逐文件，**不用** `--input-type=module --check <file>`，该形式只接受 stdin，Node v25 对文件参数报 `ERR_INPUT_TYPE_NOT_ALLOWED`）：`main.js`、`canvas_renderer.js`、`three/scene3d.js`、`canteen_scene.js`、`state_adapter.js`、`intervention_ui.js`、`scene_fx.js`、`immersive_ui.js` 全过（`node --check` 对 ESM 模块文件可直接语法检查）。
- 契约测试：扩展（不破）`test_frontend_three_js_contract.py`（新增模块存在性 + facade token 仍在）与 `test_frontend_main_js_contract.py`；特别核对 `test_preset_first_uses_single_canteen_and_3d_default` 的否定断言仍成立——`main.js` 中 `"renderMode: '2d'"`、`"state.renderMode = '2d';"` 字面**不得新增**（沉浸切换走 `.twin-immersive` 类，非 `renderMode:'2d'` 路径）。

**视觉/行为硬验收（spec §6.4 浏览器 E2E，按新视觉重出）**
1. 默认进沉浸 3D：`renderMode=3d`、`.twin-immersive` 生效、白色外壳隐藏、canvas 非空像素、三层玻璃建筑可辨。
2. λ(t) 高峰：三层排队/热力随时间变化（实时帧驱动，非伪动画）。
3. 下钻聚焦：点建筑进 FOCUS（非焦点层滑开 + 焦点层流线 + 运维台按层）；相机居中后命中应稳定。*若 headless 合成输入仍不稳，记录为 harness 限制并以 Phase G1 契约测试 + 代码路径佐证（焦点状态机已被覆盖），不掩饰。*
4. 干预因果：运维台开/关窗口 → 后端排队变化 → `GET /api/campus/history` 即时含该 intervention（沿用 Phase E/F 验收口径）。
5. 兜底：禁 WebGL → `.three-fallback` 文案出现、无 WebGL canvas（后处理失败不致崩）；console error（主流程）= 0，故意禁 WebGL 的 THREE 报错单列为预期。
6. 窄屏 390×780：运维台与拥堵图例**互不重叠**且控件不溢出视口（修复验证）。
- 证据落 `docs/phase3/screenshots/`（截图）、`three-result.json`（指标）、`browser_e2e_check.md`（叙述，含 §3 限制如实记录），提交闭合 Task I1。
- **旧证据处置**：仓库现存的 `docs/phase3/screenshots/*`、`three-result.json`、`browser_e2e_check.md` 是 **2026-05-13 demo-polish 期的旧证据**（worktree 内此前的失败 E2E 中间产物已被清回提交态），**不得当作本次视觉验收结果**；计划须明确「按新 V7 视觉重出并覆盖」这些文件。

## 7. 风险与缓解
- **后处理在 SwiftShader/headless 的性能与正确性**：Bloom 默认轻量、可关、构造失败即降级 `renderer.render`；E2E 实测把关；保 `.three-fallback`。
- **沉浸 class 残留/破坏既有视图**：用独立 `.twin-immersive` + `syncImmersiveShell()`，由 `showPage()` 与 `applyViewState()` **两处**调用（仅靠 `applyViewState()` 会在切分析/历史页时残留）；不改既有 hidden 判断；退出即复原；保留 `render-switcher` 2D 入口。
- **每帧重建性能/E2E 稳定性**：见 §4.2「RAF/重建解耦」约束——计划必须落实数据重建与 RAF 渲染分离，否则 V7 几何+Bloom 下掉帧、E2E 截图不稳。
- **契约/测试回归**：契约 token 与 main.js 字面清单逐条核对；新增模块只新增不删除既有；CI 门 = pytest + node --check + 契约测试 + E2E。
- **vendor 版本漂移**：后处理文件必须取 three 0.164.1 同版本，入本地 importmap，禁运行时 CDN。
- **范围蔓延**：仅动 `frontend/static/js/three/*`、`frontend/static/css/style.css`、`frontend/templates/index.html`、`frontend/static/js/main.js`、契约测试、three 后处理 vendor、`docs/phase3/*` 证据、本 spec/plan；不夹带 `docs/phase2/*` 等无关改动。

## 8. 交付物
- 本设计文档（提交）。
- 实现计划（下一步 writing-plans 产出）：按 TDD/小步，幂等可回归，最后闭合 Task I1 的 E2E 证据。

# 总览「分解楼层卡片」实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 总览模式从"三层半透明全细节叠加"重构为"不透明楼层卡片 + 窗口热力块 + 学生光点 + 每层 KPI 标牌";focus 模式与后端零改动。

**Architecture:** 全部改动收敛在 `canteen_scene.js` 的 `_rebuild` 楼层循环(按 `this.mode` 分支)、`canteen_layouts.js` 常量/helper、`state_adapter.js` 一个常数。合同测试(文本 token 锁)与实现同批改:先改测试(RED)再改实现(GREEN)。

**Tech Stack:** Three.js(原生 ESM,无构建)、pytest 文本合同测试、node 子进程运行时测试。

**Spec:** `docs/superpowers/specs/2026-06-12-overview-floor-cards-design.md`(含全部已确认决策,实现遇歧义以 spec 为准)

**基线:** `tests/test_frontend_three_js_contract.py` 113 passed;全量 381 passed。每个 Task 结束必须回到全绿。

**重要工作区背景:** `canteen_scene.js` 与 `tests/test_frontend_three_js_contract.py` 当前含未提交的「垂直交通核 overview-only」改动(已通过全部测试)。**执行本计划前必须先把该 WIP 单独提交**(Task 0),否则后续 Task 的 commit 会把不相干改动卷进来。

**通用约定:**
- 测试命令一律 `./.venv/bin/python -m pytest`,在仓库根目录执行。
- 「合同测试」是文本断言:钉 `frontend/static/js/three/*.js` 源码中的精确字符串。改实现必须同步改 token,反之亦然。
- 每个 Task 的 commit 只 `git add` 该 Task 列出的文件。

---

### Task 0: 提交既有 WIP(前置,需用户确认)

**Files:** 既有未提交改动:`frontend/static/js/three/canteen_scene.js`、`tests/test_frontend_three_js_contract.py`、`frontend/static/js/three/canteen_furniture.js`、`frontend/static/js/three/canteen_layouts.js`、`frontend/static/js/three/scene3d.js`、`.claude/launch.json`

- [ ] **Step 0.1:** 确认全绿:`./.venv/bin/python -m pytest tests -q` → `381 passed`
- [ ] **Step 0.2:** 提交 WIP:

```bash
git add frontend/static/js/three/canteen_scene.js tests/test_frontend_three_js_contract.py frontend/static/js/three/canteen_furniture.js frontend/static/js/three/canteen_layouts.js frontend/static/js/three/scene3d.js .claude/launch.json
git commit -m "fix(3d): A 批次渲染卫生(透明 depthWrite/阴影盒/相机深度/renderOrder 阶梯) + focus 不渲染全楼垂直核"
```

(A 批次与垂直核 WIP 在同两个文件中交织,合并为一个提交;如用户要求拆分则由用户处理后再继续。)

---

### Task 1: 卡片化常量 + 既有合同 token 同步

**Files:**
- Modify: `frontend/static/js/three/canteen_layouts.js`(`OVERVIEW_FLOOR_SLAB_OPACITY`、`OVERVIEW_FLOOR_GRADIENT_OPACITY`)
- Modify: `frontend/static/js/three/state_adapter.js`(`FLOOR_V`,约 line 20)
- Modify: `frontend/static/js/three/canteen_scene.js`(5 处注释)
- Test: `tests/test_frontend_three_js_contract.py`

- [ ] **Step 1.1: 改测试(RED)。** 在 `tests/test_frontend_three_js_contract.py` 做以下精确替换:

| 位置(当前行号附近) | 旧 token | 新 token |
|---|---|---|
| ~903 | `"const FLOOR_V = 104"` | `"const FLOOR_V = 132"` |
| ~1451 | `"const OVERVIEW_FLOOR_GRADIENT_OPACITY = [1.0, 0.64, 0.38];"` | `"const OVERVIEW_FLOOR_GRADIENT_OPACITY = [1.0, 1.0, 1.0];"` |
| ~1453 | `"floor gradient display: 1F pulled forward, upper floors fade back"` | `"floor gradient display: 1F pulled forward; upper floors keep full opacity (cards)"` |
| `test_canteen_floor_surfaces_do_not_hide_lower_levels`(~188) | `"const OVERVIEW_FLOOR_SLAB_OPACITY = 0.07;"` | `"const OVERVIEW_FLOOR_SLAB_OPACITY = 1.0;"` |
| 同上测试 | `"floor surface must not hide lower levels"` | `"opaque floor cards: lower levels stay readable via FLOOR_V spacing"` |
| `test_focused_canteen_floor_uses_stable_readable_light_surface`(~212) | `"const OVERVIEW_FLOOR_SLAB_OPACITY = 0.07;"` | `"const OVERVIEW_FLOOR_SLAB_OPACITY = 1.0;"` |
| 同上测试 | `"floor surface opacity increases only for selected floor focus"` | `"card overview: slabs render opaque in both modes"` |
| `test_state_adapter_keeps_overview_floors_visibly_separated` 内 node 运行时断言(~973) | `assert gaps == [104, 104]` | `assert gaps == [132, 132]` |

(注意最后一行是**运行时数值断言**,不是 token 钉:该测试用 node 真实计算 baseY 间距,FLOOR_V 改 132 后输出必为 [132, 132],漏改会在 Step 1.4 卡红。)

同时把 `test_canteen_floor_surfaces_do_not_hide_lower_levels` 函数名改为 `test_overview_floor_cards_use_opaque_readable_slabs`(语义已变)。

- [ ] **Step 1.2: 验证 RED。** `./.venv/bin/python -m pytest tests/test_frontend_three_js_contract.py -q` → 至少 3 个 FAILED(token 缺失),无 ERROR。
- [ ] **Step 1.3: 改实现(GREEN)。**
  - `canteen_layouts.js`:`OVERVIEW_FLOOR_SLAB_OPACITY = 0.07` → `1.0`;`OVERVIEW_FLOOR_GRADIENT_OPACITY = [1.0, 0.64, 0.38]` → `[1.0, 1.0, 1.0]`。
  - `state_adapter.js` line ~20:`const FLOOR_V = 104;` → `const FLOOR_V = 132;`(行尾注释改为 `// 楼层竖向间距(卡片总览:保证三层卡片在默认俯角下完全分离)`)。
  - `canteen_scene.js` 注释同步(与 Step 1.1 新 token 逐字一致):
    - `_floorGradientDisplay` 内 `// floor gradient display: 1F pulled forward, upper floors fade back.` → `// floor gradient display: 1F pulled forward; upper floors keep full opacity (cards).`
    - `_floorSlabOpacity` 内两行注释 → `// card overview: slabs render opaque in both modes; depth cues come from`<br>`// FLOOR_V spacing + Z offsets, not slab transparency.`
    - `_floorShapeMesh` 内 `// floor surface must not hide lower levels in overview, while focused`(及其后半句)→ `// opaque floor cards: lower levels stay readable via FLOOR_V spacing, not`<br>`// via slab transparency; focused single-floor mode uses the same opaque slab.`
    - `const WALL_H = 90;  // 填满楼层间距 (FLOOR_V-~14)` → `const WALL_H = 90;  // 楼层墙高(focus 独占;低于 FLOOR_V=132 层间距)`
    - 其上一行分节注释 `// ---- Style B: 正面开放，后墙+侧墙填满楼层间距（FLOOR_V≈104，墙高90）----` → `// ---- Style B: 正面开放,后墙+侧墙 focus 独占(FLOOR_V=132,墙高90)----`(无测试钉,顺手修正)
- [ ] **Step 1.4: 验证 GREEN。** `./.venv/bin/python -m pytest tests/test_frontend_three_js_contract.py -q` → 113 passed;`./.venv/bin/python -m pytest tests -q` → 381 passed。
- [ ] **Step 1.5: Commit。**

```bash
git add frontend/static/js/three/canteen_layouts.js frontend/static/js/three/state_adapter.js frontend/static/js/three/canteen_scene.js tests/test_frontend_three_js_contract.py
git commit -m "feat(3d): 总览楼层卡片化常量(slab 1.0/渐变全1/FLOOR_V 132)+ 合同同步"
```

---

### Task 2: 学生光点颜色 helper(overviewStudentDotColor)

**Files:**
- Modify: `frontend/static/js/three/canteen_layouts.js`
- Test: `tests/test_frontend_three_js_contract.py`

- [ ] **Step 2.1: 写失败测试。** 紧跟 `test_transparent_layers_use_explicit_render_order_ladder` 之后新增:

```python
def test_overview_student_dot_color_is_independent_helper():
    s = _canteen_scene_contract_source()
    # 光点配色是独立 helper:focus avatar 的 studentStatusColor() 语义不被触碰。
    for tok in (
        "export const OVERVIEW_DOT_QUEUE_COLOR = 0xe7bd63;",
        "export const OVERVIEW_DOT_SEATED_COLOR = 0x2dd4bf;",
        "export const OVERVIEW_DOT_MOVING_COLOR = 0xf3f6f4;",
        "export function overviewStudentDotColor(student) {",
        "if (pos === 'window_queue' || pos === 'waiting_queue' || pos === 'being_served') return OVERVIEW_DOT_QUEUE_COLOR;",
        "if (pos === 'seated') return OVERVIEW_DOT_SEATED_COLOR;",
        "return OVERVIEW_DOT_MOVING_COLOR;",
    ):
        assert tok in s, f"overview dot color helper missing: {tok!r}"
    assert "export function studentStatusColor(student) {" in s  # 原 helper 原样保留
```

- [ ] **Step 2.2: 验证 RED。** `./.venv/bin/python -m pytest tests/test_frontend_three_js_contract.py -q -k overview_student_dot_color` → 1 failed(token 缺失)。
- [ ] **Step 2.3: 实现。** `canteen_layouts.js` 中 `studentStatusColor` 定义之后追加:

```js
// 总览光点配色(独立于 focus avatar 的 studentStatusColor,合同分别锁定):
// 排队压力(窗口队/等位队/正被服务)→ 琥珀;就座 → 青;其余移动态 → 白。
export const OVERVIEW_DOT_QUEUE_COLOR = 0xe7bd63;
export const OVERVIEW_DOT_SEATED_COLOR = 0x2dd4bf;
export const OVERVIEW_DOT_MOVING_COLOR = 0xf3f6f4;
export function overviewStudentDotColor(student) {
    const pos = student?.position;
    if (pos === 'window_queue' || pos === 'waiting_queue' || pos === 'being_served') return OVERVIEW_DOT_QUEUE_COLOR;
    if (pos === 'seated') return OVERVIEW_DOT_SEATED_COLOR;
    return OVERVIEW_DOT_MOVING_COLOR;
}
```

- [ ] **Step 2.4: 验证 GREEN + 全绿。** 同 Task 1 两条命令,基线 114 / 382。
- [ ] **Step 2.5: Commit。** `git add frontend/static/js/three/canteen_layouts.js tests/test_frontend_three_js_contract.py && git commit -m "feat(3d): overviewStudentDotColor 独立配色 helper(不动 studentStatusColor)"`

---

### Task 3: 总览学生光点(_studentAvatar 分支)

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js`(import + `_studentAvatar` 内分支)
- Test: `tests/test_frontend_three_js_contract.py`

- [ ] **Step 3.1: 写失败测试。**

```python
def test_overview_students_render_as_light_dots():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    avatar_start = s.index("_studentAvatar(")
    avatar_src = s[avatar_start:avatar_start + 4000]
    for tok in (
        "if (this.mode === 'overview') {",
        "overviewStudentDotColor(student)",
        "'overview student light dot'",
        "return avatar;",
    ):
        assert tok in avatar_src, f"overview light-dot branch missing in _studentAvatar: {tok!r}"
    # focus avatar 细节仍在(光点分支不删 avatar 实现)
    for tok in ("studentBody", "studentHead", "studentStatusRing"):
        assert tok in avatar_src, f"focus avatar must stay intact: {tok!r}"
```

- [ ] **Step 3.2: 验证 RED。** `-k overview_students_render_as_light_dots` → 1 failed。
- [ ] **Step 3.3: 实现。**
  - `canteen_scene.js` 顶部 layouts import 列表加入 `overviewStudentDotColor`(放在 `studentStatusColor,` 之后)。
  - `_studentAvatar` 内,定位锚点行 `const clothingColor = stableStudentClothingColor(student);`(其上方是 avatar group 的 userData/位置装配,实施时先读函数开头确认 group 变量名为 `avatar`),在该行**之前**插入:

```js
        if (this.mode === 'overview') {
            // 卡片总览:学生缩为状态色发光点,人流可读、彩屑噪声消失;focus 保持完整 avatar。
            const dotColor = overviewStudentDotColor(student);
            const dot = new THREE.Mesh(
                new THREE.SphereGeometry(1.2, 10, 8),
                new THREE.MeshStandardMaterial({
                    color: dotColor,
                    emissive: dotColor,
                    emissiveIntensity: 0.5,
                    roughness: 0.4,
                })
            );
            dot.name = 'overview student light dot';
            dot.position.set(0, 2.2, 0);
            dot.userData = avatar.userData;
            avatar.add(dot);
            return avatar;
        }
```

  注意:分支在 tracked-halo 逻辑之前返回——总览不渲染追踪光环(spec 未要求,YAGNI)。
- [ ] **Step 3.4: 验证 GREEN + 全绿(115 / 383)+ `node --input-type=module --check < frontend/static/js/three/canteen_scene.js`。**
- [ ] **Step 3.5: Commit。** `git add frontend/static/js/three/canteen_scene.js tests/test_frontend_three_js_contract.py && git commit -m "feat(3d): 总览学生光点(状态色,focus avatar 不动)"`

---

### Task 4: 总览窗口热力块 + 干预动效继承

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js`(windows 循环分支 + 新方法 `_windowHeatBlock`)
- Test: `tests/test_frontend_three_js_contract.py`

- [ ] **Step 4.1: 写失败测试。**

```python
def test_overview_windows_render_as_heat_blocks_with_intervention():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    block_start = s.index("_windowHeatBlock(group, win, floorId)")
    block_src = s[block_start:block_start + 2000]
    for tok in (
        "this._activeWindowInterventionEffect(win, floorId)",
        "'overview window heat block'",
        "heatColor(this.THREE, sat)",
        "PALETTE.windowClosedEmpty",
        "{ floorId, kind: 'window', windowId: win.id }",
        "this._tagWindowInterventionBody(block, interventionEffect);",
        "this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);",
        "QUEUE_HEAT_RENDER_ORDER",
    ):
        assert tok in block_src, f"overview heat block contract missing: {tok!r}"
    # 总览分支替换摊位;focus 摊位调用原样保留
    assert "this._windowHeatBlock(fg, win, floor.floor_id);" in s
    assert "this._addServiceStall(fg, win, floor.floor_id, winIdx," in s
```

- [ ] **Step 4.2: 验证 RED。**
- [ ] **Step 4.3: 实现。**
  - `_rebuild` 楼层循环中,把现有 `floor.windows.forEach((win, winIdx) => { this._addServiceStall(...); });` 改为:

```js
            floor.windows.forEach((win, winIdx) => {
                if (this.mode === 'overview') {
                    // 卡片总览:摊位缩为热力块;干预反馈(高亮+脉冲)显式接管,不随摊位消失。
                    this._windowHeatBlock(fg, win, floor.floor_id);
                    return;
                }
                this._addServiceStall(fg, win, floor.floor_id, winIdx, this._shouldShowWindowLabel(floor, win, winIdx));
            });
```

  - 在 `_addServiceStall` 定义之前新增方法:

```js
    _windowHeatBlock(group, win, floorId) {
        const x = win.position.x;
        const y = win.position.y;
        const z = win.position.z;
        const layoutSide = win.position.side || 'front';
        const interventionEffect = this._activeWindowInterventionEffect(win, floorId);
        const sat = Math.min(1, (win.queue_length || 0) / 12);
        const color = win.is_open ? heatColor(this.THREE, sat).getHex() : PALETTE.windowClosedEmpty;
        const block = addBox(this.THREE, group, 'overview window heat block', [12, 2.4, 18],
            [x, y - 4, z],
            photoMat(this.THREE, color, {
                opacity: 0.9,
                emissive: color,
                emissiveIntensity: win.is_open ? 0.18 : 0.04,
            }),
            { floorId, kind: 'window', windowId: win.id }
        );
        block.renderOrder = QUEUE_HEAT_RENDER_ORDER;
        this._tagWindowInterventionBody(block, interventionEffect);
        this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);
    }
```

- [ ] **Step 4.4: 验证 GREEN + 全绿(116 / 384)+ node --check。**
- [ ] **Step 4.5: Commit。** `git commit -m "feat(3d): 总览窗口热力块(继承干预高亮与脉冲)"`(add 同 Task 3 两文件)

---

### Task 5: 总览隐藏清单(墙/玻璃墙/管线/识别贴/桌椅 → focus 独占)

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js`(`_rebuild` 楼层循环)
- Test: `tests/test_frontend_three_js_contract.py`

- [ ] **Step 5.1: 写失败测试。**

```python
def test_overview_hides_interior_detail_builders():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    loop_start = s.index("frame.floors.forEach(floor => {")
    loop_src = s[loop_start:loop_start + 6000]
    gate = "// overview hides interior detail: walls/glass/pipes/decals/furniture are focus-only"
    assert gate in loop_src, "focus-only gate comment missing"
    gate_idx = loop_src.index(gate)
    gated = loop_src[gate_idx:gate_idx + 2600]
    for tok in (
        "if (this.mode === 'focus') {",
        "this._applyFloorGradientMaterial(backWall.material, floor);",
        "this._applyFloorGradientMaterial(leftWall.material, floor);",
        "this._applyFloorGradientMaterial(rightWall.material, floor);",
        "this._addWallDepthCues(fg, footprint, baseY, floor.floor_id);",
        "this._addPhotoReferenceShell(fg, floor, baseY);",
        "this._addFloorIdentityCues(fg, floor, baseY);",
        "this._addPhotoTableClusters(fg, floor);",
    ):
        assert tok in gated, f"interior builder must sit inside the focus-only gate: {tok!r}"
    # 两种模式都保留的结构锚点(在 gate 之外)
    before_gate = loop_src[:gate_idx]
    for tok in (
        "this._floorEdgeBands(",
        "this._addOpenFloorFrame(fg, footprint, baseY, floor.floor_id);",
        "this._addEntranceMarker(fg, floor.floor_id, baseY, footprint);",
    ):
        assert tok in before_gate, f"structural anchor must stay outside the gate: {tok!r}"
```

- [ ] **Step 5.2: 验证 RED。**
- [ ] **Step 5.3: 实现。** 调整 `_rebuild` 楼层循环顺序与包裹(保持每行原样,只动位置/缩进;`_addOpenFloorFrame`、`_addEntranceMarker` 移到 gate 之前):

```js
            this._addOpenFloorFrame(fg, footprint, baseY, floor.floor_id);
            this._addEntranceMarker(fg, floor.floor_id, baseY, footprint);

            // overview hides interior detail: walls/glass/pipes/decals/furniture are focus-only
            if (this.mode === 'focus') {
                /* backWall/leftWall/rightWall 三段创建代码原样移入 */
                this._addWallDepthCues(fg, footprint, baseY, floor.floor_id);
                this._addPhotoReferenceShell(fg, floor, baseY);
                this._addFloorIdentityCues(fg, floor, baseY);
                this._addPhotoTableClusters(fg, floor);
            }
```

  注意:`_addPhotoTableClusters` 原在 windows 循环之后,移入 gate(摊位循环保持在 gate 外,因 Task 4 已自带 overview 分支)。墙体三段连同各自 `_applyFloorGradientMaterial(...)` 行整体移入(合同 1459-1461 token 不丢)。天花管线/玻璃墙在 `_addPhotoReferenceShell` 内部,随之隐藏。
- [ ] **Step 5.4: 验证 GREEN + 全绿(117 / 385)+ node --check。**
- [ ] **Step 5.5: Commit。** `git commit -m "feat(3d): 总览隐藏内饰细节(墙/玻璃/管线/识别贴/桌椅 focus 独占)"`

---

### Task 6: 每层 KPI 标牌

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js`(`_rebuild` 楼层循环尾部)
- Test: `tests/test_frontend_three_js_contract.py`

- [ ] **Step 6.1: 写失败测试。**

```python
def test_overview_floor_kpi_boards():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "frame.perFloorKpi",
        "k.floor_id === floor.floor_id",
        "`${floor.floor_id}F · 在场 ${kpi.students} · 排队 ${kpi.total_in_queue}`",
        "'overview floor kpi board'",
        "board.userData = { floorId: floor.floor_id, kind: 'floor' };",
    ):
        assert tok in s, f"overview floor KPI board missing: {tok!r}"
```

- [ ] **Step 6.2: 验证 RED。**
- [ ] **Step 6.3: 实现。** 楼层循环内、`this._applyFloorGradientToGroup(fg, floor);` 之前插入:

```js
            if (this.mode === 'overview') {
                // 每层 KPI 标牌:perFloorKpi 用 rawStudentCount 聚合(真实在场数,
                // 非可视上限裁剪后的 students 数组),点击标牌等同点击楼层进 focus。
                const kpi = (frame.perFloorKpi || []).find(k => k.floor_id === floor.floor_id);
                if (kpi) {
                    const board = this._label(
                        `${floor.floor_id}F · 在场 ${kpi.students} · 排队 ${kpi.total_in_queue}`,
                        footprint.minX - 16,
                        baseY + 14,
                        footprint.centerZ,
                        '#e8f4f1',
                        0.92,
                        1.35
                    );
                    board.name = 'overview floor kpi board';
                    board.userData = { floorId: floor.floor_id, kind: 'floor' };
                    fg.add(board);
                }
            }
```

  (**签名注意顺序**:`_label(text, x, y, z, color, opacity, scale = 1, options = {})`——opacity 在 scale 之前(canteen_scene.js:233),上面实参 `0.92, 1.35` 即 opacity=0.92、scale=1.35。返回 sprite,renderOrder 已默认 `DEFAULT_LABEL_RENDER_ORDER`;raycaster 对 `floorId` 命中即进层,sprite 可被 raycast。)
- [ ] **Step 6.4: 验证 GREEN + 全绿(118 / 386)+ node --check + import 守门(`-k import_bindings_resolve`)。**
- [ ] **Step 6.5: Commit。** `git commit -m "feat(3d): 总览每层 KPI 标牌(perFloorKpi,点击进层)"`

---

### Task 7: 浏览器验证 + 相机微调

**Files:**
- 可能 Modify: `frontend/static/js/three/canteen_scene.js`(相机 padding 常量,仅在实测需要时)

- [ ] **Step 7.1:** 起服务(若未运行):`./.venv/bin/python -m canteen`(后台,端口 5001)。
- [ ] **Step 7.2:** 浏览器(preview 工具或用户手动)进 3D 总览,核对清单:
  - 三层不透明卡片完全分离,默认俯角无互相遮挡
  - 卡片上:学生光点(琥珀/青/白)、窗口热力块、KPI 标牌可读
  - 无墙体/玻璃/桌椅/识别贴;边带、楼梯核、入口标记仍在
  - console 0 error
  - 环绕一圈无闪烁
  - 右侧面板开/关窗 → 总览热力块出现高亮+脉冲
  - 点 KPI 标牌进对应层 focus;focus 内全细节(桌椅/摊位/avatar)与改造前一致
  - 热力模式切换正常
- [ ] **Step 7.3:** 若三层取景不佳:微调 `OVERVIEW_CAMERA_Y_PADDING`(118 起步,步进 ±20)与 `OVERVIEW_LOOK_Y_RATIO`(0.54),每次改完浏览器复核;改动需保持 `test_default_twin_view_prioritizes_building_over_empty_ground` 钉的公式 token 不变(只改常量值时同步 token)。
- [ ] **Step 7.4:** 最终全绿:合同文件 + 全量;截图存证(用户终审)。
- [ ] **Step 7.5: Commit(如有相机改动)。** `git commit -m "feat(3d): 总览相机取景微调(三层卡片全可见)"`

---

## 不变量(每个 Task 自检)

1. focus 模式渲染分支零行为变化(只允许代码被移动进 `if (this.mode === 'focus')`)。
2. `/api/config`、`/api/simulation/*`、campus API 响应形状零接触。
3. `studentStatusColor()`、`stableStudentClothingColor()` 函数体不动。
4. A 批次规则不回退:半透明材质 depthWrite=false、renderOrder 阶梯、camera near/far、`FLOOR_EDGE_BAND_Y_EPSILON`。
5. raycaster 钻取(`kind:'window'`/`floorId`)与干预 UI 事件流不动。

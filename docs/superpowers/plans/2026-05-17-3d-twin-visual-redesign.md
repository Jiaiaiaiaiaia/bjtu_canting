# 3D 单食堂数字孪生 · V7 全屏沉浸视觉重做 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已验证的实时单食堂数字孪生内核，用 V7 级全屏沉浸视觉（玻璃建筑/雾/软阴影/冷青辉光/悬浮玻璃面板）重新表达，且不回退任何已验证能力。

**Architecture:** `scene3d.js` 仍是唯一 facade（`window.CanteenApp3D`），委派 `state_adapter`（实时帧）/`canteen_scene`（重做几何 + RAF 解耦）/`intervention_ui`（玻璃面板）/新增 `scene_fx`（Bloom 后处理）/新增 `immersive_ui`（玻璃 overlay）。后端零改动；渲染只读 `StateAdapter` 帧。沉浸态由 `main.js` 新增 `syncImmersiveShell()` 切 `body.twin-immersive`。

**Tech Stack:** 原生 JS ES module、Three.js 0.164.1（本地 vendored，含 postprocessing/shaders addon 依赖闭包，运行时不连 CDN）、原生 CSS、Flask 静态托管、pytest 契约测试、Node `--check` 语法门、Headless Chrome CDP E2E。

**Spec:** `docs/superpowers/specs/2026-05-17-3d-twin-visual-redesign-design.md`（Approved）。
**V7 视觉参照（主仓库绝对路径，`.superpowers/` 被 gitignore 不随 worktree 检出）：**
`/Users/sissi/PycharmProjects/Canteen/.superpowers/brainstorm/96186-1778598663/canteen-three-real-model-v7.html`
（只作视觉参照，**不复制其静态 `CANTEENS` 数据**；本项目数据来自后端实时帧。）

**全程不变量（每个 Task 的 commit 前都须满足）：**
- 后端零改动 → `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` 维持 `212 passed`。
- `scene3d.js` 契约 token 逐字保留：`window.CanteenApp3D = {`、`init(container)`、`render(snapshot, appState)`、`dispose()`、`visibleCanteens`、`pendingCanteens`。
- 无 WebGL 兜底 token 逐字保留：`let webglAvailable = true;`、`webglAvailable = false;`、`if (!webglAvailable || !renderer || !contentGroup) {`、`showFallback(document.getElementById('three-stage'));`、`return;`。
- `main.js` 不得新增字面 `renderMode: '2d'` 或 `state.renderMode = '2d';`（`test_frontend_main_js_contract.py` 否定断言）。
- `node --check <file>`（**不要** `--input-type=module --check <file>`，Node v25 对文件参数报 `ERR_INPUT_TYPE_NOT_ALLOWED`）。
- 工作目录始终在 worktree `/Users/sissi/PycharmProjects/Canteen/.worktrees/3d-single-canteen-twin`；分支 `3d-single-canteen-twin`。

---

## 文件结构（决策锁定）

| 文件 | 职责 | 动作 |
|---|---|---|
| `frontend/static/js/three/vendor/postprocessing/*.js`、`vendor/shaders/*.js` | three 0.164.1 后处理 addon 依赖闭包 | 新增（vendor，保留相对目录） |
| `frontend/static/js/three/scene_fx.js` | EffectComposer+RenderPass+UnrealBloomPass+ACESFilmic；失败降级 `renderer.render` | 新增 |
| `frontend/static/js/three/immersive_ui.js` | V7 玻璃顶栏/工具条/楼层条/状态行/tooltip + 返回2D/导航入口 | 新增 |
| `frontend/static/js/three/scene3d.js` | CORE/facade：灯光/雾/tone-mapping/composer 装配；RAF 解耦 | 改 |
| `frontend/static/js/three/canteen_scene.js` | V7 几何重做；`update()`(快照重建) 与 `tick()`(RAF 推进) 拆分 | 改 |
| `frontend/static/js/three/intervention_ui.js` | 三段台 V7 玻璃观感；DOM 钩子/端点不变 | 改 |
| `frontend/static/js/three/state_adapter.js` | 仅按需在帧对象**追加**只读字段 | 改（可能极小/不改） |
| `frontend/templates/index.html` | importmap 加 postprocessing/shaders；加 scene_fx/immersive_ui module 标签 | 改 |
| `frontend/static/css/style.css` | `.twin-immersive` 作用域玻璃面板+全屏+`@media` 响应式（修窄屏重叠） | 改 |
| `frontend/static/js/main.js` | 新增 `syncImmersiveShell()`，`showPage()`+`applyViewState()` 调用 | 改 |
| `backend/tests/test_frontend_three_js_contract.py` | 扩展：新模块存在 + facade/兜底 token 仍在 + RAF 解耦 token | 改 |
| `backend/tests/test_frontend_main_js_contract.py` | 扩展：`syncImmersiveShell` 定义/被调；负 `'2d'` 断言仍立 | 改 |
| `backend/tests/test_twin_visual_assets_contract.py` | vendor 闭包存在 + importmap 条目 + style.css 沉浸 token | 新增 |
| `docs/phase3/screenshots/*`、`three-result.json`、`browser_e2e_check.md` | 按新 V7 视觉重出并覆盖旧证据 | 改（Task I1 收尾） |

> 既有 `docs/phase3/screenshots/*` 等是 2026-05-13 旧证据，**不得**当作本次验收，Task V10 覆盖。

---

## Task V1：vendor three 0.164.1 后处理依赖闭包 + importmap

**Files:**
- Create: `frontend/static/js/three/vendor/postprocessing/{EffectComposer,Pass,RenderPass,ShaderPass,MaskPass,UnrealBloomPass,OutputPass}.js`
- Create: `frontend/static/js/three/vendor/shaders/{CopyShader,LuminosityHighPassShader,OutputShader}.js`
- Modify: `frontend/templates/index.html`（importmap）
- Test: `backend/tests/test_twin_visual_assets_contract.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_twin_visual_assets_contract.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "frontend/static/js/three/vendor"

def test_postprocessing_dependency_closure_vendored():
    pp = VENDOR / "postprocessing"
    sh = VENDOR / "shaders"
    for f in ("EffectComposer", "Pass", "RenderPass", "ShaderPass",
              "MaskPass", "UnrealBloomPass", "OutputPass"):
        assert (pp / f"{f}.js").is_file(), f"missing postprocessing/{f}.js"
    for f in ("CopyShader", "LuminosityHighPassShader", "OutputShader"):
        assert (sh / f"{f}.js").is_file(), f"missing shaders/{f}.js"

def test_importmap_has_postprocessing_entries():
    html = (ROOT / "frontend/templates/index.html").read_text(encoding="utf-8")
    for spec in ("three/addons/postprocessing/EffectComposer.js",
                 "three/addons/postprocessing/RenderPass.js",
                 "three/addons/postprocessing/UnrealBloomPass.js",
                 "three/addons/postprocessing/OutputPass.js",
                 "three/addons/shaders/CopyShader.js"):
        assert spec in html, f"importmap missing {spec}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_twin_visual_assets_contract.py -q`
Expected: FAIL（文件/importmap 条目不存在）。

- [ ] **Step 3: vendor 依赖闭包（一次性下载，运行时不连网）**

Run（与已 vendored three 同版本 0.164.1）：
```bash
cd /Users/sissi/PycharmProjects/Canteen/.worktrees/3d-single-canteen-twin
mkdir -p frontend/static/js/three/vendor/postprocessing frontend/static/js/three/vendor/shaders
B=https://unpkg.com/three@0.164.1/examples/jsm
for f in postprocessing/EffectComposer postprocessing/Pass postprocessing/RenderPass \
         postprocessing/ShaderPass postprocessing/MaskPass postprocessing/UnrealBloomPass \
         postprocessing/OutputPass shaders/CopyShader shaders/LuminosityHighPassShader \
         shaders/OutputShader; do
  curl -fsSL "$B/$f.js" -o "frontend/static/js/three/vendor/$f.js"
done
```
闭包完整性判据：下一步 `node --check` 全过且无未解析相对 `import`。若 `node --check` 或后续 Task V2 import 报缺某文件，**追加**该文件到对应 `postprocessing/` 或 `shaders/` 目录（保持相对结构），直至闭包闭合。

- [ ] **Step 4: 语法门**

Run: `for f in frontend/static/js/three/vendor/postprocessing/*.js frontend/static/js/three/vendor/shaders/*.js; do node --check "$f" || echo "FAIL $f"; done; echo done`
Expected: 无 `FAIL`。

- [ ] **Step 5: importmap 接线**

在 `frontend/templates/index.html` 既有 importmap（含 `"three"` 与 `"three/addons/controls/OrbitControls.js"`）的 `imports` 内追加（路径用 `url_for('static', ...)` 与既有条目同风格）：
```
"three/addons/postprocessing/EffectComposer.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/EffectComposer.js') }}",
"three/addons/postprocessing/Pass.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/Pass.js') }}",
"three/addons/postprocessing/RenderPass.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/RenderPass.js') }}",
"three/addons/postprocessing/ShaderPass.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/ShaderPass.js') }}",
"three/addons/postprocessing/MaskPass.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/MaskPass.js') }}",
"three/addons/postprocessing/UnrealBloomPass.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/UnrealBloomPass.js') }}",
"three/addons/postprocessing/OutputPass.js": "{{ url_for('static', filename='js/three/vendor/postprocessing/OutputPass.js') }}",
"three/addons/shaders/CopyShader.js": "{{ url_for('static', filename='js/three/vendor/shaders/CopyShader.js') }}",
"three/addons/shaders/LuminosityHighPassShader.js": "{{ url_for('static', filename='js/three/vendor/shaders/LuminosityHighPassShader.js') }}",
"three/addons/shaders/OutputShader.js": "{{ url_for('static', filename='js/three/vendor/shaders/OutputShader.js') }}"
```
注意：vendored three 的 postprocessing 文件内部用相对 `import './Pass.js'` / `'../shaders/CopyShader.js'`，**保留目录结构**即可解析；importmap 仅供 `scene_fx.js` 与 `index.html` 用裸 specifier 引入。

- [ ] **Step 6: 验证通过 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_twin_visual_assets_contract.py -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 新测试 PASS；全量 `212 + ...`（仅新增测试增量，后端不变）全绿。

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/three/vendor/postprocessing frontend/static/js/three/vendor/shaders frontend/templates/index.html backend/tests/test_twin_visual_assets_contract.py
git -c user.name=Sissi commit -m "feat(3d/vendor): vendor three 0.164.1 postprocessing closure + importmap"
```

---

## Task V2：`scene_fx.js`（Bloom 后处理 + 失败降级）

**Files:**
- Create: `frontend/static/js/three/scene_fx.js`
- Test: `backend/tests/test_frontend_three_js_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_three_js_contract.py
from pathlib import Path
THREE_DIR = Path(__file__).resolve().parents[2] / "frontend/static/js/three"

def test_scene_fx_module_contract():
    s = (THREE_DIR / "scene_fx.js").read_text(encoding="utf-8")
    assert "export class SceneFX" in s
    assert "three/addons/postprocessing/EffectComposer.js" in s
    assert "UnrealBloomPass" in s
    assert "ACESFilmicToneMapping" in s
    # 失败降级、不触发 .three-fallback
    assert "this.enabled = false" in s
    assert "renderer.render(" in s
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_scene_fx_module_contract -q`
Expected: FAIL（文件不存在）。

- [ ] **Step 3: 实现 `scene_fx.js`（完整）**

```javascript
// scene_fx.js — 后处理：Bloom + ACESFilmic。失败只关后处理，不触发 .three-fallback。
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export class SceneFX {
  constructor() {
    this.enabled = false;
    this.composer = null;
    this._renderer = null;
    this._scene = null;
    this._camera = null;
  }

  // 装配；任何失败 → enabled=false（调用方回落 renderer.render(scene,camera)）。
  mount(renderer, scene, camera) {
    this._renderer = renderer; this._scene = scene; this._camera = camera;
    try {
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      const size = renderer.getSize(new THREE.Vector2());
      const composer = new EffectComposer(renderer);
      composer.addPass(new RenderPass(scene, camera));
      const bloom = new UnrealBloomPass(
        new THREE.Vector2(Math.max(1, size.x), Math.max(1, size.y)),
        0.65,   // strength（保守，仅提亮高 emissive）
        0.4,    // radius
        0.85    // threshold（仅窗口/流线/交通核等高亮溢出）
      );
      composer.addPass(bloom);
      composer.addPass(new OutputPass());
      this.composer = composer;
      this.enabled = true;
    } catch (err) {
      this.enabled = false;
      this.composer = null;
    }
  }

  setSize(w, h) {
    if (this.enabled && this.composer) {
      try { this.composer.setSize(w, h); } catch (e) { this.enabled = false; }
    }
  }

  // 由 RAF 调用：enabled 走 composer，否则回落基础渲染（仍 3D，无辉光）。
  render() {
    if (this.enabled && this.composer) {
      try { this.composer.render(); return; } catch (e) { this.enabled = false; }
    }
    if (this._renderer && this._scene && this._camera) {
      this._renderer.render(this._scene, this._camera);
    }
  }

  dispose() {
    try { this.composer?.dispose?.(); } catch (e) { /* noop */ }
    this.composer = null; this.enabled = false;
    this._renderer = this._scene = this._camera = null;
  }
}
```

- [ ] **Step 4: 验证通过 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --check frontend/static/js/three/scene_fx.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 契约测试 PASS；`node --check` 退出 0；全量回归全绿。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/scene_fx.js backend/tests/test_frontend_three_js_contract.py
git -c user.name=Sissi commit -m "feat(3d): scene_fx Bloom+ACES with graceful degrade (no .three-fallback)"
```

---

## Task V3：`scene3d.js` — 灯光/雾/tone-mapping/composer + RAF 解耦（契约/兜底不破）

**Files:**
- Modify: `frontend/static/js/three/scene3d.js`
- Modify: `backend/tests/test_frontend_three_js_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_three_js_contract.py
def test_scene3d_fx_and_raf_decouple_contract():
    s = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    # 契约 token 仍在
    for tok in ("window.CanteenApp3D = {", "init(container)",
                "render(snapshot, appState)", "dispose()",
                "visibleCanteens", "pendingCanteens",
                "let webglAvailable = true;", "webglAvailable = false;",
                "if (!webglAvailable || !renderer || !contentGroup) {",
                "showFallback(document.getElementById('three-stage'));"):
        assert tok in s, f"missing contract token: {tok!r}"
    # scene_fx 接入
    assert "import { SceneFX } from './scene_fx.js'" in s
    assert "sceneFX" in s
    # RAF 解耦：animate 不再调 canteenScene.update（避免每帧 _rebuild）
    import re
    m = re.search(r"function animate\(\)\s*\{.*?\n\}", s, re.S)
    assert m, "animate() not found"
    assert "canteenScene.update(" not in m.group(0), \
        "animate() must NOT call canteenScene.update (per-RAF rebuild)"
    assert "canteenScene.tick(" in m.group(0), "animate() should call canteenScene.tick()"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_scene3d_fx_and_raf_decouple_contract -q`
Expected: FAIL。

- [ ] **Step 3: 改 `scene3d.js`（按点改，勿动契约/兜底 token）**

读 V7 绝对路径参照灯光/雾手感（`addLights`、`scene.fog`、renderer 设置）。具体改动：
1. `import { SceneFX } from './scene_fx.js';`，模块级 `let sceneFX = null;`。
2. `init()` 内 renderer 创建后：`renderer.shadowMap.type = THREE.PCFSoftShadowMap;`；`scene.fog = new THREE.Fog(0x07111d, /*near*/ 520, /*far*/ 2200);`（按现单食堂尺度，FOCUS/OVERVIEW 都不雾穿，必要时实测微调）；现有 Hemisphere/Directional 之外加一盏冷青 PointLight（参 V7 `0x52d6d1`）。
3. `init()` 末（`animate()` 前）：`sceneFX = new SceneFX(); sceneFX.mount(renderer, scene, camera);`。
4. `resize()` 末追加：`if (sceneFX) sceneFX.setSize(width, height);`。
5. **RAF 解耦**：`animate()` 内现有 `if (canteenScene && lastAppState?.view === 'canteen') { canteenScene.update(canteenScene.lastFrame); }`——把其中 `canteenScene.update(canteenScene.lastFrame)` 换成 `canteenScene.tick()`，**保留同样的外层守卫**（`canteenScene && lastAppState?.view === 'canteen'`），使 campus 路径与无帧场景不抛；末尾 `renderer.render(scene, camera)` 改为 `sceneFX ? sceneFX.render() : renderer.render(scene, camera)`。
6. `dispose()` 内追加 `if (sceneFX) { sceneFX.dispose(); sceneFX = null; }`。
7. **不动**任何契约 token / `webglAvailable` 兜底分支 / `showFallback`。`render(snapshot,appState)` 仍走既有 `renderCanteen/renderCampus`（数据重建在此，见 V4）。

- [ ] **Step 4: 验证 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --check frontend/static/js/three/scene3d.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS；`node --check` 0；回归全绿。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/scene3d.js backend/tests/test_frontend_three_js_contract.py
git -c user.name=Sissi commit -m "feat(3d): scene3d lights/fog/tonemap + composer + RAF decouple (contract/fallback intact)"
```

---

## Task V4：`canteen_scene.js` — V7 几何重做 + `update()`/`tick()` 拆分

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js`
- Modify: `backend/tests/test_frontend_three_js_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_three_js_contract.py
def test_canteen_scene_split_and_v7_geometry():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    import re
    assert "tick(" in s, "missing tick() (RAF advance entry)"
    assert "update(frame)" in s.replace(" ", "") or "update(frame)" in s
    assert "_rebuild(" in s

    # Indentation-robust: slice a class method body from its signature up to the
    # NEXT class-method declaration (4-space-indented `name(...) {`) or EOF.
    # Does NOT depend on the method's closing-brace indentation.
    def method_body(src, name):
        m = re.search(r"\n\s*" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
        if not m:
            return None
        start = m.end()
        nxt = re.search(r"\n {4}[A-Za-z_]\w*\s*\([^)]*\)\s*\{", src[start:])
        return src[start: start + (nxt.start() if nxt else len(src) - start)]

    tb = method_body(s, "tick")
    ub = method_body(s, "update")
    assert tb is not None and "_rebuild(" not in tb, "tick() must NOT _rebuild() (RAF path)"
    assert ub is not None and "_rebuild(" in ub, "update(frame) must _rebuild() on snapshot"
    # V7 几何元素存在
    for tok in ("plinth", "glass", "stair", "BoxGeometry", "Group"):
        assert tok in s, f"missing V7 geometry token: {tok!r}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_canteen_scene_split_and_v7_geometry -q`
Expected: FAIL。

- [ ] **Step 3: 实现（参照 V7 绝对路径 `buildInterior/addWindows/addTables/addQueue`，绑定实时帧）**

关键改动（保持类名 `CanteenScene`、`group`、`focusFloor/resetView/trackStudent` 公共面不变）：
1. **拆分**：
   - `update(frame)`：保存帧、`_floorCount`、`_rebuild(frame)`、`_recomputeCameraTarget()`（**只在快照到来时重建几何**）。
   - 新增 `tick()`：仅 `_animateFloors()` + `_animateCamera()`（RAF 每帧推进，**不** `_rebuild`）。**首帧前安全**：`tick()` 必须能在尚未收到任何 `update(frame)` 时被调用而不抛——开头 `if (!this._lastFrame || this._floorGroups.size === 0) return;`（RAF 在 `init()` 即启动，早于首个 `render()`）。
   - 删除 `update()` 里对 `_animateFloors/_animateCamera` 的每帧调用改由 `tick()` 承担；`scene3d.animate()` 改调 `tick()`（Task V3 已对齐，含原外层守卫保留）。
2. **V7 几何**（每层 `fg` 组内，尺度沿用现单食堂世界单位；参照 V7 函数结构但坐标按现 `floor.baseY/z`）：
   - 站台基座 `plinth`（深青 `0x13243a` 大 slab）。
   - 每层：`slab`（隔层 `0x263a50`/`0x243f56`，热力态用 heatColor）、**玻璃幕墙前壁** `front glass`（半透 `0xbdebf2` opacity~.2；`剖`(cutaway) 开则不建前壁）、半透背/侧墙、楼层标牌 sprite（`{id} · {windows}窗 · {seats}座`，非焦点 opacity 降）。
   - 窗口：`is_open` 开=青、`is_serving` 红高亮、`!is_open` 暗灰 + `closing` 时「关闭中」标签（沿用帧字段；`userData.kind='window'` 不变以保下钻 raycast）。
   - 桌组 + 座位点：`seat.status==='occupied'` 金/红、空绿。
   - 队列/学生：沿用帧 `students`（`userData.kind='student'` 不变）；焦点层 `_flowPath` 保留接新发光材质。
   - 垂直交通核 `stair core`（半透发光 `0x52d6d1`，贯通各层）+ 入口标记。
   - 增大 `FLOOR_GAP`（现 74 → 实测取值使三层明确分层、OVERVIEW 不挤）；`_recomputeCameraTarget` 调整使建筑居中可辨。
3. `userData.kind`（`floor`/`window`/`student`）与 `_floorGroups` 滑开逻辑保持，保证下钻 raycast 与非焦点层滑开不回退。

- [ ] **Step 4: 验证 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --check frontend/static/js/three/canteen_scene.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS；`node --check` 0；回归全绿。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/canteen_scene.js backend/tests/test_frontend_three_js_contract.py
git -c user.name=Sissi commit -m "feat(3d): V7 building geometry (glass/stair/plinth) + update()/tick() split"
```

---

## Task V5：`intervention_ui.js` — V7 玻璃面板观感（钩子/端点不变）

**Files:**
- Modify: `frontend/static/js/three/intervention_ui.js`
- Modify: `backend/tests/test_frontend_three_js_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_three_js_contract.py
def test_intervention_ui_hooks_preserved_after_restyle():
    s = (THREE_DIR / "intervention_ui.js").read_text(encoding="utf-8")
    for tok in ("three-ops-console", "ops-grid", "ops-win", "ops-log",
                "twin-congestion-legend",
                "/campus/canteens/", "/windows/", "/toggle"):
        assert tok in s, f"intervention hook lost: {tok!r}"
    # 玻璃观感类（CSS 由 style.css 提供，这里只需结构 className 仍可被样式命中）
    assert "ops-kpi" in s
```

- [ ] **Step 2: 跑测试确认失败/通过基线**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_intervention_ui_hooks_preserved_after_restyle -q`
Expected: 现状大概率 PASS（钩子已在）——本测试是**防回退栅栏**：V5 改样式期间须保持其绿。

- [ ] **Step 3: 实现（仅观感，不动数据/端点/DOM 钩子）**

- 保留 `#three-ops-console`、`.ops-kpi`/`.ops-grid`/`.ops-win button`/`.ops-log`/`#twin-congestion-legend` 全部 id/class 与 `_toggle()` 的 `POST /api/campus/canteens/<cid>/windows/<wid>/toggle`。
- 视觉移到 CSS（Task V9 的 `.twin-immersive` 作用域）；本文件仅在需要时把内联零散 style 收敛为 class（如 KPI 用 `.ops-kpi`/`.metric` 网格、楼层用 `.ops-floor`、日志 `.ops-log`），不新增依赖。
- 内联 `CSS` 常量（模块内 `<style>` 注入）保留但精简为与 V7 一致的玻璃 token（深青底/青字/细边）；若与 style.css 重复，优先 style.css，模块内仅保功能性最小样式。

- [ ] **Step 4: 验证 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --check frontend/static/js/three/intervention_ui.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/intervention_ui.js backend/tests/test_frontend_three_js_contract.py
git -c user.name=Sissi commit -m "feat(3d): intervention console V7 glass look (hooks/endpoint intact)"
```

---

## Task V6：`immersive_ui.js`（新增 V7 玻璃顶栏/工具条/楼层条/状态/返回入口）

**Files:**
- Create: `frontend/static/js/three/immersive_ui.js`
- Modify: `backend/tests/test_frontend_three_js_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_three_js_contract.py
def test_immersive_ui_module_contract():
    s = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    assert "export class ImmersiveUI" in s
    # 玻璃 overlay 容器 + 返回2D/导航可达性
    for tok in ("twin-topbar", "twin-toolbar", "twin-floorstrip",
                "twin-status", "data-render", "data-page"):
        assert tok in s, f"immersive_ui missing {tok!r}"
    assert "mount(" in s and "dispose(" in s
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_immersive_ui_module_contract -q`
Expected: FAIL。

- [ ] **Step 3: 实现 `immersive_ui.js`（纯 DOM overlay，挂 `#three-stage`）**

- `export class ImmersiveUI { mount(container){...} update(frame, sceneApi){...} dispose(){...} }`。
- 注入：`.twin-topbar`（品牌 + 视图段「校园/食堂」复用既有 `#view-switcher` 语义或镜像按钮）、`.twin-toolbar`（剖 cutaway / 热 heat / 播放暂停 / 复位视角）、`.twin-floorstrip`（整栋 + 各层，点按 → `sceneApi.focusFloor(id)`/`resetView()`）、`.twin-status`、`.twin-tooltip`。
- **可达性**：顶栏含「返回 2D」按钮 → 点击现有 `#render-switcher [data-render="2d"]`（`.click()`，不写 `renderMode:'2d'` 字面）；含「参数/分析/历史」入口 → 调既有 `nav-link[data-page]` `.click()`（复用 `showPage`）。
- 剖/热：维护本地 `cutaway/heat` 布尔，回调通知 `scene3d`（经 `sceneApi`）触发**一次重建**（非每帧）。
- 不引新库；样式类由 Task V9 的 style.css 提供。

- [ ] **Step 4: 验证 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --check frontend/static/js/three/immersive_ui.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/immersive_ui.js backend/tests/test_frontend_three_js_contract.py
git -c user.name=Sissi commit -m "feat(3d): immersive_ui glass topbar/toolbar/floorstrip + 2D/nav reachability"
```

---

## Task V7：scene3d ↔ immersive_ui 接线 + index.html module 标签

**Files:**
- Modify: `frontend/static/js/three/scene3d.js`、`frontend/templates/index.html`
- Modify: `backend/tests/test_frontend_three_js_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_three_js_contract.py
def test_index_loads_new_three_modules_and_scene3d_wires_immersive():
    html = (Path(__file__).resolve().parents[2] / "frontend/templates/index.html").read_text(encoding="utf-8")
    assert "js/three/scene_fx.js" in html
    assert "js/three/immersive_ui.js" in html
    s = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    assert "ImmersiveUI" in s and "immerseUI" in s.replace(" ", "")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_index_loads_new_three_modules_and_scene3d_wires_immersive -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

- `index.html`：**明确动作 —— 新增两个 module script 标签**：`<script type="module" src="{{ url_for('static', filename='js/three/scene_fx.js') }}"></script>` 与 `immersive_ui.js` 同形式，与既有 `state_adapter/canteen_scene/intervention_ui/scene3d` 四个 module 标签并列，**顺序**：state_adapter → canteen_scene → intervention_ui → scene_fx → immersive_ui → scene3d。理由：运行时正确性不依赖此加载顺序（`scene3d.js` 自身 `import` scene_fx/immersive_ui），但 Task V7 契约测试 `test_index_loads_new_three_modules...` 与文件结构表都要求这两个文件名出现在 `index.html`，故以新增 script 标签满足（与现状风格一致，不引入 modulepreload 等新写法）。
- `scene3d.js`：`import { ImmersiveUI } from './immersive_ui.js';`；`init()` 内 `immerseUI = new ImmersiveUI(); immerseUI.mount(container);` 暴露窄 `sceneApi`（`focusFloor/resetView/setCutaway/setHeat/resetCamera`）给它；`render()` 内 `immerseUI.update(frame, sceneApi)`；`dispose()` 清理。剖/热触发 `canteenScene` 一次 `update(lastFrame)` 重建（非每帧）。

- [ ] **Step 4: 验证 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --check frontend/static/js/three/scene3d.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/scene3d.js frontend/templates/index.html backend/tests/test_frontend_three_js_contract.py
git -c user.name=Sissi commit -m "feat(3d): wire immersive_ui into scene3d + load new modules in index.html"
```

---

## Task V8：`main.js` — `syncImmersiveShell()`（showPage + applyViewState 调用；禁 '2d' 字面）

**Files:**
- Modify: `frontend/static/js/main.js`
- Modify: `backend/tests/test_frontend_main_js_contract.py`（append；不改既有断言）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_frontend_main_js_contract.py
from pathlib import Path
MAIN = Path(__file__).resolve().parents[2] / "frontend/static/js/main.js"

def test_sync_immersive_shell_wired_and_no_2d_literal():
    s = MAIN.read_text(encoding="utf-8")
    assert "function syncImmersiveShell()" in s
    assert "twin-immersive" in s
    assert "getElementById('simulation-page')" in s or 'simulation-page' in s
    # showPage 与 applyViewState 都调用 syncImmersiveShell
    import re
    sp = re.search(r"function showPage\([^)]*\)\s*\{.*?\n\}", s, re.S)
    av = re.search(r"function applyViewState\([^)]*\)\s*\{.*?\n\}", s, re.S)
    assert sp and "syncImmersiveShell()" in sp.group(0), "showPage must call syncImmersiveShell"
    assert av and "syncImmersiveShell()" in av.group(0), "applyViewState must call syncImmersiveShell"
    # 负断言仍立（沉浸切换不得引入 2D 字面）
    assert "renderMode: '2d'" not in s
    assert "state.renderMode = '2d';" not in s
```

- [ ] **Step 2: 跑全文件确认新失败、旧断言仍绿**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py -q`
Expected: 新用例 FAIL，其余既有用例（含 `test_preset_first_uses_single_canteen_and_3d_default`）PASS。

- [ ] **Step 3: 实现（最小、不改既有判断）**

```javascript
// main.js：新增（放在 applyViewState 附近）
function syncImmersiveShell() {
    const onSim = document.getElementById('simulation-page')?.classList.contains('active');
    const isImmersive = !!onSim && state.mode === 'campus' && state.renderMode === '3d';
    document.body.classList.toggle('twin-immersive', isImmersive);
}
```
- 在 `showPage()` 末尾追加一行 `syncImmersiveShell();`（`showPage` 现切换 `.page.active` 后即应同步外壳）。
- 在 `applyViewState()` 末尾追加一行 `syncImmersiveShell();`（mode/renderMode 变化时同步）。
- 不写任何 `renderMode: '2d'` / `state.renderMode = '2d';`；2D 返回经既有 `#render-switcher` 路径（Task V6 用 `.click()`）。

- [ ] **Step 4: 验证 + 语法门 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py -q
node --check frontend/static/js/main.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS（既有 + 新；负 '2d' 断言绿）；回归 212+ 全绿。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/main.js backend/tests/test_frontend_main_js_contract.py
git -c user.name=Sissi commit -m "feat(frontend): syncImmersiveShell() via showPage+applyViewState (no 2d literal)"
```

---

## Task V9：`style.css` — `.twin-immersive` 玻璃面板 + 全屏 + 响应式（修窄屏重叠）

**Files:**
- Modify: `frontend/static/css/style.css`
- Modify: `backend/tests/test_twin_visual_assets_contract.py`（append）

- [ ] **Step 1: 扩展契约测试（失败）**

```python
# append to backend/tests/test_twin_visual_assets_contract.py
def test_style_css_immersive_scope_and_responsive():
    css = (ROOT / "frontend/static/css/style.css").read_text(encoding="utf-8")
    assert ".twin-immersive" in css
    # 全屏舞台 + 隐藏白色外壳
    assert "#three-stage" in css
    assert "@media" in css and "960px" in css  # 移植 V7 响应式
    # 沉浸态玻璃 token
    assert "backdrop-filter" in css
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_twin_visual_assets_contract.py::test_style_css_immersive_scope_and_responsive -q`
Expected: FAIL。

- [ ] **Step 3: 实现（参照 V7 `<style>` 段，全部 scope 在 `.twin-immersive`）**

- `body.twin-immersive`：隐藏白色应用导航/页面 padding/2D 专用容器（`.nav`, 应用 header, `.canvas-area` 非沉浸部分等——按现 index.html 结构精确定位，**只加规则不改既有非沉浸样式**）。
- `body.twin-immersive #three-stage { position:fixed; inset:0; z-index:...; }`；shell 径向青/琥珀辉光渐变背景。
- 移植 V7 玻璃面板规则（`.twin-topbar/.twin-toolbar/.twin-floorstrip/.twin-status/.twin-tooltip` 与 `#three-ops-console`/`#twin-congestion-legend` 在沉浸态的玻璃观感：`backdrop-filter:blur`、圆角、细边、阴影、冷青 token）。
- 移植 V7 `@media (max-width:960px)`（面板重排/收起）——**此节须使 390×780 下 `#three-ops-console` 与 `#twin-congestion-legend` 不重叠且不溢出视口**（Task V10 E2E 验证 `controls_overlap_each_other=false`）。
- 仅作用 `.twin-immersive` 后代，确保**非沉浸态既有 UI 像素级不变**。

- [ ] **Step 4: 验证 + 回归**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_twin_visual_assets_contract.py -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```
Expected: 全 PASS（CSS 无 node --check；靠 token 测试 + E2E 把关）。

- [ ] **Step 5: Commit**

```bash
git add frontend/static/css/style.css backend/tests/test_twin_visual_assets_contract.py
git -c user.name=Sissi commit -m "feat(css): .twin-immersive glass shell + V7 responsive (fixes narrow overlap)"
```

---

## Task V10：集成 + 浏览器 E2E 证据（按新 V7 视觉重出）+ 闭合 Task I1

**Files:**
- Modify: `docs/phase3/browser_e2e_check.md`、`docs/phase3/screenshots/*`、`docs/phase3/screenshots/three-result.json`
- Driver（不提交，置 `/tmp`）：改造既有 `/tmp/e2e_twin_driver.mjs` 适配新沉浸 UI

- [ ] **Step 1: 全量回归门**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
Expected: `212 + 新增契约测试` 全绿。任一红 → 停，修复再继续。

- [ ] **Step 2: JS 语法门（逐文件）**

Run:
```bash
for f in main.js canvas_renderer.js \
  three/scene3d.js three/canteen_scene.js three/state_adapter.js \
  three/intervention_ui.js three/scene_fx.js three/immersive_ui.js; do
  node --check "frontend/static/js/$f" || echo "FAIL $f"
done
for f in frontend/static/js/three/vendor/postprocessing/*.js frontend/static/js/three/vendor/shaders/*.js; do
  node --check "$f" || echo "FAIL $f"; done
echo done
```
Expected: 无 `FAIL`。

- [ ] **Step 3: 浏览器 E2E（spec §6.4，无 reloader 稳定起服务）**

- 稳定起后端（避开 debug reloader 抖动，不改产品代码）：
  `PYTHONPATH=backend ./.venv/bin/python -c "import sys; sys.argv=['app']; from app import create_app; create_app().run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)" &`
- 改造 `/tmp/e2e_twin_driver.mjs`：等 `.twin-immersive` 生效（替代旧 #three-stage 可见判定）；六场景按 spec §6.4：
  1. 默认进沉浸 3D：`renderMode=3d`、`document.body.classList.contains('twin-immersive')`、白色外壳隐藏（应用 nav 不可见）、canvas 非空像素、三层玻璃建筑可辨。
  2. λ(t) 高峰：tick=60 快进过脉冲（t≈2600，<3600 不触尾，每步 try/catch），实时帧驱动队列升降。
  3. 下钻：合成 `PointerEvent('pointerdown')` 命中建筑 → FOCUS（运维台 KPI 出现 `NF 排队`、非焦点层滑开）；居中后应稳定，仍不稳则如实记为 harness 限制 + Phase G1 契约佐证。
  4. 干预因果：运维台开/关窗 → `GET /api/campus/history` 即时含该 intervention（after.iv>before.iv 且命中窗口 id）。
  5. 兜底：禁 WebGL（`getContext('webgl*')→null`）→ `.three-fallback` 文案、无 WebGL canvas；主流程 console error=0，禁 WebGL 的 THREE 报错单列预期；另验 Bloom 失败**不**触发 fallback（可注入 composer 构造抛错，断言仍 `renderer.render` 出图、无 `.three-fallback`）。
  6. 窄屏 390×780：`#three-ops-console` 与 `#twin-congestion-legend` `controls_overlap_each_other=false` 且控件不溢出视口。
- 产出覆盖：`docs/phase3/screenshots/twin-*.png`、`docs/phase3/screenshots/three-result.json`、`docs/phase3/browser_e2e_check.md`（叙述含场景3限制如实记录、旧证据已被本次覆盖说明）。

- [ ] **Step 4: 关服务 + 提交证据（闭合 Task I1）**

```bash
lsof -ti tcp:5001 | xargs kill -9 2>/dev/null; true
git add docs/phase3/browser_e2e_check.md docs/phase3/screenshots
git -c user.name=Sissi commit -m "test(e2e): V7 immersive 3D twin browser evidence; close Task I1"
```

- [ ] **Step 5: 收尾自检**

- `git status --short` 仅期望改动；无 `docs/phase2/*` 夹带。
- spec 全部硬验收逐条对照 `three-result.json`：默认沉浸、λ峰、下钻、干预因果、兜底边界（fallback 仅 WebGL 不可用 / Bloom 失败不 fallback）、窄屏不重叠、console 主流程 0。
- 在 `docs/superpowers/plans/2026-05-17-3d-twin-visual-redesign.md` 勾选完成项。

---

## Out of scope（如需，单独评审提交）
- 后端任何改动 / API 形状 / 数据语义。
- 校园沙盘、跨食堂路由、`in_transit`、学活待补点位（spec 已 drop）。
- `docs/phase2/*` 既有未提交改动（绝不夹带）。

## Plan-level done criteria
- `pytest backend/tests -q` 全绿（212 + 新增契约测试）；后端逐字未改。
- `scene3d.js` 契约/兜底 token、`main.js` 负 '2d' 断言全部仍立。
- 默认沉浸 V7 视觉（玻璃建筑/雾/软阴影/辉光/玻璃面板/可读三层）；2D 兜底与导航可达。
- 实时帧驱动不退化；窗口干预即时入 `/api/campus/history`。
- Bloom 失败仅降级 `renderer.render`（不 fallback）；WebGL 不可用才 `.three-fallback`。
- 窄屏 390×780 运维台/图例不重叠不溢出。
- 新 V7 E2E 证据覆盖旧证据，Task I1 闭合。
